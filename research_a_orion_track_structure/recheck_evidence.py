"""Frozen-source lookup and fresh fixed-plan official replays (no hash tests)."""
from __future__ import annotations
import argparse, csv, gzip, json, shutil, time, traceback, zipfile
from collections import Counter
from pathlib import Path
from research_a_orion_anytime.core import plan_view
from research_a_orion_anytime.engine import OfficialSession
from research_a_orion_anytime.worker import atomic_json
from .plugin import pad_plan

ROOT=Path(__file__).resolve().parents[1]
OFF=ROOT/'题目/A题/通用神经网络处理器下的多核调度问题  附件'
DAY=ROOT/'research_a_orion_anytime/team_results/day01/combined_final'

def read(p):
    p=Path(p)
    if p.suffix=='.gz':
        with gzip.open(p,'rt',encoding='utf8') as f:return json.load(f)
    return json.loads(p.read_text(encoding='utf-8-sig'))

def gzwrite(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp')
    with gzip.open(tmp,'wt',encoding='utf8',compresslevel=3) as f:json.dump(x,f,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    tmp.replace(p)

def csvwrite(p,rows):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

def formal(case,q,n):
    """Follow selected_plans and exact plan equality, never first filename match."""
    case=f'{int(str(case).replace("case_","")):03d}'
    name=f'plans/q{q}/n{n}/case_{case}_multicore_res.json'
    with zipfile.ZipFile(DAY/'selected_plans.zip') as z:plan=json.loads(z.read(name))
    rows=list(csv.DictReader((DAY/'per_case.csv').open(encoding='utf-8-sig')))
    row=next(r for r in rows if (r['case'],int(r['q']),int(r['n']))==(f'case_{case}',q,n))
    matched=[]; histories=[]
    for phase in ('coverage','refinement'):
        for progress in sorted((ROOT/'raw_day01').glob(f'shard_*/run/{phase}/case_{case}_q{q}_n{n}/progress.json')):
            s=read(progress);m=s.get('incumbent');sm=read(progress.parent/'summary.json')
            histories.append({'phase':phase,'progress':str(progress.relative_to(ROOT)), 'summary':sm})
            if not m:continue
            pp=progress.parent/m['plan_file'];rr=progress.parent/m['result_file']
            if read(pp)==plan and int(m['makespan'])==int(row['makespan']):
                matched.append({'phase':phase,'progress':str(progress.relative_to(ROOT)),'plan':str(pp.relative_to(ROOT)), 'result':str(rr.relative_to(ROOT))})
    if not matched:raise ValueError(f'No raw selected-plan match for {case},q{q},n{n}')
    chosen=matched[-1]
    # Historical end-to-end is the complete selected job chain; not only first improvement time.
    costs=[x['summary'].get('total_job_seconds') for x in histories]
    total=sum(costs) if all(v is not None for v in costs) else None
    return plan,read(ROOT/chosen['result']),dict(case=case,q=q,n=n,archive=str((DAY/'selected_plans.zip').relative_to(ROOT)),member=name,raw_matches=matched,chosen=chosen,history=histories,seed_solve_seconds=total,table_solve_seconds=float(row['solve_seconds']),baseline=int(row['baseline']))

def metrics(g,plan,result):
    raw=result['official_result'];m,gs,owner,_=plan_view(g,plan)
    cores=[]
    for c in raw['per_core_timeline']:
        ops=[o for o in c['ops'] if o['op_id'] in g.ops]
        work=Counter()
        for o in ops:work[o['pipe']]+=o['duration']
        cores.append({'core':c['core_id'],'ops':len(ops),'pipe_work':dict(work),'last_compute_end':max((o['end'] for o in ops),default=0),'last_any_end':max((o['end'] for o in c['ops']),default=0)})
    return dict(makespan=raw['makespan'],effective_cores=sum(c['ops']>0 for c in cores),cores=cores,data_movement_bytes=raw['data_movement_bytes'],cache_hit_rate=raw.get('cache_stats',{}).get('hit_rate'),bounds=result['audit']['certificate'])

def replay(job):
    out=Path(job['out']);out.mkdir(parents=True,exist_ok=True);start=time.monotonic()
    atomic_json(out/'request.json',job)
    try:
        if job.get('plan_file'):
            plan=read(job['plan_file']);original=read(job['result_file']) if job.get('result_file') else None
            provenance=job.get('provenance',{})
        else:
            plan,original,provenance=formal(job['case'],job['q'],job.get('source_n',job['n']))
        if job['n']>len(plan['core_schedules']):plan=pad_plan(plan,job['n'])
        atomic_json(out/'plan.json',plan);atomic_json(out/'source.json',provenance)
        if original:gzwrite(out/'original_response.json.gz',original)
        st=time.monotonic();session=OfficialSession(OFF,OFF/'data'/f'case_{job["case"]}.json',OFF/'data/config.txt')
        construction=time.monotonic()-st;plan_view(session.graph,plan)
        st=time.monotonic();result=session.evaluate(plan,job['q']);official_and_audit=time.monotonic()-st
        gzwrite(out/'official_response.json.gz',result)
        diag=metrics(session.graph,plan,result);atomic_json(out/'diagnostics.json',diag)
        old=original['official_result']['makespan'] if original else None
        row=dict(case=job['case'],q=job['q'],n=job['n'],source_n=job.get('source_n',job['n']),label=job['label'],status=result['status'],old_makespan=old,new_makespan=result['official_result']['makespan'],equal=old==result['official_result']['makespan'] if original else None,construction_seconds=construction,official_eval_seconds=result['eval_seconds'],audit_seconds=official_and_audit-result['eval_seconds'],total_seconds=time.monotonic()-start,effective_cores=diag['effective_cores'],added_copy_bytes=diag['data_movement_bytes']['added_copy_bytes'],seed_solve_seconds=provenance.get('seed_solve_seconds'),plan_file=str(out/'plan.json'),result_file=str(out/'official_response.json.gz'))
    except Exception as e:row={**job,'status':'error','error':str(e),'traceback':traceback.format_exc(),'total_seconds':time.monotonic()-start}
    atomic_json(out/'summary.json',row);print(json.dumps(row,ensure_ascii=False),flush=True)
    return row

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('request');a=p.parse_args();replay(read(a.request))
