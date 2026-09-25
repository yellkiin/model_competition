"""Continuous-clock warm memory repair. Published scores are trusted, not replayed.

Epoch and local candidates change only the two official plan fields. This is an
isolated adapter, not a replacement FIFO/public-solver controller. All raw new
responses, failures and real availability times are retained.
"""
from __future__ import annotations
import argparse,csv,gzip,json,os,platform,shutil,subprocess,sys,time,traceback,zipfile
from collections import deque
from pathlib import Path
from research_a_orion_anytime.engine import OfficialSession
from research_a_orion_anytime.core import plan_view,bounds
from .run import resources,rss,terminate
from .policy import RULE_VERSION,PHASE_ORDER,PHASE_EVALUATIONS,STOP_RATIO,better,search_state
from . import reuse_repair,local_repair
OFFICIAL=Path('题目/A题/通用神经网络处理器下的多核调度问题  附件')
PUBLISHED=Path('research_a_orion_anytime/team_results/day01/combined_final')


def read(p):
    p=Path(p)
    with (gzip.open(p,'rt',encoding='utf8') if p.suffix=='.gz' else p.open(encoding='utf-8-sig')) as f:return json.load(f)


def write(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.tmp')
    with (gzip.open(tmp,'wt',encoding='utf8',compresslevel=2) if p.suffix=='.gz' else tmp.open('w',encoding='utf8')) as f:
        json.dump(obj,f,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    tmp.replace(p)


def table(p,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with Path(p).open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def seed_meta(old):
    return dict(name='trusted_day01',makespan=int(old['makespan']),added_copy_bytes=int(old['added_copy_bytes']),
                spill_bytes=int(old['spill_added_copy_bytes']),partition_bytes=int(old['partition_added_copy_bytes']),
                ready_seconds=0.,plan_file='seed_plan.json',result_file='',cache_hit_rate=old.get('cache_hit_rate',''))


def worker(req):
    # Across processes transfer durations, never monotonic absolute deadlines.
    started=time.monotonic();offset=max(0.,time.time()-req['launch_wall']);clock=lambda:time.monotonic()-started+offset
    deadline=started+max(0.,req['seconds']-offset);out=Path(req['job']);old=req['old'];q,n=req['q'],req['n']
    seed=read(out/'seed_plan.json');raw={'makespan':int(old['makespan']),'data_movement_bytes':{k:int(old[k]) for k in
         ('added_copy_bytes','partition_added_copy_bytes','spill_added_copy_bytes')}}
    state=dict(case=req['case'],q=q,n=n,status='running',selected=seed_meta(old),attempts=[],diagnostics=[],events=[],evaluations=0,
               construction_seconds=0.,candidate_generation_seconds=0.,official_eval_seconds=0.,phase='construction',
               phase_started_seconds=0.,best_new=None,seed_solve_seconds=float(old['solve_seconds']))
    def checkpoint():state['elapsed_seconds']=clock();write(out/'progress.json',state)
    def event(phase,t=None):
        sel=state['selected'];state['events'].append(dict(phase=phase,elapsed_seconds=clock() if t is None else t,
          best_makespan=sel['makespan'],added_copy_bytes=sel['added_copy_bytes'],spill_bytes=sel['spill_bytes'],
          evaluations=state['evaluations'],selected_name=sel['name']))
    event('trusted_seed',0.);checkpoint()
    if q in (1,2) and n==1:
        state.update(status='complete',stop_reason='fixed_original_singlecore_reference',lower=float(old['lower']),phase='finished')
        event('fixed_reference');checkpoint();return
    try:
        session=OfficialSession(req['official'],req['graph'],req['config']);g,cfg=session.graph,session.cfg
        if len(seed['core_schedules'])!=n:raise ValueError('seed NPU core mismatch')
        plan_view(g,seed);state['construction_seconds']=clock();state['lower']=bounds(g,cfg,n,q)['global_lower']
        best_plan,best_raw=seed,raw;state['initial_diagnosis']=search_state(g,cfg,n,q,{'plan':seed,'official_result':raw})
        seen={reuse_repair.plan_key(seed)}
        for phase in PHASE_ORDER:
            if clock()>=req['seconds']:break
            if not search_state(g,cfg,n,q,{'plan':best_plan,'official_result':best_raw})['should_search']:
                state['stop_reason']='near_bound_stop';break
            proposal={'epochs':reuse_repair.propose,'local':local_repair.propose}[phase];feedback=[];phase_calls=0
            stream=proposal(g,n,cfg,q,incumbent={'plan':best_plan,'official_result':best_raw},feedback=feedback,deadline=deadline)
            while phase_calls<req['phase_caps'][phase] and state['evaluations']<req['max_evaluations'] and clock()<req['seconds']:
                state.update(phase='candidate_generation',phase_started_seconds=clock(),generator=phase);checkpoint();st=time.monotonic()
                try:c=next(stream)
                except StopIteration:
                    state['candidate_generation_seconds']+=time.monotonic()-st;break
                state['candidate_generation_seconds']+=time.monotonic()-st;key=reuse_repair.plan_key(c['plan'])
                if key in seen:
                    state['diagnostics'].append(dict(phase=phase,name=c['name'],status='duplicate_plan'));continue
                seen.add(key);i=len(state['attempts'])+1;pn=f'raw/e{i:04d}_plan.json';rn=f'raw/e{i:04d}_result.json.gz'
                row=dict(index=i,phase=phase,name=c['name'],family=c['family'],plan_file=pn,result_file=rn,
                    mechanism=c.get('mechanism',{}),proxy=c['proxy'],bounds=c['bounds'],status='prepared',started_seconds=clock(),parent_name=state['selected']['name'])
                write(out/pn,c['plan']);state['attempts'].append(row)
                if c['bounds']['candidate_lower']>state['selected']['makespan']:
                    row.update(status='certified_pruned',completed_seconds=clock());checkpoint();continue
                if clock()>=req['seconds']:
                    row.update(status='not_evaluated_deadline',completed_seconds=clock());break
                row['status']='running';state['evaluations']+=1;phase_calls+=1
                state.update(phase='official_evaluation',phase_started_seconds=clock());checkpoint();st=time.monotonic()
                try:
                    r=session.evaluate(c['plan'],q);wall=time.monotonic()-st;state['official_eval_seconds']+=wall
                    row.update(status=r['status'],eval_seconds=wall,evaluation_completed_seconds=clock())
                    state.update(phase='output',phase_started_seconds=clock());write(out/rn,r)
                    rr=r['official_result'];dm=rr['data_movement_bytes'];cache=rr.get('cache_stats',{})
                    row.update(makespan=rr['makespan'],added_copy_bytes=dm['added_copy_bytes'],spill_bytes=dm['spill_added_copy_bytes'],partition_bytes=dm['partition_added_copy_bytes'])
                    row.update(available_seconds=clock(),accepted=False)
                    if r['status']=='ok' and clock()<req['seconds']:
                        prev=state['best_new']
                        if prev is None or better(row['makespan'],row['added_copy_bytes'],prev['makespan'],prev['added_copy_bytes']):
                            state['best_new']={k:row[k] for k in ('name','makespan','added_copy_bytes','spill_bytes','plan_file','result_file')}
                        prev=state['selected']
                        if better(row['makespan'],row['added_copy_bytes'],prev['makespan'],prev['added_copy_bytes']):
                            state['selected']={k:row[k] for k in ('name','makespan','added_copy_bytes','spill_bytes','partition_bytes','plan_file','result_file')}
                            state['selected'].update(ready_seconds=clock(),cache_hit_rate=cache.get('hit_rate_bytes',cache.get('hit_rate','')))
                            best_plan,best_raw=c['plan'],rr;row['accepted']=True
                    elif r['status']=='ok':row['status']='completed_after_deadline_not_selected'
                    event(phase);row['completed_seconds']=clock();checkpoint()
                except Exception as exc:
                    state['official_eval_seconds']+=time.monotonic()-st
                    row.update(status='error',error=str(exc),traceback=traceback.format_exc(),completed_seconds=clock());checkpoint()
            state['diagnostics'].extend(dict(phase=phase,**x) for x in feedback);checkpoint()
            if state['evaluations']>=req['max_evaluations']:break
        state.update(status='complete',stop_reason=state.get('stop_reason','time_budget' if clock()>=req['seconds'] else
                     'evaluation_cap' if state['evaluations']>=req['max_evaluations'] else 'finite_candidate_space'),phase='finished')
        event('finished');checkpoint()
    except Exception as exc:
        state.update(status='worker_error',error=str(exc),traceback=traceback.format_exc(),phase='finished');checkpoint();raise


def pair_worker(req):
    out=Path(req['job']);session=OfficialSession(req['official'],req['graph'],req['config']);sel=read(out/'progress.json')['selected']
    r=session.evaluate(read(out/sel['plan_file']),3,{'cache_capacity_bytes':0});write(out/'no_l2_result.json.gz',r)
    write(out/'pair_selection.json',dict(plan_file=sel['plan_file'],selected_name=sel['name'],l2_makespan=sel['makespan'],status=r['status']))


def run_queue(requests,args,root,deadline,pair=False):
    pending=deque(requests);active=[];log=[];observed=256*1024**2
    while pending or active:
        now=time.monotonic();res=resources();memory_slots=int(max(0,res['available_memory']-512*1024**2)/max(512*1024**2,observed*1.5))
        capacity=min(max(1,res['cpu_quota']-1),3,max(0,memory_slots))
        if not active and capacity==0:capacity=1 if res['available_memory']>=max(256*1024**2,observed*1.2) else 0
        cap=capacity if args.workers=='auto' else min(int(args.workers),capacity)
        while pending and len(active)<cap and now<deadline:
            req=pending.popleft();out=Path(req['job']);out.mkdir(parents=True,exist_ok=True)
            budget=min(args.pair_seconds if pair else req['seconds'],deadline-time.monotonic())
            if budget<=0:pending.appendleft(req);break
            launch=time.monotonic();req={**req,'seconds':budget,'launch_wall':time.time()}
            rp=out/('pair_request.json' if pair else 'request.json');write(rp,req)
            err=(out/('pair_stderr.txt' if pair else 'stderr.txt')).open('w')
            cmd=[sys.executable,'-m','research_a_orion_track_memory.continuous_run','--pair-request' if pair else '--request',str(rp)]
            proc=subprocess.Popen(cmd,stdout=err,stderr=err,start_new_session=os.name!='nt',cwd=args.root)
            active.append(dict(proc=proc,req=req,started=launch,err=err,peak=0,workers=cap));log.append(dict(event='start',case=req['case'],q=req['q'],n=req['n'],workers=cap,resources=res,pair=pair))
        if pending and time.monotonic()>=deadline:
            while pending:
                req=pending.popleft();out=Path(req['job']);out.mkdir(parents=True,exist_ok=True)
                write(out/('pair_execution.json' if pair else 'execution.json'),dict(status='not_started_global_deadline',wall_seconds=0))
        for a in active[:]:
            a['peak']=max(a['peak'],rss(a['proc'].pid) or 0);observed=max(observed,a['peak']);code=a['proc'].poll();elapsed=time.monotonic()-a['started'];reason=None
            if code is None:
                if time.monotonic()>=deadline:reason='global_deadline'
                elif elapsed>=a['req']['seconds']:reason='hard_time_budget'
                if reason:terminate(a['proc']);code=a['proc'].poll()
            if code is not None:
                elapsed=time.monotonic()-a['started'];a['err'].close();active.remove(a);out=Path(a['req']['job'])
                info=dict(status=reason or ('completed' if code==0 else 'worker_error'),wall_seconds=elapsed,returncode=code,peak_rss_bytes=a['peak'],workers_at_start=a['workers'])
                write(out/('pair_execution.json' if pair else 'execution.json'),info);log.append(dict(event='finish',case=a['req']['case'],q=a['req']['q'],n=a['req']['n'],pair=pair,**info))
                print(a['req']['case'],a['req']['q'],a['req']['n'],'pair' if pair else 'solve',info['status'],round(elapsed,2),flush=True)
        write(root/('pair_worker_policy.json' if pair else 'worker_policy.json'),log);time.sleep(.04)


def export(root):
    manifest=read(root/'manifest.json');rows=[];trajectory=[];prefixes=[];attempts=[];diagnostics=[]
    for item in manifest['jobs']:
        out=root/item['relative_job'];req=read(out/'request.json');old=req['old']
        ex=read(out/'execution.json') if (out/'execution.json').exists() else dict(status='not_started',wall_seconds=0)
        s=read(out/'progress.json') if (out/'progress.json').exists() else dict(selected=seed_meta(old),events=[],attempts=[],diagnostics=[],evaluations=0)
        sel=s['selected'];old_ms=int(old['makespan']);elapsed=ex['wall_seconds'];seed_seconds=float(old['solve_seconds'])
        cache=sel.get('cache_hit_rate','');pair_cost=0.;no_l2=old.get('no_l2_makespan','') if not sel['result_file'] else ''
        pair_status='inherited_old_pair' if req['q']==3 and not sel['result_file'] else 'not_applicable'
        if sel['result_file'] and req['q']==3:
            pair_status='missing'
            if (out/'pair_execution.json').exists():pair_cost=read(out/'pair_execution.json')['wall_seconds']
            if (out/'no_l2_result.json.gz').exists() and (out/'pair_selection.json').exists():
                matched=read(out/'pair_selection.json');paired=read(out/'no_l2_result.json.gz')
                if paired['status']=='ok' and matched['plan_file']==sel['plan_file']:
                    no_l2=paired['official_result']['makespan'];pair_status='ok'
        row=dict(case=req['case'],q=req['q'],n=req['n'],method=RULE_VERSION,run_id=root.name,mode='warm_start',
                 status='new_official_selected' if sel['result_file'] else 'trusted_retained',search_status=ex['status'],
                 baseline=int(old['baseline']),old_makespan=old_ms,new_makespan=sel['makespan'],
                 old_speedup=int(old['baseline'])/old_ms,new_speedup=int(old['baseline'])/sel['makespan'],
                 old_added_copy_bytes=int(old['added_copy_bytes']),new_added_copy_bytes=sel['added_copy_bytes'],
                 old_spill_bytes=int(old['spill_added_copy_bytes']),new_spill_bytes=sel['spill_bytes'],
                 old_partition_bytes=int(old['partition_added_copy_bytes']),new_partition_bytes=sel['partition_bytes'],
                 seed_solve_seconds=seed_seconds,added_solve_seconds=elapsed,total_solve_seconds=seed_seconds+elapsed,
                 construction_seconds=s.get('construction_seconds',0),candidate_generation_seconds=s.get('candidate_generation_seconds',0),
                 official_eval_seconds=s.get('official_eval_seconds',0),evaluations=s.get('evaluations',0),
                 lower=s.get('lower',old['lower']),no_l2_makespan=no_l2,cache_hit_rate=cache,pair_status=pair_status,pair_seconds=pair_cost,
                 experiment_total_seconds=elapsed+pair_cost,selected_name=sel['name'],
                 plan_file=str((out/sel['plan_file']).relative_to(root)),result_file=str((out/sel['result_file']).relative_to(root)) if sel['result_file'] else '',
                 stop_reason=s.get('stop_reason',ex['status']),best_new_makespan=(s.get('best_new') or {}).get('makespan',''))
        row['other_or_interrupted_seconds']=max(0,elapsed-row['construction_seconds']-row['candidate_generation_seconds']-row['official_eval_seconds'])
        row['interrupted_phase']=s.get('phase','') if ex['status']!='completed' else ''
        row['interrupted_evaluations']=sum(a['status']=='running' for a in s['attempts'])
        row['new_cache_speedup']=float(no_l2)/sel['makespan'] if no_l2 else '';row['old_cache_speedup']=old.get('cache_speedup','');rows.append(row)
        ident={k:row[k] for k in ('case','q','n','method','run_id','mode')}
        evs=s.get('events',[]) or [dict(phase='trusted_seed',elapsed_seconds=0,best_makespan=old_ms,added_copy_bytes=int(old['added_copy_bytes']),evaluations=0)]
        for e in evs:
            trajectory.append({**ident,**e,'total_elapsed_seconds':seed_seconds+e['elapsed_seconds'],
              'baseline':int(old['baseline']),'speedup':int(old['baseline'])/e['best_makespan'],'has_valid_incumbent':True})
        for kind in ('additional','end_to_end'):
            for cutoff in (30,60,120,300):
                eligible=[e for e in evs if e['elapsed_seconds']+(seed_seconds if kind=='end_to_end' else 0)<=cutoff]
                best=eligible[-1] if eligible else None;stop_time=elapsed+(seed_seconds if kind=='end_to_end' else 0)
                prefixes.append({**ident,'clock':kind,'cutoff_seconds':cutoff,'best_makespan':best['best_makespan'] if best else '',
                  'speedup':int(old['baseline'])/best['best_makespan'] if best else '', 'added_copy_bytes':best['added_copy_bytes'] if best else '',
                  'has_valid_incumbent':bool(best),'after_stop':cutoff>stop_time,
                  'label':'stopped_carry_forward' if cutoff>stop_time else 'completed_prefix' if best else 'seed_not_yet_acquired'})
        for a in s['attempts']:
            attempts.append({**ident,**{k:v for k,v in a.items() if k not in ('proxy','bounds','mechanism','traceback')},
                             'mechanism':json.dumps(a.get('mechanism',{}),ensure_ascii=False)})
        for d in s.get('diagnostics',[]):diagnostics.append({**ident,**d})
    for fn,data in [('per_case.csv',rows),('trajectory.csv',trajectory),('budget_prefixes.csv',prefixes),('attempts.csv',attempts),('diagnostics.csv',diagnostics)]:table(root/fn,data)
    return rows


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request');p.add_argument('--pair-request');p.add_argument('--root',default='.')
    p.add_argument('--out');p.add_argument('--cases',nargs='+',type=int)
    p.add_argument('--questions',nargs='+',type=int,default=[1,2,3]);p.add_argument('--cores',nargs='+',type=int,default=[5])
    p.add_argument('--seconds',type=float,default=300);p.add_argument('--max-evaluations',type=int,default=40)
    p.add_argument('--workers',default='auto');p.add_argument('--total-seconds',type=float,default=1800)
    p.add_argument('--pair-seconds',type=float,default=180);p.add_argument('--pair-total-seconds',type=float,default=600)
    p.add_argument('--shards',type=int,default=1);p.add_argument('--shard-index',type=int,default=0)
    p.add_argument('--export-only',action='store_true');p.add_argument('--pairs-only',action='store_true');args=p.parse_args(argv)
    if args.request:worker(read(args.request));return
    if args.pair_request:pair_worker(read(args.pair_request));return
    if not args.out:p.error('--out required')
    args.root=str(Path(args.root).resolve());root=Path(args.out).resolve()
    if args.export_only:export(root);return
    if args.pairs_only:
        reqs=[read(x) for x in root.glob('jobs/*/request.json')]
        reqs=[r for r in reqs if r['q']==3 and (Path(r['job'])/'progress.json').exists() and
              read(Path(r['job'])/'progress.json')['selected']['result_file'] and not (Path(r['job'])/'pair_selection.json').exists()]
        run_queue(reqs,args,root,time.monotonic()+args.pair_total_seconds,pair=True);export(root);return
    if root.exists() and any(root.iterdir()):p.error('Use a new empty output directory')
    if not args.cases or args.shards<1 or not 0<=args.shard_index<args.shards:p.error('case list and valid shard index required')
    if any(q not in (1,2,3) for q in args.questions) or any(n not in range(1,6) for n in args.cores):p.error('q=1..3 and n=1..5 required')
    if min(args.seconds,args.total_seconds,args.pair_seconds,args.pair_total_seconds)<=0 or args.max_evaluations<1:p.error('positive budgets required')
    if args.workers!='auto' and (not args.workers.isdigit() or int(args.workers)<1):p.error('--workers auto or positive integer')
    root.mkdir(parents=True,exist_ok=True);repo=Path(args.root);base=repo/PUBLISHED;off=repo/OFFICIAL
    allrows=list(csv.DictReader((base/'per_case.csv').open(encoding='utf-8-sig')));lookup={(r['case'],int(r['q']),int(r['n'])):r for r in allrows}
    names=sorted(set(args.cases));selected_cases=names[args.shard_index::args.shards];requests=[]
    with zipfile.ZipFile(base/'selected_plans.zip') as z:
        for case in selected_cases:
            for n in args.cores:
                for q in args.questions:
                    label=f'case_{case:03d}';seedq=0 if n==1 and q in (1,2) else q;old=lookup[label,seedq,n]
                    job=root/'jobs'/f'{label}_q{q}_n{n}';job.mkdir(parents=True)
                    member=f'plans/q{seedq}/n{n}/{label}_multicore_res.json';(job/'seed_plan.json').write_bytes(z.read(member))
                    req=dict(case=label,q=q,n=n,job=str(job),graph=str(off/'data'/f'{label}.json'),official=str(off),config=str(off/'data/config.txt'),
                             old=old,seconds=args.seconds,max_evaluations=args.max_evaluations,phase_caps=PHASE_EVALUATIONS,
                             seed_source=f'{PUBLISHED}/selected_plans.zip!{member}')
                    if not Path(req['graph']).is_file():raise FileNotFoundError(req['graph'])
                    write(job/'request.json',req);requests.append(req)
    manifest=dict(version=RULE_VERSION,rule=dict(stop_ratio=STOP_RATIO,phase_order=PHASE_ORDER,phase_caps=PHASE_EVALUATIONS,
                  acceptance='official (makespan, added_copy_bytes)',case_specific_branches=False),mode='warm_start',
                  old_scores='trusted day01 combined_final; no baseline re-evaluation',python=sys.version,platform=platform.platform(),
                  resources=resources(),options=vars(args),complete_sorted_cases=names,selected_cases=selected_cases,
                  started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                  jobs=[dict(case=r['case'],q=r['q'],n=r['n'],relative_job=str(Path(r['job']).relative_to(root))) for r in requests])
    write(root/'manifest.json',manifest);frozen=root/'source';frozen.mkdir()
    for name in ('policy.py','continuous_run.py','reuse_repair.py','local_repair.py','plugin.py','run.py'):shutil.copy2(Path(__file__).parent/name,frozen/name)
    started=time.monotonic();run_queue(requests,args,root,started+args.total_seconds);solve_wall=time.monotonic()-started
    selected_pairs=[r for r in requests if r['q']==3 and (Path(r['job'])/'progress.json').exists() and read(Path(r['job'])/'progress.json')['selected']['result_file']]
    pstart=time.monotonic();run_queue(selected_pairs,args,root,pstart+args.pair_total_seconds,pair=True);rows=export(root)
    write(root/'campaign.json',dict(optimization_wall_seconds=solve_wall,pair_wall_seconds=time.monotonic()-pstart,
          total_wall_seconds=time.monotonic()-started,jobs=len(requests),rows=len(rows),new_selected=sum(bool(r['result_file']) for r in rows),
          old_evaluator_calls=0,reporting='warm continuous trajectory; not cold equal-budget comparison'))


if __name__=='__main__':main()
