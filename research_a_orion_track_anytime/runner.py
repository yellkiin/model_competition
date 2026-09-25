"""Bounded paired real experiments. No synthetic inputs or deferred score backfill."""
from __future__ import annotations
import argparse,csv,json,math,os,platform,shutil,signal,subprocess,sys,time,traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from .storage import read,write,incumbent_from_job
from .prepare import csv_write
ROOT=Path(__file__).resolve().parents[1];PKG=Path(__file__).resolve().parent

def worker_limit(requested,history,max_workers=2):
    import psutil
    available=psutil.virtual_memory().available;cpu=len(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else os.cpu_count() or 1
    try:
        q,p=Path('/sys/fs/cgroup/cpu.max').read_text().split()
        if q!='max':cpu=min(cpu,max(1,int(q)//int(p)))
    except (OSError,ValueError):pass
    peak=max((r.get('peak_rss_bytes',0) or 0 for r in history),default=0)
    need=max(700*1024**2,int(peak*1.6));ram=max(1,int(max(0,available-600*1024**2)//need))
    target=max(1,min(max_workers,cpu//2 or 1,ram))
    if requested!='auto':target=min(target,max(1,int(requested)))
    elif not history:target=1
    elif any(r.get('exit_code') in (-9,137) for r in history[-4:]):target=1
    return target,dict(available_bytes=available,cpu_budget=cpu,predicted_worker_bytes=need,peak_observed_bytes=peak)

def terminate(proc):
    if proc.poll() is not None:return
    if os.name=='nt':subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True)
    else:
        try:os.killpg(proc.pid,signal.SIGTERM)
        except ProcessLookupError:return
    try:proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        if os.name=='nt':proc.kill()
        else:
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        proc.wait()

def run_job(req,cap,baseline,seed_cost=None):
    folder=Path(req['job']);folder.mkdir(parents=True,exist_ok=False);write(folder/'request.json',req)
    clock=time.monotonic();obs=[];seen=set();events=[];eventseen=set();peak=0;state={};timed=False
    prior,_=incumbent_from_job(req['seed_job']) if req.get('seed_job') else (None,{})
    if prior:
        m=prior['meta'];obs.append(dict(elapsed_seconds=0.,makespan=m['makespan'],added_copy_bytes=m['added_copy_bytes'],plan_file=prior['plan_file'],result_file=prior['result_file'],name='verified_seed',phase='seed',evaluations=0))
    def observe():
        nonlocal state,peak
        if not (folder/'progress.json').exists():return
        try:state=read(folder/'progress.json')
        except (OSError,json.JSONDecodeError):return
        now=time.monotonic()-clock;meta=state.get('incumbent')
        if meta:
            key=meta.get('plan_file'),meta.get('makespan'),meta.get('added_copy_bytes')
            if key not in seen:
                pf=folder/meta['plan_file'];rf=folder/meta['result_file']
                if pf.exists() and rf.exists():
                    seen.add(key);obs.append(dict(elapsed_seconds=now,makespan=meta['makespan'],added_copy_bytes=meta.get('added_copy_bytes',0),plan_file=str(pf),result_file=str(rf),name=meta.get('name'),phase=state.get('phase','upstream'),evaluations=state.get('evaluations',0)))
        for a in state.get('attempts',[]):
            i=a.get('index')
            if i and i not in eventseen and a.get('status') not in ('running',None):
                eventseen.add(i);events.append(dict(elapsed_seconds=now,index=i,status=a['status'],family=a.get('family'),name=a.get('name'),makespan=a.get('makespan')))
    with (folder/'stdout.log').open('w') as log:
        kw=dict(cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONUTF8':'1','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'})
        if os.name!='nt':kw['start_new_session']=True
        proc=subprocess.Popen([sys.executable,'-u','-m','research_a_orion_track_anytime.adapter',str(folder/'request.json')],**kw)
        while True:
            observe()
            try:
                import psutil
                peak=max(peak,psutil.Process(proc.pid).memory_info().rss)
            except Exception:pass
            if proc.poll() is not None:break
            if time.monotonic()-clock>=cap:timed=True;terminate(proc);break
            time.sleep(.025)
        observe()
    elapsed=time.monotonic()-clock
    valid=[o for o in obs if o['elapsed_seconds']<=cap]
    chosen=min(valid,key=lambda x:(x['makespan'],x['added_copy_bytes'])) if valid else None
    costs=state.get('costs',{})
    status=('timeout_with_incumbent' if timed else 'ok' if proc.returncode==0 else 'error_with_incumbent') if chosen else ('timeout_no_incumbent' if timed else 'error_no_incumbent')
    row={**req,'status':status,'hard_timeout':timed,'exit_code':proc.returncode,'solve_seconds':elapsed,'peak_rss_bytes':peak,'baseline':baseline,'seed_solve_seconds':seed_cost,'seed_cost_complete':seed_cost is not None,'total_solve_seconds':seed_cost+elapsed if seed_cost is not None else None,'observations':obs,'evaluation_events':events,'evaluations_completed_within_budget':sum(e['elapsed_seconds']<=cap for e in events),'evaluations_started':state.get('evaluations',0),'stopped':'parent_deadline' if timed else state.get('stopped','worker_exit'),'first_valid_parent_seconds':min((o['elapsed_seconds'] for o in valid),default=None),'initialization_seconds':costs.get('initialization_seconds'),'candidate_generation_seconds':costs.get('candidate_generation_seconds'),'official_eval_seconds':costs.get('official_eval_seconds',sum(a.get('eval_seconds',0) for a in state.get('attempts',[]))),'audit_seconds':costs.get('audit_seconds'),'output_seconds':costs.get('io_seconds'),'selection_seconds':costs.get('selection_other_seconds'),'construction_seconds':state.get('construction_seconds'),'duplicate_candidates':state.get('duplicate_candidates',0),'generation_errors':len(state.get('construction_errors',[]))}
    if chosen:
        response=read(chosen['result_file']);raw=response['official_result']
        if response['status']!='ok' or not response['audit']['ok']:raise ValueError('unvalidated incumbent')
        row.update(chosen,makespan=raw['makespan'],speedup=baseline/raw['makespan'],lower=response['audit']['certificate']['global_lower'],cache_hit_rate=raw.get('cache_stats',{}).get('hit_rate'),spill_added_copy_bytes=raw['data_movement_bytes'].get('spill_added_copy_bytes'))
        row['selected_available_seconds']=chosen['elapsed_seconds']
        target=folder/'selected';target.mkdir();shutil.copy(chosen['plan_file'],target/'plan.json');shutil.copy(chosen['result_file'],target/'response.json.gz')
        row['plan_file']=str(target/'plan.json');row['result_file']=str(target/'response.json.gz')
    write(folder/'observations.json',obs);write(folder/'summary.json',row)
    print(req['case'],req['q'],req['n'],req.get('mode'),req['method'],status,row.get('makespan'),round(elapsed,3),flush=True)
    return row

def export(out,records,manifest):
    controls={(r['case'],r['q'],r['n'],r['mode']):r for r in records if r['method']=='old'};rows=[];prefixes=[]
    for r in records:
        control=controls.get((r['case'],r['q'],r['n'],r['mode']),{});row={k:v for k,v in r.items() if not isinstance(v,(dict,list))}
        row.update(run_id=out.name,old_makespan=control.get('makespan'),new_makespan=r.get('makespan'),old_added_copy_bytes=control.get('added_copy_bytes'),new_added_copy_bytes=r.get('added_copy_bytes'),added_solve_seconds=r.get('solve_seconds'),evaluations=r.get('evaluations_completed_within_budget'),matched_budget=bool(control) and control.get('seconds')==r['seconds'])
        rows.append(row)
        for t in (30,60,120,300,600):
            available=[o for o in r.get('observations',[]) if o['elapsed_seconds']<=min(t,r['seconds'])];best=min(available,key=lambda x:(x['makespan'],x['added_copy_bytes'])) if available else None
            phase='not_started' if r['status']=='not_started' else 'stopped_carry_forward' if t>r.get('solve_seconds',0) else 'observed_prefix'
            prefixes.append(dict(case=r['case'],q=r['q'],n=r['n'],method=r['method'],mode=r['mode'],run_id=out.name,phase=phase,budget_seconds=t,elapsed_seconds=min(t,r.get('solve_seconds',0)),total_elapsed_seconds=None if r.get('seed_solve_seconds') is None else r['seed_solve_seconds']+min(t,r.get('solve_seconds',0)),best_makespan=best['makespan'] if best else None,baseline=r.get('baseline'),speedup=r['baseline']/best['makespan'] if best else None,has_valid_incumbent=best is not None,evaluations=sum(e['elapsed_seconds']<=t for e in r.get('evaluation_events',[]))))
    csv_write(out/'per_case.csv',rows);csv_write(out/'trajectory.csv',prefixes);write(out/'all_jobs.json',records)
    write(out/'run_summary.json',dict(jobs=len(records),statuses=dict(Counter(r['status'] for r in records)),q3_pairs_requested=sum(r['q']==3 and r.get('makespan') is not None for r in records),q3_pairs_completed=sum(r.get('pair_status')=='ok' for r in records),full_100_rerun=False,policy=manifest['policy']))

def main():
    p=argparse.ArgumentParser();p.add_argument('--cases',required=True);p.add_argument('--questions',default='1,2,3');p.add_argument('--cores',default='2,5');p.add_argument('--methods',default='old,combined');p.add_argument('--modes',default='warm,cold');p.add_argument('--seconds',type=float,default=30);p.add_argument('--max-evaluations',type=int,default=16);p.add_argument('--total-seconds',type=float,default=1800);p.add_argument('--pair-seconds',type=float,default=60);p.add_argument('--workers',default='auto');p.add_argument('--max-workers',type=int,default=2);p.add_argument('--shards',type=int,default=1);p.add_argument('--shard-index',type=int,default=0);p.add_argument('--seed-manifest',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--official',type=Path,default=ROOT/'题目/A题/通用神经网络处理器下的多核调度问题  附件');p.add_argument('--gap-tolerance',type=float,default=.02);a=p.parse_args()
    if not 0<=a.shard_index<a.shards or min(a.seconds,a.total_seconds,a.pair_seconds)<=0:p.error('invalid budget/sharding')
    cases=sorted({'case_'+f'{int(x.removeprefix("case_")):03d}' for x in a.cases.split(',')})[a.shard_index::a.shards];qs=list(map(int,a.questions.split(',')));ns=list(map(int,a.cores.split(',')));methods=a.methods.split(',');modes=a.modes.split(',')
    if set(methods)-{'old','budget','combined','queue','fifo'} or set(modes)-{'warm','cold'} or set(qs)-{1,2,3} or any(n<1 or n>5 for n in ns):p.error('unsupported mode')
    seeds={(r['case'],r['q'],r['n']):r for r in read(a.seed_manifest)};out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    for case in cases:
        if not (a.official/'data'/f'{case}.json').is_file():raise FileNotFoundError(case)
    manifest=dict(utc_start=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),platform=platform.platform(),python=sys.version,exe=sys.executable,policy='wu-v1.1',base_commit='b513a98f86183a8c1b41d67a547f06fa9d578e2a',branch='orion/track-anytime_wu',lineage_pr26='eaf9a67f86d54b87e3a6f80d815bea5593bf8d0e',cases=cases,questions=qs,cores=ns,methods=methods,modes=modes,seconds=a.seconds,evaluation_cap=a.max_evaluations,total_seconds=a.total_seconds,gap_tolerance=a.gap_tolerance,worker_policy='adaptive between completed matched blocks using CPU/RAM/peakRSS; constant inside block',seed_manifest=str(a.seed_manifest),baseline_source='original day01 q0 singlecore, historical; no free cold seed')
    write(out/'manifest.json',manifest);(out/'source').mkdir()
    for f in PKG.glob('*.py'):shutil.copy(f,out/'source'/f.name)
    clock=time.monotonic();deadline=clock+a.total_seconds;records=[];hist=[];waves=[]
    specs=[(c,q,n,m) for m in modes for c in cases for q in qs for n in ns];write(out/'planned_units.json',specs)
    def unit(spec):
        c,q,n,mode=spec;seed=seeds[c,q,n];order=list(methods)
        if (int(c[-3:])+q+n)%2:order.reverse()
        base=dict(case=c,q=q,n=n,mode=mode+'_start',baseline=seed['baseline'],seconds=a.seconds,max_evaluations=a.max_evaluations,official=str(a.official.resolve()),graph=str((a.official/'data'/f'{c}.json').resolve()),config=str((a.official/'data/config.txt').resolve()),identity={'base':manifest['base_commit'],'policy':manifest['policy']},strategy='anytime',gap_tolerance=a.gap_tolerance)
        required=len(methods)*(a.seconds+(a.pair_seconds if q==3 else 0))
        if time.monotonic()+required>deadline:return [dict(base,method=method,status='not_started',reason='whole_matched_block_not_admitted',solve_seconds=0.) for method in order]
        results=[]
        cost=seed['seed_solve_seconds']+seed['validation_seconds'] if mode=='warm' else 0.
        for method in order:
            req=dict(base,method=method,job=str(out/'jobs'/f'{c}_q{q}_n{n}_{mode}_{method}'))
            if mode=='warm':req.update(seed_job=seed['seed_job'],seed_makespan=seed['recorded_makespan'],seed_validation_seconds=seed['validation_seconds'])
            result=run_job(req,a.seconds,seed['baseline'],cost);results.append(result)
        for result in results:
            if q!=3 or result.get('makespan') is None:continue
            req=dict(base,q=2,method='fixed',job=str(out/'pairs'/f'{c}_q3_n{n}_{mode}_{result["method"]}'),fixed_plan=result['plan_file'],seconds=a.pair_seconds)
            pair=run_job(req,a.pair_seconds,seed['baseline'],0.)
            exact=pair.get('plan_file') and read(pair['plan_file'])==read(result['plan_file'])
            result.update(pair_status='ok' if exact and pair['status']=='ok' else pair['status'],no_l2_makespan=pair.get('makespan'),pair_seconds=pair['solve_seconds'],pair_plan_file=pair.get('plan_file'),pair_result_file=pair.get('result_file'),pair_exact_plan=bool(exact))
        return results
    pos=0
    while pos<len(specs):
        workers,probe=worker_limit(a.workers,hist,a.max_workers);batch=specs[pos:pos+workers];pos+=len(batch);waves.append(dict(workers=workers,resources=probe,units=batch,elapsed_seconds=time.monotonic()-clock))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures=[pool.submit(unit,s) for s in batch]
            for s,f in zip(batch,futures):
                try:part=f.result();records.extend(part);hist.extend(part)
                except Exception as exc:
                    write(out/f'ERROR_{s[0]}_{s[1]}_{s[2]}_{s[3]}.json',dict(error=str(exc),traceback=traceback.format_exc()))
        export(out,records,manifest);write(out/'worker_waves.json',waves)
    manifest['actual_wall_seconds']=time.monotonic()-clock;write(out/'manifest.json',manifest);export(out,records,manifest)
    print('COMPLETE',out,flush=True)
if __name__=='__main__':main()
