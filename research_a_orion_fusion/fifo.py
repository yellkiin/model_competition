"""Observed FIFO windows + bounded, cost-aware source allocation (F component).

Uses the merged peer-v4 issue/fill/eviction proposals. No private-island
constructor is duplicated here: that already belongs to the M component.
Repair-v6's useful principle (preserve a representative before sorting a batch)
is applied by the host's one-candidate source warm-up, not by patching upstream.
"""
from __future__ import annotations
from collections import defaultdict, deque
from math import log, sqrt
from statistics import median
import time
from research_a_orion_anytime.core import bounds, plan_view, topological
from research_a_orion_track_anytime.trace import read_requests, operations

FUSION_API = 1


def proposed_moves(g, n, cfg, q, context, feedback, deadline):
    if q != 3 or not context.get('plan'):
        return
    plan, raw = context['plan'], context['official_result']
    reads, fills = read_requests(raw)
    seqs = plan['core_schedules']
    if len(seqs) != n:
        raise ValueError('FIFO proposal target core count differs')
    mapping, groups, _, _ = plan_view(g, plan)
    # All F candidates retain membership and core owners. The existing Q3
    # necessary-condition bounds do not depend on within-core group order.
    parent_bounds = bounds(g,cfg,n,q,plan)
    group_pred = {s:set() for s in groups}
    for v,parents in g.pred.items():
        group_pred[mapping[v]].update(mapping[u] for u in parents if mapping[u]!=mapping[v])
    positions = [{s:i for i,s in enumerate(seq)} for seq in seqs]
    group_work = {s:sum(g.duration[u] for u in us) for s,us in groups.items()}
    ends = {c['core_id']:max((o['end'] for o in c['ops']),default=0) for c in raw['per_core_timeline']}
    by_tensor, evictions = defaultdict(list), {}
    for r in reads:
        by_tensor[r['tensor_id']].append(r)
    for f in fills:
        for t in f.get('evicted_tensor_ids', []):
            evictions[t, f['time']] = f
    ops = operations(raw)
    targets = []
    for r in reads:
        k,s = r['core_id'],r['subgraph_id']
        if s not in positions[k] or len(seqs[k])<2 or r['cause'] not in ('cold_inflight','evicted_inflight','evicted'):
            continue
        relevance = .25 + .5*r['completion']/max(1,raw['makespan']) + .25*ends[k]/max(1,raw['makespan'])
        timing = 1.
        if r['earliest_pending_completion'] is not None:
            timing += max(0,r['earliest_pending_completion']-r['issue'])/max(1,r['completion']-r['issue'])
        elif r['last_eviction'] is not None:
            timing += min(1.,max(0,r['issue']-r['last_eviction'])/max(1,raw['makespan']))
        priority = r['bytes']*max(0.,1/cfg.bandwidth-1/cfg.cache_bandwidth)*relevance*timing
        targets.append((priority,r,1 if 'inflight' in r['cause'] else -1))
    targets.sort(key=lambda x:(-x[0],x[1]['event_index']))
    # Preserve original v4's first 12 requests; no grouping or score reordering
    # can silently change the already measured candidate representative.
    targets=targets[:12]
    seen={tuple(tuple(x) for x in seqs)}; changes=[]; emitted=0

    def moved(k,s,delta,base=None):
        base=seqs if base is None else base
        if s not in base[k]:return None
        i=base[k].index(s);j=max(0,min(len(base[k])-1,i+delta))
        if i==j:return None
        result=[list(x) for x in base];result[k].pop(i);result[k].insert(j,s)
        return result,i,j

    def emit(new,name,family,evidence):
        nonlocal emitted
        key=tuple(tuple(x) for x in new)
        if key in seen:return None
        seen.add(key)
        p={'node_to_subgraph':dict(plan['node_to_subgraph']),'core_schedules':new}
        try:
            pred={s:set(ps) for s,ps in group_pred.items()}
            for seq in new:
                for a,b in zip(seq,seq[1:]):pred[b].add(a)
            topological(groups,pred)
            bd=parent_bounds
        except ValueError as exc:
            feedback.append({'source':'f','status':'order_invalid','name':name,'error':str(exc)})
            return None
        emitted+=1
        proxy={'score':max(bd['candidate_lower'],raw['makespan']-.05*evidence.get('priority_hint',0)),
               'heuristic_only':True,'model':'observed_event_priority'}
        return dict(plan=p,name=name,family='fifo/'+family,bounds=bd,proxy=proxy,evidence=evidence)

    for distance in (1,2,4,8):
        for priority,r,direction in targets:
            if time.monotonic()>=deadline:return
            change=moved(r['core_id'],r['subgraph_id'],direction*distance)
            if not change:continue
            new,i,j=change
            evidence=dict(tensor_id=r['tensor_id'],cause=r['cause'],issue=r['issue'],completion=r['completion'],
                          pending_fill=r['earliest_pending_completion'],previous_eviction=r['last_eviction'],
                          priority_hint=priority,priority_is_bound=False,mechanism='consumer_window')
            c=emit(new,f'fifo_{r["cause"]}_c{r["core_id"]}_s{r["subgraph_id"]}_{i}_to{j}','consumer_window',evidence)
            if c:changes.append((r,new,evidence));yield c
            if emitted>=12:break
        if emitted>=12:break
    for priority,r,_ in targets:
        if time.monotonic()>=deadline:return
        if 'inflight' not in r['cause'] or r['earliest_pending_completion'] is None:continue
        parents=[x for x in by_tensor[r['tensor_id']] if x['event_index']<r['event_index'] and x['completion']==r['earliest_pending_completion']]
        if not parents:continue
        first=parents[0];k,s=first['core_id'],first['subgraph_id']
        for distance in (1,2,4):
            change=moved(k,s,-distance)
            if not change:continue
            new,i,j=change
            c=emit(new,f'fifo_fill_advance_t{r["tensor_id"]}_c{k}_s{s}_{i}_to{j}','fill_advance',
                   dict(tensor_id=r['tensor_id'],duplicate_issue=r['issue'],pending_fill=r['earliest_pending_completion'],
                        fill_core=k,fill_subgraph=s,fill_issue=first['issue'],fill_completion=first['completion'],
                        mechanism='advance_actual_fill_reader',priority_hint=priority))
            if c:yield c
            if emitted>=18:break
        if emitted>=18:break
    for priority,r,_ in targets:
        if time.monotonic()>=deadline:return
        if r['cause']!='evicted' or r['last_eviction'] is None:continue
        f=evictions.get((r['tensor_id'],r['last_eviction']))
        if not f:continue
        k=f['core_id'];s=ops.get((k,f['op_id']),{}).get('subgraph_id')
        for distance in (1,2):
            change=moved(k,s,distance)
            if not change:continue
            new,i,j=change
            c=emit(new,f'fifo_evictor_delay_t{r["tensor_id"]}_c{k}_s{s}_{i}_to{j}','evictor_delay',
                   dict(tensor_id=r['tensor_id'],reuse_issue=r['issue'],eviction_time=r['last_eviction'],
                        evictor_tensor=f['tensor_id'],mechanism='delay_actual_fifo_evictor',priority_hint=priority))
            if c:yield c
            if emitted>=22:break
        if emitted>=22:break
    for x in range(min(3,len(changes))):
        for y in range(x+1,min(6,len(changes))):
            if time.monotonic()>=deadline:return
            a,b=changes[x],changes[y];ra,rb=a[0],b[0]
            if ra['core_id']==rb['core_id']:continue
            ma=moved(ra['core_id'],ra['subgraph_id'],1 if 'inflight' in ra['cause'] else -1)
            if not ma:continue
            mb=moved(rb['core_id'],rb['subgraph_id'],1 if 'inflight' in rb['cause'] else -1,ma[0])
            if not mb:continue
            c=emit(mb[0],f'fifo_joint_c{ra["core_id"]}_c{rb["core_id"]}_{x}_{y}','joint',
                   dict(first=a[2],second=b[2],mechanism='joint_reuse_windows'))
            if c:yield c
            if emitted>=24:break
        if emitted>=24:break
    used_targets=set()
    for priority,r,direction in targets:
        if time.monotonic()>=deadline:return
        k,s=r['core_id'],r['subgraph_id'];key=(k,s,r['cause'])
        if key in used_targets:continue
        used_targets.add(key);i=positions[k][s]
        target=r['earliest_pending_completion'] if direction>0 else r['last_eviction']
        if target is None:continue
        need=abs(target-r['issue']);work=0;j=i
        for step in range(1,min(32,len(seqs[k]))+1):
            at=i+direction*step
            if not 0<=at<len(seqs[k]):break
            work+=group_work[seqs[k][at]];j=at
            if work>=need:break
        change=moved(k,s,j-i)
        if not change:continue
        new,i,j=change
        c=emit(new,f'fifo_observed_window_c{k}_g{s}_{i}_to{j}','completion_window',
               dict(tensor_id=r['tensor_id'],cause=r['cause'],observed_issue=r['issue'],
                    observed_target_time=target,cumulative_work_hint=work,priority_hint=priority,
                    mechanism='observed_work_window',counterfactual_prediction=False))
        if c:yield c
        if emitted>=32:return


