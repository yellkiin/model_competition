"""Deterministic construction and directed neighborhoods; proxies are not scores.

Reuse the repository's public graph/plan helpers without altering the evaluator.
No smoke suite, fingerprint pass, random seed sweep, or optimizer dependency.
"""
from __future__ import annotations
from collections import defaultdict
from research_a.model import Graph, Plan, PIPES, copy_accounting, residency, fifo_requests
from .component_moves import component_neighbors


def relaxation_bound(g: Graph, cores: int) -> float:
    """Compute-only relaxation, using raw nonnegative cycles (not g.cost's floor).

    Requires non-COPY ops to retain at least their input cycles, one server for
    each Pipe type per core, and the explicit dependencies used below to survive
    official construction. See THEORY.md. Contracted COPY paths are not used.
    """
    if cores < 1:
        raise ValueError('cores must be positive')
    cost = {u: max(0., float(g.ops[u].get('cycles', 0))) for u in g.ids}
    pred = {u: set() for u in g.ids}
    for t in g.tensors:
        for v in g.cs[t]:
            pred[v].update(g.ps[t] - {v})
    for edge in g.direct:
        a, b = edge['source'], edge['target']
        if a in pred and b in pred:
            pred[b].add(a)
    finish, load = {}, defaultdict(float)
    for u in g.order:
        finish[u] = cost[u] + max((finish[v] for v in pred[u]), default=0.)
        load[g.ops[u]['pipe']] += cost[u]
    return max(max(finish.values(), default=0.), max(load.values(), default=0.) / cores)


