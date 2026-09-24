"""Measured warm repair from published plans, with no old-score re-evaluation.

This adapter accepts trusted baseline metrics at explicit user request. All new
candidates pass unchanged OfficialSession; rejected attempts remain on disk.
"""
from __future__ import annotations
import argparse,csv,gzip,json,os,platform,sys,time,traceback,subprocess
from pathlib import Path
from collections import deque
from .run import resources, rss, terminate
from research_a_orion_anytime.engine import OfficialSession
from research_a_orion_anytime.core import bounds
from . import reuse_repair

FIELDS=['case','q','n','method','run_id','mode','status','baseline','old_makespan','new_makespan','old_added_copy_bytes','new_added_copy_bytes','old_spill_bytes','new_spill_bytes','seed_solve_seconds','added_solve_seconds','total_solve_seconds','construction_seconds','candidate_generation_seconds','official_eval_seconds','evaluations','lower','no_l2_makespan','cache_hit_rate','plan_file','result_file','selected_name','best_new_makespan','best_new_name']

def read(p):
    p=Path(p)
    with (gzip.open(p,'rt',encoding='utf8') if p.suffix=='.gz' else p.open(encoding='utf-8-sig')) as f:return json.load(f)

def write(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.tmp')
    with (gzip.open(tmp,'wt',encoding='utf8',compresslevel=1) if p.suffix=='.gz' else tmp.open('w',encoding='utf8')) as f:json.dump(v,f,ensure_ascii=False,allow_nan=False)
    tmp.replace(p)

def worker(req):
    offset=max(0.0,time.time()-req.get('launch_wall_seconds',time.time()))
    started=time.monotonic()-offset; deadline=started+req['seconds'];out=Path(req['job']);out.mkdir(parents=True,exist_ok=True)
    write(out/'worker_clock.json',{'process_startup_seconds':offset,'budget_seconds':req['seconds']})
    old=req['old'];seed=read(req['seed_plan']);write(out/'seed_plan.json',seed)
    old_result={'makespan':int(old['makespan']), 'data_movement_bytes':{k:int(old[k]) for k in ('added_copy_bytes','partition_added_copy_bytes','spill_added_copy_bytes')}}
    state={'case':req['case'],'q':req['q'],'n':req['n'],'status':'running','attempts':[],
           'baseline_source':'trusted selected parent; no old score re-evaluation',
           'selected':{'name':'trusted_day01','makespan':int(old['makespan']),'added_copy_bytes':int(old['added_copy_bytes']),'spill_bytes':int(old['spill_added_copy_bytes']),
                       'plan_file':'seed_plan.json','result_file':'','ready_seconds':0.0},
           'seed_solve_seconds':float(old['solve_seconds']),'best_new':None,'construction_seconds':0.0,'candidate_generation_seconds':0.0,'official_eval_seconds':0.0,'evaluations':0}
    write(out/'progress.json',state)
    if req['n']==1 and req['q'] in (1,2):
        state.update(status='ok',stop_reason='fixed_original_singlecore_reference',elapsed_seconds=time.monotonic()-started,lower=float(old['lower']))
        write(out/'progress.json',state);return
    session=OfficialSession(req['official'],req['graph'],req['config']);g,cfg=session.graph,session.cfg
    state['construction_seconds']=time.monotonic()-started
    state['lower']=bounds(g,cfg,req['n'],req['q'])['global_lower']
    diagnostics=[]
    from . import local_repair
    proposal = local_repair.propose if req.get('proposal')=='local' else reuse_repair.propose
    stream=proposal(g,req['n'],cfg,req['q'],incumbent={'plan':seed,'official_result':old_result},feedback=diagnostics,deadline=deadline)
    while time.monotonic()<deadline and state['evaluations']<req['max_evaluations']:
        st=time.monotonic()
        try:c=next(stream)
        except StopIteration:
            state['candidate_generation_seconds']+=time.monotonic()-st
            state['stop_reason']='candidate_space_exhausted';break
        state['candidate_generation_seconds']+=time.monotonic()-st
        idx=len(state['attempts'])+1;name=f'e{idx:04d}';pn=f'raw/{name}_plan.json';rn=f'raw/{name}_result.json.gz'
        row={'name':c['name'],'family':c['family'],'mechanism':c.get('mechanism'), 'proxy':c['proxy'],'bounds':c['bounds'],'plan_file':pn,'result_file':rn,'started_seconds':time.monotonic()-started,'status':'running'}
        write(out/pn,c['plan']);state['attempts'].append(row);write(out/'progress.json',state)
        if time.monotonic()>=deadline:row['status']='generation_deadline';break
        if c['bounds']['candidate_lower']>state['selected']['makespan']:
            row.update(status='certified_pruned',completed_seconds=time.monotonic()-started);write(out/'progress.json',state);continue
        evaluation_started=time.monotonic();state['evaluations']+=1
        try:
            r=session.evaluate(c['plan'],req['q'])
            state['official_eval_seconds']+=time.monotonic()-evaluation_started
            row.update(status=r['status'],eval_seconds=r['eval_seconds'],evaluation_completed_seconds=time.monotonic()-started)
            write(out/rn,r);raw=r['official_result'];traffic=raw['data_movement_bytes']
            row.update(makespan=raw['makespan'],added_copy_bytes=traffic['added_copy_bytes'],spill_bytes=traffic['spill_added_copy_bytes'],partition_bytes=traffic['partition_added_copy_bytes'])
            if r['status']=='ok' and time.monotonic()<deadline:
                if state['best_new'] is None or (row['makespan'],row['added_copy_bytes'])<(state['best_new']['makespan'],state['best_new']['added_copy_bytes']):state['best_new']={**row}
                previous=state['selected']
                if (row['makespan'],row['added_copy_bytes']) < (previous['makespan'],previous['added_copy_bytes']):
                    state['selected']={k:row[k] for k in ['name','makespan','added_copy_bytes','spill_bytes','plan_file','result_file']}
                    state['selected']['ready_seconds']=time.monotonic()-started
            row['completed_seconds']=time.monotonic()-started
        except Exception as exc:
            state['official_eval_seconds']+=time.monotonic()-evaluation_started
            row.update(status='error',error=str(exc),traceback=traceback.format_exc(),completed_seconds=time.monotonic()-started)
        state['elapsed_seconds']=time.monotonic()-started;state['diagnostics']=diagnostics;write(out/'progress.json',state)
    state.update(status='ok',elapsed_seconds=time.monotonic()-started,stop_reason=state.get('stop_reason','budget_or_call_limit'),diagnostics=diagnostics)
    write(out/'progress.json',state)


def run_queue(jobs, worker_policy, global_deadline, root):
    pending=deque(jobs);active=[];log=[];peak=256*1024**2
    while pending or active:
        now=time.monotonic();res=resources()
        capacity=max(1,min(4,res['cpu_quota'],int(max(0,res['available_memory']-512*1024**2)/max(512*1024**2,peak*1.5))))
        cap=capacity if worker_policy=='auto' else min(int(worker_policy),capacity)
        while pending and len(active)<cap and now<global_deadline:
            req=pending.popleft();out=Path(req['job']);out.mkdir(parents=True,exist_ok=True)
            req['launch_wall_seconds']=time.time();write(out/'request.json',req)
            err=(out/'stderr.txt').open('w')
            proc=subprocess.Popen([sys.executable,'-m','research_a_orion_track_memory.trusted_run','--request',str(out/'request.json')],stdout=err,stderr=err,start_new_session=os.name!='nt')
            active.append(dict(proc=proc,req=req,start=time.monotonic(),err=err,peak=0,workers=cap))
            log.append(dict(event='start',job=str(out),workers=cap,resources=res))
        if pending and now>=global_deadline:
            while pending:
                req=pending.popleft();write(Path(req['job'])/'request.json',req)
                write(Path(req['job'])/'execution.json',{'status':'not_started_global_deadline','wall_seconds':0})
        for a in active[:]:
            a['peak']=max(a['peak'],rss(a['proc'].pid) or 0);peak=max(peak,a['peak'])
            elapsed=time.monotonic()-a['start'];reason=None
            if time.monotonic()>=global_deadline:reason='global_deadline'
            elif elapsed>=a['req']['seconds']:reason='hard_time_budget'
            if reason:terminate(a['proc'])
            if a['proc'].poll() is not None:
                a['err'].close();active.remove(a);out=Path(a['req']['job'])
                info=dict(status=reason or ('completed' if a['proc'].returncode==0 else 'worker_error'),returncode=a['proc'].returncode,wall_seconds=elapsed,peak_rss_bytes=a['peak'],workers_at_start=a['workers'])
                write(out/'execution.json',info);log.append(dict(event='finish',job=str(out),**info))
                print(a['req']['case'],a['req']['q'],a['req']['n'],info['status'],flush=True)
        write(root/'worker_policy.json',log)
        time.sleep(.05)


def export(root):
    rows=[];events=[]
    for path in root.glob('jobs/*/request.json'):
        req=read(path);out=path.parent
        if not (out/'progress.json').exists():continue
        s=read(out/'progress.json');sel=s['selected'];old=req['old'];elapsed=read(out/'execution.json')['wall_seconds'] if (out/'execution.json').exists() else s.get('elapsed_seconds',0)
        r=dict(case=req['case'],q=req['q'],n=req['n'],method=read(root/'manifest.json')['version'],run_id=root.name,mode='warm_start',status=s['status'],baseline=int(old['baseline']),old_makespan=int(old['makespan']),new_makespan=sel['makespan'],old_added_copy_bytes=int(old['added_copy_bytes']),new_added_copy_bytes=sel['added_copy_bytes'],old_spill_bytes=int(old['spill_added_copy_bytes']),new_spill_bytes=sel['spill_bytes'],seed_solve_seconds=s['seed_solve_seconds'],added_solve_seconds=elapsed,total_solve_seconds=elapsed+s['seed_solve_seconds'],construction_seconds=s['construction_seconds'],candidate_generation_seconds=s['candidate_generation_seconds'],official_eval_seconds=s['official_eval_seconds'],evaluations=s['evaluations'],lower=s.get('lower'),no_l2_makespan='',cache_hit_rate='',plan_file=str((out/sel['plan_file']).relative_to(root)),result_file=str((out/sel['result_file']).relative_to(root)) if sel['result_file'] else '',selected_name=sel['name'],best_new_makespan=s['best_new']['makespan'] if s['best_new'] else '',best_new_name=s['best_new']['name'] if s['best_new'] else '')
        if not sel['result_file']:r.update(no_l2_makespan=old.get('no_l2_makespan',''),cache_hit_rate=old.get('cache_hit_rate',''))
        rows.append(r)
        pair_path=out/'no_l2_result.json.gz'
        if pair_path.exists():
            paired=read(pair_path)
            if paired.get('status')=='ok':r['no_l2_makespan']=paired['official_result']['makespan']
        inherited_path=out/'inherited_pair.json'
        if not pair_path.exists() and inherited_path.exists():r['no_l2_makespan']=read(inherited_path).get('no_l2_makespan','')
        if sel['result_file']:
            selected_raw=read(out/sel['result_file'])['official_result']
            cache=selected_raw.get('cache_stats',{})
            r['cache_hit_rate']=cache.get('hit_rate_bytes',cache.get('hit_rate',''))
        best=int(old['makespan']);bcopy=int(old['added_copy_bytes'])
        events.append(dict(case=req['case'],q=req['q'],n=req['n'],method=read(root/'manifest.json')['version'],run_id=root.name,mode='warm_start',phase='trusted_seed',elapsed_seconds=0,total_elapsed_seconds=s['seed_solve_seconds'],best_makespan=best,baseline=int(old['baseline']),speedup=int(old['baseline'])/best,added_copy_bytes=bcopy,evaluations=0,has_valid_incumbent=True))
        evaluation_count=0
        for i,a in enumerate(s['attempts']):
            if a['status'] in ('ok','error','audit_failed','running'):evaluation_count+=1
            if a['status']!='ok' or 'completed_seconds' not in a or a['completed_seconds']>req['seconds']:continue
            if (a['makespan'],a['added_copy_bytes']) < (best,bcopy):best,bcopy=a['makespan'],a['added_copy_bytes']
            t=a['completed_seconds']
            events.append(dict(case=req['case'],q=req['q'],n=req['n'],method=read(root/'manifest.json')['version'],run_id=root.name,mode='warm_start',phase='new_official_evaluation',elapsed_seconds=t,total_elapsed_seconds=t+s['seed_solve_seconds'],best_makespan=best,baseline=int(old['baseline']),speedup=int(old['baseline'])/best,added_copy_bytes=bcopy,evaluations=evaluation_count,has_valid_incumbent=True))
    for name,data,fields in [('per_case.csv',rows,FIELDS),('trajectory.csv',events,list(events[0]) if events else [])]:
        with (root/name).open('w',newline='',encoding='utf8') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)


