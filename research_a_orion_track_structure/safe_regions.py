"""Serial-region whole-chain grouping; no new lower bound or FIFO model.

Experimental negative candidate, NOT used by safe_refine_plugin. On the real
024/Q1/5 pilot all three region variants were worse than the protected seed.
"""
from collections import defaultdict
from research_a_orion_anytime.core import make_plan,plan_view


def regions(g):
    """Split only at computation nodes dominating every retained-compute sink."""
    pos={u:i for i,u in enumerate(g.topo)};dom={};succ={u:set() for u in g.ops}
    for v in g.topo:
        ps=g.retained_pred[v]
        for u in ps:succ[u].add(v)
        parents=iter(ps);first=next(parents,None);mask=dom[first] if first is not None else 0
        for u in parents:mask &= dom[u]
        dom[v]=mask | (1<<pos[v])
    sinks=[u for u in g.topo if not succ[u]]
    if not sinks:return []
    common=dom[sinks[0]]
    for u in sinks[1:]:common &= dom[u]
    barriers=[u for u in g.topo if common & (1<<pos[u])]
    if len(barriers)<2:return []
    ordinal={pos[u]:i for i,u in enumerate(barriers)};parts=defaultdict(set)
    for v in g.topo:
        previous=(dom[v]&common&~(1<<pos[v])).bit_length()-1
        parts[ordinal[previous]+1 if previous>=0 else 0].add(v)
    return [part for _,part in sorted(parts.items()) if part]


def pack_regions(g,n,reserve_join=False,rotate=False):
    """Keep expensive induced chains intact; place a small merge tail separately.

    This may be structurally inapplicable to a graph: plan_view rejects the whole
    candidate rather than dropping operations or changing the graph.
    """
    if n<2:return None
    parts=regions(g)
    if not parts:return None
    groups=[];cores=[];heavy_count=n-1 if reserve_join else n
    for i,us in enumerate(parts):
        ordered=sorted(g.duration[u] for u in us);median=ordered[len(ordered)//2]
        light={u for u in us if g.duration[u]<median*.25}
        if not light:light={u for u in us if not (g.succ[u]&us)}
        heavy=us-light
        components=g.weak_components(heavy) if heavy else []
        bins=[set() for _ in range(heavy_count)];loads=[0.]*heavy_count
        for comp in sorted(components,key=lambda c:(-g.weight(c),min(c))):
            k=min(range(heavy_count),key=lambda k:(loads[k],k));bins[k].update(comp);loads[k]+=g.weight(comp)
        offset=(i%heavy_count) if rotate else 0
        for k,chunk in enumerate(bins):
            if chunk:groups.append(chunk);cores.append((k+offset)%heavy_count)
        if light:
            join=n-1 if reserve_join else ((min(range(heavy_count),key=lambda k:loads[k])+offset)%heavy_count)
            groups.append(light);cores.append(join)
    p=make_plan(groups,cores,n);plan_view(g,p);return p
