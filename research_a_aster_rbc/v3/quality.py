"""Plan validation, conservative bounds, and bounded directed neighbours.

Only certified_candidate_lower is used for pruning. The traffic score is a
ranking heuristic, not an event simulator, a memory bound, or a feasibility test.
Final feasibility and makespan always come from the unchanged official evaluator.
No content fingerprints or third-party dependencies are used.
"""
from __future__ import annotations
from collections import defaultdict
import math
from .model import make_plan, topo


def view(g, plan):
    """Return (op_to_block, blocks, block_to_core, common_topological_order).

    Check exact coverage, unique nonnegative block IDs, and the union of quotient
    dependencies with per-core orders. This does not replace the official checks.
    """
    if not isinstance(plan, dict) or set(plan) != {'node_to_subgraph', 'core_schedules'}:
        raise ValueError('plan must contain exactly the two official fields')
    raw, schedules = plan['node_to_subgraph'], plan['core_schedules']
    if not isinstance(raw, dict) or not isinstance(schedules, list) or not schedules:
        raise ValueError('invalid plan containers')
    mapping = {}
    blocks = defaultdict(list)
    for text, block in raw.items():
        u = int(text)
        if u in mapping or isinstance(block, bool) or not isinstance(block, int) or block < 0:
            raise ValueError('duplicate operation or invalid subgraph ID')
        mapping[u] = block
        blocks[block].append(u)
    if set(mapping) != set(g.ids):
        raise ValueError('non-COPY operation coverage differs from the input graph')
    owners = {}
    for core, sequence in enumerate(schedules):
        if not isinstance(sequence, list):
            raise ValueError('core schedule must be a list')
        for block in sequence:
            if isinstance(block, bool) or not isinstance(block, int) or block < 0 or block in owners:
                raise ValueError('subgraph must occur on exactly one core')
            owners[block] = core
    if set(owners) != set(blocks):
        raise ValueError('scheduled subgraphs and mapped subgraphs differ')
    pred = {s: set() for s in blocks}
    for v in g.ids:
        pred[mapping[v]].update(mapping[u] for u in g.pred[v] if mapping[u] != mapping[v])
    for seq in schedules:
        for a, b in zip(seq, seq[1:]):
            pred[b].add(a)
    order = topo(pred)
    blocks = {s: sorted(nodes, key=g.index.__getitem__) for s, nodes in blocks.items()}
    return mapping, blocks, owners, order


