"""Additive structural candidates. Official scores are never inferred here."""
from __future__ import annotations
from bisect import bisect_right
from collections import Counter, defaultdict
from copy import deepcopy
import time
from research_a_orion_anytime.core import make_plan, plan_view, map_groups, estimate, bounds


def pad_plan(plan: dict, n: int) -> dict:
    """Keep all core and group IDs; append independent empty schedules."""
    if isinstance(n, bool) or not isinstance(n, int) or n < len(plan['core_schedules']):
        raise ValueError('target must have at least as many cores as source')
    if set(plan) != {'node_to_subgraph', 'core_schedules'}:
        raise ValueError('exactly the two official plan fields are required')
    result = deepcopy(plan)
    result['core_schedules'].extend([] for _ in range(n - len(result['core_schedules'])))
    return result


def linear_blocks(g):
    """Contract degree-one edges only; no alternative path can create a cycle."""
    owner, groups = {}, []
    for v in g.topo:
        ps = g.pred[v]
        if len(ps) == 1 and len(g.succ[next(iter(ps))]) == 1:
            index = owner[next(iter(ps))]
        else:
            index = len(groups)
            groups.append(set())
        owner[v] = index
        groups[index].add(v)
    return groups


def nonuniform_blocks(g):
    """Preserve width-turning layers rather than compressing all depths to 24 bins.

    Monotone-depth intervals cannot have backwards edges. Induced components
    inside one interval have no inter-component edges. This proves quotient
    acyclicity, not full official execution feasibility.
    """
    depth = {}
    for v in g.topo:
        depth[v] = max((depth[p] + 1 for p in g.pred[v]), default=0)
    widths = Counter(depth.values())
    cuts, direction = [0], 0
    for d in sorted(widths)[1:]:
        change = (widths[d] > widths[d - 1]) - (widths[d] < widths[d - 1])
        if change and change != direction:
            cuts.append(d)
            direction = change
    intervals = defaultdict(set)
    for u in g.topo:
        intervals[bisect_right(cuts, depth[u]) - 1].add(u)
    groups, phase = [], {}
    for i in sorted(intervals):
        for component in g.weak_components(intervals[i]):
            groups.append(component)
            phase.update((u, i) for u in component)
    return groups, phase


def pack_within_phase(g, plan, phase):
    mapping, _, owner, _ = plan_view(g, plan)
    packed = defaultdict(set)
    for u in g.ops:
        packed[phase[u], owner[mapping[u]]].add(u)
    keys = sorted(packed)
    return make_plan([packed[k] for k in keys], [k[1] for k in keys],
                     len(plan['core_schedules']))


def _reassign(g, plan, overrides):
    """Rebuild core lists in a legal global topological group order."""
    _, groups, core, order = plan_view(g, plan)
    placed = [overrides.get(s, core[s]) for s in order]
    return make_plan([groups[s] for s in order], placed, len(plan['core_schedules']))


def _critical_group_edges(g, plan):
    """Rank structural cross-core dependencies for candidate ordering only."""
    mapping, _, core, _ = plan_view(g, plan)
    head = {}
    for v in g.topo:
        head[v] = g.duration[v] + max((head[p] for p in g.retained_pred[v]), default=0)
    longest = max(head.values(), default=0)
    tail = {}
    retained_succ = {u: set() for u in g.ops}
    for v, ps in g.retained_pred.items():
        for p in ps:
            retained_succ[p].add(v)
    for u in reversed(g.topo):
        tail[u] = g.duration[u] + max((tail[v] for v in retained_succ[u]), default=0)

    byte_weight = defaultdict(int)
    for t in g.tensors:
        size = g.tensors[t]['size']
        for p in g.tp[t]:
            for c in g.tc[t]:
                a, b = mapping[p], mapping[c]
                if a != b:
                    byte_weight[a, b] += size
    for a, b, size in g.direct_edges:
        if a in mapping and b in mapping and mapping[a] != mapping[b]:
            byte_weight[mapping[a], mapping[b]] += size

    edges = {}
    scale = max(1, g.weight(g.ops))
    for v, ps in g.retained_pred.items():
        for u in ps:
            a, b = mapping[u], mapping[v]
            if a == b or core[a] == core[b]:
                continue
            through = head[u] + tail[v]
            slack = max(0, longest - through)
            criticality = longest / max(1, longest + slack)
            key = (a, b)
            score = criticality * (1.0 + byte_weight.get(key, 0) / scale)
            old = edges.get(key)
            if old is None or score > old[0]:
                edges[key] = (score, byte_weight.get(key, 0), u, v, slack)
    return sorted(
        ((score, bytes_, a, b, u, v, slack)
         for (a, b), (score, bytes_, u, v, slack) in edges.items()),
        key=lambda x: (-x[0], -x[1], x[2], x[3]))


