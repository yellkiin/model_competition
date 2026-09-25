"""Real-graph recheck runner with observation-time prefixes and exact cold/warm pairing.

Examples use the unchanged contest evaluator. No automatic all-100 run.
"""
from __future__ import annotations
import argparse,csv,json,os,platform,shutil,signal,subprocess,sys,time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
from .recheck_evidence import ROOT,OFF,DAY,read,gzwrite,csvwrite,metrics
from research_a_orion_anytime.worker import atomic_json


def worker_limit(value):
    if value!='auto':return max(1,int(value))
    cpus=os.cpu_count() or 1
    if hasattr(os,'sched_getaffinity'):cpus=min(cpus,len(os.sched_getaffinity(0)))
    try:
        quota,period=Path('/sys/fs/cgroup/cpu.max').read_text().split()
        if quota!='max':cpus=min(cpus,max(1,int(quota)//int(period)))
    except (OSError,ValueError):pass
    try:
        from .run import available_memory
        mem=available_memory() or 1024**3
    except Exception:mem=1024**3
    return max(1,min(2,cpus//2,int(max(0,mem-512*1024**2)//(1024**3))))


def terminate(p):
    try:
        if os.name=='nt':p.terminate()
        else:os.killpg(p.pid,signal.SIGTERM)
        p.wait(timeout=1)
    except subprocess.TimeoutExpired:
        if os.name=='nt':p.kill()
        else:os.killpg(p.pid,signal.SIGKILL)
        p.wait()
    except ProcessLookupError:pass


def prepare_seed(source,out):
    """Accept only a completed fresh fixed-plan replay as common target-n seed."""
    source=Path(source);r=read(source/'summary.json');res=read(source/'official_response.json.gz')
    if r['status']!='ok' or res['status']!='ok':raise ValueError('seed replay is not valid')
    out=Path(out);out.mkdir(parents=True,exist_ok=True);t=time.monotonic()
    shutil.copy2(source/'plan.json',out/'plan.json');shutil.copy2(source/'official_response.json.gz',out/'result.json.gz')
    meta=dict(name='common_freshly_replayed_seed',makespan=res['official_result']['makespan'],added_copy_bytes=res['official_result']['data_movement_bytes']['added_copy_bytes'],plan_file='plan.json',result_file='result.json.gz',elapsed_seconds=0.,evaluation=0,certificate=res['audit']['certificate'])
    atomic_json(out/'progress.json',dict(status='ok',incumbent=meta,attempts=[],evaluations=0))
    return dict(seed_job=str(out),seed_plan=str(out/'plan.json'),seed_source=str(source),seed_solve_seconds=r.get('seed_solve_seconds'),seed_validation_seconds=r['total_seconds']+time.monotonic()-t,seed_id=source.name,seed_makespan=meta['makespan'],seed_added_copy_bytes=meta['added_copy_bytes'])


def run_arm(req,deadline):
    job=Path(req['job']);job.mkdir(parents=True,exist_ok=False)
    atomic_json(job/'request.json',req)
    start=time.monotonic();observations=[];events=[];observed=set();last=None;timed_out=False
    if req.get('seed_job'):
        m=read(Path(req['seed_job'])/'progress.json')['incumbent']
        observations.append(dict(elapsed_seconds=0.,makespan=m['makespan'],added_copy_bytes=m['added_copy_bytes'],plan_file=str(Path(req['seed_job'])/m['plan_file']),result_file=str(Path(req['seed_job'])/m['result_file']),name='input_seed',evaluations=0,provided_seed=True))
    with (job/'stdout.log').open('wb') as log:
        kw=dict(cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        if os.name=='nt':kw['creationflags']=subprocess.CREATE_NEW_PROCESS_GROUP
        else:kw['start_new_session']=True
        p=subprocess.Popen([sys.executable,'-u','-m','research_a_orion_track_structure.recheck_worker',str(job/'request.json')],**kw)
        while True:
            now=time.monotonic();elapsed=now-start
            try:
                s=read(job/'progress.json');inc=s.get('incumbent')
                if elapsed<=req['seconds'] and now<=deadline:
                    for a in s.get('attempts',[]):
                        if a.get('index') is not None and a.get('status') not in ('running',None) and a['index'] not in observed:
                            observed.add(a['index']);events.append(dict(elapsed_seconds=elapsed,index=a['index'],status=a['status'],makespan=a.get('makespan')))
                    if inc:
                        key=(inc['plan_file'],inc['makespan'],inc.get('added_copy_bytes'))
                        if key!=last:
                            last=key;event=dict(elapsed_seconds=elapsed,makespan=inc['makespan'],added_copy_bytes=inc.get('added_copy_bytes',0),plan_file=str(job/inc['plan_file']),result_file=str(job/inc['result_file']),name=inc.get('name'),evaluations=len(observed),provided_seed=False)
                            observations.append(event)
                            with (job/'observations.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(event)+'\n')
            except (OSError,ValueError,KeyError):pass
            if p.poll() is not None:break
            if elapsed>=req['seconds'] or now>=deadline:timed_out=True;terminate(p);break
            time.sleep(.03)
    elapsed=time.monotonic()-start
    try:s=read(job/'progress.json')
    except (OSError,ValueError):s={}
    best=min(observations,key=lambda e:(e['makespan'],e['added_copy_bytes'])) if observations else None
    route=read(job/'routing.json') if (job/'routing.json').exists() else {}
    row={**req,'status':('ok_with_timeout' if timed_out else 'ok') if best else ('timeout' if timed_out else 'no_valid_solution'),'timed_out':timed_out,'solve_seconds':elapsed,'makespan':best['makespan'] if best else None,'added_copy_bytes':best['added_copy_bytes'] if best else None,'plan_file':best['plan_file'] if best else None,'result_file':best['result_file'] if best else None,'winning_name':best.get('name') if best else None,'best_is_input_seed':bool(best and best.get('provided_seed')),'actual_route':route.get('actual_route'),'routing_seconds':route.get('routing_seconds'),'construction_seconds':s.get('construction_seconds'),'candidate_generation_seconds':s.get('candidate_generation_seconds',s.get('expanded_construction_seconds')),'official_eval_seconds':sum(a.get('eval_seconds',0) for a in s.get('attempts',[])),'audit_seconds':sum(a.get('audit_seconds',0) for a in s.get('attempts',[])) if req['method']=='corrected' else None,'completed_evaluations':len(observed),'attempts_started':s.get('evaluations'),'stopped':'parent_deadline' if timed_out else s.get('stopped'),'observations':observations,'evaluation_events':events,'attempt_status_counts':dict(Counter(a.get('status') for a in s.get('attempts',[]))),'first_valid_seconds':min((o['elapsed_seconds'] for o in observations),default=None),'last_improvement_seconds':None}
    incumbent=float('inf')
    for o in observations:
        if o['makespan']<incumbent:incumbent=o['makespan'];row['last_improvement_seconds']=o['elapsed_seconds']
    if best:
        r=read(best['result_file']);raw=r['official_result'];row.update(lower=r['audit']['certificate']['global_lower'],spill_added_copy_bytes=raw['data_movement_bytes'].get('spill_added_copy_bytes'),cache_hit_rate=raw.get('cache_stats',{}).get('hit_rate'))
    atomic_json(job/'observation_events.json',events);atomic_json(job/'summary.json',row)
    print(req['mode'],req['case'],req['q'],req['n'],req['method'],row['status'],row['makespan'],round(elapsed,3),flush=True)
    return row


def replay_pair(row,root,seconds,deadline):
    name=Path(row['job']).name;out=Path(root)/'pairs'/name
    pair=dict(case=row['case'],q=2,n=row['n'],label='same_plan_no_l2',out=str(out),plan_file=row['plan_file'],provenance={'paired_job':str(row['job']),'q3_makespan':row['makespan']})
    if time.monotonic()+seconds>deadline:return dict(status='not_started',reason='insufficient_remaining_pair_budget',requested=True,started=False)
    out.mkdir(parents=True,exist_ok=True);atomic_json(out/'request.json',pair);t=time.monotonic()
    with (out/'stdout.log').open('wb') as f:
        kw=dict(cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
        if os.name!='nt':kw['start_new_session']=True
        p=subprocess.Popen([sys.executable,'-m','research_a_orion_track_structure.recheck_evidence',str(out/'request.json')],**kw)
        try:p.wait(timeout=min(seconds,max(.001,deadline-time.monotonic())))
        except subprocess.TimeoutExpired:terminate(p);return dict(status='timeout',requested=True,started=True,seconds=time.monotonic()-t)
    if not (out/'summary.json').exists():return dict(status='error',requested=True,started=True,seconds=time.monotonic()-t)
    r=read(out/'summary.json');return dict(status=r['status'],requested=True,started=True,makespan=r.get('new_makespan'),seconds=time.monotonic()-t,result_file=str(out/'official_response.json.gz'),plan_file=str(out/'plan.json'))


def export(out,records,manifest):
    old={(r['case'],r['q'],r['n'],r['mode'],r.get('seed_id'),r.get('rep',0)):r for r in records if r['method']=='old'}
    rows=[];trajectories=[]
    for r in records:
        key=(r['case'],r['q'],r['n'],r['mode'],r.get('seed_id'),r.get('rep',0));o=old.get(key,{})
        pair=r.get('no_l2',{});seed=r.get('seed_solve_seconds',0.);validation=r.get('seed_validation_seconds',0.)
        total=None if seed is None else seed+validation+r.get('solve_seconds',0)
        vals={k:v for k,v in r.items() if not isinstance(v,(dict,list))}
        vals.update(run_id=out.name,old_makespan=o.get('makespan'),new_makespan=r.get('makespan'),old_added_copy_bytes=o.get('added_copy_bytes'),new_added_copy_bytes=r.get('added_copy_bytes'),added_solve_seconds=r.get('solve_seconds'),total_solve_seconds=total,evaluations=r.get('completed_evaluations'),no_l2_makespan=pair.get('makespan'),no_l2_replay_seconds=pair.get('seconds'),pair_status=pair.get('status','not_applicable' if r['q']!=3 else 'missing'))
        for k in ('plan_file','result_file','job'):
            if vals.get(k):
                try:vals[k]=str(Path(vals[k]).relative_to(out))
                except ValueError:pass
        rows.append(vals)
        for t in [30,60,120,300]+([600] if r['seconds']>300 else []):
            obs=[e for e in r.get('observations',[]) if e['elapsed_seconds']<=t]
            b=min(obs,key=lambda e:(e['makespan'],e['added_copy_bytes'])) if obs else None
            dur=r.get('solve_seconds',0);phase='not_started' if r['status']=='not_started' else ('stopped_carry_forward' if t>dur else 'running_prefix')
            elapsed=min(t,dur)
            trajectories.append(dict(case=r['case'],q=r['q'],n=r['n'],method=r['method'],requested_method=r['method'],actual_route=r.get('actual_route'),run_id=out.name,mode=r['mode'],seed_id=r.get('seed_id'),rep=r.get('rep',0),phase=phase,budget_seconds=t,elapsed_seconds=elapsed,total_elapsed_seconds=None if seed is None else seed+validation+elapsed,best_makespan=b['makespan'] if b else None,baseline=r.get('baseline'),speedup=r['baseline']/b['makespan'] if b and r.get('baseline') else None,added_copy_bytes=b['added_copy_bytes'] if b else None,evaluations=sum(e['elapsed_seconds']<=t for e in r.get('evaluation_events',[])),has_valid_incumbent=bool(b)))
    csvwrite(out/'per_case.csv',rows);csvwrite(out/'trajectory.csv',trajectories);atomic_json(out/'all_jobs.json',records)
    pairs=[r['no_l2'] for r in records if r.get('no_l2')]
    atomic_json(out/'run_summary.json',dict(jobs=len(records),statuses=dict(Counter(r['status'] for r in records)),q3_pairs_requested=len(pairs),q3_pairs_started=sum(bool(p.get('started')) for p in pairs),q3_pairs_completed=sum(p.get('status')=='ok' for p in pairs),q3_pairs_valid=sum(p.get('status')=='ok' and p.get('makespan') is not None for p in pairs),formal_complete=False,wall_seconds_actual=time.monotonic()-manifest['local_start']))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cases',required=True);p.add_argument('--questions',default='1,2,3');p.add_argument('--cores',default='2,5');p.add_argument('--methods',default='old,published,corrected');p.add_argument('--mode',choices=['cold_start','warm_start'],default='cold_start');p.add_argument('--seconds',type=float,default=300);p.add_argument('--wall-seconds',type=float,default=1800);p.add_argument('--pair-seconds',type=float,default=120);p.add_argument('--max-evaluations',type=int,default=256);p.add_argument('--workers',default='auto');p.add_argument('--shards',type=int,default=1);p.add_argument('--shard-index',type=int,default=0);p.add_argument('--seed-root',type=Path);p.add_argument('--seed-spec',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--rep',type=int,default=0)
    a=p.parse_args();out=a.out.resolve()
    if out.exists():p.error('refusing to overwrite existing run')
    if not 0<=a.shard_index<a.shards or a.seconds<=0 or a.wall_seconds<=0:p.error('invalid budgets/sharding')
    cases=sorted({f'{int(c):03d}' for c in a.cases.split(',')})[a.shard_index::a.shards];qs=[int(q) for q in a.questions.split(',')];ns=[int(n) for n in a.cores.split(',')];methods=a.methods.split(',')
    if set(qs)-{1,2,3} or any(n<1 or n>5 for n in ns):p.error('invalid scene/core list')
    for c in cases:
        if not (OFF/'data'/f'case_{c}.json').is_file():p.error(f'missing real graph {c}')
    out.mkdir(parents=True);cap=worker_limit(a.workers);start=time.monotonic();deadline=start+a.wall_seconds
    manifest=dict(run_id=out.name,utc=datetime.now(timezone.utc).isoformat(),python=sys.version,platform=platform.platform(),executable=sys.executable,workers_requested=a.workers,workers_actual=cap,argv=sys.argv,local_start=start,source_base='91f0ca1aa0b911a124601a0c460a7fbeff33771f',source_official='e04b2bf5df946f48714c66ba84d61bd4b90ece00',seconds=a.seconds,max_evaluations=a.max_evaluations,mode=a.mode,cases=cases,questions=qs,cores=ns,scope='real selected graphs, not full 100')
    atomic_json(out/'manifest.json',manifest)
    baseline={r['case'].replace('case_',''):int(r['baseline']) for r in csv.DictReader((DAY/'per_case.csv').open(encoding='utf-8-sig'))}
    specs=read(a.seed_spec) if a.seed_spec else {};blocks=[(c,q,n) for c in cases for q in qs for n in ns]
    records=[]
    def block(item):
        c,q,n=item;seed={};ans=[]
        if a.mode=='warm_start':
            source=specs.get(f'{c}_q{q}_n{n}') if specs else None
            source=Path(source) if source else a.seed_root/f'formal_{c}_q{q}_n{n}'
            seed=prepare_seed(source,out/'seeds'/f'{c}_q{q}_n{n}')
        ordered=methods if (int(c)+q+n+a.rep)%2==0 else list(reversed(methods))
        for method in ordered:
            req=dict(case=c,q=q,n=n,method=method,mode=a.mode,rep=a.rep,job=str(out/'jobs'/f'{c}_q{q}_n{n}_{method}'),official=str(OFF),config=str(OFF/'data/config.txt'),graph=str(OFF/'data'/f'case_{c}.json'),seconds=a.seconds,max_evaluations=a.max_evaluations,strategy='anytime',baseline=baseline[c],baseline_source='day01 historical official singlecore; not a fresh local singlecore timing',identity=dict(base=manifest['source_base'],run_id=out.name,case=c,q=q,n=n,method=method),**seed)
            reserve=a.pair_seconds if q==3 else 0
            if time.monotonic()+a.seconds+reserve>deadline:
                ans.append({**req,'status':'not_started','solve_seconds':0.,'reason':'round_deadline_reserved_pair','observations':[],'evaluation_events':[]});continue
            r=run_arm(req,deadline)
            if q==3 and r.get('plan_file'):r['no_l2']=replay_pair(r,out,a.pair_seconds,deadline)
            ans.append(r)
        return ans
    with ThreadPoolExecutor(max_workers=cap) as pool:
        fs=[pool.submit(block,b) for b in blocks]
        for f in as_completed(fs):
            try:records.extend(f.result())
            except Exception as e:atomic_json(out/f'block_error_{len(records)}.json',dict(error=str(e)))
            export(out,records,manifest)
    export(out,records,manifest);print('COMPLETE',out,flush=True)

if __name__=='__main__':main()
