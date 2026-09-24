"""Direct bounded A experiments. No smoke/unit/hash/audit prerequisite."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
import csv
from datetime import datetime,timezone
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import time
from .job import run_job
from .model import read_json
from .policy import VERSION
from .session import dump

ROOT=Path(__file__).resolve().parents[2]
from .reporting import aggregate


def official_path(explicit):
    if explicit:return Path(explicit).expanduser().resolve()
    found=sorted((ROOT/'题目'/'A题').glob('*附件'))
    if len(found)!=1:raise ValueError('Provide --official-dir with the A attachment directory (containing code/ and data/).')
    return found[0]


def available(path):
    if not path.is_file():return False
    with path.open('rb') as f:head=f.read(128)
    return bool(head) and not head.startswith(b'version https://git-lfs.github.com/spec/v1')


def main(argv=None):
    run_started=time.monotonic()
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--official-dir');p.add_argument('--cases',type=int,nargs='+',default=[1,2,16,44,59,71,83])
    p.add_argument('--all-cases',action='store_true');p.add_argument('--cores',type=int,nargs='+',default=[5])
    p.add_argument('--questions',type=int,nargs='+',default=[1,2,3]);p.add_argument('--workers',type=int,default=2)
    p.add_argument('--wall-seconds',type=float,default=1800);p.add_argument('--job-seconds',type=float,default=90)
    p.add_argument('--eval-seconds',type=float,default=45);p.add_argument('--budget',type=int,default=8)
    p.add_argument('--gap-tolerance',type=float,default=.03);p.add_argument('--mode',choices=['full','fast'],default='full')
    p.add_argument('--shards',type=int,default=1);p.add_argument('--shard',type=int,default=0)
    p.add_argument('--out');p.add_argument('--resume',action='store_true')
    args=p.parse_args(argv)
    if args.workers<1 or min(args.wall_seconds,args.job_seconds,args.eval_seconds)<=0 or args.budget<2:p.error('positive caps/workers and budget >=2 required')
    if args.shards<1 or not 0<=args.shard<args.shards:p.error('invalid shard')
    if not 0<=args.gap_tolerance<1:p.error('invalid gap tolerance')
    if any(n<1 or n>5 for n in args.cores) or any(q not in (1,2,3) for q in args.questions):p.error('cores 1..5, questions 1..3')
    official=official_path(args.official_dir);config=official/'data/config.txt';code=official/'code'
    cases=list(range(1,101)) if args.all_cases else sorted(set(args.cases))
    cases=[c for i,c in enumerate(cases) if i%args.shards==args.shard]
    if not cases:p.error('empty case selection')
    required=[config]+[official/f'data/case_{c:03d}.json' for c in cases]
    required += [code/x for x in ('contest_io.py','evaluation_validation.py','schedule_step1.py','schedule_step2.py','schedule_step3.py','singlecore_evaluate.py','multicore_cut_evaluate_problem_1.py','multicore_cut_evaluate_problem_2.py','multicore_cut_evaluate_problem_3.py')]
    missing=[str(x) for x in required if not available(x)]
    if missing:raise ValueError('Required A inputs are missing/LFS pointers. Restore only A from its ZIP or Git LFS; then repeat the command. First missing: '+missing[0])
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%f')
    out=Path(args.out).resolve() if args.out else ROOT/'research_a_aster_rbc'/'runs'/f'v3_{stamp}_{os.getpid()}'
    settings=dict(version=VERSION,cases=cases,cores=sorted(set(args.cores)),questions=sorted(set(args.questions)),
                  job_seconds=args.job_seconds,eval_seconds=args.eval_seconds,budget=args.budget,gap_tolerance=args.gap_tolerance,mode=args.mode,
                  official_dir=str(official),config_text=config.read_text(encoding='utf-8-sig'),shards=args.shards,shard=args.shard)
    jobs=[]
    for c in cases:
        jobs.append(dict(id=f'case_{c:03d}_q0_n1',case=c,q=0,n=1))
        for n in settings['cores']:
            for q in settings['questions']:jobs.append(dict(id=f'case_{c:03d}_q{q}_n{n}',case=c,q=q,n=n))
    manifest=dict(settings=settings,jobs=jobs,machine=platform.node(),python=sys.version,created_utc=stamp)
    if args.resume:
        old=read_json(out/'manifest.json')
        if old['settings']!=settings:raise ValueError('Resume requires identical protocol and config text. Use a new directory for changes.')
        manifest=old
    else:
        out.mkdir(parents=True,exist_ok=False);dump(out/'manifest.json',manifest)
    pending=[job for job in jobs if not (out/job['id']).exists()]
    deadline=time.monotonic()+args.wall_seconds;active={};cursor=0
    print(f'Output: {out}; unstarted jobs: {len(pending)}',flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        while active or (cursor<len(pending) and time.monotonic()<deadline):
            while len(active)<args.workers and cursor<len(pending) and time.monotonic()<deadline:
                job=pending[cursor];cursor+=1
                request=dict(job,graph=str(official/f'data/case_{job["case"]:03d}.json'),config=str(config),code=str(code),
                    job_seconds=args.job_seconds,eval_seconds=args.eval_seconds,budget=args.budget,gap_tolerance=args.gap_tolerance,mode=args.mode)
                active[pool.submit(run_job,request,out/job['id'],deadline)]=job
            if not active:break
            done,_=wait(active,timeout=.25,return_when=FIRST_COMPLETED)
            for f in done:
                job=active.pop(f)
                try:r=f.result();print(f'{job["id"]}: {r["status"]}, U={(r.get("incumbent") or {}).get("makespan")}',flush=True)
                except Exception as e:
                    print(f'{job["id"]}: controller error {e}',flush=True)
                    path=out/job['id']/'result.json'
                    old=read_json(path) if path.exists() else dict(case=job['case'],q=job['q'],n=job['n'],attempts=[],incumbent=None)
                    old.update(status='partial' if old.get('incumbent') else 'failed',controller_error=str(e));dump(path,old)
    aggregate(out,manifest)
    dump(out/'run_receipt.json',dict(elapsed_wall_seconds=time.monotonic()-run_started,requested_wall_seconds=args.wall_seconds,workers=args.workers,version=VERSION,resume=args.resume))
    print(f'Finished bounded request: {out / "REPORT.md"}',flush=True)
    return out


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError) as e:raise SystemExit(str(e))