def incumbent_moves(g, plan, limit=8):
    """Critical-edge affinity and joint migration around a validated incumbent."""
    _, groups, core, _ = plan_view(g, plan)
    n = len(plan['core_schedules'])
    load = [g.weight(u for s, us in groups.items() if core[s] == k for u in us)
            for k in range(n)]
    yielded = 0
    for _, _, a, b, _, _, _ in _critical_group_edges(g, plan)[:6]:
        variants = [
            ('critical_producer_to_consumer', {a: core[b]}),
            ('critical_consumer_to_producer', {b: core[a]}),
        ]
        pair_weight = g.weight(groups[a] | groups[b])
        targets = sorted(range(n), key=lambda k: (load[k] + pair_weight, load[k], k))
        for k in targets[:2]:
            variants.append(('critical_pair_joint_move', {a: k, b: k}))
        for name, overrides in variants:
            if all(core[s] == k for s, k in overrides.items()):
                continue
            yield name, _reassign(g, plan, overrides)
            yielded += 1
            if yielded >= limit:
                return


def propose(g, n, cfg, q, incumbent=None, feedback=None, deadline=None):
    """COMMON generator; no official evaluator calls and no case-ID branches."""
    def expired():
        return deadline is not None and time.monotonic() >= deadline

    seen = set()

    def wrap(plan, name, family):
        plan_view(g, plan)
        key = (tuple(sorted((int(u), s)
                            for u, s in plan['node_to_subgraph'].items())),
               tuple(tuple(x) for x in plan['core_schedules']))
        if key in seen:
            return None
        seen.add(key)
        return dict(name=name, family='structure/' + family, plan=plan,
                    proxy=estimate(g, plan, cfg, q),
                    bounds=bounds(g, cfg, n, q, plan))

    for i, seed in enumerate((incumbent or {}).get('effective_core_seeds', [])):
        if expired():
            return
        if len(seed['plan']['core_schedules']) <= n:
            c = wrap(pad_plan(seed['plan'], n), f'padded_seed_{i}',
                     'effective_cores')
            if c:
                yield c

    if expired():
        return
    groups, phase = nonuniform_blocks(g)
    mapped = map_groups(g, groups, n, cfg, q)
    for p, name in ((mapped, 'width_valley_ordered'),
                    (pack_within_phase(g, mapped, phase), 'width_valley_packed')):
        if expired():
            return
        c = wrap(p, name, 'nonuniform_phases')
        if c:
            yield c

    if expired():
        return
    c = wrap(map_groups(g, linear_blocks(g), n, cfg, q),
             'chain_rank_eft', 'chain_partition')
    if c:
        yield c

    for effective in range(2, n):
        if expired():
            return
        p = map_groups(g, groups, effective, cfg, q)
        c = wrap(pad_plan(pack_within_phase(g, p, phase), n),
                 f'width_valley_effective_{effective}', 'effective_cores')
        if c:
            yield c

    live = (incumbent or {}).get('plan')
    if live is not None:
        for name, p in incumbent_moves(g, live):
            if expired():
                return
            c = wrap(p, name, 'critical_affinity')
            if c:
                yield c
