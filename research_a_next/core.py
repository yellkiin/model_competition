"""Problem-aligned graph views, analytical relaxation, and solution certificates.

Uses the existing read-only research_a model for data structures/COPY counting.
No direct op-op edges or graph rewriting: original A section 1.2 is bipartite.
"""
from __future__ import annotations
from collections import defaultdict
import math
from research_a.model import Graph, Plan, PIPES, COPY, topo, copy_accounting, residency, fifo_requests


def graph(raw: dict) -> Graph:
    ops = {o['id'] for o in raw['ops']}
    for e in raw['edges']:
        if (e['source'] in ops) == (e['target'] in ops):
            raise ValueError('Original A requires Tensor->Op or Op->Tensor, not direct Op->Op')
    g = Graph(raw)
    g.retained = {u: {} for u in g.ids}
    for t in g.tensors:
        for v in g.cs[t]:
            for u in g.ps[t] - {v}:
                g.retained[v][u] = max(g.retained[v].get(u, 0), g.tensors[t]['size'])
    return g


def components(g: Graph, nodes=None):
    nodes = set(g.ids if nodes is None else nodes)
    result = []
    for root in sorted(nodes):
        if root not in nodes:
            continue
        nodes.remove(root)
        stack, block = [root], []
        while stack:
            u = stack.pop()
            block.append(u)
            for v in sorted(g.pred[u] | g.succ[u]):
                if v in nodes:
                    nodes.remove(v)
                    stack.append(v)
        result.append(sorted(block))
    return result


def normalize(g, plan):
    """Check coverage and quotient + core-order DAG; official execution still required."""
    value = plan.json()
    mapping = {int(u): s for u, s in value['node_to_subgraph'].items()}
    flat = [u for b in plan.blocks for u in b]
    if set(mapping) != set(g.ids) or len(flat) != len(set(flat)) or len(flat) != len(g.ids):
        raise ValueError('Plan does not cover each compute op once')
    if len(plan.owners) != len(plan.blocks) or any(not 0 <= k < plan.cores for k in plan.owners):
        raise ValueError('Invalid core assignment')
    ids = set(mapping.values())
    pred, succ = {s:set() for s in ids}, {s:set() for s in ids}
    pairs = [(mapping[u],mapping[v]) for u in g.ids for v in g.succ[u]]
    pairs += [(a,b) for seq in value['core_schedules'] for a,b in zip(seq,seq[1:])]
    for a,b in pairs:
        if a!=b:
            succ[a].add(b); pred[b].add(a)
    order=topo(pred,succ)
    buckets={s:[] for s in ids}
    for u in g.order: buckets[mapping[u]].append(u)
    owner={s:k for k,seq in enumerate(value['core_schedules']) for s in seq}
    return Plan([buckets[s] for s in order],[owner[s] for s in order],plan.cores,
                encoded=plan.encoded)



def relaxed_lower(g, cores):
    """Global LB, independent of a chosen partition.

    Fractional per-Pipe assignment LP has exact optimum max_p W_p/n:
    x_ik=1/n attains the summed-load lower bound. Keep the retained compute CP.
    Splitting/coarsening restrictions are NOT included in this global bound.
    """
    distance = {}
    for u in g.order:
        distance[u] = g.cost[u] + max((distance[v] for v in g.retained[u]), default=0.)
    cp = max(distance.values(), default=0.)
    fractional = max(g.work.values(), default=0.) / cores
    return dict(global_lower=max(cp, fractional), compute_path=cp, fractional_load=fractional)


def assignment_path(g, plan, q, cfg):
    """Candidate-dependent lower bound. NEVER use it as a global optimality LB."""
    owner = {u: plan.owners[i] for i, b in enumerate(plan.blocks) for u in b}
    if q in (2, 3):
        end = {}
        for u in g.order:
            end[u] = g.cost[u] + max((end[v] + cfg['cross_core_copy_delay_cycles'] * (owner[u] != owner[v])
                                    for v in g.retained[u]), default=0.)
        return max(end.values(), default=0.)
    labels = plan.labels(1)
    ends, tails = {}, {}
    for s, b in enumerate(plan.blocks):
        inner = {}
        for u in b:
            inner[u] = g.cost[u] + max((inner[v] for v in g.retained[u] if labels[v] == s), default=0.)
        duration = max(max(inner.values(), default=0.),
                       max(sum(g.cost[u] for u in b if g.ops[u]['pipe'] == p) for p in PIPES))
        predecessors = {labels[v] for u in b for v in g.pred[u] if labels[v] != s}
        k = plan.owners[s]
        ready = max((ends[p] + (cfg['task_same_core_wait_cycles'] if plan.owners[p] == k
                               else cfg['task_cross_core_wait_cycles']) for p in predecessors), default=0.)
        if k in tails:
            ready = max(ready, ends[tails[k]] + cfg['task_same_core_wait_cycles'])
        ends[s], tails[k] = ready + duration, s
    return max(ends.values(), default=0.)


