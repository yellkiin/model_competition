"""Adaptive real-job queue, hard deadlines and selected-result publication."""
from __future__ import annotations
from collections import deque
from pathlib import Path
import json, os, shutil, subprocess, sys, time, platform
from .io import ROOT, read, write, score
from .resources import Admission, terminate


def summarize(req,execution):
    out=Path(req['out']);p=out/'progress.json'
    state=read(p) if p.is_file() else {}
    if not state.get('incumbent') and req.get('seed_response') and req.get('reuse_verified_response'):
        inherited=read(req['seed_response'])
        if inherited.get('status')=='ok' and inherited.get('audit',{}).get('ok'):
            plan=read(req['seed_plan']);value=inherited['official_result']
            if len(plan['core_schedules'])!=req['n'] or value['num_cores']!=req['n']:
                raise ValueError('Inherited fallback target core count differs')
            write(out/'inherited_plan.json',plan);write(out/'inherited_result.json.gz',inherited)
            meta={'makespan':value['makespan'],'added_copy_bytes':value['data_movement_bytes']['added_copy_bytes'],
                  'plan_file':'inherited_plan.json','result_file':'inherited_result.json.gz','name':'inherited_after_interrupt',
                  'family':'seed','certificate':inherited['audit']['certificate'],'ready_seconds':execution['wall_seconds']}
            state['incumbent']=meta;state['baseline']=dict(meta);state['fallback_only']=True
            # No fabricated early event: this availability time is conservative.
            state.setdefault('improvement_events',[]).append({'elapsed_seconds':execution['wall_seconds'],
                'makespan':meta['makespan'],'added_copy_bytes':meta['added_copy_bytes'],'source':'seed','name':meta['name']})
            write(out/'progress.json',state)
    inc=state.get('incumbent');base=state.get('baseline');raw=state.get('raw_candidate_best')
    status='ok' if inc else 'failed'
    if state.get('status')=='reference_mismatch':status='reference_mismatch'
    if execution['reason']=='worker_error' and status=='ok':execution['partial_worker_error']=True
    runtime=read(out/'runtime.json') if (out/'runtime.json').is_file() else {}
    history=req.get('source_seed_seconds')
    if req.get('alternatives') or req.get('baseline_alternatives') or runtime.get('dynamic_alternatives'):history=None
    summary={'case':req['case'],'q':req['q'],'n':req['n'],'components':req['components'],
             'fifo_module':req.get('fifo_module'),'version':state.get('version'),
             'status':status,'seed_mode':req.get('mode','warm'),'execution':execution,
             'reference_makespan':req.get('reference_makespan'),
             'seed_replay_seconds':state.get('seed_replay_seconds'),
             'candidate_generation_seconds':state.get('candidate_generation_seconds'),'construction_seconds':state.get('construction_seconds'),'parse_seconds':state.get('parse_seconds'),
             'official_eval_seconds':state.get('official_eval_seconds'),
             'source_seed_seconds':history,'known_primary_seed_seconds':req.get('source_seed_seconds'),'job_seconds':req.get('job_seconds',req.get('seconds')),
             'cache_overrides':req.get('cache_overrides'),'stop_reason':state.get('stop_reason'),
             'graph_features':state.get('graph_features'), 'phase_events':state.get('phase_events',[]),'io_seconds':state.get('io_seconds'),
             'pair_status':state.get('pair_status'),'pair_seconds':state.get('pair_seconds'),
             'pair_ready_seconds':state.get('pair_ready_seconds'),'no_l2_makespan':state.get('no_l2_makespan'),
             'end_to_end_seconds':None if history is None else history+execution['wall_seconds'],
             'attempt_count':len(state.get('attempts',[])),
             'source_errors':state.get('generator_notes',[]),
             'request':'request.json','progress':'progress.json'}
    if inc and status=='ok':
        summary.update(makespan=inc['makespan'],added_copy_bytes=inc['added_copy_bytes'],
                       selected_name=inc['name'],selected_family=inc['family'],
                       certificate=inc['certificate'],selected_plan_ready_seconds=inc.get('ready_seconds'))
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
                if (folder/'runtime.json').is_file():
                    # A machine/process interruption is not a fresh free budget.
                    # Recover the last persisted incumbent and close this attempt;
                    # an explicit new round may seed from it later.
                    if (folder/'request.json').is_file() and read(folder/'request.json')!=req:
                        raise ValueError('Interrupted request changed; use a new round')
                    previous=read(folder/'progress.json') if (folder/'progress.json').is_file() else {}
                    execution={'reason':'recovered_interruption_budget_closed','returncode':None,
                        'wall_seconds':min(600,req.get('job_seconds',req.get('seconds',600))),
                        'wall_time_is_upper_bound':True,'last_persisted_seconds':previous.get('elapsed_seconds'),
                        'measured_wall_seconds':None,'peak_rss_bytes':None,'workers_at_start':None,
                        'python':sys.version,'platform':platform.platform(),'host':platform.node()}
                    write(folder/'execution.json',execution)
                    results.append(summarize(req,execution));continue
                write(folder/'request.json',req)
                dynamic=[]
                if req.get('campaign_jobs_root') and 's' in req.get('components','') and req['q']>0:
                    for prior in Path(req['campaign_jobs_root']).glob(req['case']+'_q*_n*/summary.json'):
                        old=read(prior)
                        if old.get('status')=='ok' and old['q']>0 and old['n']<req['n'] and (old['q'],old['n'])!=(req['q'],req['n']):
                            dynamic.append({'path':str(prior.parent/'plan.json'),'name':f'current_q{old["q"]}_n{old["n"]}', 'observed_source_makespan':old['makespan'],'source_job':str(prior.parent),'source_local_seconds':old.get('execution',{}).get('wall_seconds')})
                    dynamic.sort(key=lambda x:x['observed_source_makespan'])
                write(folder/'runtime.json',{'launched_epoch':time.time(),'dynamic_alternatives':dynamic[:3]})
                log=(folder/'worker.log').open('w',encoding='utf8')
                p=subprocess.Popen([sys.executable,'-m','research_a_orion_trident.solve',str((folder/'request.json').resolve())],
                                   cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                                   start_new_session=os.name!='nt',env={**os.environ,'PYTHONUTF8':'1','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'})
                active.append({'proc':p,'request':req,'log':log,'start':time.monotonic(),'peak_rss':0,
                               'workers_at_start':sample['target_workers']})
            for a in active[:]:
                p=a['proc'];req=a['request'];elapsed=time.monotonic()-a['start'];reason=None
                folder=Path(req['out'])
                if now>=deadline_epoch:reason='campaign_deadline'
                elif elapsed>=min(600,req.get('job_seconds',req.get('seconds',600))):reason='configuration_wall_limit'
                if reason:terminate(p)
                if p.poll() is not None:
                    a['log'].close();active.remove(a)
                    execution={'reason':reason or ('completed' if p.returncode==0 else 'worker_error'),
                        'returncode':p.returncode,'wall_seconds':time.monotonic()-a['start'],
                        'peak_rss_bytes':a['peak_rss'],'workers_at_start':a['workers_at_start'],
                        'wall_cap_seconds':min(600,req.get('job_seconds',req.get('seconds',600))),
                        'python':sys.version,'platform':platform.platform(),'host':platform.node(),
                        'late_cleanup_seconds':max(0,time.monotonic()-a['start']-min(600,req.get('job_seconds',req.get('seconds',600))))}
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
