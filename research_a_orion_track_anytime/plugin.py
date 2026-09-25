"""FIFO candidates only reorder whole existing subgraphs on their owner cores.

No changes to op latency, sleep/delay or FIFO rules. Revision v4 adds two
mechanism-faithful hypotheses from the original event stream: advancing the
read that will perform an in-flight fill, and delaying the fill that evicted a
later-reused tensor. Both remain ordinary legal subgraph reorderings.
"""
from __future__ import annotations
from collections import defaultdict
import time
from .trace import read_requests, operations


def propose(g,n,cfg,q,incumbent=None,feedback=None,deadline=None):
    if q!=3 or not incumbent:return
    from research_a_orion_anytime.core import plan_view,estimate,bounds
    plan=incumbent['plan'];raw=incumbent['official_result'];reads,fills=read_requests(raw)
    if len(plan['core_schedules'])!=n:raise ValueError('wrong target core count')
    plan_view(g,plan);seqs=plan['core_schedules'];seen=set();emitted=0
    ops=operations(raw)
    end_by_core={c['core_id']:max((o['end'] for o in c['ops']),default=0) for c in raw['per_core_timeline']}
    by_tensor=defaultdict(list)
    for r in reads:by_tensor[r['tensor_id']].append(r)
    for rows in by_tensor.values():rows.sort(key=lambda r:r['event_index'])
    opportunities=[]
    for r in reads:
        k,s=r['core_id'],r['subgraph_id']
        if s not in seqs[k] or len(seqs[k])<2:continue
        if r['cause'] not in ('cold_inflight','evicted_inflight','evicted'):continue
        direction=1 if 'inflight' in r['cause'] else -1
        relevance=.25+.5*r['completion']/max(raw['makespan'],1)+.25*end_by_core[k]/max(raw['makespan'],1)
        timing=1.0
        if r['earliest_pending_completion'] is not None:
            timing += max(0,r['earliest_pending_completion']-r['issue'])/max(1,r['completion']-r['issue'])
        elif r['last_eviction'] is not None:
            timing += min(1.0,max(0,r['issue']-r['last_eviction'])/max(1,raw['makespan']))
        priority=r['bytes']*(1/cfg.bandwidth-1/cfg.cache_bandwidth)*relevance*timing
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

    def move(base,k,s,delta):
        if s not in base[k]:return None
        new=[list(v) for v in base];i=new[k].index(s);j=max(0,min(len(new[k])-1,i+delta))
        if i==j:return None
        new[k].pop(i);new[k].insert(j,s)
        return new,i,j

    for distance in (1,2,4,8):
        for priority,r,direction in opportunities[:12]:
            if deadline is not None and time.monotonic()>=deadline:return
            moved=move(seqs,r['core_id'],r['subgraph_id'],direction*distance)
            if not moved:continue
            new,i,j=moved
            evidence=dict(tensor_id=r['tensor_id'],cause=r['cause'],issue=r['issue'],completion=r['completion'],pending_fill=r['earliest_pending_completion'],previous_eviction=r['last_eviction'],priority_hint=priority,priority_is_bound=False,mechanism='consumer_window')
            c=wrap(new,f'fifo_{r["cause"]}_c{r["core_id"]}_s{r["subgraph_id"]}_{i}_to{j}','fifo_window',evidence)
            if c:changes.append((r,new,evidence));yield c
            if emitted>=12:break
        if emitted>=12:break

    for priority,r,_ in opportunities[:12]:
        if deadline is not None and time.monotonic()>=deadline:return
        if 'inflight' not in r['cause'] or r['earliest_pending_completion'] is None:continue
        parents=[x for x in by_tensor[r['tensor_id']] if x['event_index']<r['event_index'] and x['completion']==r['earliest_pending_completion']]
        if not parents:continue
        first=parents[0];fk,fs=first['core_id'],first['subgraph_id']
        if fs not in seqs[fk]:continue
        for distance in (1,2,4):
            moved=move(seqs,fk,fs,-distance)
            if not moved:continue
            new,i,j=moved
            evidence=dict(tensor_id=r['tensor_id'],cause=r['cause'],duplicate_issue=r['issue'],pending_fill=r['earliest_pending_completion'],fill_core=fk,fill_subgraph=fs,fill_issue=first['issue'],fill_completion=first['completion'],mechanism='advance_actual_fill_reader',priority_hint=priority,priority_is_bound=False)
            c=wrap(new,f'fifo_fill_advance_t{r["tensor_id"]}_c{fk}_s{fs}_{i}_to{j}','fifo_fill_advance',evidence)
            if c:yield c
            if emitted>=18:break
        if emitted>=18:break

    for priority,r,_ in opportunities[:12]:
        if deadline is not None and time.monotonic()>=deadline:return
        if r['cause']!='evicted' or r['last_eviction'] is None:continue
        evictors=[f for f in fills if f['time']==r['last_eviction'] and r['tensor_id'] in f.get('evicted_tensor_ids',[])]
        for f in evictors[:1]:
            op=ops.get((f['core_id'],f['op_id']),{});ek,es=f['core_id'],op.get('subgraph_id')
            if es not in seqs[ek]:continue
            for distance in (1,2):
                moved=move(seqs,ek,es,distance)
                if not moved:continue
                new,i,j=moved
                evidence=dict(tensor_id=r['tensor_id'],reuse_issue=r['issue'],eviction_time=r['last_eviction'],evictor_tensor=f['tensor_id'],evictor_core=ek,evictor_subgraph=es,mechanism='delay_actual_fifo_evictor',priority_hint=priority,priority_is_bound=False)
                c=wrap(new,f'fifo_evictor_delay_t{r["tensor_id"]}_c{ek}_s{es}_{i}_to{j}','fifo_evictor_delay',evidence)
                if c:yield c
                if emitted>=22:break
        if emitted>=22:break

    for x in range(min(3,len(changes))):
        for y in range(x+1,min(6,len(changes))):
            if deadline is not None and time.monotonic()>=deadline:return
            a,b=changes[x],changes[y]
            ra,rb=a[0],b[0]
            if ra['core_id']==rb['core_id']:continue
            base=[list(v) for v in seqs]
            ma=move(base,ra['core_id'],ra['subgraph_id'],1 if 'inflight' in ra['cause'] else -1)
            if not ma:continue
            mb=move(ma[0],rb['core_id'],rb['subgraph_id'],1 if 'inflight' in rb['cause'] else -1)
            if not mb:continue
            c=wrap(mb[0],f'fifo_joint_c{ra["core_id"]}_c{rb["core_id"]}_{x}_{y}','fifo_joint',dict(first=a[2],second=b[2]))
            if c:yield c
            if emitted>=24:return
