"""Release-aware construction and tensor-affinity minimax stage partitioning.

Adapted from the separately delivered ASTER FRONTIER v2 constructors. Only the
plan is changed. Interval DP is exact for its surrogate, not official execution.
"""
from __future__ import annotations
from collections import defaultdict
from .model import make_plan, topo
from .quality import view


def export_split(g, plan, grain=0):
    """Split topological block prefixes after exports, keeping all core owners."""
    m, blocks, owners, order = view(g, plan)
    core = {u: owners[m[u]] for u in g.ids}
    out, where = [], []
    for s in order:
        part = []
        for u in blocks[s]:
            part.append(u)
            if any(core[v] != core[u] for v in g.succ[u]) or grain and len(part) >= grain:
                out.append(part); where.append(owners[s]); part = []
        if part:
            out.append(part); where.append(owners[s])
    result = make_plan(out, where, len(plan['core_schedules']))
    view(g, result)
    return result


def release_frontier(g, n, q, cfg, transfer_weight=1.):
    """Chain list scheduling using actual producer-op finishes, then release waves."""
    seen, units = set(), []
    for u in g.order:
        if u in seen: continue
        block, v = [u], u
        seen.add(u)
        while len(g.succ[v]) == 1:
            w = next(iter(g.succ[v]))
            if len(g.pred[w]) != 1 or w in seen: break
            block.append(w); seen.add(w); v = w
        units.append(block)
    m = {u: i for i, b in enumerate(units) for u in b}
    pred = {i: set() for i in range(len(units))}
    succ = {i: set() for i in pred}
    edge = defaultdict(float)
    for u in g.ids:
        for v in g.succ[u]:
            if m[u] != m[v]:
                pred[m[v]].add(m[u]); succ[m[u]].add(m[v])
    for t, tensor in g.tensors.items():
        for u in g.ps[t]:
            for v in g.cs[t] - {u}: edge[u, v] += tensor['size']
    for e in g.direct:
        edge[e['source'], e['target']] += max(0, e.get('data_size', 0))
    rank = {}
    for i in reversed(topo(pred)):
        rank[i] = max(g.loads(units[i])) + max((rank[j] for j in succ[i]), default=0.)
    order = topo(pred, key=lambda i: (-rank[i], min(units[i])))
    owner, end = {}, {}
    clock = [[0.] * 4 for _ in range(n)]
    wait = cfg['task_cross_core_wait_cycles'] if q == 1 else cfg['cross_core_copy_delay_cycles']
    for i in order:
        candidates = []
        for k in range(n):
            c, local, traffic = list(clock[k]), {}, 0.
            for u in units[i]:
                ready = 0.
                for v in g.pred[u]:
                    if v in local: arrival = local[v]
                    else:
                        remote = owner[m[v]] != k
                        extra = wait + 2 * edge[v, u] / cfg['bandwidth'] if remote else 0.
                        arrival = end[v] + transfer_weight * extra
                        if remote: traffic += edge[v, u]
                    ready = max(ready, arrival)
                pipe = g.pipe[u]
                local[u] = max(c[pipe], ready) + g.cost[u]
                c[pipe] = local[u]
            score = max(local.values(), default=0.) + .02 * traffic / cfg['bandwidth']
            candidates.append((score, k, c, local))
        _, k, clock[k], finished = min(candidates, key=lambda x: (x[0], x[1]))
        owner[i] = k; end.update(finished)
    exports = {i: any(owner[i] != owner[j] for j in succ[i]) for i in pred}
    wave, groups = {}, defaultdict(list)
    for i in order:
        wave[i] = max((wave[j] + int(owner[i] != owner[j] or exports[j]) for j in pred[i]), default=0)
        groups[wave[i], owner[i]].extend(units[i])
    keys = sorted(groups)
    plan = make_plan([sorted(groups[key], key=g.index.__getitem__) for key in keys], [key[1] for key in keys], n)
    return export_split(g, plan) if q != 1 else plan


