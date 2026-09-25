"""FIFO candidates only reorder whole existing subgraphs on their owner cores.

No changes to node assignment, partition, op latency, sleep/delay or FIFO rules.
"""
from __future__ import annotations
import time
from .trace import read_requests

def propose(g,n,cfg,q,incumbent=None,feedback=None,deadline=None):
    if q!=3 or not incumbent:return
    from research_a_orion_anytime.core import plan_view,estimate,bounds
    plan=incumbent['plan'];raw=incumbent['official_result'];reads,fills=read_requests(raw)
    if len(plan['core_schedules'])!=n:raise ValueError('wrong target core count')
    plan_view(g,plan);seqs=plan['core_schedules'];seen=set();emitted=0
    end_by_core={c['core_id']:max((o['end'] for o in c['ops']),default=0) for c in raw['per_core_timeline']}
    opportunities=[]
    for r in reads:
        k,s=r['core_id'],r['subgraph_id']
        if s not in seqs[k] or len(seqs[k])<2:continue
        if r['cause'] not in ('cold_inflight','evicted_inflight','evicted'):continue
        direction=1 if 'inflight' in r['cause'] else -1
        relevance=.25+.5*r['completion']/max(raw['makespan'],1)+.25*end_by_core[k]/max(raw['makespan'],1)
        priority=r['bytes']*(1/cfg.bandwidth-1/cfg.cache_bandwidth)*relevance
        opportunities.append((priority,r,direction))
    opportunities.sort(key=lambda x:(-x[0],x[1]['event_index']))
    changes=[]
    def wrap(new,name,family,evidence):
        nonlocal emitted
        key=tuple(tuple(s) for s in new)
        if key in seen or key==tuple(tuple(s) for s in seqs):return None
        seen.add(key)
        p={'node_to_subgraph':dict(plan['node_to_subgraph']),'core_schedules':new}
        try:plan_view(g,p)
        except ValueError as exc:
            if feedback is not None:feedback.append(dict(name=name,family='anytime/'+family,status='order_invalid',error=str(exc)))
            return None
        c=dict(name=name,family='anytime/'+family,plan=p,proxy=estimate(g,p,cfg,q),bounds=bounds(g,cfg,n,q,p),evidence=evidence)
        emitted+=1;return c
    for distance in (1,2,4,8):
        for priority,r,direction in opportunities[:12]:
            if deadline is not None and time.monotonic()>=deadline:return
            k,s=r['core_id'],r['subgraph_id'];i=seqs[k].index(s);j=max(0,min(len(seqs[k])-1,i+direction*distance))
            if i==j:continue
            new=[list(v) for v in seqs];new[k].pop(i);new[k].insert(j,s)
            evidence=dict(tensor_id=r['tensor_id'],cause=r['cause'],issue=r['issue'],completion=r['completion'],pending_fill=r['earliest_pending_completion'],previous_eviction=r['last_eviction'],priority_hint=priority,priority_is_bound=False)
            c=wrap(new,f'fifo_{r["cause"]}_c{k}_s{s}_{i}_to{j}','fifo_window',evidence)
            if c:changes.append((k,i,j,s,evidence));yield c
            if emitted>=16:break
        if emitted>=16:break
    # Preserve room for joint hypotheses instead of exhausting the single-move cap.
    for x in range(min(4,len(changes))):
        for y in range(x+1,min(8,len(changes))):
            if deadline is not None and time.monotonic()>=deadline:return
            a,b=changes[x],changes[y]
            if a[0]==b[0]:continue
            new=[list(v) for v in seqs]
            for k,i,j,s,e in (a,b):new[k].pop(i);new[k].insert(j,s)
            c=wrap(new,f'fifo_joint_c{a[0]}_c{b[0]}_{x}_{y}','fifo_joint',dict(first=a[4],second=b[4]))
            if c:yield c
            if emitted>=24:return
