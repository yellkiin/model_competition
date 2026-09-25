"""Adaptive real-job queue, hard deadlines and selected-result publication."""
from __future__ import annotations
from collections import deque
from pathlib import Path
import json, os, shutil, subprocess, sys, time
from .io import ROOT, read, write, score
from .resources import Admission, terminate


def summarize(req,execution):
    out=Path(req['out']);p=out/'progress.json'
    state=read(p) if p.is_file() else {}
    inc=state.get('incumbent');base=state.get('baseline');raw=state.get('raw_candidate_best')
    status='ok' if inc else 'failed'
    if state.get('status')=='reference_mismatch':status='reference_mismatch'
    if execution['reason']=='worker_error' and status=='ok':execution['partial_worker_error']=True
    summary={'case':req['case'],'q':req['q'],'n':req['n'],'components':req['components'],
             'fifo_module':req.get('fifo_module'),'version':state.get('version'),
             'status':status,'seed_mode':req.get('mode','warm'),'execution':execution,
             'reference_makespan':req.get('reference_makespan'),
             'seed_replay_seconds':state.get('seed_replay_seconds'),
             'candidate_generation_seconds':state.get('candidate_generation_seconds'),
             'official_eval_seconds':state.get('official_eval_seconds'),
             'source_seed_seconds':req.get('source_seed_seconds'),
             'end_to_end_seconds':None if req.get('source_seed_seconds') is None else req['source_seed_seconds']+execution['wall_seconds'],
             'attempt_count':len(state.get('attempts',[])),
             'source_errors':state.get('generator_notes',[]),
             'request':'request.json','progress':'progress.json'}
    if inc and status=='ok':
        summary.update(makespan=inc['makespan'],added_copy_bytes=inc['added_copy_bytes'],
                       selected_name=inc['name'],selected_family=inc['family'],
                       certificate=inc['certificate'])
        shutil.copyfile(out/inc['plan_file'],out/'plan.json')
        shutil.copyfile(out/inc['result_file'],out/'result.json.gz')
        summary.update(plan='plan.json',result='result.json.gz')
        summary['baseline_makespan']=base['makespan'] if base else None
        summary['raw_candidate_makespan']=raw['makespan'] if raw else None
        summary['regression_retained']=bool(base and raw and raw['makespan']>base['makespan'] and inc['makespan']==base['makespan'])
        if base and inc['makespan']>base['makespan']:raise RuntimeError('Selected plan regressed despite incumbent rule')
        final=read(out/'result.json.gz')['official_result']
        summary.update(final.get('data_movement_bytes',{}))
        summary['cache_hit_rate']=final.get('cache_stats',{}).get('hit_rate')
    write(out/'summary.json',summary)
    return summary


def run_jobs(jobs,out,deadline_epoch,max_workers=0,reserve=.25):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    pending=deque(jobs);active=[];results=[];policy=Admission(max_workers,reserve)
    resource_log=(out/'resources.jsonl').open('a',encoding='utf8');last_sample=0;sample=None
    try:
        while pending or active:
            now=time.time()
            if now-last_sample>=1 or sample is None:
                sample=policy.update(active);last_sample=now
                resource_log.write(json.dumps({'epoch':now,'active':len(active),**sample})+'\n');resource_log.flush()
            while pending and len(active)<sample['target_workers'] and now<deadline_epoch:
                req=pending.popleft();folder=Path(req['out']);folder.mkdir(parents=True,exist_ok=True)
                prior=folder/'summary.json'
                if prior.is_file():
                    old=read(folder/'request.json')
                    if old!=req:raise ValueError(f'Changed request; use a new run directory: {folder}')
                    results.append(read(prior));continue
                write(folder/'request.json',req)
                log=(folder/'worker.log').open('w',encoding='utf8')
                p=subprocess.Popen([sys.executable,'-m','research_a_orion_fusion.solve',str((folder/'request.json').resolve())],
                                   cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                                   start_new_session=os.name!='nt',env={**os.environ,'PYTHONUTF8':'1'})
                active.append({'proc':p,'request':req,'log':log,'start':time.monotonic(),'peak_rss':0,
                               'workers_at_start':sample['target_workers']})
            for a in active[:]:
                p=a['proc'];req=a['request'];elapsed=time.monotonic()-a['start'];reason=None
                folder=Path(req['out']);progress=folder/'progress.json'
                state={}
                if progress.is_file():
                    try:state=read(progress)
                    except (OSError,json.JSONDecodeError):pass
                if now>=deadline_epoch:reason='campaign_deadline'
                elif state.get('phase')=='search':
                    # Each subprocess owns its own monotonic origin; compare its
                    # relative search deadline against elapsed launcher time.
                    if now>=state.get('search_deadline_epoch',now+state['search_deadline_seconds']-elapsed)+.5:reason='search_timeout'
                elif elapsed>=req.get('seed_timeout',240)+req['seconds']:
                    reason='job_timeout'
                elif state.get('phase')=='seed_replay' and elapsed>=req.get('seed_timeout',240):reason='seed_timeout'
                if reason:terminate(p)
                if p.poll() is not None:
                    a['log'].close();active.remove(a)
                    execution={'reason':reason or ('completed' if p.returncode==0 else 'worker_error'),
                        'returncode':p.returncode,'wall_seconds':time.monotonic()-a['start'],
                        'peak_rss_bytes':a['peak_rss'],'workers_at_start':a['workers_at_start']}
                    write(folder/'execution.json',execution)
                    r=summarize(req,execution);results.append(r)
                    print(f"{folder.name}: {r['status']} {r.get('baseline_makespan')} -> {r.get('makespan')} [{execution['reason']}]",flush=True)
            if pending and now>=deadline_epoch:
                while pending:
                    req=pending.popleft();write(Path(req['out'])/'request.json',req)
                    r={'case':req['case'],'q':req['q'],'n':req['n'],'status':'not_started_deadline','components':req['components']}
                    write(Path(req['out'])/'summary.json',r);results.append(r)
            if pending or active:time.sleep(.2)
    finally:
        for a in active:terminate(a['proc']);a['log'].close()
        resource_log.close()
    return results
