"""Generic one-graph/one-core-count solver, independent of the experiment panel.

FAST and REFINED each evaluate ONE proposed solution, not a measured portfolio.
A failed proposal may use one one-core recovery; its cost is reported explicitly.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from .core import graph,certificate
from .construct import construct,refine,window_optimize
from .official import call,write
from .run import EXPECTED,ROOT,kill_tree
from research_a.model import Plan,read_json,settings


def worker(a):
    start=time.monotonic();cfg=settings(a.config)
    if cfg!=EXPECTED:raise ValueError('Use original fixed configuration; use sensitivity for nonofficial settings')
    g=graph(read_json(a.graph));out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    plan=construct(g,a.cores,a.question,cfg,a.profile)
    details={}
    if a.method=='refined':plan,details=refine(g,plan,a.question,cfg,a.profile)
    elif a.method=='window':plan,details=window_optimize(g,plan,a.question,cfg)
    generation=time.monotonic()-start
    records=[]
    for index,candidate in enumerate((plan,Plan([g.order],[0],a.cores))):
        left=a.seconds-(time.monotonic()-start)
        if left<=0:break
        rec,raw=call(a.code,a.config,a.graph,candidate,a.question,out/f'evaluation_{index}',min(a.eval_seconds,left))
        records.append(rec)
        if rec['status']=='ok':
            write(out/f'{a.graph.stem}_multicore_res.json',candidate.json())
            write(out/'result.json',raw)
            write(out/'certificate.json',certificate(g,candidate,a.question,cfg,raw))
            write(out/'solver.json',dict(status='ok',method=a.method,profile=a.profile,question=a.question,cores=a.cores,
                  generation_seconds=generation,solve_seconds=time.monotonic()-start,evaluations=records,
                  recovery_used=index==1,details=details))
            return
    write(out/'solver.json',dict(status='no_certified_solution',evaluations=records,generation_seconds=generation))
    raise SystemExit(2)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('graph',type=Path)
    p.add_argument('--code',type=Path,required=True);p.add_argument('--config',type=Path,required=True)
    p.add_argument('--cores',type=int,choices=range(1,6),required=True);p.add_argument('--question',type=int,choices=[1,2,3],required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--method',choices=['fast','refined','window'],default='fast')
    p.add_argument('--profile',choices=['balanced','components','locality','spill','cache'],default='balanced')
    p.add_argument('--seconds',type=float,default=60);p.add_argument('--eval-seconds',type=float,default=20)
    p.add_argument('--_worker',action='store_true',help=argparse.SUPPRESS);a=p.parse_args()
    if min(a.seconds,a.eval_seconds)<=0:p.error('Positive time limits required')
    a.graph=a.graph.resolve();a.code=a.code.resolve();a.config=a.config.resolve();a.out=a.out.resolve()
    if a._worker:worker(a);return
    a.out.mkdir(parents=True,exist_ok=False)
    args=[sys.executable,'-X','utf8','-u','-m','research_a_next.solve',str(a.graph),'--code',str(a.code),'--config',str(a.config),
          '--cores',str(a.cores),'--question',str(a.question),'--out',str(a.out),'--method',a.method,'--profile',a.profile,
          '--seconds',str(a.seconds),'--eval-seconds',str(a.eval_seconds),'--_worker']
    with (a.out/'process.log').open('w',encoding='utf-8') as log:
        proc=subprocess.Popen(args,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
             env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8'),start_new_session=os.name!='nt')
        try:proc.wait(timeout=a.seconds)
        except (subprocess.TimeoutExpired,KeyboardInterrupt):
            kill_tree(proc);write(a.out/'interrupted.json',dict(reason='wall_clock_limit_or_user_interrupt'));raise SystemExit(2)
    print(a.out)
    raise SystemExit(proc.returncode)

if __name__=='__main__':main()
