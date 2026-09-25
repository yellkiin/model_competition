"""Combine this track's explicitly staged runs, not three research tracks.

Old scores are trusted published data. Baseline + selected-plan comparisons are
not equal-budget cold-start experiments or a newly executed 100-graph campaign.
"""
from __future__ import annotations
import argparse,csv,json,time
from pathlib import Path
from collections import Counter
from .trusted_run import read,write
from .analyze import compare_plans,timeline_metrics
from research_a_orion_anytime.core import Graph


def csv_read(p):
    with Path(p).open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))


def csv_write(p,rows):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)


def resolve(job):
    s=read(job/'progress.json');req=read(job/'request.json');sel=s['selected']
    if sel['result_file'] or not req.get('parent_run'):return job,sel
    return resolve(Path(req['parent_run'])/'jobs'/job.name)


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--epochs',type=Path,required=True);p.add_argument('--local',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    started=time.monotonic();root=a.root.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    runs=[a.epochs.resolve()]+([a.local.resolve()] if a.local else [])
    published=csv_read(root/'research_a_orion_anytime/team_results/day01/combined_final/per_case.csv')
    old={(r['case'],int(r['q']),int(r['n'])):r for r in published}
    paths={};events=[];prefixes=[];attempts=[];count=Counter();process_seconds=0;pair_seconds=0
    for run in runs:
        events+=csv_read(run/'trajectory.csv')
        for jf in sorted(run.glob('jobs/*/request.json')):
            job=jf.parent;req=read(jf)
            if not (job/'progress.json').exists():continue
            s=read(job/'progress.json');key=(req['case'],req['q'],req['n']);paths.setdefault(key,[]).append(job)
            ex=read(job/'execution.json');elapsed=ex['wall_seconds'];process_seconds+=elapsed
            count['jobs']+=1;count['job_'+ex['status']]+=1
            if (job/'pair_execution.json').exists():pair_seconds+=read(job/'pair_execution.json')['wall_seconds']
            for r in s['attempts']:
                count['attempt_'+r['status']]+=1
                attempts.append(dict(case=req['case'],q=req['q'],n=req['n'],run_id=run.name,**{k:r.get(k,'') for k in ('name','status','makespan','added_copy_bytes','spill_bytes','started_seconds','completed_seconds','eval_seconds','plan_file','result_file')}))
            for d in s.get('diagnostics',[]):count['diagnostic_'+d['status']]+=1
            track=sorted([e for e in events if e['case']==key[0] and int(e['q'])==key[1] and int(e['n'])==key[2] and e['run_id']==run.name],key=lambda e:float(e['elapsed_seconds']))
            for cutoff in (30,60,120):
                eligible=[e for e in track if float(e['elapsed_seconds'])<=cutoff and float(e['elapsed_seconds'])<=req['seconds']]
                e=eligible[-1] if eligible else None
                prefixes.append(dict(case=key[0],q=key[1],n=key[2],run_id=run.name,method=read(run/'manifest.json')['version'],cutoff_seconds=cutoff,best_makespan=e['best_makespan'] if e else '',seed_solve_seconds=s['seed_solve_seconds'],total_cutoff_seconds=s['seed_solve_seconds']+cutoff,observed_stop_seconds=elapsed,stopped_and_held=elapsed<cutoff,stop_reason=ex['status']+'/'+s.get('stop_reason','hard_stop'),has_valid_incumbent=e is not None))
    rows=[];cache_rows=[];graphs={};diagnostic_rows=[]
    for key,jobs in sorted(paths.items()):
        b=old[key];job=jobs[-1];s=read(job/'progress.json');src,sel=resolve(job)
        elapsed=sum(read(j/'execution.json')['wall_seconds'] for j in jobs)
        best=s['selected']['makespan'];added=s['selected']['added_copy_bytes'];spill=s['selected']['spill_bytes']
        if best>int(b['makespan']):raise ValueError('Selected incumbent regressed')
        raw=read(src/sel['result_file'])['official_result'] if sel['result_file'] else None
        start=float(b['solve_seconds']);paircost=sum(read(j/'pair_execution.json')['wall_seconds'] for j in jobs if (j/'pair_execution.json').exists())
        generations=sum(read(j/'progress.json')['candidate_generation_seconds'] for j in jobs);construction=sum(read(j/'progress.json')['construction_seconds'] for j in jobs);evaluation=sum(read(j/'progress.json')['official_eval_seconds'] for j in jobs)
        allattempts=[r for j in jobs for r in read(j/'progress.json')['attempts']]
        complete=sum(r['status'] in ('ok','error','audit_failed') for r in allattempts);inflight=sum(r['status']=='running' for r in allattempts)
        r=dict(case=key[0],q=key[1],n=key[2],method='memory/epochs_then_local' if len(jobs)>1 else 'memory/epochs',run_id=out.name,mode='warm_start',status='new_official_selected' if raw else 'trusted_retained',baseline=int(b['baseline']),old_makespan=int(b['makespan']),new_makespan=best,old_speedup=float(b['speedup']),new_speedup=int(b['baseline'])/best,makespan_reduction_pct=100*(1-best/int(b['makespan'])),old_added_copy_bytes=int(b['added_copy_bytes']),new_added_copy_bytes=added,old_spill_bytes=int(b['spill_added_copy_bytes']),new_spill_bytes=spill,seed_solve_seconds=start,added_solve_seconds=elapsed,total_solve_seconds=start+elapsed,construction_seconds=construction,candidate_generation_seconds=generations,completed_official_eval_seconds=evaluation,other_or_interrupted_seconds=max(0,elapsed-construction-generations-evaluation),evaluations=complete,interrupted_evaluations=inflight,lower=float(b['lower']),ratio_upper=best/float(b['lower']),no_l2_makespan='',cache_hit_rate='',pair_seconds=paircost,experiment_total_seconds=start+elapsed+paircost,selected_name=sel['name'],plan_file=str((src/sel['plan_file']).relative_to(out.parent)),result_file=str((src/sel['result_file']).relative_to(out.parent)) if sel['result_file'] else '',last_search_status=read(job/'execution.json')['status'])
        if key[1]==3:
            cp=job.parent.parent/'cache_pairs.csv';pair=next(x for x in csv_read(cp) if x['case']==key[0] and int(x['n'])==key[2]);r['no_l2_makespan']=int(pair['no_l2_makespan']);r['cache_hit_rate']=raw.get('cache_stats',{}).get('hit_rate','') if raw else b['cache_hit_rate'];r['same_plan_cache_speedup']=r['no_l2_makespan']/best;r['old_same_plan_cache_speedup']=float(b['no_l2_makespan'])/int(b['makespan'])
            cache_rows.append({k:r[k] for k in ('case','q','n','old_makespan','new_makespan','no_l2_makespan','old_same_plan_cache_speedup','same_plan_cache_speedup','cache_hit_rate','pair_seconds')})
        rows.append(r)
        if raw:
            if key[0] not in graphs:graphs[key[0]]=Graph(read(root/f'题目/A题/通用神经网络处理器下的多核调度问题  附件/data/{key[0]}.json'))
            change=compare_plans(graphs[key[0]],read(jobs[0]/'seed_plan.json'),read(src/sel['plan_file']),key[1]);tm=timeline_metrics(raw)
            write(out/f'diagnostics/{key[0]}_q{key[1]}_n{key[2]}.json',dict(plan_change=change,new_timeline=tm,old_timeline='Not re-evaluated at user request; old metrics are published.'))
            diagnostic_rows.append(dict(case=key[0],q=key[1],n=key[2],**{k:change[k] for k in ('old_subgraphs','new_subgraphs','operations_changed_core','old_pre_spill_bytes','new_pre_spill_bytes')},copy_without_compute=tm['copy_without_any_compute_cycles'],queue_wait_max=tm['queue_wait_max_cycles']))
    means=[]
    for q in (1,2,3):
        rr=[r for r in rows if r['q']==q];x=sum(r['old_speedup'] for r in rr)/len(rr);y=sum(r['new_speedup'] for r in rr)/len(rr)
        means.append(dict(scope='selected_eight_graphs',metric='T1_over_T5',q=q,n=5,graphs=len(rr),old_mean=x,new_mean=y,relative_change_pct=100*(y/x-1)))
    mean_all=[];new={(r['case'],r['q'],r['n']):r for r in rows}
    for q in (1,2,3):
        for n in range(1,6):
            qq=0 if n==1 and q in (1,2) else q;rr=[r for r in published if int(r['q'])==qq and int(r['n'])==n]
            values=[new.get((b['case'],q,n)) for b in rr];xo=sum(float(b['speedup']) for b in rr)/len(rr);xn=sum(v['new_speedup'] if v else float(b['speedup']) for b,v in zip(rr,values))/len(rr)
            mean_all.append(dict(scope='hybrid_100_accounting_NOT_100_new_runs',metric='T1_over_Tn',q=q,n=n,graphs=len(rr),new_graphs=sum(v is not None and v['new_makespan']<v['old_makespan'] for v in values),old_mean=xo,new_mean=xn,relative_change_pct=100*(xn/xo-1)))
    c_old=sum(r['old_same_plan_cache_speedup'] for r in cache_rows)/len(cache_rows);c_new=sum(r['same_plan_cache_speedup'] for r in cache_rows)/len(cache_rows)
    means.append(dict(scope='selected_eight_graphs',metric='same_plan_noL2_over_L2',q=3,n=5,graphs=8,old_mean=c_old,new_mean=c_new,relative_change_pct=100*(c_new/c_old-1)))
    for name,data in [('per_case.csv',rows),('trajectory.csv',events),('budget_prefixes.csv',prefixes),('attempts.csv',attempts),('cache_pairs.csv',cache_rows),('means.csv',means),('hybrid_100_curves.csv',mean_all),('mechanisms.csv',diagnostic_rows)]:csv_write(out/name,data)
    count.update(improved=sum(r['new_makespan']<r['old_makespan'] for r in rows),retained=sum(r['new_makespan']==r['old_makespan'] for r in rows))
    write(out/'summary.json',dict(counts=dict(count),optimization_process_seconds=process_seconds,pair_process_seconds=pair_seconds,stage_runs=[r.name for r in runs],cold_start_comparison=False,old_evaluator_calls=0,full_100_new_runs=False,report_seconds=time.monotonic()-started))
    print(json.dumps(dict(counts=dict(count),means=means),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
