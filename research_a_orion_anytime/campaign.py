"""Pilot -> quality/capacity admission -> 100-case coverage -> refinement -> pairs.

All phases share one persisted wall-clock deadline. A timeout is NOT a success
certificate; unfinished mandatory jobs remain missing. Nothing is submitted to a
contest service, and no generated results are committed automatically.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import statistics
import time
from .core import fingerprint
from .inputs import ensure
from .reporting import collect,gmean,prefix_best
from .solver import read
from .supervisor import (batch,run_job,locate_official,code_sha,PACKAGE,machine,job_name,sha)
from .worker import atomic_json

DEV=['case_001','case_002','case_044']
STRESS=['case_016','case_059','case_083']


def required(cases):
    return [(c,q,n) for c in cases for q,n in [(0,1),(3,1)]+[(q,n) for n in (2,3,4,5) for q in (1,2,3)]]


def list_bound(caps,workers):
    """Greedy list-scheduling envelope for finite job caps (not actual runtimes)."""
    caps=list(caps)
    return sum(caps)/workers+(1-1/workers)*max(caps,default=0)


def count_ops(path):
    return sum(o['op'] not in ('COPY_IN','COPY_OUT') for o in read(path)['ops'])


def index_write(path,selected,pairs,expected,policy):
    atomic_json(path,dict(chosen=[dict(key=list(k),summary=str(Path(v['job'])/'summary.json')) for k,v in sorted(selected.items()) if 'job' in v],
                         pairs=[dict(key=list(k),summary=str(Path(v['job'])/'summary.json')) for k,v in sorted(pairs.items()) if 'job' in v],
                         expected=[list(x) for x in sorted(expected)],policy=policy))


def make_job(official,config,root,c,q,n,seconds,calls,deadline,**kwargs):
    return dict(official=official,config=config,graph=official/'data'/f'{c}.json',folder=root/job_name(c,q,n),
                q=q,n=n,seconds=seconds,max_evaluations=calls,deadline_epoch=deadline,**kwargs)


def pilot(a,official,config,out,deadline):
    cases=DEV+STRESS
    ensure(official,cases,a.archive,a.restore_inputs,deadline)
    sizes={c:count_ops(official/'data'/f'{c}.json') for c in cases}
    spec=[(c,q,n) for c in cases for q,n in [(0,1),(3,1)]+[(q,n) for n in (2,5) for q in (1,2,3)]]
    jobs=[]
    for c,q,n in spec:
        seconds=a.large_seconds if sizes[c]>8000 else a.seconds
        if q==0:seconds=max(seconds,a.large_seconds)
        jobs.append(make_job(official,config,out/'pilot',c,q,n,seconds,1 if q==0 else a.calls,deadline))
    rows=batch(jobs,a.workers);chosen={(r['case'],r['q'],r['n']):r for r in rows}
    pair_jobs=[]
    for (c,q,n),r in chosen.items():
        if q==3 and r['status']=='ok':
            pair_jobs.append(make_job(official,config,out/'pilot_pairs',c,2,n,a.large_seconds,1,deadline,fixed_plan=r['plan']))
    pair_rows=batch(pair_jobs,a.workers);pairs={(r['case'],3,r['n']):r for r in pair_rows}
    index_write(out/'pilot_index.json',chosen,pairs,spec,dict(stage='pilot',seconds=a.seconds,large_seconds=a.large_seconds,calls=a.calls))
    report=collect(out/'pilot_index.json',out/'pilot_report',official,verify=True)
    # Budget-only comparator uses identical wall-clock and evaluation caps.
    legacy_jobs=[make_job(official,config,out/'matched_legacy',c,q,5,a.seconds,a.calls,deadline,strategy='legacy') for c in DEV for q in (1,2,3)]
    legacy=batch(legacy_jobs,a.workers)
    matched=[]
    for old in legacy:
        key=(old['case'],old['q'],old['n']);new=chosen.get(key,{})
        if old['status']=='ok' and new.get('status')=='ok':
            matched.append(dict(case=key[0],q=key[1],n=key[2],legacy_time=old['makespan'],new_time=new['makespan'],
                                ratio=old['makespan']/new['makespan'],legacy_wall=old['process_seconds'],new_wall=new['process_seconds'],
                                legacy_calls=old['evaluations'],new_calls=new['evaluations']))
    prefix=[];prefix_regress=[]
    for r in rows:
        if r.get('status')!='ok' or r['q']==0:continue
        before=prefix_best(r,evaluations=3)
        if before:
            entry=dict(case=r['case'],q=r['q'],n=r['n'],first3=before,final=r['makespan'],ratio=before/r['makespan'])
            prefix.append(entry)
            if r['makespan']>before:prefix_regress.append(entry)
    per_q={q:gmean([r['ratio'] for r in prefix if r['q']==q and r['case'] in DEV and r['n'] in (2,5)]) for q in (1,2,3)}
    # Gate is preregistered here; it is not silently loosened on a failing run.
    valid=not report['failures_or_missing']
    matched_good=len(matched)==9 and gmean([x['ratio'] for x in matched])>=1.005
    improved=all(per_q[q] is not None and per_q[q]>=1.0 for q in (1,2,3)) and gmean([r['ratio'] for r in prefix if r['case'] in DEV and r['n'] in (2,5)])>=1.01
    gate=dict(accepted=valid and improved and matched_good and not prefix_regress,all_requested_valid=valid,
              algorithm=code_sha(PACKAGE),official=code_sha(official/'code'),config=sha(config),
              hardware=machine(),thresholds=dict(prefix_geomean=1.01,matched_budget_geomean=1.005,per_question_prefix=1.0),
              matched=matched,matched_geomean=gmean([x['ratio'] for x in matched]),per_question_prefix_geomean=per_q,
              prefix_comparisons=prefix,prefix_regressions=prefix_regress,pilot_index=str(out/'pilot_index.json'),
              records=[str(Path(r['job'])/'summary.json') for r in rows if 'job' in r],sizes=sizes,
              reason='pass' if valid and improved and matched_good and not prefix_regress else 'quality_or_coverage_gate_failed')
    atomic_json(out/'gate.json',gate)
    return gate


def calibrate(gate):
    samples=[]
    for p in gate['records']:
        s=read(p)
        if s['status']!='ok':continue
        prog=read(Path(s['job'])/'progress.json')
        times=[a['eval_seconds'] for a in prog['attempts'] if a['status']=='ok']
        if times:samples.append((s['features']['ops'],s['q'],s['n'],max(times),s.get('construction_seconds') or 0))
    return samples


def estimate_cap(size,q,n,samples,calls=1):
    matches=[x for x in samples if x[1]==q and x[2]==n]
    if not matches:matches=[x for x in samples if x[1]==q]
    if not matches:matches=samples
    # Nearest-size calibration with a quadratic extrapolation and a 2x risk margin.
    # This estimates required time; it does not guarantee a valid solution on a new graph.
    closest=sorted(matches,key=lambda x:abs(math.log(max(1,size)/max(1,x[0]))))[:2]
    estimates=[t*max(.25,(size/max(1,m))**2) for m,_,_,t,_ in closest]
    construct=max((c*max(.5,size/max(1,m)) for m,_,_,_,c in closest),default=1)
    return max(8,math.ceil(2*(max(estimates,default=5)*calls+construct)+2))


def formal(a,official,config,out,deadline,gate):
    if not gate['accepted']:raise ValueError('Pilot gate did not pass; formal runs not launched')
    for k,value in [('algorithm',code_sha(PACKAGE)),('official',code_sha(official/'code')),('config',sha(config))]:
        if gate[k]!=value:raise ValueError(f'Pilot gate {k} differs from current files; rerun pilot in a new root')
    all_cases=[f'case_{i:03d}' for i in range(1,101)]
    cases=[c for i,c in enumerate(all_cases) if i%a.shards==a.shard_index]
    ensure(official,cases,a.archive,a.restore_inputs,deadline)
    sizes={c:count_ops(official/'data'/f'{c}.json') for c in cases};samples=calibrate(gate)
    expected=required(cases);coverage_caps={};pair_caps={}
    for c,q,n in expected:
        # Cover all instances before spending the optional improvement allowance.
        calls=1 if q==0 or sizes[c]>8000 else 3
        coverage_caps[c,q,n]=(estimate_cap(sizes[c],q,n,samples,calls),calls)
        if q==3:pair_caps[c,q,n]=estimate_cap(sizes[c],2,n,samples,1)
    reserve=a.verify_reserve_seconds
    upper=list_bound([x[0] for x in coverage_caps.values()],a.workers)+list_bound(pair_caps.values(),a.workers)+reserve
    available=deadline-time.time()
    admission=dict(accepted=upper<=available,mandatory_capped_wall_bound=upper,available_seconds=available,
                   note='Bound assumes each job is stopped at its cap; cap adequacy on unmeasured graphs is empirical, not guaranteed',
                   shards=a.shards,shard_index=a.shard_index,workers=a.workers,sizes=sizes,
                   coverage_caps=[dict(key=list(k),seconds=v[0],calls=v[1]) for k,v in coverage_caps.items()],
                   pair_caps=[dict(key=list(k),seconds=v) for k,v in pair_caps.items()])
    atomic_json(out/'capacity_admission.json',admission)
    if not admission['accepted']:
        atomic_json(out/'formal_status.json',dict(status='not_launched_capacity_gate',suggested_minimum_total_shards=max(a.shards+1,math.ceil(upper/max(1,available))*a.shards)))
        return None
    coverage=[]
    for c,q,n in expected:
        sec,calls=coverage_caps[c,q,n]
        coverage.append(make_job(official,config,out/'coverage',c,q,n,sec,calls,deadline-reserve))
    rows=batch(coverage,a.workers);selected={(r['case'],r['q'],r['n']):r for r in rows}
    # No refinement is allowed to consume the reserved same-plan counterfactual budget.
    pair_reserve=list_bound(pair_caps.values(),a.workers)
    refinement_deadline=deadline-reserve-pair_reserve
    # One bounded retry for coverage failures; it must not borrow the pair/audit reserve.
    retry_jobs=[];retry_slack=max(0,refinement_deadline-time.time())
    for r in rows:
        key=(r['case'],r['q'],r['n'])
        if r['status']!='ok':
            sec,calls=coverage_caps[key];sec*=2
            if sec<=retry_slack:
                retry_jobs.append(make_job(official,config,out/'coverage_retry',*key,sec,1,refinement_deadline))
                retry_slack-=sec  # Conservative serial reservation, even with two workers.
    for r in batch(retry_jobs,a.workers):
        if r['status']=='ok':selected[r['case'],r['q'],r['n']]=r
    rows=list(selected.values())
    good=[r for r in rows if r['status']=='ok' and r['q']>0]
    good.sort(key=lambda r:(-(r['makespan']/max(1,r['certificate']['global_lower'])-1),r['case'],r['q'],r['n']))
    slack=max(0,refinement_deadline-time.time())
    weights=[2 if sizes[r['case']]>8000 else 1 for r in good]
    uniform=min(a.refine_seconds,math.floor(.9*slack*a.workers/max(1,sum(weights))))
    refine_jobs=[]
    if uniform>=5:
        for r,w in zip(good,weights):
            if r['certificate']['approximation_ratio_upper']<=1+a.gap_tolerance:continue
            refine_jobs.append(make_job(official,config,out/'refinement',r['case'],r['q'],r['n'],uniform*w,256,
                                        refinement_deadline,seed_job=r['job'],gap_tolerance=a.gap_tolerance))
    atomic_json(out/'refinement_policy.json',dict(uniform_base_seconds=uniform,max_requested=a.refine_seconds,
                                                large_multiplier=2,priority='descending certified ratio upper',jobs=len(refine_jobs)))
    for r in batch(refine_jobs,a.workers):
        key=(r['case'],r['q'],r['n'])+        if r['status']=='ok':
            old=selected[key]
            if (r['makespan'],r['added_copy_bytes'])>(old['makespan'],old['added_copy_bytes']):raise ValueError('Refinement lost the seed incumbent')
            r['coverage_seconds']=old.get('total_job_seconds',old['process_seconds']);r['end_to_end_solve_seconds']=r.get('total_job_seconds',r['process_seconds'])+r['coverage_seconds']
            atomic_json(Path(r['job'])/'summary.json',r);selected[key]=r
    pair_jobs=[]
    for (c,q,n),r in selected.items():
        if q==3 and r['status']=='ok':pair_jobs.append(make_job(official,config,out/'pairs',c,2,n,pair_caps[c,q,n],1,deadline-reserve,fixed_plan=r['plan']))
    pairs={(r['case'],3,r['n']):r for r in batch(pair_jobs,a.workers)}
    index_write(out/'final_index.json',selected,pairs,expected,dict(algorithm='ORION-A',coverage='first',refinement_seconds=uniform,
                                                                 shards=a.shards,shard_index=a.shard_index,deadline_epoch=deadline))
    # Verification has its own reserved interval; the outer PowerShell launcher also
    # supervises the whole campaign when an absolute end-to-end cutoff is required.
    report=collect(out/'final_index.json',out/'final_report',official,verify=True,require_complete=a.shards==1)
    atomic_json(out/'formal_status.json',dict(status='complete' if report['formal_complete'] else 'shard_or_incomplete',report=report))
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['pilot','auto','formal','collect','mechanisms','sensitivity'])
    p.add_argument('--official');p.add_argument('--out',required=True);p.add_argument('--gate');p.add_argument('--indices',nargs='+')
    p.add_argument('--workers',type=int,choices=[1,2],default=2);p.add_argument('--hours',type=float,default=11.5)
    p.add_argument('--seconds',type=float,default=30);p.add_argument('--large-seconds',type=float,default=180);p.add_argument('--calls',type=int,default=24)
    p.add_argument('--refine-seconds',type=int,default=30);p.add_argument('--gap-tolerance',type=float,default=.005)
    p.add_argument('--verify-reserve-seconds',type=int,default=1800);p.add_argument('--shards',type=int,default=1);p.add_argument('--shard-index',type=int,default=0)
    p.add_argument('--index');p.add_argument('--reoptimize-grid',action='store_true')
    p.add_argument('--archive');p.add_argument('--restore-inputs',action='store_true')
    a=p.parse_args(argv)
    if not 0<a.hours<=12 or a.seconds<=0 or a.large_seconds<=0 or a.calls<1 or a.refine_seconds<0:p.error('Invalid positive budgets; hours must be <=12')
    if a.shards<1 or not 0<=a.shard_index<a.shards:p.error('Invalid shard')
    official,config=locate_official(a.official);out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    if a.command=='collect':
        if not a.indices:p.error('collect requires --indices')
        chosen={};pairs={};expected=set();policy=[]
        for f in a.indices:
            idx=read(f);policy.append(idx['policy']);expected.update(tuple(k) for k in idx['expected'])
            for name,dest in [('chosen',chosen),('pairs',pairs)]:
                for entry in idx.get(name,[]):
                    key=tuple(entry['key']);s=read(entry['summary'])
                    if key in dest and dest[key]['job_identity']!=s['job_identity']:raise ValueError('Conflicting duplicate shard, not selected post hoc')
                    dest[key]=s
        index_write(out/'merged_index.json',chosen,pairs,expected,dict(shards=policy))
        print(json.dumps(collect(out/'merged_index.json',out/'report',official,True,True),ensure_ascii=False,indent=2));return 0
    manifest_file=out/'campaign.json';identity=dict(command=a.command,algorithm=code_sha(PACKAGE),official=code_sha(official/'code'),config=sha(config),
                                                      args={k:v for k,v in vars(a).items() if k not in ('archive','restore_inputs')})
    if manifest_file.is_file():
        manifest=read(manifest_file)
        if manifest['identity']!=identity:raise ValueError('Campaign policy/source changed; use a new output root')
    else:
        manifest=dict(identity=identity,started_epoch=time.time(),deadline_epoch=time.time()+a.hours*3600,hardware=machine())
        atomic_json(manifest_file,manifest)
    deadline=manifest['deadline_epoch']
    if time.time()>=deadline:raise TimeoutError('Persisted campaign deadline has expired; no implicit deadline reset on resume')
    if a.command=='sensitivity':
        if not a.index:p.error('sensitivity requires --index with completed default plans')
        idx=read(a.index);chosen={tuple(e['key']):read(e['summary']) for e in idx['chosen']}
        ensure(official,['case_044','case_083'],a.archive,a.restore_inputs,deadline)
        jobs=[]
        for c in ['case_044','case_083']:
            base=chosen.get((c,3,5),{})
            if base.get('status')!='ok':raise ValueError('Missing default Q3 five-core plan: '+c)
            for capacity in [262144,1048576,4194304]:
                for bandwidth in [60,250,500]:
                    tag=f'{capacity}_{bandwidth}'
                    params=dict(cache_capacity_bytes=capacity,cache_bandwidth_bytes_per_cycle=bandwidth)
                    jobs.append(make_job(official,config,out/('fixed_'+tag),c,3,5,a.large_seconds,1,deadline,
                                         fixed_plan=base['plan'],cache_overrides=params))
                    if a.reoptimize_grid:
                        jobs.append(make_job(official,config,out/('reoptimized_'+tag),c,3,5,a.seconds,a.calls,deadline,cache_overrides=params))
        records=batch(jobs,a.workers);atomic_json(out/'non_official_grid_records.json',records)
        return 0 if all(r['status']=='ok' for r in records) else 1
    if a.command=='mechanisms':
        ensure(official,DEV,a.archive,a.restore_inputs,deadline);jobs=[]
        for label,flag in [('full',{}),('no_stage',{'no_stage':True}),('no_window',{'no_window':True}),('no_dp',{'no_dp':True})]:
            for c in ['case_002','case_044']:
                for q in (1,2,3):jobs.append(make_job(official,config,out/label,c,q,5,a.seconds,a.calls,deadline,flags=flag))
        rows=batch(jobs,a.workers);atomic_json(out/'mechanism_records.json',rows);return 0 if all(r['status']=='ok' for r in rows) else 1
    gate=read(a.gate) if a.command=='formal' and a.gate else pilot(a,official,config,out,deadline)
    print(json.dumps({k:v for k,v in gate.items() if k not in ('records','prefix_comparisons','matched')},ensure_ascii=False,indent=2))
    if a.command=='pilot':return 0 if gate['accepted'] else 2
    if not gate['accepted']:return 2
    report=formal(a,official,config,out,deadline,gate)
    return 0 if report and not report['failures_or_missing'] else 3

if __name__=='__main__':raise SystemExit(main())
