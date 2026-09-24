"""Finite stage surrogates: exact DP only within the stated restricted model."""
from __future__ import annotations
from collections import defaultdict
import math
from .model import Graph, make_plan, topo
from .junctions import map_groups


def stage_plan(g, n, cfg, q, stages=8, weighted=False, pack=True):
    values = g.earliest if weighted else g.depth
    levels = sorted(set(values.values()))
    # Rank compression avoids a huge time coordinate and never splits a layer.
    ix = {v:i for i,v in enumerate(levels)}
    bins = defaultdict(list)
    for u in g.order:
        bins[min(stages-1,ix[values[u]]*stages//max(1,len(levels)))].append(u)
    groups=[]
    for b in sorted(bins):groups.extend(g.wcc(set(bins[b])))
    return map_groups(g,groups,n,cfg,q,pack=pack)


def dp_stage_plan(g, n, cfg, q, bins_count=16, penalty=.5):
    """Exact shortest path ONLY for a finite additive stage surrogate.

    The official global execution overlaps operations, so DP's value is neither
    official makespan nor a certified lower bound. Retain actual evaluation.
    """
    levels=sorted(set(g.depth.values())); idx={d:i for i,d in enumerate(levels)}
    count=min(bins_count,len(levels));bins=[set() for _ in range(count)]
    for u in g.order:bins[min(count-1,idx[g.depth[u]]*count//len(levels))].add(u)
    intervals={};cost={}
    for i in range(count):
        nodes=set()
        for j in range(i+1,count+1):
            nodes.update(bins[j-1]);parts=g.wcc(nodes);intervals[i,j]=parts
            loads=[[0.]*4 for _ in range(n)];assigned={}
            for part in sorted(parts,key=lambda c:(-max(g.loads(c)),-len(c),min(c))):
                w=g.loads(part)
                k=min(range(n),key=lambda k:(max(a+b for a,b in zip(loads[k],w)),sum(loads[k]),k))
                loads[k]=[a+b for a,b in zip(loads[k],w)];assigned.update({u:k for u in part})
            touched=set().union(*(g.inputs[u]|g.outputs[u] for u in nodes))
            traffic=0.;events=defaultdict(lambda:defaultdict(float))
            position={};seqs=defaultdict(list)
            for u in g.order:
                if u in nodes:position[u]=len(seqs[assigned[u]]);seqs[assigned[u]].append(u)
            for t in touched:
                ps={assigned[u] for u in g.ps[t]&nodes};cs={assigned[u] for u in g.cs[t]&nodes};size=g.tensors[t]['size']
                traffic+=size*len(cs-ps)
                traffic+=size*sum(g.final[t] or bool(g.cs[t]-nodes) or bool(cs-{k}) for k in ps)
                loc=g.tensors[t]['pos']
                if loc not in cfg['capacity']:continue
                pins=defaultdict(list)
                for u in (g.ps[t]|g.cs[t])&nodes:pins[assigned[u]].append(position[u])
                for k,ixs in pins.items():
                    events[k,loc][min(ixs)]+=size;events[k,loc][max(ixs)+1]-=size
            excess=0.
            for (k,pos),ev in events.items():
                live=peak=0.
                for index in sorted(ev):live+=ev[index];peak=max(peak,live)
                excess+=max(0.,peak-cfg['capacity'][pos])
            work=max(max(row) for row in loads)
            lag=cfg['task_cross_core_wait_cycles'] if q==1 else cfg['cross_core_copy_delay_cycles']
            cost[i,j]=max(work,traffic/cfg['bandwidth'])+penalty*excess/cfg['bandwidth']+lag
    best=[0.]+[math.inf]*count;back=[0]*(count+1)
    for j in range(1,count+1):best[j],back[j]=min((best[i]+cost[i,j],i) for i in range(j))
    cuts=[];end=count
    while end:cuts.append((back[end],end));end=back[end]
    groups=[part for ij in reversed(cuts) for part in intervals[ij]]
    return map_groups(g,groups,n,cfg,q)


def frontier_cuts(g,n,stages):
    """Balanced, low-frontier stage partition via a constrained shortest path.

    Exact only for the chosen layer-axis, per-stage work caps and byte proxy.
    """
    levels=sorted(set(g.depth.values())); ix={d:i for i,d in enumerate(levels)}; L=len(levels)
    w=[0.]*L
    for u in g.order:w[ix[g.depth[u]]]+=g.cost[u]
    prefix=[0.]
    for x in w:prefix.append(prefix[-1]+x)
    frontier=[0.]*(L+1)
    for t in g.tensors:
        pins=g.ps[t]|g.cs[t]
        if not pins:continue
        a=min(ix[g.depth[u]] for u in pins); b=max(ix[g.depth[u]] for u in pins)
        for k in range(a+1,b+1):frontier[k]+=g.tensors[t]['size']
    alloc=[n//stages+int(s<n%stages) for s in range(stages)]
    limit=max(max(w),prefix[-1]/n)
    for slack in (1.1,1.3,1.7,2.2):
        states={0:(0.,[])}
        for s in range(stages):
            next_states={}
            for j in range(1,L+1):
                choices=[]
                for i,(value,cuts) in states.items():
                    if i<j and prefix[j]-prefix[i]<=limit*alloc[s]*slack:
                        choices.append((value+(frontier[j] if j<L else 0.),cuts+[j]))
                if choices:next_states[j]=min(choices)
            states=next_states
        if L in states:return states[L][1]
    return [math.ceil(L*(s+1)/stages) for s in range(stages)]
