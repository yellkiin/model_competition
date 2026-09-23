"""Small, CPU-only A experiments. Explicit prepare/run/collect/sensitivity stages.

No main/dev mega-grid. Default six diagnostic cases, 2 and 5 simulated cores,
all THREE questions, with a 30 minute wall-clock cap per machine.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from . import __version__
from .core import graph, normalize, predict, certificate
from .construct import construct, refine, window_optimize, paper_candidates
from .official import call, write
from research_a.model import Plan, settings, read_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ['case_001','case_002','case_044','case_059','case_062','case_083']
EXPECTED = dict(capacity={'L1':524288,'UB':131072},bandwidth=60,
                task_cross_core_wait_cycles=1000,task_same_core_wait_cycles=100,
                cross_core_copy_delay_cycles=500,cache_capacity_bytes=1048576,
                cache_bandwidth_bytes_per_cycle=250)


def locate():
    found = list((ROOT/'题目'/'A题').glob('*附件'))
    if len(found)!=1: raise FileNotFoundError('Locate exactly one A attachment directory; use prepare --archive')
    return found[0]


def prepare(a):
    from research_a.launch import ensure_inputs
    attachment=ensure_inputs(ROOT, a.archive)
    cfg=settings(attachment/'data'/'config.txt')
    if cfg!=EXPECTED: raise ValueError('Formal experiment requires the original fixed A configuration')
    cases=[f'case_{i:03d}' for i in range(1,101)] if a.full else sorted(set(a.cases))
    for name in cases:
        if name not in {f'case_{i:03d}' for i in range(1,101)}: raise ValueError(f'Unknown original case {name}')
    out=a.out.resolve(); out.mkdir(parents=True,exist_ok=True)
    if (out/'manifest.json').exists(): raise FileExistsError('Manifest already exists: use run to resume, or a NEW output root')
    imported={}
    if a.baseline_catalog:
        with a.baseline_catalog.open(encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f):
                key=f"{row['case']}/q{int(row['question'])}/n{int(row['cores'])}"
                if key in imported: raise ValueError(f'Duplicate baseline key {key}')
                src=Path(row['plan_path'])
                if not src.is_absolute(): src=a.baseline_catalog.parent/src
                dst=out/'baseline_plans'/(key.replace('/','_')+'.json')
                dst.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(src,dst)
                imported[key]=str(dst.relative_to(out)).replace('\\','/')
    try:
        revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    except (OSError,subprocess.SubprocessError): revision='unavailable'
    manifest=dict(schema=1,algorithm=__version__,source_revision=revision,cases=cases,
                  cores=[1,2,3,4,5] if a.full else a.cores,questions=[1,2,3],config=cfg,
                  profile=a.profile,eval_seconds=a.eval_seconds,case_seconds=a.case_seconds,
                  max_calls=(100 if a.full and a.max_calls==40 else a.max_calls),formal_scope=a.full,imported=imported,
                  baseline_kind='supplied_plan_where_available' if imported else 'draft_description_reimplementation',
                  panel='full100' if a.full else 'six-purpose-selected diagnostic cases; not an unbiased estimate of full100')
    write(out/'manifest.json',manifest)
    print(out/'manifest.json')


def case_job(root, name):
    m=read_json(root/'manifest.json'); start=time.monotonic(); deadline=start+m['case_seconds']
    attachment=locate(); source=attachment/'data'/f'{name}.json'; cfg=m['config']
    g=graph(read_json(source)); dest=root/'cases'/name; dest.mkdir(parents=True,exist_ok=True)
    state=dict(case=name,rows=[],status='running',calls=0,algorithm=__version__,config=cfg,
               python=platform.python_version(),machine=platform.node())
    def save():
        state['seconds']=time.monotonic()-start; write(dest/'case.json',state)
    cache={}
    def evaluate(plan,q,label):
        key=(q,plan.key() if plan is not None else 'singlecore')
        if key in cache:
            rec,raw=cache[key]
            return {**rec,'original_evaluation_seconds':rec.get('seconds'), 'seconds':0.,'reused_in_this_case':True},raw
        left=deadline-time.monotonic()
        if state['calls']>=m['max_calls'] or left<=.1:
            return dict(status='budget_exhausted',seconds=0.),None
        state['calls']+=1
        with tempfile.TemporaryDirectory(prefix='evaluation_',dir=dest) as td:
            rec,raw=call(attachment/'code',attachment/'data'/'config.txt',source,plan,q,Path(td),
                         min(m['eval_seconds'],max(.1,left)))
        # Preserve every evaluator response and error: temporary stderr must not vanish.
        record_dir=dest/'evaluations'/f'{state["calls"]:03d}_q{q}_{label}'
        write(record_dir/'record.json',rec)
        if raw: write(record_dir/'raw.json',raw)
        cache[key]=(rec,raw)
        return rec,raw
    base,rawbase=evaluate(None,0,'singlecore')
    state['singlecore']=base
    if base['status']=='ok': write(dest/'singlecore.json',rawbase)
    save()
    single=base.get('makespan')
    for n in m['cores']:
        for q in (1,2,3):
            if time.monotonic()>=deadline:
                state['budget_stopped']=True;state['status']='finished';save();return
            job=dest/f'q{q}'/f'n{n}';job.mkdir(parents=True,exist_ok=True)
            if n==1 and q in (1,2):
                row=dict(question=q,cores=n,variant='baseline_by_definition',**base,
                         speedup=1. if single else None,source='original whole-graph no-L2 singlecore')
                state['rows'].append(row);save();continue
            baseline_start=time.monotonic()
            imported=m['imported'].get(f'{name}/q{q}/n{n}')
            candidates=([('supplied_baseline',normalize(g,Plan.load(read_json(root/imported),g)))] if imported
                        else list(paper_candidates(g,n)))
            baseline_generation=time.monotonic()-baseline_start
            generation_start=time.monotonic()
            fast=construct(g,n,q,cfg,m['profile'])
            fast_seconds=time.monotonic()-generation_start
            new,details=(window_optimize(g,fast,q,cfg) if m['profile']=='window'
                         else refine(g,fast,q,cfg,m['profile']))
            generation=time.monotonic()-generation_start
            candidates += [('fast',fast),('refined',new)]
            available=[]
            for label,plan in candidates:
                rec,raw=evaluate(plan,q,label)
                row=dict(question=q,cores=n,variant=label,**rec,
                         generation_seconds=(fast_seconds if label=='fast' else generation-fast_seconds if label=='refined' else baseline_generation),
                         speedup=single/rec['makespan'] if single and rec['status']=='ok' else None)
                write(job/f'{label}_multicore_res.json',plan.json())
                if raw:
                    try:
                        cert=certificate(g,plan,q,cfg,raw,single)
                        row['certificate']=cert
                        write(job/f'{label}_certificate.json',cert)
                    except ArithmeticError as e:
                        row['certificate_error']=str(e)
                        write(job/f'{label}_uncertified_response.json',raw)
                    available.append((rec['makespan'],rec['ddr_accounted_bytes'],label,plan,raw,rec))
                state['rows'].append(row);save()
            # Feasible recovery, only on failure. Counted and reported, not a
            # hidden candidate used to select the fast algorithm by performance.
            if not available:
                fallback=Plan([g.order],[0],n)
                rec,raw=evaluate(fallback,q,'fallback_single')
                state['rows'].append(dict(question=q,cores=n,variant='fallback_single',**rec,
                                         speedup=single/rec['makespan'] if single and raw else None))
                if raw: available.append((rec['makespan'],rec['ddr_accounted_bytes'],'fallback_single',fallback,raw,rec))
                save()
            if available:
                _,_,label,plan,raw,rec=min(available,key=lambda x:x[:3])
                write(job/f'{name}_multicore_res.json',plan.json())
                write(job/'best_result.json',raw)
                write(job/'selected.json',dict(source_variant=label,**rec,
                    certificate=certificate(g,plan,q,cfg,raw,single),
                    speedup=single/rec['makespan'] if single else None,
                    generation_seconds=generation,refinement=details))
                # Freeze the selected Q3 plan when switching L2 off.
                if q==3:
                    pair,praw=evaluate(plan,2,'same_plan_no_l2')
                    paired=dict(status=pair['status'],on=rec['makespan'],off=pair.get('makespan'),
                                cache_ratio=pair['makespan']/rec['makespan'] if praw else None,
                                off_metrics=pair,on_metrics=rec)
                    write(job/'same_plan_cache.json',paired)
                    if praw: write(job/'same_plan_no_l2_result.json',praw)
            print(f'{name} q{q} n{n}: calls={state["calls"]}, selected={label if available else "NONE"}',flush=True)
    state['status']='finished';save()


def kill_tree(proc):
    if proc.poll() is not None: return
    if os.name=='nt':
        subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True)
    else:
        try: os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError: pass
    proc.wait()


def run(a):
    root=a.out.resolve();m=read_json(root/'manifest.json')
    try:
        current=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
    except (OSError,subprocess.SubprocessError): current='unavailable'
    if current!=m.get('source_revision') and 'unavailable' not in (current,m.get('source_revision')):
        raise ValueError('Checkout revision differs from experiment manifest; use the recorded revision or a NEW root')
    if m['algorithm']!=__version__: raise ValueError('Algorithm version changed; prepare a NEW experiment root')
    if not 0<=a.shard_index<a.shard_count or a.workers<1: raise ValueError('Invalid workers/shard parameters')
    deadline=time.monotonic()+60*a.minutes
    cases=[name for i,name in enumerate(m['cases']) if i%a.shard_count==a.shard_index]
    write(root/f'machine_{a.shard_index}.json',dict(machine=platform.node(),python=platform.python_version(),
          implementation=platform.python_implementation(),os=platform.platform(),shard_count=a.shard_count,
          shard_index=a.shard_index,cases=cases,workers=a.workers,minutes=a.minutes,manifest=m))
    active={};lock=threading.Lock();stop=threading.Event()
    def launch(name):
        if stop.is_set(): return name,'cancelled'
        output=root/'cases'/name;output.mkdir(parents=True,exist_ok=True)
        prior=output/'case.json'
        if prior.exists():
            status=read_json(prior)
            if status.get('status')=='finished': return name,'already_finished'
            # Incomplete runs are preserved, never silently overwritten on resume.
            archive=output.with_name(output.name+f'_incomplete_{int(time.time())}')
            shutil.move(output,archive); output.mkdir()
        left=deadline-time.monotonic()
        if left<=0: return name,'not_started_deadline'
        args=[sys.executable,'-X','utf8','-u','-m','research_a_next.run','_case','--out',str(root),'--case',name]
        with (output/'process.log').open('w',encoding='utf-8') as log:
            proc=subprocess.Popen(args,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8'),start_new_session=os.name!='nt')
            with lock: active[name]=proc
            try:
                proc.wait(timeout=min(left,m['case_seconds']+5))
            except (subprocess.TimeoutExpired,KeyboardInterrupt):
                kill_tree(proc)
                write(output/'interrupted.json',dict(status='wall_clock_limit',case=name))
                return name,'wall_clock_limit'
            finally:
                with lock: active.pop(name,None)
            return name,'ok' if proc.returncode==0 else f'process_error_{proc.returncode}'
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures=[pool.submit(launch,name) for name in cases]
        try:
            for future in as_completed(futures): print(*future.result(),flush=True)
        except KeyboardInterrupt:
            stop.set()
            for future in futures: future.cancel()
            with lock:
                for proc in active.values(): kill_tree(proc)
            raise
    from .report import collect
    collect(root)


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare');prep.add_argument('--out',type=Path,required=True)
    prep.add_argument('--archive');prep.add_argument('--cases',nargs='+',default=DEFAULT_CASES)
    prep.add_argument('--cores',type=int,nargs='+',default=[2,5]);prep.add_argument('--full',action='store_true')
    prep.add_argument('--profile',choices=['balanced','components','locality','spill','cache','window','no_memory','no_cache'],default='balanced')
    prep.add_argument('--eval-seconds',type=float,default=20.);prep.add_argument('--case-seconds',type=float,default=600.)
    prep.add_argument('--max-calls',type=int,default=40);prep.add_argument('--baseline-catalog',type=Path)
    r=sub.add_parser('run');r.add_argument('--out',type=Path,required=True);r.add_argument('--workers',type=int,default=2)
    r.add_argument('--minutes',type=float,default=30.);r.add_argument('--shard-index',type=int,default=0);r.add_argument('--shard-count',type=int,default=1)
    c=sub.add_parser('collect');c.add_argument('--out',type=Path,required=True)
    j=sub.add_parser('_case');j.add_argument('--out',type=Path,required=True);j.add_argument('--case',required=True)
    a=p.parse_args()
    if a.command=='prepare':
        if any(n not in range(1,6) for n in a.cores) or len(set(a.cores))!=len(a.cores) or min(a.eval_seconds,a.case_seconds,a.max_calls)<=0: p.error('Invalid cores/budgets')
        prepare(a)
    elif a.command=='run':
        if a.minutes<=0 or a.shard_count<1: p.error('Positive time/shard count required')
        run(a)
    elif a.command=='collect':
        from .report import collect
        collect(a.out.resolve())
    else: case_job(a.out.resolve(),a.case)

if __name__=='__main__': main()