def bound_and_proxy(g, plan, q, cfg):
    """Compute/path/core-load lower bounds, with separately labelled traffic proxy.

    For Q1 only tensor-backed cross-Task predecessors are used in the barrier
    bound. Q2/Q3 charge fixed cross-core latency on retained compute dependencies.
    COPY-contracted paths are used for structural validation, not for path proof.
    Scope: official non-COPY cycles use max(1, cycles); configuration is unchanged.
    """
    if q not in (1, 2, 3):
        raise ValueError('question must be 1, 2 or 3')
    m, blocks, owner, order = view(g, plan)
    n = len(plan['core_schedules'])
    core = {u: owner[m[u]] for u in g.ids}
    loads = [[0.] * 4 for _ in range(n)]
    for u in g.ids:
        loads[core[u]][g.pipe[u]] += g.cost[u]
    core_load = max((max(row) for row in loads), default=0.)
    if q == 1:
        pred = {s: set() for s in blocks}
        for t in g.tensors:
            ps = {m[u] for u in g.ps[t]}
            for v in g.cs[t]:
                pred[m[v]].update(ps - {m[v]})
        for seq in plan['core_schedules']:
            for a, b in zip(seq, seq[1:]):
                pred[b].add(a)
        finish = {}
        for s in order:
            ready = max((finish[p] + (cfg['task_same_core_wait_cycles'] if owner[p] == owner[s]
                          else cfg['task_cross_core_wait_cycles']) for p in pred[s]), default=0.)
            finish[s] = ready + max(g.loads(blocks[s]), default=0.)
    else:
        finish = {}
        for v in g.order:
            finish[v] = g.cost[v] + max((finish[u] + (cfg['cross_core_copy_delay_cycles']
                         if core[u] != core[v] else 0.) for u in g.retained_pred[v]), default=0.)
    path = max(finish.values(), default=0.)
    lower = max(g.lower_bound(n), core_load, path)
    labels = m if q == 1 else core
    reads = writes = 0.
    for t, tensor in g.tensors.items():
        ps = {labels[u] for u in g.ps[t]}
        cs = {labels[u] for u in g.cs[t]}
        size = float(tensor['size'])
        if q == 1:
            reads += size * len(cs - ps)
            writes += size * sum(g.final[t] or bool(cs - {p}) for p in ps)
        else:
            reads += size * (len(cs) if not ps else 0)
            writes += size * (len(ps) if g.final[t] else 0)
            remote = sum(p != c for p in ps for c in cs)
            reads += size * remote
            writes += size * remote
    if q != 1:
        for e in g.direct:
            a, b = e['source'], e['target']
            if a in core and b in core and core[a] != core[b]:
                reads += max(0, e.get('data_size', 0))
                writes += max(0, e.get('data_size', 0))
    # Q3 is not discounted by guessed cache hits. No traffic quantity is used to prune.
    traffic = (reads + writes) / cfg['bandwidth']
    score = max(lower, traffic) + .05 * traffic
    if not all(math.isfinite(x) for x in (lower, score)):
        raise ValueError('nonfinite plan score')
    return dict(certified_candidate_lower=lower, global_compute_lower=g.lower_bound(n),
                candidate_core_load_lower=core_load, candidate_path_lower=path,
                pre_spill_read_bytes=reads, pre_spill_write_bytes=writes,
                score=score, score_kind='heuristic_not_official')


def neighbors(g, plan, q, cfg, incumbent=None, limit=6):
    """At most limit valid proposals: targeted moves and adjacent merges."""
    m, blocks, owner, order = view(g, plan)
    n = len(plan['core_schedules'])
    if n < 2 or not order:
        return
    weight = {s: sum(g.cost[u] for u in blocks[s]) for s in order}
    load = [sum(weight[s] for s in order if owner[s] == k) for k in range(n)]
    heavy = max(range(n), key=lambda k: (load[k], -k))
    light = min(range(n), key=lambda k: (load[k], k))
    cut = defaultdict(float)
    for t, tensor in g.tensors.items():
        for a in {m[u] for u in g.ps[t]}:
            for b in {m[u] for u in g.cs[t]}:
                if owner[a] != owner[b]:
                    cut[a, b] += float(tensor['size'])
    proposals = []
    for (a, b), _ in sorted(cut.items(), key=lambda x: (-x[1], x[0]))[:2]:
        proposals.extend([(b, owner[a]), (a, owner[b])])
    target = max(0., (load[heavy] - load[light]) / 2)
    movable = sorted((s for s in order if owner[s] == heavy),
                     key=lambda s: (abs(weight[s] - target), s))[:2]
    proposals.extend((s, light) for s in movable)
    emitted = 0
    seen = set()
    for s, k in proposals:
        if k == owner[s] or (s, k) in seen:
            continue
        seen.add((s, k))
        candidate = make_plan([blocks[a] for a in order],
                              [k if a == s else owner[a] for a in order], n)
        try:
            prediction = bound_and_proxy(g, candidate, q, cfg)
        except ValueError:
            continue
        yield 'move', candidate, prediction
        emitted += 1
        if emitted >= limit:
            return
    for i in range(len(order) - 1):
        a, b = order[i:i + 2]
        if owner[a] != owner[b]:
            continue
        groups = [blocks[s] for s in order]
        where = [owner[s] for s in order]
        groups[i:i + 2] = [groups[i] + groups[i + 1]]
        where[i:i + 2] = [where[i]]
        candidate = make_plan(groups, where, n)
        try:
            prediction = bound_and_proxy(g, candidate, q, cfg)
        except ValueError:
            continue
        yield 'merge', candidate, prediction
        emitted += 1
        if emitted >= limit:
            return
