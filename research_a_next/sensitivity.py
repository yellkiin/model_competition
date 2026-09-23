"""Small Q3 capacity/bandwidth study, separate from the fixed official score.

Two selected cases, five axis points (not a 2D exhaustive grid). At each point
compare the same default plan and an adapted constructor; <=20 evaluator calls.
"""
from __future__ import annotations
import argparse
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import time
from .core import graph, normalize
from .construct import construct
from .official import call,write
from .report import csv_write
from .run import locate, ROOT, kill_tree
from research_a.model import Plan,read_json


def config_text(cfg):
    return ('[capacity]\nL1 {capacity[L1]}\nUB {capacity[UB]}\n'
            '[bandwidth]\nbandwidth {bandwidth}\n[multicore_scene_a]\n'
            'task_cross_core_wait_cycles {task_cross_core_wait_cycles}\ntask_same_core_wait_cycles {task_same_core_wait_cycles}\n'
            '[multicore_scene_b]\ncross_core_copy_delay_cycles {cross_core_copy_delay_cycles}\n'
            '[problem_3]\ncache_capacity_bytes {cache_capacity_bytes}\n'
            'cache_bandwidth_bytes_per_cycle {cache_bandwidth_bytes_per_cycle}\n').format(**cfg)


def worker(a):
    source=a.source.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    m=read_json(source/'manifest.json');attachment=locate();deadline=time.monotonic()+60*a.minutes
    points=[('default',1,1),('half_capacity',.5,1),('double_capacity',2,1),('half_bandwidth',1,.5),('double_bandwidth',1,2)]
    rows=[]
    for name in a.cases:
        planpath=source/'cases'/name/'q3'/f'n{a.cores}'/f'{name}_multicore_res.json'
        if not planpath.exists():
            rows.append(dict(case=name,status='missing_default_plan'));continue
        path=attachment/'data'/f'{name}.json';g=graph(read_json(path));fixed=normalize(g,Plan.load(read_json(planpath),g))
        for point,cap,bw in points:
            cfg=dict(m['config'],cache_capacity_bytes=int(m['config']['cache_capacity_bytes']*cap),
                     cache_bandwidth_bytes_per_cycle=int(m['config']['cache_bandwidth_bytes_per_cycle']*bw))
            folder=out/name/point;folder.mkdir(parents=True)
            config=folder/'config.txt';config.write_text(config_text(cfg),encoding='utf-8')
            if time.monotonic()>=deadline:
                rows.append(dict(case=name,point=point,status='not_started_deadline'));continue
            adjusted=construct(g,a.cores,3,cfg,profile='cache')
            cache={}
            for variant,plan in [('same_default_plan',fixed),('adapted_constructor',adjusted)]:
                left=deadline-time.monotonic()
                if left<=0:rec,raw=dict(status='not_started_deadline'),None
                elif plan.key() in cache:rec,raw=cache[plan.key()]
                else:
                    with tempfile.TemporaryDirectory(dir=folder) as td:
                        rec,raw=call(attachment/'code',config,path,plan,3,Path(td),min(a.eval_seconds,left))
                    cache[plan.key()]=(rec,raw)
                row=dict(case=name,point=point,variant=variant,**rec,
                         cache_capacity_bytes=cfg['cache_capacity_bytes'],cache_bandwidth=cfg['cache_bandwidth_bytes_per_cycle'],
                         scope='official_default_anchor' if point=='default' else 'NONOFFICIAL_PARAMETER_SENSITIVITY')
                if raw:
                    write(folder/f'{variant}_result.json',raw);write(folder/f'{variant}_plan.json',plan.json())
                    if point=='default' and variant=='same_default_plan':
                        original=read_json(planpath.parent/'best_result.json')
                        row['anchor_matches_original']=raw['makespan']==original['makespan']
                        if not row['anchor_matches_original']:
                            write(folder/'anchor_mismatch.json',dict(original=original['makespan'],new=raw['makespan']))
                            raise RuntimeError('Default anchor differs; preserve outputs and check local source/config versions')
                rows.append(row);csv_write(out/'sensitivity.csv',rows)
    csv_write(out/'sensitivity.csv',rows)
    write(out/'scope.json',dict(experiment='Q3 mechanism only',fixed_official_scores_unchanged=True,
          expected_rows=len(a.cases)*len(points)*2,completed_rows=sum(r.get('status')=='ok' for r in rows),
          not_a_full100_score=True,axes='five isolated axis points; no continuous optimum claim'))
    print(out/'sensitivity.csv')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--cases',nargs='+',default=['case_044','case_083']);p.add_argument('--cores',type=int,default=5)
    p.add_argument('--minutes',type=float,default=10);p.add_argument('--eval-seconds',type=float,default=20)
    p.add_argument('--_worker',action='store_true',help=argparse.SUPPRESS);a=p.parse_args()
    if min(a.minutes,a.eval_seconds)<=0 or a.cores not in range(1,6):raise ValueError('Invalid limits')
    a.source=a.source.resolve();a.out=a.out.resolve()
    if a._worker:worker(a);return
    a.out.mkdir(parents=True,exist_ok=False)
    command=[sys.executable,'-X','utf8','-u','-m','research_a_next.sensitivity',
        '--source',str(a.source),'--out',str(a.out),'--cases',*a.cases,'--cores',str(a.cores),
        '--minutes',str(a.minutes),'--eval-seconds',str(a.eval_seconds),'--_worker']
    with (a.out/'process.log').open('w',encoding='utf-8') as log:
        proc=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8'),start_new_session=os.name!='nt')
        try:proc.wait(timeout=60*a.minutes)
        except (subprocess.TimeoutExpired,KeyboardInterrupt):
            kill_tree(proc)
            write(a.out/'interrupted.json',dict(status='wall_clock_limit_or_user_interrupt',complete=False))
            raise SystemExit(2)
    print(a.out/'sensitivity.csv')
    raise SystemExit(proc.returncode)

if __name__=='__main__':main()
