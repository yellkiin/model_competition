"""Three-host scheduler; one child per graph, one <=600s cap for ALL its keys.

No repeated whole-repository checks. --keys makes targeted real experiments;
formal default is 14 original main rows + 5 exact-plan Q3/Q2 pairs per graph.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from .io import read,write,csv_write,utc,ROOT,PACKAGE,attachment
from .resources import Budget

def required(questions=(1,2,3),cores=(1,2,3,4,5)):
    return [(q,n) for n in cores for q in questions if n>1 or q==3]

def launch(req,cap):
    out=Path(req['out']);out.mkdir(parents=True,exist_ok=False)
    req=dict(req,seconds=cap,launch_epoch=time.time())
    write(out/'request.json',req)
    logs=[(out/n).open('w',encoding='utf-8') for n in ('stdout.txt','stderr.txt')]
    started=time.monotonic()
    child=subprocess.Popen([sys.executable,'-m','research_a_orion_concord.engine',str(out/'request.json')],
        cwd=ROOT,stdout=logs[0],stderr=logs[1],env={**os.environ,'PYTHONUTF8':'1',
        'PYTHONHASHSEED':'0','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'})
    return dict(process=child,start=started,cap=cap,req=req,logs=logs,peak_rss=0)

def finish(task,hard=False):
    p=task['process']
    if p.poll() is None:p.kill()
    p.wait()
    for f in task['logs']:f.close()
    receipt=dict(case=task['req']['case'],process_seconds=time.monotonic()-task['start'],
                 exit_code=p.returncode,hard_deadline=hard,peak_rss_bytes=task['peak_rss'],
                 cap_seconds=task['cap'],finished_utc=utc())
    write(Path(task['req']['out'])/'process.json',receipt)
    return receipt

def execute(requests,wall_seconds,reserve=.25,workers=None,telemetry=None):
    deadline=time.monotonic()+wall_seconds;budget=Budget(reserve,workers)
    queue=list(requests);active=[];receipts=[];metrics=[];sample_at=0.;slots=1
    try:
        while (queue or active) and time.monotonic()<deadline:
            now=time.monotonic()
            if now>=sample_at:
                slots,m=budget.sample(active);metrics.append(m);sample_at=now+2
                if telemetry:csv_write(telemetry,metrics)
            for t in list(active):
                done=t['process'].poll() is not None
                hard=now-t['start']>=t['cap']
                if done or hard:
                    receipts.append(finish(t,hard and not done));active.remove(t)
            while queue and len(active)<slots:
                req=queue.pop(0);left=deadline-time.monotonic()
                # Do not silently shorten a last job and call it equal-budget.
                if left<req['seconds']+.5:
                    receipts.append(dict(case=req['case'],status='not_admitted_total_deadline'));continue
                active.append(launch(req,req['seconds']))
            time.sleep(.1 if active else 1.)
        for t in active:receipts.append(finish(t,True))
        for r in queue:receipts.append(dict(case=r['case'],status='not_started_total_deadline'))
    except BaseException:
        for t in active:finish(t,True)
        raise
    return receipts,budget.policy

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cases',nargs='+');p.add_argument('--keys',nargs='+',help='q:n, same subset per selected graph')
    p.add_argument('--manifest');p.add_argument('--shard',type=int,choices=[0,1,2],default=0)
    p.add_argument('--catalog',required=True);p.add_argument('--official')
    p.add_argument('--out',required=True);p.add_argument('--mode',choices=['SMF','SM','SF','MF','S','M','F'],default='SMF')
    p.add_argument('--seconds',type=float,default=600);p.add_argument('--wall-seconds',type=float,default=43200)
    p.add_argument('--max-evaluations',type=int,default=64);p.add_argument('--max-proposals',type=int,default=256)
    p.add_argument('--workers',default='auto');p.add_argument('--reserve',type=float,default=.25)
    p.add_argument('--phase',choices=['gate','full','targeted'],default='full')
    p.add_argument('--resume',action='store_true');p.add_argument('--no-diagnostics',action='store_true');p.add_argument('--allow-cold',action='store_true');p.add_argument('--with-studies',action='store_true')
    a=p.parse_args()
    if not 0<a.seconds<=600 or a.wall_seconds<=0 or not .25<=a.reserve<1:p.error('seconds must be in (0,600], reserve >=25%')
    workers=None if a.workers=='auto' else int(a.workers)
    if workers is not None and workers<1:p.error('workers must be auto or positive')
    official=attachment(a.official)
    if not (official/'code/evaluation_validation.py').is_file():p.error('Original evaluator is missing')
    manifest=read(a.manifest) if a.manifest else None
    cases=a.cases or (manifest['shards'][str(a.shard)]['cases'] if manifest else None)
    if not cases:p.error('Supply --cases or --manifest')
    cases=[f'case_{int(c.removeprefix("case_")):03d}' for c in cases]
    all_cases=list(cases)
    if a.phase=='gate':cases=cases[:1]
    keys=[tuple(map(int,k.split(':'))) for k in a.keys] if a.keys else required()
    if any(q not in (1,2,3) or not 1<=n<=5 or (n==1 and q!=3) for q,n in keys):p.error('Invalid q:n')
    if not a.allow_cold:
        from .seeds import load_catalog
        have={(r['case'],r['q'],r['n']) for r in load_catalog(a.catalog)['entries']}
        missing=[(c,q,n) for c in cases for q,n in [(0,1)]+keys if (c,q,n) not in have]
        if missing:p.error(f'Prepare real reference plans first, or use --allow-cold for a separate cold experiment: {missing[:8]}')
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    policy=dict(version='concord-1.2',mode=a.mode,keys=keys,seconds=a.seconds,
                max_evaluations=a.max_evaluations,max_proposals=a.max_proposals,reserve=a.reserve,diagnostics=not a.no_diagnostics,allow_cold=a.allow_cold,with_studies=a.with_studies)
    existing=out/'campaign.json'
    if existing.exists():
        previous=read(existing)
        if not a.resume or json.loads(json.dumps(policy))!=previous['policy']:
            p.error('Existing run: pass --resume with unchanged policy or choose a new output root')
        start_epoch=previous['start_epoch'];deadline_epoch=previous['deadline_epoch']
    else:
        start_epoch=time.time();deadline_epoch=start_epoch+a.wall_seconds
        write(existing,dict(created_utc=utc(),start_epoch=start_epoch,deadline_epoch=deadline_epoch,
            policy=policy,shard=a.shard,cases=all_cases,manifest=a.manifest,python=sys.version,
            platform=platform.platform(),scope='one cap for a graph including all requested q/n and pairs'))
    requests=[]
    for case in cases:
        graph=official/'data'/f'{case}.json'
        if not graph.is_file():p.error(f'Restore original graph: {graph}')
        folder=out/'graphs'/case
        if folder.exists():
            # Completed or interrupted trajectories are never overwritten/restarted.
            continue
        requests.append(dict(case=case,graph=str(graph),official=str(official),
            config=str(official/'data/config.txt'),catalog=str(Path(a.catalog).resolve()),
            keys=keys,mode=a.mode,seconds=a.seconds,out=str(folder),max_evaluations=a.max_evaluations,
            max_proposals=a.max_proposals,diagnostics=not a.no_diagnostics,
            cache_study=a.with_studies and case in (manifest['shards'][str(a.shard)].get('study_cases',[]) if manifest else cases[:1]),source_revision='055bb20a3b660f23d2179d732c82234aa1e8ba0a'))
    receipts,resource=execute(requests,max(.01,deadline_epoch-time.time()),a.reserve,workers,out/'resources.csv')
    write(out/f'dispatch_{time.time_ns()}.json',dict(receipts=receipts,resource_policy=resource))
    from .report import collect
    summary=collect(out,expected_cases=cases,keys=keys)
    print(json.dumps(summary,ensure_ascii=False))
    return 0 if summary['complete'] else 3

if __name__=='__main__':raise SystemExit(main())
