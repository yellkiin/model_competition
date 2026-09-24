"""Read-only computational-region bounds and actual per-core timeline diagnostics."""
from collections import Counter, defaultdict
import math
from research_a_orion_anytime.core import bounds, plan_view, PIPES


def serial_region_bound(g, n):
    """Diagnostic bound only: no new pruning inside the solver.

    Common dominators of every retained-computation sink separate sequential
    regions. Within each region take the maximum of pipe load, computational
    path, and equal-duration-floor nonpreemptive demand bounds. Ignore COPY,
    memory, and synchronization delays rather than making a new timing model.
    """
    if not g.ops:
        return dict(lower=0, barriers=0, regions=[], used_for_pruning=False)
    position = {u:i for i,u in enumerate(g.topo)}
    successors = {u:set() for u in g.ops}
    dominators = {}
    for v in g.topo:
        parents = g.retained_pred[v]
        for u in parents:
            successors[u].add(v)
        it = iter(parents)
        first = next(it, None)
        mask = dominators[first] if first is not None else 0
        for u in it:
            mask &= dominators[u]
        dominators[v] = mask | (1 << position[v])
    sinks = [u for u in g.topo if not successors[u]]
    common = dominators[sinks[0]]
    for u in sinks[1:]:
        common &= dominators[u]
    barriers = [u for u in g.topo if common & (1 << position[u])]
    ordinal = {position[u]:i for i,u in enumerate(barriers)}
    regions, owner = defaultdict(list), {}
    for v in g.topo:
        strict = dominators[v] & common & ~(1 << position[v])
        previous = strict.bit_length()-1
        group = ordinal[previous]+1 if previous >= 0 else 0
        regions[group].append(v)
        owner[v] = group
    del dominators
    head, tail = {}, {}
    for v in g.topo:
        head[v] = max((head[u]+g.duration[u] for u in g.retained_pred[v]
                       if owner[u]==owner[v]), default=0)
    for v in reversed(g.topo):
        tail[v] = max((g.duration[u]+tail[u] for u in successors[v]
                       if owner[u]==owner[v]), default=0)
    rows = []
    for i, nodes in sorted(regions.items()):
        load = max(g.loads(nodes).values(), default=0)/n
        path = max((head[u]+g.duration[u] for u in nodes), default=0)
        demand, witness = 0, None
        for pipe in PIPES:
            selected = sorted((u for u in nodes if g.ops[u]['pipe']==pipe),
                              key=lambda u:(-g.duration[u],u))
            minimum_head, minimum_tail = math.inf, math.inf
            for k, u in enumerate(selected, 1):
                minimum_head = min(minimum_head, head[u])
                minimum_tail = min(minimum_tail, tail[u])
                value = minimum_head+math.ceil(k/n)*g.duration[u]+minimum_tail
                if value > demand:
                    demand = value
                    witness = dict(pipe=pipe, operations=k, duration_floor=g.duration[u],
                                   minimum_head=minimum_head, minimum_tail=minimum_tail)
        rows.append(dict(region=i, ops=len(nodes), entrance=barriers[i-1] if i else None,
                    exit=barriers[i] if i<len(barriers) else None, load_lower=load,
                    path_lower=path, atomic_demand_lower=demand,
                    lower=max(load,path,demand), witness=witness))
    return dict(lower=sum(row['lower'] for row in rows), barriers=len(barriers),
                regions=rows, used_for_pruning=False,
                assumptions='fixed nonpreemptive compute durations; retained dependencies; one of each Pipe per core')


def graph_features(g, cfg, n):
    depths = {}
    for u in g.topo:
        depths[u] = max((depths[v]+1 for v in g.pred[u]), default=0)
    widths = Counter(depths.values())
    return dict(ops=len(g.ops), components=len(g.components), pipe_work=g.loads(g.ops),
                levels=len(widths), level_width_histogram=dict(Counter(widths.values())),
                indegree_histogram=dict(Counter(map(len,g.pred.values()))),
                outdegree_histogram=dict(Counter(map(len,g.succ.values()))),
                ordinary_bounds=bounds(g,cfg,n,2), serial_region_bound=serial_region_bound(g,n))


def timeline(g, plan, result):
    raw = result.get('official_result', result)
    cores = []
    for core in raw['per_core_timeline']:
        compute = [o for o in core['ops'] if o['op_id'] in g.ops]
        work = Counter()
        for op in compute:
            work[op['pipe']] += op['duration']
        cores.append(dict(core=core['core_id'], compute_ops=len(compute), pipe_work=dict(work),
                    last_compute_end=max((o['end'] for o in compute), default=0),
                    last_any_end=max((o['end'] for o in core['ops']), default=0),
                    groups=len(plan['core_schedules'][core['core_id']])))
    return dict(makespan=raw['makespan'], effective_cores=sum(c['compute_ops']>0 for c in cores),
                cores=cores, data_movement_bytes=raw['data_movement_bytes'],
                latest_transfers=sorted(raw.get('cross_core_transfers',[]),
                                       key=lambda t:-t['copy_in_end'])[:8],
                caution='late transfers are candidates for attribution, not a proven critical-path decomposition')
