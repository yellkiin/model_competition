"""Bounded tensor-reuse/transfer-local neighbourhood. No new partition framework.

The fixed partition is retained. We change legal subgroup order or co-locate
whole groups that share an expensive producer/consumer tensor. Proxies rank
proposals only; official makespan and the incumbent guard decide acceptance.
"""
from __future__ import annotations
from collections import defaultdict
from copy import deepcopy
import time
from research_a_orion_anytime.core import plan_view, make_plan, estimate, bounds
from .reuse_repair import plan_key
from .plugin import _peak_window
from .policy import search_state
VERSION='memory-local-2.3'


def propose(g,n,cfg,q,incumbent=None,feedback=None,deadline=None):
    if incumbent is None:return
    p=incumbent['plan'];m,groups,owner,order=plan_view(g,p)
    if len(p['core_schedules'])!=n:raise ValueError('NPU core mismatch')
    state=search_state(g,cfg,n,q,incumbent);upper=state['upper']
    if not state['should_search']:return
    seen={plan_key(p)};pool=[];trials=0
    pred={s:set() for s in groups}
    for u in g.topo:pred[m[u]].update(m[v] for v in g.pred[u] if m[v]!=m[u])
    positions={s:i for seq in p['core_schedules'] for i,s in enumerate(seq)}
    def add(plan,name,mechanism):
        nonlocal trials
        if trials>=160 or (deadline is not None and time.monotonic()>=deadline):return
        key=plan_key(plan)
        if key in seen:return
        seen.add(key);trials+=1
        try:
            plan_view(g,plan)
            bd=bounds(g,cfg,n,q,plan)
            if bd['candidate_lower']>upper:
                if feedback is not None:feedback.append(dict(name=name,status='certified_pruned',lower=bd['candidate_lower']))
                return
            proxy=estimate(g,plan,cfg,q,cache=False)
            pool.append(dict(name=name,family='memory/local_tensor',plan=plan,proxy=proxy,bounds=bd,mechanism=mechanism))
        except (ValueError,KeyError) as e:
            if feedback is not None:feedback.append(dict(name=name,status='structural_rejected',error=str(e)))
    def shift(s,target,name):
        k=owner[s];trial=deepcopy(p);seq=trial['core_schedules'][k]
        seq.remove(s);seq.insert(max(0,min(len(seq),target)),s)
        add(trial,name,{'fixed_partition':True,'cores_unchanged':True,'moved_subgraph':s})
    edges=[];reuse=[]
    for t,ts in g.tensors.items():
        ps={m[u] for u in g.tp[t]};cs={m[u] for u in g.tc[t]};size=ts['size']
        remote=[(a,b) for a in ps for b in cs if owner[a]!=owner[b]]
        for a,b in remote:edges.append((size+cfg.cross_b*cfg.bandwidth,t,a,b))
        bycore=defaultdict(list)
        for s in ps|cs:bycore[owner[s]].append(s)
        for k,uses in bycore.items():
            uses.sort(key=positions.get)
            for a,b in zip(uses,uses[1:]):
                distance=positions[b]-positions[a]
                if distance>1:reuse.append((size*distance,t,a,b))
    for _,t,a,b in sorted(edges,reverse=True)[:20]:
        for s in (a,b):
            for delta in (1,3,6):shift(s,positions[s]-delta,f'transfer_pull_{s}_{delta}')
        for moved,dest in ((a,owner[b]),(b,owner[a])):
            trial=make_plan([groups[s] for s in order],[dest if s==moved else owner[s] for s in order],n)
            add(trial,f'tensor_colocate_{t}_{moved}_{dest}',{'tensor':t,'moved_subgraph':moved,'destination':dest,'fixed_partition':True})
    for _,t,a,b in sorted(reuse,reverse=True)[:20]:
        shift(b,positions[a]+1,f'reuse_pull_{t}_{b}')
        shift(a,positions[b]-1,f'producer_late_{t}_{a}')
    for seq in p['core_schedules']:
        for i in range(1,len(seq)):
            if seq[i-1] not in pred[seq[i]]:
                shift(seq[i],i-1,f'local_boundary_swap_{seq[i]}')
    for start in sorted(set([0,max(0,len(order)//2-4),max(0,len(order)-8)])):
        if deadline is not None and time.monotonic()>=deadline:return
        trial=_peak_window(g,p,cfg,start,8)
        if trial:add(trial,f'local_peak_frontier_{start}',{'fixed_core_window':8,'peak':'heuristic, separate L1/UB'})
    pool.sort(key=lambda c:(c['proxy']['score'],c['name']))
    for c in pool[:24]:
        if deadline is not None and time.monotonic()>=deadline:return
        yield c
