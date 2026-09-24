"""Read original full result timelines; do not infer causality from Spill bytes alone."""
from __future__ import annotations
import argparse
from collections import defaultdict
import json
from pathlib import Path
import time
from research_a_orion_anytime.core import Graph, plan_view
from .plugin import tensor_ledger
from .run import read, csv_write


def union(intervals):
    out=[]
    for a,b in sorted(intervals):
        if b<=a:continue
        if out and a<=out[-1][1]:out[-1]=(out[-1][0],max(b,out[-1][1]))
        else:out.append((a,b))
    return out


def length(intervals):return sum(b-a for a,b in union(intervals))


def overlap(a,b):
    a=union(a);b=union(b);i=j=0;total=0
    while i<len(a) and j<len(b):
        total+=max(0,min(a[i][1],b[j][1])-max(a[i][0],b[j][0]))
        if a[i][1]<b[j][1]:i+=1
        else:j+=1
    return total


def timeline_metrics(result):
    compute=[];copies=[];ddr=[];l2=[];core_rows=[]
    for c in result['per_core_timeline']:
        cp=[(o['start'],o['end']) for o in c['ops'] if o['op'] not in ('COPY_IN','COPY_OUT')]
        io=[(o['start'],o['end']) for o in c['ops'] if o['op'] in ('COPY_IN','COPY_OUT')]
        compute+=cp;copies+=io
        ddr += [(o['start'],o['end']) for o in c['ops'] if o['op'] in ('COPY_IN','COPY_OUT') and o.get('memory_path','DDR') not in ('L2','CACHE_READ')]
        l2 += [(o['start'],o['end']) for o in c['ops'] if o.get('memory_path') in ('L2','CACHE_READ')]
        ts=sorted(c['tasks'],key=lambda t:t['start'])
        core_rows.append(dict(core_id=c['core_id'],compute_union_cycles=length(cp),
            copy_union_cycles=length(io),compute_copy_overlap_cycles=overlap(cp,io),
            task_count=len(ts),between_tasks_gap_cycles=sum(max(0,b['start']-a['end']) for a,b in zip(ts,ts[1:]))))
    transfers=result.get('cross_core_transfers',[])
    waits=[t['copy_in_start']-t['copy_in_release'] for t in transfers]
    return dict(makespan=result['makespan'],data_movement_bytes=result['data_movement_bytes'],
        official_step3_memory_peaks=result.get('memory_peak_by_core'),
        compute_union_cycles=length(compute),copy_union_cycles=length(copies),
        compute_copy_overlap_cycles=overlap(compute,copies),
        copy_without_any_compute_cycles=length(copies)-overlap(compute,copies),
        ddr_union_cycles=length(ddr),l2_union_cycles=length(l2),
        cross_transfer_count=len(transfers),queue_wait_sum_cycles=sum(waits),
        queue_wait_max_cycles=max(waits,default=0),
        largest_queue_waits=sorted(transfers,key=lambda t:-(t['copy_in_start']-t['copy_in_release']))[:10],
        per_core=core_rows,
        interpretation='Union/intersection of observed intervals, not an attribution of the critical path. Queue wait sums overlap and must not be added to Makespan. Step3 peaks are official local results, not independently replayed multicore capacity.')


def compare_plans(g, old_plan, new_plan, q):
    om,og,oc,_=plan_view(g,old_plan);nm,ng,nc,_=plan_view(g,new_plan)
    old=tensor_ledger(g,old_plan,q);new=tensor_ledger(g,new_plan,q)
    a={r['tensor_id']:r for r in old};b={r['tensor_id']:r for r in new}
    rows=[]
    for t in a.keys()|b.keys():
        x=a.get(t,{});y=b.get(t,{})
        delta=y.get('scheduled_bytes',0)-x.get('scheduled_bytes',0)
        if delta:rows.append(dict(tensor_id=t,size=g.tensors[t]['size'],pos=g.tensors[t]['pos'],
            old_bytes=x.get('scheduled_bytes',0),new_bytes=y.get('scheduled_bytes',0),delta_bytes=delta,
            old_producer_owners=x.get('producer_owners'),new_producer_owners=y.get('producer_owners'),
            old_consumer_owners=x.get('consumer_owners'),new_consumer_owners=y.get('consumer_owners')))
    return dict(old_subgraphs=len(og),new_subgraphs=len(ng),
        operations_changed_core=sum(oc[om[u]]!=nc[nm[u]] for u in g.ops),
        old_pre_spill_bytes=sum(r['scheduled_bytes'] for r in old),
        new_pre_spill_bytes=sum(r['scheduled_bytes'] for r in new),
        changed_tensor_count=len(rows),tensor_deltas=sorted(rows,key=lambda x:-abs(x['delta_bytes'])),
        note='Task labels are plan-local. Q2/3 same core ownership gives the same pre-Spill tensor-set ledger, but not necessarily the same official Spill or Makespan.')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True);p.add_argument('--data',required=True)
    args=p.parse_args(argv);root=Path(args.run).resolve();data=Path(args.data).resolve();st=time.monotonic()
    import csv
    records=list(csv.DictReader((root/'per_case.csv').open(encoding='utf-8-sig')))
    outputs=[];graphs={}
    for r in records:
        if r['status']!='ok' or not r.get('result_file'):continue
        g=graphs.setdefault(r['case'],Graph(read(data/(r['case']+'.json')))) if r['case'] not in graphs else graphs[r['case']]
        result=read(root/r['result_file'])['official_result'];plan=read(root/r['plan_file'])
        payload=timeline_metrics(result)
        req_dir=root/r['mode']/f"{r['case']}_q{r['q']}_n{r['n']}"/r['method']
        req=read(req_dir/'request.json')
        if req.get('seed_job'):
            sd=Path(req['seed_job']);s=read(sd/'progress.json');old=read(sd/s['incumbent']['plan_file'])
            payload['plan_change_from_seed']=compare_plans(g,old,plan,int(r['q']))
            payload['seed_timeline']=timeline_metrics(read(sd/s['incumbent']['result_file'])['official_result'])
        path=root/'diagnostics'/f"{r['case']}_q{r['q']}_n{r['n']}_{r['mode']}_{r['method']}.json"
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(payload,indent=2),encoding='utf-8')
        outputs.append({k:r[k] for k in ('case','q','n','mode','method')}|{
            k:payload[k] for k in ('makespan','compute_union_cycles','copy_union_cycles','compute_copy_overlap_cycles',
            'copy_without_any_compute_cycles','queue_wait_max_cycles','queue_wait_sum_cycles')})
    csv_write(root/'timeline_metrics.csv',outputs)
    (root/'diagnostic_cost.json').write_text(json.dumps({'seconds':time.monotonic()-st,'records':len(outputs)}),encoding='utf-8')
    print('Diagnosed original timelines:',len(outputs))
if __name__=='__main__':main()