def affinity_pipeline(g, n, q, cfg, batch=1, replicas=None, io_weight=1., window=0):
    """Ordered minimax DP over <=96 depth bins with a read-only working-set penalty.

    Existing WCCs act as microbatches. Stage cores are disjoint. Tensor sets count
    each primary input once per stage, not once per consumer edge. No new work,
    artificial delay, tensor replication or capacity override is introduced.
    """
    levels = sorted(set(g.depth.values()))
    count = min(96, len(levels))
    if not count: raise ValueError('empty graph')
    replicas = tuple(replicas or [1] * min(n, count))
    if not replicas or any(r < 1 for r in replicas) or sum(replicas) > n or len(replicas) > count:
        raise ValueError('invalid stage replication profile')
    ix = {d: i for i, d in enumerate(levels)}
    bins = [[] for _ in range(count)]
    bin_of = {u: min(count - 1, ix[g.depth[u]] * count // len(levels)) for u in g.ids}
    for u in g.order: bins[bin_of[u]].append(u)
    prefix = [[0.] for _ in range(4)]
    for b in bins:
        load = g.loads(b)
        for p in range(4): prefix[p].append(prefix[p][-1] + load[p])
    primary = [set() for _ in bins]
    delta = [0.] * (count + 1)
    for t in g.tensors:
        if g.cs[t] and not g.ps[t]:
            for j in {bin_of[u] for u in g.cs[t]}: primary[j].add(t)
        elif g.ps[t] and g.cs[t]:
            a = min(bin_of[u] for u in g.ps[t]); b = max(bin_of[u] for u in g.cs[t])
            if a < b:
                delta[a] += g.tensors[t]['size']; delta[b] -= g.tensors[t]['size']
    boundary, value = [], 0.
    for x in delta[:-1]:
        value += x; boundary.append(value)
    costs = {}
    for i in range(count):
        seen, ins, shared = set(), 0., defaultdict(float)
        for j in range(i + 1, count + 1):
            for t in primary[j - 1] - seen:
                size = g.tensors[t]['size']; ins += size
                if len(g.cs[t]) > 1: shared[g.tensors[t].get('pos')] += size
            seen.update(primary[j - 1])
            comp = max(prefix[p][j] - prefix[p][i] for p in range(4))
            cut = (boundary[i - 1] if i else 0.) + (boundary[j - 1] if j < count else 0.)
            penalty = sum(20 * max(0., shared[pos] - .8 * capacity) / cfg['bandwidth']
                          for pos, capacity in cfg['capacity'].items())
            costs[i, j] = comp, io_weight * (ins + cut) / cfg['bandwidth'] + penalty
    stages = len(replicas)
    dist, paths = {(0, 0): 0.}, {(0, 0): []}
    for k in range(1, stages + 1):
        for j in range(k, count - (stages - k) + 1):
            val, i = min((max(dist[k - 1, i], costs[i, j][0] / replicas[k - 1] + costs[i, j][1]), i)
                         for i in range(k - 1, j) if (k - 1, i) in dist)
            dist[k, j] = val; paths[k, j] = paths[k - 1, i] + [j]
    component = {u: i for i, b in enumerate(g.components) for u in b}
    ordered = sorted(range(len(g.components)), key=lambda i: (-sum(g.cost[u] for u in g.components[i]), min(g.components[i])))
    rank = {c: i for i, c in enumerate(ordered)}
    previous, base, blocks, owners = 0, 0, [], []
    for stage, end in enumerate(paths[stages, count]):
        groups = defaultdict(list)
        for b in bins[previous:end]:
            for u in b:
                r = rank[component[u]]
                replica = r % replicas[stage]
                microbatch = r // replicas[stage] // max(1, batch)
                groups[microbatch, replica, bin_of[u] // window if window else 0].append(u)
        for (_, replica, _), b in sorted(groups.items()):
            blocks.append(sorted(b, key=g.index.__getitem__)); owners.append(base + replica)
        previous = end; base += replicas[stage]
    return make_plan(blocks, owners, n)
