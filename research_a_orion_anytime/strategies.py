"""Bounded stage DP and joint reassignment of topology-convex block windows.

Inspired by IOS (stage decomposition), SERENITY (live-state memoization), and
acyclic partition formulations. Their optimality claims DO NOT apply here.
Only official plan variables change; all internal costs are surrogates.
"""
from __future__ import annotations
from collections import defaultdict
from functools import lru_cache
import math
import random
from .core import (Graph, Config, PIPES, topological, make_plan, plan_view,
                   map_groups, partition, estimate, bounds, fingerprint)


def candidate(g, cfg, q, plan, name, family):
    plan_view(g, plan)
    return dict(name=name, family=family, plan=plan,
                proxy=estimate(g, plan, cfg, q),
                bounds=bounds(g, cfg, len(plan['core_schedules']), q, plan))


def _stage_groups(g, bins, cuts):
    groups=[]; previous=0
    for end in cuts:
        nodes=set().union(*bins[previous:end])
        groups.extend(g.weak_components(nodes))
        previous=end
    return groups


def _bins(g, count=24, weighted=False):
    depth={}
    for u in g.topo:
        depth[u]=max((depth[p]+(g.duration[p] if weighted else 1)
                      for p in g.pred[u]), default=0)
    # Rank-compress distinct depths; do not split a depth layer.
    levels=sorted(set(depth.values())); ix={d:i for i,d in enumerate(levels)}
    count=min(count,len(levels))
    bins=[set() for _ in range(max(1,count))]
    for u in g.topo:
        bins[min(count-1,ix[depth[u]]*count//max(1,len(levels)))].add(u)
    return bins


def _pack_by_stage(g, plan, bins, cuts):
    m, groups, cores, _=plan_view(g,plan)
    owner={u:cores[m[u]] for u in g.ops}+    packed=[]; where=[]; previous=0
    for end in cuts:
        nodes=set().union(*bins[previous:end]); previous=end
        for k in range(len(plan['core_schedules'])):
            part={u for u in nodes if owner[u]==k}
            if part:packed.append(part);where.append(k)
    return make_plan(packed,where,len(plan['core_schedules']))


def stage_candidates(g, n, cfg, q, include_dp=True):
    """A lazy stream: caller can stop between candidates without building a grid.

    DP is exact ONLY for the additive stage surrogate over <=16 fixed bins.
    Official execution overlaps stages; no additive-execution claim is made.
    """
    bins=_bins(g,24)
    for nstages in (8,4,16,2):
        cuts=sorted(set(max(1,math.ceil(len(bins)*j/nstages))
                        for j in range(1,nstages+1)))
        groups=_stage_groups(g,bins,cuts)
        plan=map_groups(g,groups,n,cfg,q)
        yield candidate(g,cfg,q,plan,f'stages_{nstages}_ordered','stage')
        packed=_pack_by_stage(g,plan,bins,cuts)
        yield candidate(g,cfg,q,packed,f'stages_{nstages}_packed','stage')
    if not include_dp:return
    for penalty in (0.25,1.0):
        bs=_bins(g,16,weighted=True)
        cost={}; parts={}
        for i in range(len(bs)):
            nodes=set()
            for j in range(i+1,len(bs)+1):
                nodes.update(bs[j-1]); comps=g.weak_components(nodes)
                parts[i,j]=[set(c) for c in comps]
                # Relax within-stage mapping by per-pipe work and max WCC weight.
                work=max(max(g.loads(nodes).values())/n,
                         max((g.weight(c) for c in comps),default=0))
                boundary=set()
                for u in nodes:
                    boundary.update(t for t in g.outputs[u] if g.tc[t]-nodes)
                traffic=sum(g.tensors[t]['size'] for t in boundary)
                cost[i,j]=work+penalty*2*traffic/cfg.bandwidth+(cfg.cross_a if q==1 else cfg.cross_b)
        dp=[0.0]+[float('inf')]*len(bs); paths=[[] for _ in dp]
        for j in range(1,len(dp)):
            val,i=min((dp[i]+cost[i,j],i) for i in range(j))
            dp[j]=val;paths[j]=paths[i]+[j]
        groups=[];prev=0
        for end in paths[-1]:groups.extend(parts[prev,end]);prev=end
        plan=map_groups(g,groups,n,cfg,q)
        yield candidate(g,cfg,q,plan,f'stage_dp_{penalty}_ordered','stage_dp')
        yield candidate(g,cfg,q,_pack_by_stage(g,plan,bs,paths[-1]),f'stage_dp_{penalty}_packed','stage_dp')


def fine_candidates(g,n,cfg,q):
    for grain in (12,16,24):
        groups=partition(g,n,cfg,q,grain)
        yield candidate(g,cfg,q,map_groups(g,groups,n,cfg,q),f'frontier_g{grain}','finer')


def _group_data(g,plan):
    m,groups,owner,order=plan_view(g,plan)
    preds={s:set() for s in groups}
    for v,ps in g.pred.items():
        preds[m[v]].update(m[u] for u in ps if m[u]!=m[v])
    return m,groups,owner,order,preds


def joint_window(g,plan,cfg,q,result,round_no=0,width=6,beam_width=12):
    """Reassign a contiguous topological window jointly; no per-op enumeration.

    State stores assignments and multi-pipe loads. A bounded beam keeps alternatives;
    this is not an exact solver of the original or even the full proxy problem.
    """
    m,groups,owner,order,preds=_group_data(g,plan);n=len(plan['core_schedules'])
    if len(order)<2 or n<2:return []
    counts={k:0 for k in range(n)}
    for c in (result or {}).get('per_core_timeline',[]):
        counts[c['core_id']]=max((o['end'] for o in c['ops']),default=0)
    busy=max(counts,key=lambda k:(counts[k],-k))
    focus=[s for s in order if owner[s]==busy]
    focus.sort(key=lambda s:(-g.weight(groups[s]),s))
    anchor=focus[round_no%len(focus)] if focus else order[round_no%len(order)]
    start=max(0,min(len(order)-width,order.index(anchor)-width//2))
    window=order[start:start+width]; movable=set(window)
    load=[[0.0]*len(PIPES) for _ in range(n)]
    weights={s:tuple(g.loads(groups[s])[p] for p in PIPES) for s in groups}
    for s in groups:
        if s not in movable:
            for j,w in enumerate(weights[s]):load[owner[s]][j]+=w
    tensor_pins=[]
    for t in g.tensors:
        ps={m[u] for u in g.tp[t]};cs={m[u] for u in g.tc[t]}
        if (ps|cs)&movable:
            tensor_pins.append((g.tensors[t]['size'],ps,cs))
    states=[(0.0,{},load)]
    for s in window:
        expanded=[]
        for _,assignment,loads in states:
            for k in range(n):
                a={**assignment,s:k};ll=[v[:] for v in loads]
                for j,w in enumerate(weights[s]):ll[k][j]+=w
                used={**owner,**a}; traffic=0
                for size,ps,cs in tensor_pins:
                    if (ps|cs)&(movable-a.keys()):continue
                    pk={used[x] for x in ps};ck={used[x] for x in cs}
                    traffic+=size*(len(ck) if not pk else 2*sum(x!=y for x in pk for y in ck))
                path={}
                for b in order:
                    path[b]=max(weights[b])+max((path[p]+(cfg.cross_a if q==1 else cfg.cross_b)
                                                 *(used[p]!=used[b]) for p in preds[b]),default=0)
                score=max(max(map(max,ll)),max(path.values(),default=0),traffic/cfg.bandwidth)
                expanded.append((score,tuple(a[x] for x in window if x in a),a,ll))
        # Diversity of assignments is retained even when proxy scores tie.
        expanded.sort(key=lambda e:(e[0],e[1]))
        states=[(e[0],e[2],e[3]) for e in expanded[:beam_width]]
    out=[];seen={fingerprint(plan)}
    for _,a,_ in states[:4]:
        p=make_plan([groups[s] for s in order],[a.get(s,owner[s]) for s in order],n)
        h=fingerprint(p)
        if h in seen:continue
        seen.add(h)
        out.append(candidate(g,cfg,q,p,f'joint_window_r{round_no}','joint_window'))
    return sorted(out,key=lambda c:c['proxy']['score'])


def memory_window_order(g,plan,cfg,q,round_no=0,width=8):
    """Subset DP minimizing an additive live-frontier surrogate in a local window.

    Only existing subgraphs are ordered. Peak memory is NOT assumed to equal this
    score; official Step1/2/3 and FIFO semantics are not changed. The selected global
    window is contiguous in a common topological order, so external paths cannot
    leave and return to the window. All final plans still pass full validation.
    """
    m,groups,owner,order,preds=_group_data(g,plan)
    if len(order)<2:return None
    start=(round_no*max(1,width//2))%max(1,len(order)-width+1)
    win=order[start:start+width];ws=set(win);ix={s:i for i,s in enumerate(win)}
    pm=[sum(1<<ix[p] for p in preds[s]&ws) for s in win]
    relevant=[]
    for t in g.tensors:
        ps={m[u] for u in g.tp[t]};cs={m[u] for u in g.tc[t]}
        if (ps|cs)&ws:
            before=bool(ps-set(order[start:])) or (not ps)
            after=bool(cs-set(order[:start+len(win)]))
            relevant.append((g.tensors[t]['size']/max(1,cfg.capacity.get(g.tensors[t]['pos'],cfg.ub)),
                             sum(1<<ix[s] for s in ps&ws),sum(1<<ix[s] for s in cs&ws),before,after))
    @lru_cache(None)
    def live(mask):
        return sum(size for size,ps,cs,before,after in relevant
                   if (before or ps&mask) and (after or cs&~mask))
    weights={s:max(1,g.weight(groups[s])) for s in win}
    total=1<<len(win);dp={0:(0.0,())}
    for mask in range(total):
        if mask not in dp:continue
        cost,seq=dp[mask]
        for j,s in enumerate(win):
            if mask>>j&1 or pm[j]&mask!=pm[j]:continue
            new=mask|1<<j
            val=(cost+live(new)*weights[s],seq+(s,))
            if new not in dp or val<dp[new]:dp[new]=val
    if total-1 not in dp:return None
    changed=order[:start]+list(dp[total-1][1])+order[start+len(win):]
    p=make_plan([groups[s] for s in changed],[owner[s] for s in changed],len(plan['core_schedules']))
    return candidate(g,cfg,q,p,f'live_order_dp_r{round_no}','memory_dp')


def mutations(g,plan,cfg,q,result,round_no=0):
    """Local merge, exchange, and FIFO natural-work phase changes; no delay ops."""
    m,groups,owner,order,preds=_group_data(g,plan); n=len(plan['core_schedules'])
    if n<2:return
    rng=random.Random(104729+round_no)
    weights={s:g.weight(groups[s]) for s in groups}
    load=[sum(weights[s] for s in groups if owner[s]==k) for k in range(n)]
    busy=max(range(n),key=lambda k:(load[k],-k));light=min(range(n),key=lambda k:(load[k],k))
    a=sorted((s for s in groups if owner[s]==busy),key=lambda s:(-weights[s],s))
    b=sorted((s for s in groups if owner[s]==light),key=lambda s:(weights[s],s))
    # Choose a few joint exchanges rather than only moving one heavy block.
    for x in a[round_no%max(1,len(a)):][:2]:
        for y in b[:2]:
            cores=[owner[y] if s==x else owner[x] if s==y else owner[s] for s in order]
            yield candidate(g,cfg,q,make_plan([groups[s] for s in order],cores,n),'critical_pair_exchange','exchange')
    # Adjacent in the common topological order => contraction preserves acyclicity.
    merges=sorted(range(len(order)-1),key=lambda i:(owner[order[i]]!=owner[order[i+1]],
                  -(weights[order[i]]+weights[order[i+1]]),i))
    for idx in merges[round_no%max(1,len(merges)):][:2]:
        x,y=order[idx:idx+2]
        gg=[groups[s] for s in order[:idx]]+[groups[x]|groups[y]]+[groups[s] for s in order[idx+2:]]
        kk=[owner[s] for s in order[:idx]]+[owner[x]]+[owner[s] for s in order[idx+2:]]
        yield candidate(g,cfg,q,make_plan(gg,kk,n),'adjacent_convex_merge','merge')
    # A randomized topological key gives deterministic, repeatable diversity.
    priority={s:rng.random() for s in order}
    new=topological(order,preds,key=lambda s:priority[s])
    p=make_plan([groups[s] for s in new],[owner[s] for s in new],n)
    yield candidate(g,cfg,q,p,'topological_natural_phase','phase')
