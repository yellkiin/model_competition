"""Complete only NEVER-STARTED experiment jobs under an explicit new total deadline.

Already-started/finished search trajectories are never restarted or extended.
Per-job budgets and requests remain unchanged. Original stop records are kept.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import time
from .run import read, run_queue, summarize, atomic_json


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',required=True);p.add_argument('--seconds',type=float,default=900)
    p.add_argument('--workers',default='2');a=p.parse_args(argv)
    if a.seconds<=0:p.error('positive total deadline required')
    root=Path(a.run).resolve();started=time.monotonic();deadline=started+a.seconds;log=[]
    manifest=read(root/'manifest.json')
    if str(manifest['argv']['workers'])!=a.workers:p.error('keep the original requested concurrency for matched comparisons')
    requests=[read(f) for mode in ('warm_start','cold_start') for f in (root/mode).glob('*/*/request.json')]
    pending=[];history=root/'completion_history'/str(time.time_ns());history.mkdir(parents=True)
    if (root/'campaign_status.json').exists():atomic_json(history/'previous_campaign_status.json',read(root/'campaign_status.json'))
    atomic_json(history/'request.json',dict(total_seconds=a.seconds,workers=a.workers,
        rule='only never-started jobs; completed and interrupted trajectories unchanged'))
    def admit(req):
        ep=Path(req['job'])/'execution.json'
        if not ep.exists():return True
        old=read(ep)
        if old.get('status')!='not_started_global_deadline':return False
        dst=history/Path(req['job']).relative_to(root)/'previous_execution.json'
        atomic_json(dst,old);return True
    for r in requests:
        if admit(r):pending.append(r)
    run_queue(pending,a.workers,deadline,log)
    pairs=[]
    for r in requests:
        job=Path(r['job'])
        if r['q']!=3 or not (job/'progress.json').exists():continue
        meta=read(job/'progress.json').get('incumbent')
        if not meta:continue
        pair={**r,'method':'pair','job':str(job/'no_l2'),
              'plan':str(job/meta['plan_file']),'seconds':manifest['argv']['pair_seconds']}
        if admit(pair):pairs.append(pair)
    run_queue(pairs,a.workers,deadline,log)
    baselines={f.parent.name:read(f)['makespan'] for f in (root/'baselines').glob('*/progress.json')}
    rows=summarize(root,requests,root.name,baselines)
    atomic_json(history/'worker_policy.json',log)
    status=dict(requested_configs=len(manifest['usable_cases'])*len(manifest['argv']['cores'])*len(manifest['argv']['questions']),
        recorded_rows=len(rows),ok_rows=sum(r['status']=='ok' for r in rows),
        paired_q3=sum(r['q']==3 and r['pair_status']=='ok' for r in rows),
        originally_stopped_global_deadline=True,completion_limit_seconds=a.seconds,
        completion_wall_seconds=time.monotonic()-started,completion_deadline_reached=time.monotonic()>=deadline,
        never_started_search_jobs_completed=len(pending),same_plan_pairs_attempted=len(pairs),
        formal_100_graph_complete=False,requested_priority_gate_passed=False)
    atomic_json(root/'campaign_status.json',status);print(status)

if __name__=='__main__':main()
