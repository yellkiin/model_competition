"""Convex chain/junction contraction and multi-pipe group mapping."""
from __future__ import annotations
from collections import defaultdict
import math
from .model import Graph, make_plan, topo


def chain_junction_groups(g: Graph, cfg, q, *, junctions=True, chain_cap=0.):
    """Contract maximal degree-one chains, then small convex junction regions.

    The `heavy_rank` label increases after each non-junction component. A cheap
    region at a fixed label cannot leave through a non-cheap component and return.
    Thus WCC contraction inside such a region preserves quotient acyclicity.
    """
    groups, group_of = [], {}
    for u in g.order:
        ps = g.pred[u]
        p = next(iter(ps)) if len(ps)==1 else None
        if p is not None and len(g.succ[p])==1:
            s = group_of[p]
            if not chain_cap or sum(g.cost[v] for v in groups[s])+g.cost[u] <= chain_cap:
                groups[s].append(u); group_of[u]=s; continue
        group_of[u]=len(groups); groups.append([u])
    pred = {s:set() for s in range(len(groups))}
    succ = {s:set() for s in range(len(groups))}
    for v in g.ids:
        b=group_of[v]
        for u in g.pred[v]:
            a=group_of[u]
            if a!=b: pred[b].add(a); succ[a].add(b)
    order=topo(pred)
    wait=cfg['task_cross_core_wait_cycles'] if q==1 else cfg['cross_core_copy_delay_cycles']
    cheap={s for s,b in enumerate(groups) if sum(g.cost[u] for u in b) <= wait*.25}
    if not junctions: return [groups[s] for s in order]
    label={}
    for s in order: label[s]=max((label[p]+int(p not in cheap) for p in pred[s]), default=0)
    seen=set(); merged=[]
    for s in order:
        if s in seen: continue
        if s not in cheap:
            seen.add(s);merged.append(groups[s]);continue
        stack=[s];seen.add(s);component=[]
        while stack:
            a=stack.pop();component.append(a)
            for b in pred[a]|succ[a]:
                if b in cheap and b not in seen and label[b]==label[s]:
                    seen.add(b);stack.append(b)
        nodes=[u for b in component for u in groups[b]]
        if sum(g.cost[u] for u in nodes)<=2*wait:
            merged.append(sorted(nodes,key=g.index.__getitem__))
        else:
            merged.extend(groups[b] for b in sorted(component,key=lambda b:min(g.index[u] for u in groups[b])))
    # Sort quotient: merged IDs are arbitrary, not topology claims.
    m={u:s for s,b in enumerate(merged) for u in b}; pp={s:set() for s in range(len(merged))}
    for v in g.ids:
        pp[m[v]].update(m[u] for u in g.pred[v] if m[u]!=m[v])
    return [merged[s] for s in topo(pp)]


def map_groups(g: Graph, groups, n: int, cfg, q, *, locality=.12, pack=True):
    """Ready-list EFT mapping with per-pipe calendars and release costs.

    Only predecessor-group finish times are used. The score is a proxy, not a
    makespan certificate. Equal-depth groups are independent and can be packed.
    """
    m={u:s for s,b in enumerate(groups) for u in b}
    pred={s:set() for s in range(len(groups))};succ={s:set() for s in range(len(groups))}
    edge_bytes=defaultdict(float)
    for v in g.ids:
        b=m[v]
        for u in g.pred[v]:
            a=m[u]
            if a!=b:pred[b].add(a);succ[a].add(b)
    for t in g.tensors:
        ps={m[u] for u in g.ps[t]};cs={m[u] for u in g.cs[t]}
        for a in ps:
            for b in cs-{a}:edge_bytes[a,b]+=g.tensors[t]['size']
    weights={s:g.loads(b) for s,b in enumerate(groups)}
    internal={s:sum(g.cost[u] for u in b) for s,b in enumerate(groups)}
    base=topo(pred);rank={};depth={}
    for s in reversed(base):rank[s]=max(weights[s])+max((rank[v] for v in succ[s]),default=0)
    for s in base:depth[s]=max((depth[p]+1 for p in pred[s]),default=0)
    order=topo(pred,key=lambda s:(-rank[s],-max(weights[s]),min(groups[s])))
    clocks=[[0.]*4 for _ in range(n)];tasktail=[0.]*n
    finish={};owners={}
    wait=cfg['task_cross_core_wait_cycles'] if q==1 else cfg['cross_core_copy_delay_cycles']
    bw=cfg['bandwidth']
    for s in order:
        options=[]
        for k in range(n):
            ready=max((finish[p]+(wait+2*edge_bytes[p,s]/bw if owners[p]!=k else 0.) for p in pred[s]),default=0.)
            c=list(clocks[k]);ends={}
            for u in groups[s]:
                r=max((ends[v] for v in g.pred[u] if v in ends),default=ready)
                p=g.pipe[u];ends[u]=max(c[p],r)+g.cost[u];c[p]=ends[u]
            end=max(ends.values(),default=ready)
            moved=sum(edge_bytes[p,s] for p in pred[s] if owners[p]!=k)
            score=end+locality*2*moved/bw
            options.append((score,end,sum(c),k,c))
        _,finish[s],_,k,clocks[k]=min(options)
        owners[s]=k
    if pack:
        by=defaultdict(list)
        for s in order:by[depth[s],owners[s]].extend(groups[s])
        keys=sorted(by)
        blocks=[sorted(by[key],key=g.index.__getitem__) for key in keys]
        where=[key[1] for key in keys]
    else:
        blocks=[groups[s] for s in order];where=[owners[s] for s in order]
    return make_plan(blocks,where,n)


def junction_plan(g, n, cfg, q, *, junctions=True, pack=True, chain_cap=0., locality=.12):
    groups=chain_junction_groups(g,cfg,q,junctions=junctions,chain_cap=chain_cap)
    return map_groups(g,groups,n,cfg,q,locality=locality,pack=pack)
