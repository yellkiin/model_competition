"""Merged FIFO mechanism, not the peer's independent structural constructor.

Lookup at issue, fill at completion, hits do not refresh FIFO. Existing whole
subgraphs keep their owner. Bound terms for Q3 depend on ownership, not this
ordering: reuse the parent's candidate certificate, not its memory surrogate.
"""
from __future__ import annotations
from collections import defaultdict, deque
import time
from research_a_orion_anytime.core import bounds, plan_view
from research_a_orion_track_anytime.trace import read_requests, operations

def propose(g,n,cfg,q,context,deadline):
    if q!=3:return
    plan, raw = context['plan'], context['official_result']
    reads,fills = read_requests(raw); ops = operations(raw)
    mapping,groups,owners,_ = plan_view(g,plan)
    seqs = plan['core_schedules']; positions=[{s:i for i,s in enumerate(seq)} for seq in seqs]
    work={s:g.weight(us) for s,us in groups.items()}
    by_tensor=defaultdict(list)
    for r in reads:by_tensor[r['tensor_id']].append(r)
    evictors={}
    for f in fills:
        for t in f.get('evicted_tensor_ids',[]):evictors[t,f['time']]=f
    opportunities=[]
    for r in reads:
        if r['cause'] not in ('cold_inflight','evicted_inflight','evicted'):continue
        if r['subgraph_id'] not in positions[r['core_id']]:continue
        priority=r['bytes']*max(0,1/cfg.bandwidth-1/cfg.cache_bandwidth)*(.25+.75*r['completion']/max(1,raw['makespan']))
        opportunities.append((priority,r))
    opportunities.sort(key=lambda x:(-x[0],x[1]['event_index']))
    opportunities=opportunities[:16]
    certificate=bounds(g,cfg,n,q,plan)
    seen={tuple(tuple(s) for s in seqs)}
    def move(base,k,s,d):
        if s not in base[k]:return None
        out=[list(v) for v in base];i=out[k].index(s);j=max(0,min(len(out[k])-1,i+d))
        if i==j:return None
        out[k].pop(i);out[k].insert(j,s);return out
    def candidates(kind):
        for distance in (1,2,4):
            for priority,r in opportunities:
                if time.monotonic()>=deadline:return
                k,s=r['core_id'],r['subgraph_id'];p=None
                if kind=='consumer':
                    p=move(seqs,k,s,distance if 'inflight' in r['cause'] else -distance)
                elif kind=='fill' and 'inflight' in r['cause']:
                    parents=[x for x in by_tensor[r['tensor_id']] if x['event_index']<r['event_index'] and x['completion']==r['earliest_pending_completion']]
                    if parents:
                        a=parents[0];p=move(seqs,a['core_id'],a['subgraph_id'],-distance)
                elif kind=='evictor' and r['last_eviction'] is not None:
                    f=evictors.get((r['tensor_id'],r['last_eviction']))
                    if f:
                        op=ops[f['core_id'],f['op_id']]
                        p=move(seqs,f['core_id'],op.get('subgraph_id'),distance)
                elif kind=='window' and distance==1:
                    target=r['earliest_pending_completion'] if 'inflight' in r['cause'] else r['last_eviction']
                    if target is None:continue
                    sign=1 if 'inflight' in r['cause'] else -1
                    need=abs(target-r['issue']);i=positions[k][s];w=0.;j=i
                    for step in range(1,min(32,len(seqs[k]))):
                        z=i+sign*step
                        if not 0<=z<len(seqs[k]):break
                        w+=work[seqs[k][z]];j=z
                        if w>=need:break
                    p=move(seqs,k,s,j-i)
                if p is not None:yield p,priority,r,distance
    streams=deque((kind,iter(candidates(kind))) for kind in ('consumer','fill','evictor','window'))
    emitted=0
    while streams and time.monotonic()<deadline:
        kind,stream=streams.popleft()
        try:p,priority,r,d=next(stream)
        except StopIteration:continue
        streams.append((kind,stream));sig=tuple(tuple(s) for s in p)
        if sig in seen:continue
        seen.add(sig)
        trial=dict(node_to_subgraph=dict(plan['node_to_subgraph']),core_schedules=p)
        try:plan_view(g,trial)
        except ValueError:continue
        yield dict(plan=trial,name=f'{kind}_t{r["tensor_id"]}_op{r["op_id"]}_d{d}',
            family='anytime/fifo_'+kind,bounds=certificate,
            proxy={'score':max(certificate['candidate_lower'],raw['makespan']-priority)},
            evidence=dict(tensor_id=r['tensor_id'],issue=r['issue'],completion=r['completion'],
                cause=r['cause'],fill=r['earliest_pending_completion'],eviction=r['last_eviction'],
                mechanism=kind,heuristic_priority=priority,changes='same_owner_subgraph_order'))
        emitted+=1
        if emitted>=24:return
