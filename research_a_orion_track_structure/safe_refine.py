"""Monotone warm refinement, with unchanged official evaluation and honest costs.

Run from a repository checkout. Inputs are an explicit verified-plan manifest;
this entry never calls a history oracle or silently turns warm runs into cold ones.
"""
from __future__ import annotations
import argparse, csv, gzip, json, math, os, platform, shutil, signal, subprocess, sys, time, traceback
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from research_a_orion_anytime.engine import OfficialSession
from research_a_orion_anytime.worker import atomic_json
from .safe_refine_plugin import propose, signature

ROOT=Path(__file__).resolve().parents[1]

def read(p):
    p=Path(p)
    with (gzip.open(p,'rt',encoding='utf-8-sig') if p.suffix=='.gz' else p.open(encoding='utf-8-sig')) as f:return json.load(f)

def gzwrite(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp')
    with gzip.open(tmp,'wt',encoding='utf8',compresslevel=3) as f:json.dump(x,f,separators=(',',':'),ensure_ascii=False,allow_nan=False)
    tmp.replace(p)

def writecsv(path,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

def score(response):
    raw=response['official_result'];return raw['makespan'],raw['data_movement_bytes']['added_copy_bytes']

def resolve(p,root=ROOT):
    p=Path(p);return p if p.is_absolute() else root/p

def safe_worker(req):
    out=Path(req['job']);out.mkdir(parents=True,exist_ok=True)
    start=time.monotonic();deadline=start+req['seconds']
    seed=Path(req['seed_job']);sp=read(seed/'progress.json');inc=sp['incumbent'];plan=read(seed/inc['plan_file']);r=read(seed/inc['result_file'])
    # This seed has already been re-evaluated in this suite at target n/q.
    if r.get('status')!='ok' or not r['audit']['ok'] or len(plan['core_schedules'])!=req['n']:raise ValueError('unverified seed')
    atomic_json(out/'seed_plan.json',plan);gzwrite(out/'seed_response.json.gz',r)
    state=dict(case=req['case'],q=req['q'],n=req['n'],status='running',identity=req['identity'],attempts=[],evaluations=0,
        candidate_generation_seconds=0.,official_eval_seconds=0.,audit_seconds=0.,output_seconds=0.,
        actual_route='safe_structure_refine_v1',seed_makespan=score(r)[0],
        incumbent=dict(name='verified_seed',makespan=score(r)[0],added_copy_bytes=score(r)[1],plan_file='seed_plan.json',result_file='seed_response.json.gz',elapsed_seconds=0.,evaluation=0,from_seed=True,certificate=r['audit']['certificate']))
    def save():
        state['elapsed_seconds']=time.monotonic()-start;atomic_json(out/'progress.json',state)
    save();tick=time.monotonic();session=OfficialSession(req['official'],req['graph'],req['config']);g,cfg=session.graph,session.cfg
    state['construction_seconds']=time.monotonic()-tick
    context={'plan':plan,'official_result':r['official_result'],'effective_core_seeds':[]};best=score(r);seen={signature(plan)}
    for seed_alt in req.get('alternatives',[]):
        pa=read(seed_alt['plan_file'])
        if len(pa['core_schedules'])<=req['n'] and signature(pa)!=signature(plan):
            context['effective_core_seeds'].append({'plan':pa,'source':seed_alt})
    stream=iter(propose(g,req['n'],cfg,req['q'],context,state['attempts'],deadline));stall=0
    while state['evaluations']<req['max_evaluations'] and time.monotonic()<deadline:
        tick=time.monotonic()
        try:c=next(stream)
        except StopIteration:state['stopped']='finite_structural_pool_exhausted';break
        except Exception as exc:
            state['attempts'].append(dict(status='generation_error',error=str(exc),traceback=traceback.format_exc()));state['stopped']='generation_error';break
        dt=time.monotonic()-tick;state['candidate_generation_seconds']+=dt
        if time.monotonic()>=deadline:state['stopped']='deadline_after_generation';break
        key=signature(c['plan'])
        if key in seen:
            state['attempts'].append(dict(name=c['name'],family=c['family'],status='duplicate',generation_seconds=dt));continue
        seen.add(key)
        if c['bounds']['candidate_lower']>best[0]:
            state['attempts'].append(dict(name=c['name'],family=c['family'],status='certified_pruned',candidate_lower=c['bounds']['candidate_lower'],generation_seconds=dt));save();continue
        i=state['evaluations']+1;state['evaluations']=i
        pn=f'attempts/e{i:04d}_plan.json';rn=f'attempts/e{i:04d}_response.json.gz'
        a=dict(index=i,name=c['name'],family=c['family'],status='running',plan_file=pn,result_file=rn,started_seconds=time.monotonic()-start,generation_seconds=dt,proxy=c['proxy']['score'])
        state['attempts'].append(a);tick=time.monotonic();atomic_json(out/pn,c['plan']);state['output_seconds']+=time.monotonic()-tick;save();tick=time.monotonic()
        try:
            result=session.evaluate(c['plan'],req['q']);wall=time.monotonic()-tick
            a.update(status=result['status'],eval_seconds=result['eval_seconds'],audit_seconds=max(0.,wall-result['eval_seconds']))
            state['official_eval_seconds']+=a['eval_seconds'];state['audit_seconds']+=a['audit_seconds']
            ot=time.monotonic();gzwrite(out/rn,result);state['output_seconds']+=time.monotonic()-ot
            if result['status']=='ok':
                ss=score(result);a.update(makespan=ss[0],added_copy_bytes=ss[1],improved=ss<best)
                if ss<best:
                    # Atomic incumbent changes only after complete legal official response.
                    best=ss;stall=0;context['plan']=c['plan'];context['official_result']=result['official_result']
                    state['incumbent']=dict(name=c['name'],makespan=ss[0],added_copy_bytes=ss[1],plan_file=pn,result_file=rn,elapsed_seconds=time.monotonic()-start,evaluation=i,certificate=result['audit']['certificate'],from_seed=False)
                else:stall+=1
            else:a['audit_errors']=result['audit']['errors'];stall+=1
        except Exception as exc:
            a.update(status='error',error=str(exc),traceback=traceback.format_exc());stall+=1
        a['completed_seconds']=time.monotonic()-start;a['best_makespan']=best[0];save()
        if stall>=req.get('stall_limit',60):state['stopped']='nonimproving_evaluation_limit';break
    state['status']='ok';state.setdefault('stopped','evaluation_cap' if state['evaluations']>=req['max_evaluations'] else 'time_budget');save()


def fixed_worker(req):
    out=Path(req['job']);out.mkdir(parents=True,exist_ok=True);start=time.monotonic()
    plan=read(req['plan_file']);source_n=len(plan['core_schedules'])
    if source_n>req['n']:raise ValueError('cannot trim an occupied plan')
    plan['core_schedules'] += [[] for _ in range(req['n']-source_n)]
    session=OfficialSession(req['official'],req['graph'],req['config']);t=time.monotonic();r=session.evaluate(plan,req['q']);wall=time.monotonic()-t
    atomic_json(out/'plan.json',plan);gzwrite(out/'response.json.gz',r)
    inc=dict(name='fixed_verified',makespan=score(r)[0],added_copy_bytes=score(r)[1],plan_file='plan.json',result_file='response.json.gz',elapsed_seconds=0.,evaluation=0,certificate=r['audit']['certificate']) if r['status']=='ok' else None
    atomic_json(out/'progress.json',dict(status=r['status'],incumbent=inc,attempts=[],q=req['q'],n=req['n'],case=req['case']))
    atomic_json(out/'summary.json',dict(status=r['status'],makespan=score(r)[0],eval_seconds=r['eval_seconds'],audit_seconds=wall-r['eval_seconds'],total_seconds=time.monotonic()-start,source_n=source_n,target_n=req['n']))


def terminate(p):
    if p.poll() is not None:return
    if os.name=='nt':subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True)
    else:
        try:os.killpg(p.pid,signal.SIGTERM)
        except ProcessLookupError:return
    try:p.wait(timeout=3)
    except subprocess.TimeoutExpired:
        if os.name=='nt':p.kill()
        else:
            try:os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        p.wait()


def spawn(req,limit):
    job=Path(req['job']);job.mkdir(parents=True,exist_ok=False);atomic_json(job/'request.json',req)
    began=time.monotonic();observations=[];events=[];seen_inc=set();seen_events=set();timed=False
    # Initial verified seed is genuinely available to both warm arms at t=0.
    if req.get('seed_job'):
        sp=read(Path(req['seed_job'])/'progress.json');s=sp['incumbent'];observations.append(dict(elapsed_seconds=0.,makespan=s['makespan'],added_copy_bytes=s['added_copy_bytes'],name='verified_input_seed',plan_file=str(Path(req['seed_job'])/s['plan_file']),result_file=str(Path(req['seed_job'])/s['result_file'])))
    def poll():
        path=job/'progress.json'
        if not path.exists():return
        try:s=read(path)
        except (OSError,json.JSONDecodeError):return
        inc=s.get('incumbent');elapsed=time.monotonic()-began
        if inc and (inc['plan_file'],inc['makespan'],inc.get('added_copy_bytes')) not in seen_inc:
            pp=job/inc['plan_file'];rr=job/inc['result_file']
            if pp.exists() and rr.exists():
                seen_inc.add((inc['plan_file'],inc['makespan'],inc.get('added_copy_bytes')))
                observations.append(dict(elapsed_seconds=elapsed,makespan=inc['makespan'],added_copy_bytes=inc.get('added_copy_bytes',0),name=inc.get('name'),plan_file=str(pp),result_file=str(rr)))
        for a in s.get('attempts',[]):
            k=a.get('index')
            if k is not None and a.get('status') not in ('running',None) and k not in seen_events:
                seen_events.add(k);events.append(dict(elapsed_seconds=elapsed,index=k,status=a['status'],name=a.get('name'),makespan=a.get('makespan')))
    with (job/'stdout.log').open('wb') as f:
        kw=dict(cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
        if os.name!='nt':kw['start_new_session']=True
        p=subprocess.Popen([sys.executable,'-m','research_a_orion_track_structure.safe_refine','--worker',str(job/'request.json')],**kw)
        while p.poll() is None:
            poll()
            if time.monotonic()-began>=limit:
                timed=True;terminate(p);break
            time.sleep(.04)
        poll()
    elapsed=time.monotonic()-began
    s=read(job/'progress.json') if (job/'progress.json').exists() else {}
    eligible=[o for o in observations if o['elapsed_seconds']<=limit]
    best=min(eligible,key=lambda o:(o['makespan'],o['added_copy_bytes'])) if eligible else None
    row={**req,'status':('ok_with_timeout' if timed else 'ok') if best else ('timeout' if timed else s.get('status','error')),
         'timed_out':timed,'solve_seconds':elapsed,'observations':observations,'evaluation_events':events,
         'stopped':'parent_deadline' if timed else s.get('stopped'),'completed_evaluations':len(events),
         'attempt_status_counts':dict(Counter(a.get('status') for a in s.get('attempts',[]))),
         'construction_seconds':s.get('construction_seconds'),'candidate_generation_seconds':s.get('candidate_generation_seconds',s.get('expanded_construction_seconds')),
         'official_eval_seconds':sum(a.get('eval_seconds',0) for a in s.get('attempts',[])),
         'audit_seconds':s.get('audit_seconds'),'output_seconds':s.get('output_seconds')}
    if best:row.update(makespan=best['makespan'],added_copy_bytes=best['added_copy_bytes'],plan_file=best['plan_file'],result_file=best['result_file'],winning_name=best['name'])
    # Fixed jobs have no warm observations until their result is completely saved.
    if req['method']=='fixed' and (job/'summary.json').exists():row.update(read(job/'summary.json'))
    atomic_json(job/'controller_summary.json',row)
    print(req['case'],req['q'],req['n'],req['method'],row['status'],row.get('makespan'),round(elapsed,2),flush=True)
    return row


def worker_count(value):
    try:
        import psutil
        memory=psutil.virtual_memory().available
    except ImportError:memory=2*1024**3
    cpu=len(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else os.cpu_count() or 1
    try:
        quota,period=Path('/sys/fs/cgroup/cpu.max').read_text().split()
        if quota!='max':cpu=min(cpu,max(1,int(quota)//int(period)))
    except (OSError,ValueError):pass
    cap=max(1,min(3,cpu//2 or 1,int(memory//(2*1024**3)) or 1))
    return cap if value=='auto' else max(1,min(int(value),cap))


def export(out,records,manifest):
    rows=[];traj=[]
    old={(r['case'],r['q'],r['n']):r for r in records if r['method']=='old'}
    for r in records:
        o=old.get((r['case'],r['q'],r['n']),{});pair=r.get('no_l2',{});seedcost=r.get('seed_solve_seconds');validation=r.get('seed_validation_seconds',0.)
        row={k:v for k,v in r.items() if not isinstance(v,(dict,list))}
        row.update(run_id=out.name,mode='warm_start',requested_method=r['method'],actual_route='legacy' if r['method']=='old' else 'safe_structure_refine_v1',
            old_makespan=o.get('makespan'),new_makespan=r.get('makespan'),seed_makespan=r.get('seed_makespan'),
            seed_solve_seconds=seedcost,added_solve_seconds=r['solve_seconds'],total_solve_seconds=None if seedcost is None else seedcost+validation+r['solve_seconds'],
            no_l2_makespan=pair.get('makespan'),no_l2_replay_seconds=pair.get('solve_seconds'),pair_status=pair.get('status','not_applicable' if r['q']!=3 else 'missing'),
            evaluations=r.get('completed_evaluations'),protected_seed_no_regression=r.get('makespan') is not None and r['makespan']<=r['seed_makespan'])
        if r.get('result_file'):
            rr=read(r['result_file']);raw=rr['official_result'];row.update(lower=rr['audit']['certificate']['global_lower'],cache_hit_rate=raw.get('cache_stats',{}).get('hit_rate'),spill_added_copy_bytes=raw['data_movement_bytes'].get('spill_added_copy_bytes'))
        rows.append(row)
        for t in [30,60,120,300]+([600] if manifest['seconds']>300 else []):
            obs=[o for o in r.get('observations',[]) if o['elapsed_seconds']<=min(t,r['seconds'])]
            b=min(obs,key=lambda x:(x['makespan'],x['added_copy_bytes'])) if obs else None
            phase='not_started' if r['status']=='not_started' else ('stopped_carry_forward' if t>r['solve_seconds'] else 'running_prefix')
            traj.append(dict(case=r['case'],q=r['q'],n=r['n'],method=r['method'],run_id=out.name,mode='warm_start',phase=phase,budget_seconds=t,elapsed_seconds=min(t,r['solve_seconds']),total_elapsed_seconds=None if seedcost is None else seedcost+validation+min(t,r['solve_seconds']),best_makespan=b['makespan'] if b else None,baseline=r.get('baseline'),speedup=r['baseline']/b['makespan'] if b else None,evaluations=sum(e['elapsed_seconds']<=t for e in r.get('evaluation_events',[])),has_valid_incumbent=bool(b)))
    writecsv(out/'per_case.csv',rows);writecsv(out/'trajectory.csv',traj);atomic_json(out/'all_jobs.json',records)
    pairs=[r['no_l2'] for r in records if r.get('no_l2')]
    atomic_json(out/'summary.json',dict(jobs=len(records),status_counts=dict(Counter(r['status'] for r in records)),no_regression=sum(r.get('protected_seed_no_regression',False) for r in rows),pairs_requested=len(pairs),pairs_started=sum(p.get('status')!='not_started' for p in pairs),pairs_completed=sum(p.get('makespan') is not None for p in pairs),formal_100_complete=False))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--worker',type=Path)
    p.add_argument('--cases');p.add_argument('--questions',default='1,2,3');p.add_argument('--cores',default='5');p.add_argument('--methods',default='old,safe');p.add_argument('--seconds',type=float,default=300.);p.add_argument('--wall-seconds',type=float,default=1800.);p.add_argument('--verify-seconds',type=float,default=120.);p.add_argument('--pair-seconds',type=float,default=120.);p.add_argument('--max-evaluations',type=int,default=64);p.add_argument('--stall-limit',type=int,default=60);p.add_argument('--workers',default='auto');p.add_argument('--shards',type=int,default=1);p.add_argument('--shard-index',type=int,default=0);p.add_argument('--seed-manifest',type=Path);p.add_argument('--out',type=Path);p.add_argument('--official',type=Path,default=ROOT/'题目/A题/通用神经网络处理器下的多核调度问题  附件');p.add_argument('--data-root',type=Path);p.add_argument('--config',type=Path)
    a=p.parse_args()
    if a.worker:
        req=read(a.worker)
        try:
            if req['method']=='fixed':fixed_worker(req)
            elif req['method']=='old':
                from research_a_orion_anytime.solver import solve
                solve(req)
            else:safe_worker(req)
        except Exception as exc:
            atomic_json(Path(req['job'])/'worker_error.json',dict(error=str(exc),traceback=traceback.format_exc()));raise
        return
    if not a.cases or not a.seed_manifest or not a.out:p.error('cases, seed-manifest and out are required')
    if not 0<=a.shard_index<a.shards or min(a.seconds,a.wall_seconds,a.verify_seconds,a.pair_seconds)<=0:p.error('invalid budget/shards')
    cases=sorted({f'{int(c):03d}' for c in a.cases.split(',')})[a.shard_index::a.shards];qs=[int(q) for q in a.questions.split(',')];ns=[int(n) for n in a.cores.split(',')];methods=a.methods.split(',')
    if set(qs)-{1,2,3} or set(methods)-{'old','safe'} or any(n not in range(1,6) for n in ns):p.error('invalid questions/cores/methods')
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);seeds=read(a.seed_manifest);seedmap={(r['case'],r['q'],r['n']):r for r in seeds}
    data=(a.data_root or a.official/'data').resolve();cfg=(a.config or data/'config.txt').resolve()
    for case in cases:
        if not (data/f'case_{case}.json').is_file():p.error('missing graph '+case)
    if not cfg.is_file():p.error('missing config')
    cap=worker_count(a.workers);start=time.monotonic();deadline=start+a.wall_seconds
    manifest=dict(run_id=out.name,utc=datetime.now(timezone.utc).isoformat(),platform=platform.platform(),python=sys.version,executable=sys.executable,workers_requested=a.workers,workers_actual=cap,worker_policy='start-selected fixed comparison block; not runtime autoscaling',cases=cases,questions=qs,cores=ns,methods=methods,seconds=a.seconds,wall_seconds=a.wall_seconds,max_evaluations=a.max_evaluations,argv=sys.argv,mode='warm_start',source_main='996d7d11f10ac44ce65fcd361d5a057a5795c0f9',source_frozen_official='e04b2bf5df946f48714c66ba84d61bd4b90ece00',seed_manifest=str(a.seed_manifest.resolve()),historical_seed_selection_cost='not fully known; never imputed as zero')
    atomic_json(out/'manifest.json',manifest)
    atomic_json(out/'seed_manifest_snapshot.json',seeds)
    for module in ['safe_refine.py','safe_refine_plugin.py']:
        (out/'source').mkdir(exist_ok=True);shutil.copy(Path(__file__).parent/module,out/'source'/module)
    baselines={r['case'].removeprefix('case_'):int(r['baseline']) for r in csv.DictReader((ROOT/'research_a_orion_anytime/team_results/day01/combined_final/per_case.csv').open(encoding='utf-8-sig'))}
    records=[];errors=[]
    def block(b):
        case,q,n=b;seed=seedmap[case,q,n];common=dict(case=case,q=q,n=n,official=str(a.official.resolve()),graph=str(data/f'case_{case}.json'),config=str(cfg),identity=dict(run=out.name,case=case,q=q,n=n))
        basejob=out/'seeds'/f'{case}_q{q}_n{n}';answers=[]
        if time.monotonic()+a.verify_seconds+a.seconds+(a.pair_seconds if q==3 else 0)>deadline:return []
        prep=spawn({**common,'method':'fixed','job':str(basejob),'plan_file':str(resolve(seed['plan_file'])),'seconds':a.verify_seconds},a.verify_seconds)
        if prep.get('status')!='ok' or not (basejob/'progress.json').exists():
            atomic_json(out/f'seed_error_{case}_q{q}_n{n}.json',prep);return []
        # A provenance mismatch is surfaced, not silently turned into an improvement.
        if prep['makespan']!=seed['recorded_makespan']:raise ValueError(f'seed replay mismatch {case} q{q} n{n}')
        portfolio_start=time.monotonic()
        alts=[]
        # Same-scene smaller-core seeds first; cross-scene plans are separate
        # candidates that must be evaluated again in the target question.
        options=[r for r in seeds if r['case']==case and r['n']<=n and not (r['q']==q and r['n']==n)]
        options.sort(key=lambda r:(r['q']!=q,r['recorded_makespan'],r['n'],r['q']))
        for s in options:
            if s['q']==q and s['recorded_makespan']>prep['makespan']*1.1:continue
            pa=read(resolve(s['plan_file']))
            if q==1 and s['q']!=1 and len(set(pa['node_to_subgraph'].values()))>256:continue
            alts.append({**s,'plan_file':str(resolve(s['plan_file']))})
            if len(alts)>=8:break
        ordered=methods if (int(case)+q+n)%2 else list(reversed(methods))
        for method in ordered:
            req={**common,'method':method,'mode':'warm_start','job':str(out/'jobs'/f'{case}_q{q}_n{n}_{method}'),'seed_job':str(basejob),'seed_makespan':prep['makespan'],'seed_solve_seconds':seed.get('seed_solve_seconds'),'seed_validation_seconds':prep['solve_seconds'],'source_seed':seed,'baseline':baselines[case],'baseline_source':'day01 original singlecore; historical','seconds':a.seconds,'max_evaluations':a.max_evaluations,'stall_limit':a.stall_limit,'strategy':'anytime','alternatives':alts}
            reserve=a.pair_seconds if q==3 else 0
            if time.monotonic()+a.seconds+reserve>deadline:
                answers.append({**req,'status':'not_started','solve_seconds':0.,'reason':'round_deadline','observations':[],'evaluation_events':[]});continue
            arm_offset=time.monotonic()-portfolio_start
            r=spawn(req,a.seconds)
            r['portfolio_elapsed_offset']=arm_offset
            if q==3 and r.get('plan_file'):
                if time.monotonic()+a.pair_seconds<=deadline:
                    pr=spawn({**common,'q':2,'method':'fixed','job':str(out/'pairs'/f'{case}_q3_n{n}_{method}'),'plan_file':r['plan_file'],'seconds':a.pair_seconds,'q3_source_job':r['job']},a.pair_seconds)
                    r['no_l2']=pr
                else:r['no_l2']={'status':'not_started','reason':'round_deadline'}
            answers.append(r)
        portfolio=[o for r in answers for o in r.get('observations',[]) if o['elapsed_seconds']<=a.seconds]
        if portfolio:
            best=min(portfolio,key=lambda o:(o['makespan'],o['added_copy_bytes']))
            dest=out/'selected'/f'{case}_q{q}_n{n}';dest.mkdir(parents=True,exist_ok=True)
            shutil.copy(best['plan_file'],dest/'plan.json');shutil.copy(best['result_file'],dest/'response.json.gz')
            timeline=[dict(elapsed_seconds=0.,makespan=prep['makespan'],name='verified_seed')]
            for r in answers:
                for o in r.get('observations',[]):
                    if o['elapsed_seconds']<=a.seconds:timeline.append({**o,'elapsed_seconds':r['portfolio_elapsed_offset']+o['elapsed_seconds'],'arm':r['method']})
            timeline.sort(key=lambda o:o['elapsed_seconds'])
            atomic_json(dest/'selection.json',dict(case=case,q=q,n=n,seed_makespan=prep['makespan'],makespan=best['makespan'],winning_name=best.get('name'),origin_plan=best['plan_file'],origin_response=best['result_file'],portfolio_seconds=time.monotonic()-portfolio_start,seed_validation_seconds=prep['solve_seconds'],seed_solve_seconds=seed.get('seed_solve_seconds'),includes_both_search_costs=True,observations=timeline))
        return answers
    blocks=[(c,q,n) for c in cases for q in qs for n in ns];atomic_json(out/'planned_blocks.json',blocks)
    with ThreadPoolExecutor(max_workers=cap) as pool:
        futures={pool.submit(block,b):b for b in blocks}
        for f in as_completed(futures):
            try:records.extend(f.result())
            except Exception as exc:errors.append(dict(block=futures[f],error=str(exc),traceback=traceback.format_exc()))
            export(out,records,manifest);atomic_json(out/'block_errors.json',errors)
    manifest['actual_wall_seconds']=time.monotonic()-start;manifest['completed_blocks']=len(set((r['case'],r['q'],r['n']) for r in records));atomic_json(out/'manifest.json',manifest);export(out,records,manifest)
    print('COMPLETED',out,flush=True)

if __name__=='__main__':main()