def predict(g, plan, q, cfg, memory_weight=.15, cache=True):
    """Multi-Pipe/data-ready surrogate, NOT a replica or bound of the evaluator.

    Same-core Pipe clocks (not one serial core clock), remote COPY+500 cycles,
    Task barriers in Q1, exact pre-spill bytes, and completion-time FIFO proxy.
    """
    labels = plan.labels(q)
    owner = {u: plan.owners[i] for i, b in enumerate(plan.blocks) for u in b}
    pipe_clock = {(k, p): 0. for k in range(plan.cores) for p in PIPES}
    done, starts, task_end, tails = {}, {}, {}, {}
    bw = cfg['bandwidth']
    mapping = plan.labels(1)
    for s, block in enumerate(plan.blocks):
        k = plan.owners[s]
        barrier = 0.
        if q == 1:
            ps = {mapping[v] for u in block for v in g.pred[u] if mapping[v] != s}
            barrier = max((task_end[p] + (cfg['task_same_core_wait_cycles'] if plan.owners[p] == k
                           else cfg['task_cross_core_wait_cycles']) for p in ps), default=0.)
            if k in tails:
                barrier = max(barrier, task_end[tails[k]] + cfg['task_same_core_wait_cycles'])
        for u in block:
            ready = barrier
            for v, size in g.retained[u].items():
                delay = 0.
                if labels[u] != labels[v]:
                    delay = 2 * max(1, math.ceil(size / bw))
                    if q in (2, 3):
                        delay += cfg['cross_core_copy_delay_cycles']
                ready = max(ready, done[v] + delay)
            p = g.ops[u]['pipe']
            starts[u] = max(ready, pipe_clock[k, p])
            done[u] = starts[u] + g.cost[u]
            pipe_clock[k, p] = done[u]
        task_end[s], tails[k] = max((done[u] for u in block), default=barrier), s
    accounting = copy_accounting(g, plan, q)
    hit = 0.
    if q == 3 and cache:
        requests = []
        for t, dst, src, size in accounting['requests']:
            readers = [u for u in g.cs[t] if owner[u] == dst]
            when = min((starts[u] for u in readers), default=0.)
            if src is not None:
                writers = [u for u in g.ps[t] if owner[u] == src]
                when = max(when, max((done[u] for u in writers), default=0.) + max(1, math.ceil(size / bw))
                           + cfg['cross_core_copy_delay_cycles'])
            requests.append((when, g.tensors[t].get('logical_tid', t), size))
        hit = fifo_requests(requests, cfg['cache_capacity_bytes'], bw,
                            cfg['cache_bandwidth_bytes_per_cycle'])['hit_bytes']
    mem = residency(g, plan, q, cfg['capacity']) if memory_weight else dict(excess_bytes=0., exposure_cycles=0.)
    ddr = max(0., accounting['pre_spill_bytes'] - hit) / bw
    cache_work = hit / cfg['cache_bandwidth_bytes_per_cycle']
    path = assignment_path(g, plan, q, cfg)
    score = max(max(done.values(), default=0.), ddr, cache_work, path)
    score += .08 * ddr + memory_weight * (mem['exposure_cycles'] + 2 * mem['excess_bytes'] / bw)
    return dict(score=score, assignment_lower=path, pre_spill_bytes=accounting['pre_spill_bytes'],
                predicted_hit_bytes=hit, memory=mem, compute_finish=max(done.values(), default=0.))


def certificate(g, plan, q, cfg, raw, singlecore=None):
    """Global bracketing plus conservative a-posteriori workload upper envelope.

    Under original integer-cycle rules at most 2n COPYs share either bandwidth
    pool. Each COPY lasts <=2n*ceil(bytes/min-bandwidth), zero bytes cost >=1.
    Summing such service limits and every synchronization edge overbounds any
    path of the fixed acyclic non-idling execution graph. See THEORY.md.
    """
    lower = relaxed_lower(g, plan.cores)
    actual = float(raw['makespan'])
    movement = raw['data_movement_bytes']
    copy_ops = sum(op['op'] in COPY for c in raw['per_core_timeline'] for op in c.get('ops', []))
    bandwidth = min(cfg['bandwidth'], cfg['cache_bandwidth_bytes_per_cycle']) if q == 3 else cfg['bandwidth']
    d = movement['scheduled_copy_bytes']
    if q == 1:
        waits = len(raw.get('task_dependencies', [])) * max(cfg['task_same_core_wait_cycles'], cfg['task_cross_core_wait_cycles'])
        waits += sum(max(0, len(seq) - 1) for seq in plan.json()['core_schedules']) * cfg['task_same_core_wait_cycles']
    else:
        waits = len(raw.get('cross_core_transfers', raw.get('task_dependencies', []))) * cfg['cross_core_copy_delay_cycles']
    envelope = sum(g.cost.values()) + 2 * plan.cores * (math.ceil(d / bandwidth) + copy_ops) + waits
    assignment = assignment_path(g, plan, q, cfg)
    if lower['global_lower'] > actual + 1e-7 or assignment > actual + 1e-7 or actual > envelope + 1e-7:
        raise ArithmeticError('Certificate inequality failed; preserve result and inspect model/version, never clip it')
    return dict(**lower, candidate_lower=assignment, feasible_upper=actual, analytic_upper=envelope,
                ratio_bound=actual / lower['global_lower'] if lower['global_lower'] else None,
                speedup_upper=singlecore / lower['global_lower'] if singlecore and lower['global_lower'] else None,
                scope='LB global, candidate_lower conditional, feasible_upper certified by official simulation')
