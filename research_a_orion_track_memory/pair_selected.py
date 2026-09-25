"""Q3 selected-plan no-L2 counterfactuals; never rerun a published old score.

New plans call the unchanged evaluator with cache_capacity_bytes=0, without
editing the official config file. Unchanged parent plans reuse their recorded
pair; all additional pairing time is separate from optimization time.
"""
from __future__ import annotations
import argparse, csv, json, subprocess, sys, time, traceback
from pathlib import Path
from .trusted_run import read,write,export
from .run import terminate,resources,rss
from research_a_orion_anytime.engine import OfficialSession

def pair_worker(job):
    started=time.monotonic();req=read(job/'request.json');state=read(job/'progress.json')
    try:
        session=OfficialSession(req['official'],req['graph'],req['config'])
        plan=read(job/state['selected']['plan_file'])
        result=session.evaluate(plan,3,{'cache_capacity_bytes':0})
        write(job/'no_l2_result.json.gz',result)
        status=result['status']
    except Exception as e:
        status='error';write(job/'no_l2_error.json',dict(error=str(e),traceback=traceback.format_exc()))
    write(job/'pair_execution.json',dict(status=status,source='new_same_plan_original_evaluator',wall_seconds=time.monotonic()-started,config_file_unchanged=True))

def inherited_pair(job):
    req=read(job/'request.json');state=read(job/'progress.json')
    if state['selected']['result_file']:return None
    if req.get('parent_run'):
        parent=Path(req['parent_run'])/'jobs'/job.name
        if read(parent/'progress.json')['selected']['makespan']!=state['selected']['makespan']:raise ValueError('Parent incumbent differs')
        if read(parent/read(parent/'progress.json')['selected']['plan_file'])!=read(job/state['selected']['plan_file']):raise ValueError('Parent plan differs')
        if (parent/'no_l2_result.json.gz').exists():
            result=read(parent/'no_l2_result.json.gz')
            return dict(status=result['status'],no_l2_makespan=result['official_result']['makespan'],source='reused_parent_pair',source_file=str(parent/'no_l2_result.json.gz'),pair_seconds=0.0)
        return inherited_pair(parent)
    val=req['old'].get('no_l2_makespan')
    if val:return dict(status='trusted_published',no_l2_makespan=int(float(val)),source='published_day01_same_plan_pair_not_replayed',pair_seconds=0.0)
    return None

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path);p.add_argument('--job',type=Path);p.add_argument('--seconds',type=float,default=120);p.add_argument('--total-seconds',type=float,default=600);p.add_argument('--workers',default='auto');a=p.parse_args()
    if a.job:pair_worker(a.job);return
    root=a.run.resolve();started=time.monotonic();deadline=started+a.total_seconds;rows=[];pending=[];active=[];observed=512*1024**2
    for job in sorted((root/'jobs').iterdir()):
        if not (job/'progress.json').exists():continue
        req=read(job/'request.json')
        if req['q']!=3:continue
        row=dict(case=req['case'],q=3,n=req['n'],makespan=read(job/'progress.json')['selected']['makespan'],job=str(job))
        if (job/'no_l2_result.json.gz').exists():
            r=read(job/'no_l2_result.json.gz');row.update(status=r['status'],no_l2_makespan=r['official_result']['makespan'],source='already_evaluated_new_plan',pair_seconds=read(job/'pair_execution.json')['wall_seconds'])
        else:
            inherited=inherited_pair(job)
            if inherited:row.update(inherited);write(job/'inherited_pair.json',inherited)
            else:pending.append((job,row))
        rows.append(row)
    while pending or active:
        res=resources();cap=max(1,min(4,res['cpu_quota'],int(max(0,res['available_memory']-512*1024**2)/max(observed*1.5,512*1024**2))))
        if a.workers!='auto':cap=min(cap,int(a.workers))
        while pending and len(active)<cap and time.monotonic()<deadline:
            job,row=pending.pop(0);err=(job/'pair_stderr.txt').open('w');wall=time.monotonic()
            proc=subprocess.Popen([sys.executable,'-m','research_a_orion_track_memory.pair_selected','--job',str(job)],stdout=err,stderr=err,start_new_session=sys.platform!='win32')
            active.append((job,row,proc,wall,err))
        if time.monotonic()>=deadline:
            for job,row in pending:row.update(status='not_started_pair_deadline',pair_seconds=0)
            pending.clear()
        for item in active[:]:
            job,row,proc,wall,err=item;observed=max(observed,rss(proc.pid) or 0)
            timed=time.monotonic()-wall>=a.seconds or time.monotonic()>=deadline
            if timed:terminate(proc)
            if proc.poll() is not None:
                active.remove(item);err.close();elapsed=time.monotonic()-wall
                result=read(job/'no_l2_result.json.gz') if (job/'no_l2_result.json.gz').exists() else {}
                row.update(status=result.get('status','timeout' if timed else 'error'),no_l2_makespan=result.get('official_result',{}).get('makespan',''),source='new_same_plan_original_evaluator',pair_seconds=elapsed)
                write(job/'pair_execution.json',dict(status=row['status'],source=row['source'],wall_seconds=elapsed,config_file_unchanged=True))
        time.sleep(.05)
    for row in rows:
        if row.get('no_l2_makespan'):row['same_plan_cache_speedup']=row['no_l2_makespan']/row['makespan']
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with (root/'cache_pairs.csv').open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
    write(root/'pair_summary.json',dict(wall_seconds=time.monotonic()-started,total_pair_process_seconds=sum(r.get('pair_seconds',0) for r in rows),rows=len(rows),new_evaluations=sum(r.get('source')=='new_same_plan_original_evaluator' for r in rows)))
    export(root)

if __name__=='__main__':main()
