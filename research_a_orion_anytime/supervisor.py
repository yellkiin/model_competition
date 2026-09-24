"""Windows/POSIX hard deadlines for the WHOLE solver, including construction.

A job process does not spawn children. Killing it also interrupts a slow original
evaluator without leaving grandchildren. A validated incumbent survives the kill.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from .core import fingerprint
from .solver import read
from .worker import atomic_json

PACKAGE=Path(__file__).resolve().parent;ROOT=PACKAGE.parent


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def code_sha(path):return fingerprint({p.name:sha(p) for p in sorted(Path(path).glob('*.py'))})


def signature(official,config,graph):
    return dict(algorithm=code_sha(PACKAGE),official=code_sha(Path(official)/'code'),
                config=sha(config),graph=sha(graph),python=list(sys.version_info[:3]))


def locate_official(value=None):
    if value:root=Path(value).resolve()
    else:
        roots=list((ROOT/'题目'/'A题').glob('*附件'))
        if len(roots)!=1:raise FileNotFoundError('Use --official to select the original A attachment directory')
        root=roots[0]
    config=next((p for p in [root/'data/config.txt',root/'config.txt'] if p.is_file()),None)
    if config is None or not (root/'code/evaluation_validation.py').is_file():raise FileNotFoundError('Original A evaluator/config missing')
    return root,config


def job_name(case,q,n):return f'{case}_q{q}_n{n}'


def run_job(official,config,graph,folder,q,n,seconds=30,max_evaluations=64,
            strategy='anytime',deadline_epoch=float('inf'),seed_job=None,fixed_plan=None,
            gap_tolerance=0,flags=None,cache_overrides=None):
    whole_started=time.monotonic()
    graph,folder=Path(graph).resolve(),Path(folder).resolve();folder.mkdir(parents=True,exist_ok=True)
    ident=signature(official,config,graph)
    policy=dict(q=q,n=n,seconds=seconds,max_evaluations=max_evaluations,strategy=strategy,
                gap_tolerance=gap_tolerance,flags=flags or {},cache_overrides=cache_overrides)
    fixed_hash=sha(fixed_plan) if fixed_plan else None
    seed_hash=None
    if seed_job:
        prior=read(Path(seed_job)/'progress.json')
        if prior['identity']!=ident or (prior['q'],prior['n'])!=(q,n):raise ValueError('Seed source/config/graph/interpreter/question/core identity differs')
        if (prior.get('cache_overrides') or {}) != (cache_overrides or {}):raise ValueError('Seed cache parameters differ; evaluate the old plan under the new parameters instead of reusing its score')
        seed_hash=prior['incumbent']['plan_hash'] if prior.get('incumbent') else None
        if not seed_hash:seed_job=None
    identity=fingerprint(dict(signature=ident,policy=policy,seed=seed_hash,fixed=fixed_hash))
    summary_file=folder/'summary.json'
    if summary_file.is_file():
        prev=read(summary_file)
        if prev['job_identity']!=identity:raise ValueError(f'Existing job has a different identity: {folder}; use a new output root')
        return prev
    left=deadline_epoch-time.time()
    if left<=0:
        s=dict(status='not_started_global_deadline',job=str(folder),case=graph.stem,q=q,n=n,job_identity=identity,signature=ident,policy=policy)
        atomic_json(summary_file,s);return s
    # An interrupted earlier invocation is archived, never silently mixed with a new run.
    if (folder/'progress.json').exists():
        prior_request=folder/'request.json'
        if not prior_request.is_file() or read(prior_request).get('job_identity')!=identity:
            raise ValueError('Interrupted job policy/source changed; use a new output root')
        previous=folder/f'interrupted_{time.time_ns()}'
        previous.mkdir()
        for name in ['request.json','progress.json','stdout.txt','stderr.txt','current_plan.json','worker_error.json','incumbents','failures']:
            p=folder/name
            if p.exists():p.rename(previous/name)
        pp=previous/'progress.json'
        if pp.is_file() and (old:=read(pp)).get('incumbent'):
            if old['identity']!=ident:raise ValueError('Interrupted incumbent source identity changed')
            seed_job=previous
    req=dict(official=str(Path(official).resolve()),config=str(Path(config).resolve()),graph=str(graph),
             job=str(folder),case=graph.stem,q=q,n=n,seconds=min(seconds,left),max_evaluations=max_evaluations,
             identity=ident,job_identity=identity,strategy=strategy,gap_tolerance=gap_tolerance,**(flags or {}))
    if seed_job:req['seed_job']=str(Path(seed_job).resolve())
    if fixed_plan:req['fixed_plan']=str(Path(fixed_plan).resolve())
    if cache_overrides:req['cache_overrides']=cache_overrides
    atomic_json(folder/'request.json',req)
    started=time.monotonic();timed_out=False
    with (folder/'stdout.txt').open('w',encoding='utf8') as stdout,(folder/'stderr.txt').open('w',encoding='utf8') as stderr:
        child=subprocess.Popen([sys.executable,'-m','research_a_orion_anytime.solver',str(folder/'request.json')],
                               cwd=ROOT,stdout=stdout,stderr=stderr,
                               env={**os.environ,'PYTHONUTF8':'1','PYTHONHASHSEED':'0'})
        try:child.wait(timeout=min(seconds,left))
        except subprocess.TimeoutExpired:
            timed_out=True;child.kill();child.wait()
        except BaseException:
            child.kill();child.wait();raise
    duration=time.monotonic()-started
    state=read(folder/'progress.json') if (folder/'progress.json').exists() else dict(incumbent=None,attempts=[])
    if timed_out:
        for a in state['attempts']:
            if a['status']=='running':a.update(status='interrupted_by_budget',completed_seconds=duration)
        state.update(stopped='hard_job_deadline',status='ok' if state.get('incumbent') else 'deadline_without_incumbent')
        atomic_json(folder/'progress.json',state)
    meta=state.get('incumbent')
    s=dict(case=graph.stem,q=q,n=n,job=str(folder),job_identity=identity,signature=ident,policy=policy,
           status='ok' if meta else state.get('status','worker_failed'),hard_timeout=timed_out,
           process_seconds=duration,total_job_seconds=time.monotonic()-whole_started,construction_seconds=state.get('construction_seconds'),
           evaluations=state.get('evaluations',0),exit_code=child.returncode,
           stopped=state.get('stopped'),features=state.get('graph_features'))
    if meta:
        result=read(folder/meta['result_file']);raw=result['official_result']
        if result['status']!='ok' or not result['audit']['ok']:raise ValueError('Nonvalidated incumbent checkpoint')
        s.update(makespan=meta['makespan'],plan_hash=meta['plan_hash'],plan=str(folder/meta['plan_file']),
                 result=str(folder/meta['result_file']),certificate=result['audit']['certificate'],
                 cache_hit_rate=raw.get('cache_stats',{}).get('hit_rate'),**raw['data_movement_bytes'])
        completed=[a for a in state['attempts'] if a['status']=='ok']
        prefix3=[a for a in state['attempts'] if a.get('index',999)<=3 and a['status']=='ok']
        s['prefix3_makespan']=min((a['makespan'] for a in prefix3),default=None)
        s['completed_evaluations']=len(completed)
        s['official_eval_seconds']=sum(a.get('eval_seconds',0) for a in state['attempts'])
        s['first_valid_seconds']=min((a['completed_seconds'] for a in completed),default=None)
        s['expanded_construction_seconds']=state.get('expanded_construction_seconds',0)
    if (folder/'worker_error.json').is_file():s['worker_error']=read(folder/'worker_error.json')
    atomic_json(summary_file,s)
    return s


def batch(jobs,workers=2):
    results=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(run_job,**job):job for job in jobs}
        for f in as_completed(futures):
            j=futures[f]
            try:r=f.result()
            except Exception as e:r=dict(status='supervisor_error',error=str(e),q=j['q'],n=j['n'],case=Path(j['graph']).stem)
            results.append(r)
            print(f"{r['case']} q{r['q']} n{r['n']} {r['status']} T={r.get('makespan')} calls={r.get('evaluations')} wall={r.get('process_seconds',0):.2f}s",flush=True)
    return results


def machine():
    from .run import hardware_probe
    return {**hardware_probe(),'platform':platform.platform(),'python':sys.version}
