"""Portable adaptations of the two L2 studies, only within a Q3 supplement.

The archived portfolio is tried by the host. These generators retain its useful
pipe/byte placement and the strong-start v1 weak unpacking. Expensive or harmful
topo4/shared/stagger global reorderings, v2/v3 and entire old solvers are omitted.
No fixed IDs or per-case switches select an algorithm.
"""
from __future__ import annotations
from collections import defaultdict,OrderedDict
import math,time

def band(g,n,cfg,core,stages,weight):
    depth={}
    for u in g.topo:depth[u]=max((depth[p]+1 for p in g.pred[u]),default=0)
    width=max(1,math.ceil((max(depth.values(),default=0)+1)/stages));by=defaultdict(set)
    for u,d in depth.items():by[d//width].add(u)
    pipes=sorted({o['pipe'] for o in g.ops.values()});total=[dict.fromkeys(pipes,0.) for _ in range(n)]
    placed=set();owners={};assigned=defaultdict(set);fifo=OrderedDict();used=0
    for stage in sorted(by):
        pieces=g.weak_components(by[stage]);pieces.sort(key=lambda s:(-g.weight(s),-max(g.rank[u] for u in s),min(s)))
        loads=[dict.fromkeys(pipes,0.) for _ in range(n)];comm=[0.]*n
        for nodes in pieces:
            work=g.loads(nodes);tensors=set().union(*(g.inputs[u] for u in nodes));choices=[]
            for k in range(n):
                links=[];cost=0.
                for t in sorted(tensors):
                    size=g.tensors[t]['size'];sources={owners[u] for u in g.tp[t]-nodes if u in owners}
                    remote=sorted(sources-{k}) if g.tp[t] else [None]
                    cached=t in fifo and fifo[t][1]<stage and 0<size<=cfg.cache_capacity
                    read_cost=.5*(size/cfg.bandwidth+size/cfg.cache_bandwidth) if cached else size/cfg.bandwidth
                    for source in remote:
                        key=(t,source,k)
                        if key in placed:continue
                        links.append(key);cost+=read_cost+(size/cfg.bandwidth+cfg.cross_b if source is not None else 0)
                value=.7*max(loads[k][p]+work.get(p,0) for p in pipes)+.3*max(total[k][p]+work.get(p,0) for p in pipes)+weight*cost
                choices.append((value,comm[k],k,links,cost))
            _,_,k,links,cost=min(choices,key=lambda x:x[:3]);assigned[stage,k].update(nodes);comm[k]+=cost
            placed.update(links);owners.update((u,k) for u in nodes)
            for p in pipes:loads[k][p]+=work.get(p,0);total[k][p]+=work.get(p,0)
            for t in sorted({x[0] for x in links}):
                size=g.tensors[t]['size']
                if not 0<size<=cfg.cache_capacity or t in fifo:continue
                while fifo and used+size>cfg.cache_capacity:_,(s,_) = fifo.popitem(last=False);used-=s
                fifo[t]=(size,stage);used+=size
    keys=sorted(assigned);return core.make_plan([assigned[x] for x in keys],[k for _,k in keys],n)

def weak_orders(g,n,cfg,core,parent,deadline):
    mapping,groups,owners,order=core.plan_view(g,parent)
    units=[];owner=[];base=[]
    for i,s in enumerate(order):
        for part in g.weak_components(groups[s]):units.append(part);owner.append(owners[s]);base.append((i,min(part)))
    umap={u:v for v,nodes in enumerate(units) for u in nodes};pred={v:set() for v in range(len(units))}
    for u,parents in g.pred.items():pred[umap[u]].update(umap[p] for p in parents if umap[p]!=umap[u])
    inputs=[];sizes={}
    for v,nodes in enumerate(units):
        ts=set().union(*(g.inputs[u] for u in nodes));wanted=set()
        for t in ts:
            if g.tp[t] and all(owner[umap[p]]==owner[v] for p in g.tp[t]):continue
            logical=g.tensors[t].get('logical_tid',t);wanted.add(logical);sizes[logical]=g.tensors[t]['size']
        inputs.append(wanted)
    for policy in ('fifo','low_footprint'):
        degree={v:len(ps) for v,ps in pred.items()};succ=defaultdict(list)
        for v,ps in pred.items():
            for p in ps:succ[p].append(v)
        ready={v for v in pred if not degree[v]};resident=OrderedDict();used=0;schedule=[]
        while ready:
            if time.monotonic()>=deadline:return
            def key(v):
                hit=sum(sizes[t] for t in inputs[v] if t in resident);new=sum(sizes[t] for t in inputs[v] if t not in resident)
                return (new>cfg.cache_capacity,new,-hit,base[v]) if policy=='low_footprint' else (-hit,new,base[v])
            v=min(ready,key=key);ready.remove(v);schedule.append(v)
            for t in sorted(inputs[v]):
                size=sizes[t]
                if t in resident or size>cfg.cache_capacity:continue
                while resident and used+size>cfg.cache_capacity:_,s=resident.popitem(last=False);used-=s
                resident[t]=size;used+=size
            for s in succ[v]:
                degree[s]-=1
                if not degree[s]:ready.add(s)
        if len(schedule)!=len(units):raise ValueError('Unit graph cycle')
        # Preserve the original v1 unit IDs, not a renumbering by new order.
        p={'node_to_subgraph':{str(u):v for u,v in umap.items()},'core_schedules':[[] for _ in range(n)]}
        for v in schedule:p['core_schedules'][owner[v]].append(v)
        yield 'weak_'+policy,p

def generate(g,n,cfg,core,parent,deadline,mode='combined'):
    # 4 portfolio candidates vs 2 v1 candidates. This is a fixed proposal budget,
    # not a claim that incomparable historical percentage gains determine weights.
    if mode in ('combined','portfolio') and n>1:
        for stages,weight in ((4,.25),(8,.25),(16,.25),(8,.75)):
            if time.monotonic()>=deadline:return
            p=band(g,n,cfg,core,stages,weight);yield f'portfolio_bands{stages}_w{weight}',p
    if mode in ('combined','weak'):
        yield from weak_orders(g,n,cfg,core,parent,deadline)