def propose(g,n,cfg,q,context,feedback,deadline):
    previous=None
    while time.monotonic()<deadline and context.get('plan') is not previous:
        previous=context['plan']
        yield from proposed_moves(g,n,cfg,q,context,feedback,deadline)


def select_source(sources, state, context, remaining_seconds):
    # Equivalent sufficient statistics for the original selector, bounded to
    # eight recent records per source. Avoid rescanning the full trace each turn.
    cache=context.setdefault('_selector_stats',{'scanned':0,'counts':defaultdict(int),
                       'last':defaultdict(int),'recent':defaultdict(lambda:deque(maxlen=8))})
    for i in range(cache['scanned'],len(state['attempts'])):
        r=state['attempts'][i]
        if r.get('status')=='running':break
        s=r.get('source');cache['counts'][s]+=1
        cache['last'][s]=r['index'];cache['recent'][s].append(r);cache['scanned']=i+1
    grouped={s:list(cache['recent'][s]) for s in sources}
    counts={s:cache['counts'][s] for s in sources}
    row_count=sum(counts.values())
    empty=[s for s in sources if counts[s]<2]
    if empty:return min(empty,key=lambda s:(counts[s],list(sources).index(s)))
    last={s:cache['last'][s] for s in sources}
    counter=max(last.values(),default=0)
    oldest=min(sources,key=lambda s:(last[s],counts[s]))
    if counter-last[oldest]>=8 or row_count%4==3:return oldest
    costs={s:max(.02,median([r.get('generation_seconds',0)+r.get('eval_and_audit_seconds',r.get('eval_seconds',.1)) for r in grouped[s][-8:]])) for s in sources}
    admitted=[s for s in sources if 1.15*costs[s]+.1<remaining_seconds]
    choices=admitted or list(sources)
    def priority(s):
        recent=grouped[s][-8:]
        reward=sum(r.get('gain_fraction',0) for r in recent)/max(1,len(recent))
        explore=.012*sqrt(log(2+row_count)/(1+counts[s]))
        failure=sum(r.get('status')!='ok' for r in recent)
        return (reward+explore)/(costs[s]*(1+failure/max(1,len(recent))))
    return max(choices,key=lambda s:(priority(s),-last[s]))
