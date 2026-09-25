"""Finish only jobs that never started under the campaign's global deadline.

An interrupted/running/finished trajectory is never restarted or concatenated.
The original queue decision is retained beside the later execution record.
"""
from __future__ import annotations
import argparse,shutil,time
from pathlib import Path
from .continuous_run import read,write,run_queue,export


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',default='.');p.add_argument('--run',required=True)
    p.add_argument('--workers',default='auto');p.add_argument('--total-seconds',type=float,default=600)
    p.add_argument('--pair-seconds',type=float,default=180);p.add_argument('--pair-total-seconds',type=float,default=180)
    a=p.parse_args(argv);a.root=str(Path(a.root).resolve());root=Path(a.run).resolve()
    if not (root/'campaign.json').exists():p.error('Wait for the original campaign to finish; do not compete with its supervisor')
    if (root/'completion.json').exists():p.error('A completion record already exists; do not erase previous budget history')
    if min(a.total_seconds,a.pair_seconds,a.pair_total_seconds)<=0:p.error('Positive bounded completion budget required')
    if a.workers!='auto' and (not a.workers.isdigit() or int(a.workers)<1):p.error('workers must be auto or a positive integer')
    manifest=read(root/'manifest.json');pending=[]
    for item in manifest['jobs']:
        job=root/item['relative_job'];ex=read(job/'execution.json')
        if ex['status']!='not_started_global_deadline':continue
        if (job/'progress.json').exists():raise ValueError(f'Refusing to restart an existing trajectory: {job}')
        req=read(job/'request.json')
        if Path(req['job']).resolve()!=job.resolve():raise ValueError('Completion requires the same workspace paths')
        shutil.copy2(job/'execution.json',job/'unstarted_execution.json');pending.append(req)
    if not pending:
        write(root/'completion.json',dict(jobs=0,total_wall_seconds=0,reason='nothing_unstarted'));return
    write(root/'completion_request.json',dict(jobs=[dict(case=r['case'],q=r['q'],n=r['n']) for r in pending],
          total_seconds=a.total_seconds,pair_total_seconds=a.pair_total_seconds,workers=a.workers,
          restriction='only never-started jobs; no interrupted trajectory is restarted'))
    for name in ('worker_policy.json','pair_worker_policy.json'):
        if (root/name).exists():shutil.copy2(root/name,root/('initial_'+name))
    shutil.copy2(__file__,root/'completion_source.py')
    st=time.monotonic();run_queue(pending,a,root,st+a.total_seconds);solve=time.monotonic()-st
    pair=[r for r in pending if r['q']==3 and (Path(r['job'])/'progress.json').exists() and
          read(Path(r['job'])/'progress.json')['selected']['result_file']]
    ps=time.monotonic();run_queue(pair,a,root,ps+a.pair_total_seconds,pair=True);pairtime=time.monotonic()-ps
    export(root)
    write(root/'completion.json',dict(jobs=len(pending),optimization_wall_seconds=solve,pair_wall_seconds=pairtime,
          total_wall_seconds=time.monotonic()-st,old_evaluator_calls=0,
          semantics='Delayed initial execution, not additional optimization of a completed job'))


if __name__=='__main__':main()
