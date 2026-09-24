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
    return make_plan([packed[k] for k in keys], [k[1] for k in keys], len(plan['core_schedules']))

def propose(g, n, cfg, q, incumbent=None, feedback=None, deadline=None):
    """COMMON.md generator; optional effective_core_seeds contains plan entries.

    The caller validates seed provenance and freshly evaluates padded plans at
    the target setting. Deterministic candidate order never branches on case ID.
    No official evaluator is called inside this generator.
    """
    def expired():
        return deadline is not None and time.monotonic() >= deadline
    seen = set()
    def wrap(plan, name, family):
        plan_view(g, plan)
        key = (tuple(sorted((int(u), s) for u, s in plan['node_to_subgraph'].items())),
               tuple(tuple(x) for x in plan['core_schedules']))
        if key in seen:
            return None
        seen.add(key)
        return dict(name=name, family='structure/' + family, plan=plan,
                    proxy=estimate(g, plan, cfg, q), bounds=bounds(g, cfg, n, q, plan))
    for i, seed in enumerate((incumbent or {}).get('effective_core_seeds', [])):
        if expired():
            return
        if len(seed['plan']['core_schedules']) <= n:
            c = wrap(pad_plan(seed['plan'], n), f'padded_seed_{i}', 'effective_cores')
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
    c = wrap(map_groups(g, linear_blocks(g), n, cfg, q), 'chain_rank_eft', 'chain_partition')
    if c:
        yield c
    if n > 2 and not expired():
        effective = max(2, n - 2)
        p = map_groups(g, groups, effective, cfg, q)
        c = wrap(pad_plan(pack_within_phase(g, p, phase), n),
                 f'width_valley_effective_{effective}', 'effective_cores')
        if c:
            yield c