def main():
    p=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--root',default='.');p.add_argument('--out');p.add_argument('--cases',nargs='+',type=int);p.add_argument('--questions',nargs='+',type=int,default=[1,2]);p.add_argument('--cores',nargs='+',type=int,default=[5]);p.add_argument('--seconds',type=float,default=120);p.add_argument('--max-evaluations',type=int,default=16);p.add_argument('--workers',default='auto');p.add_argument('--total-seconds',type=float,default=1200);p.add_argument('--shards',type=int,default=1);p.add_argument('--shard-index',type=int,default=0);p.add_argument('--export',action='store_true');p.add_argument('--proposal',choices=['epochs','local'],default='epochs');p.add_argument('--seed-run');a=p.parse_args()
    if a.request:worker(read(a.request));return
    root=Path(a.root).resolve();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    if not a.export and (out/'manifest.json').exists():p.error('Output run already exists; use a fresh directory, not overwrite/resume')
    if a.export:export(out);return
    off=root/'题目/A题/通用神经网络处理器下的多核调度问题  附件';base=root/'research_a_orion_anytime/team_results/day01/combined_final'
    allrows=list(csv.DictReader((base/'per_case.csv').open(encoding='utf-8-sig')))
    if a.shards<1 or not 0<=a.shard_index<a.shards:p.error('invalid shard parameters')
    if a.seconds<=0 or a.max_evaluations<1:p.error('positive budget required')
    if not a.cases:p.error('--cases required')
    if any(q not in (1,2,3) for q in a.questions) or any(n not in range(1,6) for n in a.cores):p.error('questions 1..3 and NPU cores 1..5 required')
    cases=sorted(set(a.cases))[a.shard_index::a.shards]
    jobs=[]
    previous=Path(a.seed_run).resolve() if a.seed_run else None
    for case in cases:
        for q in a.questions:
            for n in a.cores:
                seedq=0 if n==1 and q in (1,2) else q
                old=next(r for r in allrows if r['case']==f'case_{case:03}' and int(r['q'])==seedq and int(r['n'])==n)
                seed_path=root/f'day01_plans/plans/q{seedq}/n{n}/case_{case:03}_multicore_res.json'
                if not seed_path.exists():
                    import zipfile
                    archive=base/'selected_plans.zip'
                    with zipfile.ZipFile(archive) as z:
                        member=f'plans/q{seedq}/n{n}/case_{case:03}_multicore_res.json'
                        raw=z.read(member)
                    seed_path.parent.mkdir(parents=True,exist_ok=True);seed_path.write_bytes(raw)
                if previous:
                    pd=previous/f'jobs/case_{case:03}_q{q}_n{n}';pr=read(pd/'request.json');ps=read(pd/'progress.json');pm=ps['selected']
                    if pr['case']!=f'case_{case:03}' or pr['q']!=q or pr['n']!=n:raise ValueError('seed run identity mismatch')
                    from research_a_orion_anytime.core import Config
                    if Config.read(pr['config'])!=Config.read(off/'data/config.txt'):raise ValueError('seed config mismatch')
                    seed_path=pd/pm['plan_file'];old=dict(old)
                    for key in ('makespan','added_copy_bytes'):old[key]=str(pm[key])
                    old['spill_added_copy_bytes']=str(pm['spill_bytes']);old['partition_added_copy_bytes']=str(pm['added_copy_bytes']-pm['spill_bytes'])
                    old['solve_seconds']=str(ps['seed_solve_seconds']+read(pd/'execution.json')['wall_seconds'])
                    old['no_l2_makespan']='';old['cache_hit_rate']=''
                    pair=pd/'no_l2_result.json.gz'
                    if pair.exists():old['no_l2_makespan']=str(read(pair)['official_result']['makespan'])
                    elif not pm['result_file']:old['no_l2_makespan']=pr['old'].get('no_l2_makespan','')
                    if pm['result_file']:old['cache_hit_rate']=str(read(pd/pm['result_file'])['official_result'].get('cache_stats',{}).get('hit_rate',''))
                    else:old['cache_hit_rate']=pr['old'].get('cache_hit_rate','')
                jobs.append(dict(proposal=a.proposal,parent_run=str(previous) if previous else '',case=f'case_{case:03}',q=q,n=n,old=old,seed_plan=str(seed_path),graph=str(off/f'data/case_{case:03}.json'),official=str(off),config=str(off/'data/config.txt'),job=str(out/f'jobs/case_{case:03}_q{q}_n{n}'),seconds=a.seconds,max_evaluations=a.max_evaluations))
    workers=a.workers
    write(out/'manifest.json',dict(proposal=a.proposal,seed_run=str(previous) if previous else '',version=reuse_repair.VERSION if a.proposal=='epochs' else 'memory-local-2.3',python=sys.version,platform=platform.platform(),workers=workers,cases=cases,q=a.questions,n=a.cores,seconds=a.seconds,max_evaluations=a.max_evaluations,total_seconds=a.total_seconds,baseline_policy='trusted published metrics, zero baseline evaluations'))
    deadline=time.monotonic()+a.total_seconds
    run_queue(jobs,workers,deadline,out)
    export(out)

if __name__=='__main__':main()