def units(g: Graph, bands: int):
    """Connected components inside monotone depth bands.

    Different units in a band have no edges between them; all inter-band edges
    point forward. Aggregating units by (band, core) preserves a quotient DAG.
    This is NOT a proof that the final official event graph is executable.
    """
    depth = {}
    for u in g.order:
        depth[u] = 1 + max((depth[v] for v in g.pred[u]), default=-1)
    scale = max(depth.values(), default=0) + 1
    band = {u: min(bands - 1, depth[u] * bands // scale) for u in g.ids}
    seen, result = set(), []
    position = {u: i for i, u in enumerate(g.order)}
    for u in g.order:
        if u in seen:
            continue
        stack, block = [u], []
        seen.add(u)
        while stack:
            v = stack.pop()
            block.append(v)
            for w in sorted(g.pred[v] | g.succ[v]):
                if w not in seen and band[w] == band[u]:
                    seen.add(w)
                    stack.append(w)
        block.sort(key=position.__getitem__)
        result.append((band[u], block))
    return sorted(result, key=lambda x: (x[0], -max(g.rank[u] for u in x[1]), min(x[1])))


def construct(g: Graph, cores: int, q: int, cfg: dict, *, component_baseline=False) -> Plan:
    if not g.ids or cores < 1 or q not in (1, 2, 3):
        raise ValueError('Need a nonempty graph, positive cores and question 1/2/3')
    whole = units(g, 1)
    total = sum(g.cost.values())
    biggest = max(sum(g.cost[u] for u in block) for _, block in whole)
    # A fixed input-dependent rule; never branch on a case filename or score.
    bands = 1 if component_baseline or biggest <= 1.25 * total / cores else min(8, 2 * cores)
    pieces = whole if bands == 1 else units(g, bands)
    load = [defaultdict(float) for _ in range(cores)]
    clocks = [defaultdict(float) for _ in range(cores)]
    end, owner, grouped = {}, {}, defaultdict(list)
    for layer, block in pieces:
        footprint = defaultdict(float)
        touched = set().union(*(g.inputs[u] | g.outputs[u] for u in block))
        for t in touched:
            pos = g.tensors[t].get('pos', 'UB')
            footprint['UB' if pos == 'DDR' else pos] += float(g.tensors[t]['size'])
        scored = []
        for k in range(cores):
            local = dict(end)
            clock = defaultdict(float, clocks[k])
            traffic = 0.
            for u in block:
                wait = cfg['task_cross_core_wait_cycles'] if q == 1 else cfg['cross_core_copy_delay_cycles']
                ready = max((local[v] + (wait if owner.get(v, k) != k else 0.)
                             for v in g.pred[u]), default=0.)
                pipe = g.ops[u]['pipe']
                local[u] = max(clock[pipe], ready) + g.cost[u]
                clock[pipe] = local[u]
            for t in touched:
                # A direction cue only, not exact COPY accounting or a capacity peak.
                if any(v in owner and owner[v] != k for v in g.ps[t]):
                    traffic += 2. * float(g.tensors[t]['size'])
            peak_risk = sum(max(0., size - cfg['capacity'].get(pos, float('inf')))
                            for pos, size in footprint.items())
            work = defaultdict(float, load[k])
            for u in block:
                work[g.ops[u]['pipe']] += g.cost[u]
            if component_baseline:
                score = sum(load[k].values())
            else:
                score = max(clock.values(), default=0.) + .15 * traffic / cfg['bandwidth']
                score += .05 * peak_risk / cfg['bandwidth'] + .02 * max(work.values(), default=0.)
            scored.append((score, k, clock, {u: local[u] for u in block}, work))
        _, k, clocks[k], new_end, load[k] = min(scored, key=lambda x: (x[0], x[1]))
        end.update(new_end)
        owner.update({u: k for u in block})
        grouped[layer, k].extend(block)
    order = {u: i for i, u in enumerate(g.order)}
    keys = sorted(grouped)
    return Plan([sorted(grouped[key], key=order.__getitem__) for key in keys],
                [key[1] for key in keys], cores)


def proxy(g: Graph, p: Plan, q: int, cfg: dict) -> dict:
    """Dependency/pipe calendars plus communication, lifetime and FIFO heuristics.

    Q2/Q3 cross-core latency participates in every dependent earliest finish,
    rather than being omitted from the critical path. This still is not an
    exact event simulator or a valid bound on the official makespan.
    """
    mapping = {u: s for s, block in enumerate(p.blocks) for u in block}
    owners = {u: p.owners[s] for u, s in mapping.items()}
    clock, end, start = defaultdict(float), {}, {}
    task_end, tail = {}, {}
    for s, block in enumerate(p.blocks):
        k = p.owners[s]
        gate = tail.get(k, 0.)
        if q == 1:
            if k in tail:
                gate += cfg['task_same_core_wait_cycles']
            predecessors = {mapping[v] for u in block for v in g.pred[u] if mapping[v] != s}
            gate = max([gate] + [task_end[v] + (cfg['task_same_core_wait_cycles']
                if p.owners[v] == k else cfg['task_cross_core_wait_cycles']) for v in predecessors])
        for u in block:
            ready = max((end[v] + (cfg['cross_core_copy_delay_cycles']
                         if q != 1 and owners[v] != k else 0.) for v in g.pred[u]), default=0.)
            pipe = g.ops[u]['pipe']
            start[u] = max(gate, clock[k, pipe], ready)
            end[u] = start[u] + g.cost[u]
            clock[k, pipe] = end[u]
        task_end[s] = max(end[u] for u in block)
        tail[k] = task_end[s]
    account = copy_accounting(g, p, q)
    hit = 0.
    if q == 3:
        requests = []
        for t, dst, src, size in account['requests']:
            readers = [u for u in g.cs[t] if owners[u] == dst]
            when = min((start[u] for u in readers), default=0.)
            if src is not None:
                writers = [u for u in g.ps[t] if owners[u] == src]
                when = max(when, max((end[u] for u in writers), default=0.)
                           + cfg['cross_core_copy_delay_cycles'] + size / cfg['bandwidth'])
            requests.append((when, g.tensors[t].get('logical_tid', t), size))
        hit = fifo_requests(requests, cfg['cache_capacity_bytes'], cfg['bandwidth'],
                            cfg['cache_bandwidth_bytes_per_cycle'])['hit_bytes']
    traffic = max(0., account['pre_spill_bytes'] - hit) / cfg['bandwidth']
    memory = residency(g, p, q, cfg['capacity'])
    score = max(max(end.values(), default=0.), traffic,
                hit / cfg['cache_bandwidth_bytes_per_cycle'] if q == 3 else 0.)
    score += .10 * traffic + .10 * memory['excess_bytes'] / cfg['bandwidth']
    score += .01 * memory['exposure_cycles']
    return dict(score=score, communication_calendar_proxy=max(end.values(), default=0.),
                pre_spill_bytes=account['pre_spill_bytes'], cache_hit_bytes_proxy=hit, **memory)


def neighbors(g: Graph, p: Plan, cfg: dict, limit=12):
    """Bounded moves directed at expensive cuts, imbalance, and task boundaries.

    Blocks retain their global topological order. Only consecutive global blocks
    are merged, so quotient-DAG ordering is preserved. Official checks remain
    mandatory after all structural checks.
    """
    mapping = {u: s for s, block in enumerate(p.blocks) for u in block}
    weights = [sum(g.cost[u] for u in block) for block in p.blocks]
    loads = [0.] * p.cores
    for s, k in enumerate(p.owners):
        loads[k] += weights[s]
    cut = defaultdict(float)
    for v in g.ids:
        for u in g.pred[v]:
            a, b = mapping[u], mapping[v]
            if p.owners[a] != p.owners[b]:
                cut[a, b] += cfg['cross_core_copy_delay_cycles'] + g.rank[v]
    moves = []
    for (a, b), _ in sorted(cut.items(), key=lambda x: (-x[1], x[0]))[:4]:
        moves.extend(((b, p.owners[a]), (a, p.owners[b])))
    light = min(range(p.cores), key=lambda k: (loads[k], k))
    heavy = max(range(p.cores), key=lambda k: (loads[k], -k))
    candidates = [s for s, k in enumerate(p.owners) if k == heavy]
    for s in sorted(candidates, key=lambda s: (-weights[s], s))[:3]:
        moves.append((s, light))
    produced = 0
    for candidate in component_neighbors(g, p, limit=min(6, limit)):
        yield candidate
        produced += 1
        if produced >= limit:
            return
    seen_moves = set()
    for s, k in moves:
        if (s, k) in seen_moves or p.owners[s] == k:
            continue
        seen_moves.add((s, k))
        owners = list(p.owners)
        owners[s] = k
        yield Plan([list(b) for b in p.blocks], owners, p.cores)
        produced += 1
        if produced >= limit:
            return
    for s in range(len(p.blocks) - 1):
        if p.owners[s] != p.owners[s + 1]:
            continue
        blocks = [list(b) for b in p.blocks]
        blocks[s:s + 2] = [blocks[s] + blocks[s + 1]]
        owners = p.owners[:s + 1] + p.owners[s + 2:]
        yield Plan(blocks, owners, p.cores)
        produced += 1
        if produced >= limit:
            return
