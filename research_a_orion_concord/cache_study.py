"""Independent non-default hardware study: fixed plan grid, two bounded adaptations.

Formal selected scores/config files are untouched. When invoked by the graph
worker, all calls and saves remain inside that graph's parent deadline.
"""
from __future__ import annotations
import argparse
import time
from pathlib import Path
from .io import read,write,csv_write,score
from .sources import GraphCache,structure_local,memory
from .fifo import propose
from research_a_orion_anytime.engine import OfficialSession,model_config

def study(session,plan,response,out,deadline,event=None):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);write(out/'plan.json',plan)
    rows=[];last_cost=.05;calls=0
    cap=session.cfg.cache_capacity;bw=session.cfg.cache_bandwidth
    def evaluate(p,settings,label):
        nonlocal calls,last_cost
        if time.monotonic()+1.5*last_cost+.1>=deadline:return None
        calls+=1;t=time.monotonic();write(out/f'{calls:03d}_plan.json',p)
        r=session.evaluate(p,3,settings);last_cost=time.monotonic()-t
        write(out/f'{calls:03d}_response.json.gz',r)
        if event:event('sensitivity_evaluation',label=label,seconds=last_cost,status=r['status'])
        return r
    corners=[]
    for scale in (.5,1.,2.):
        for speed in (.5,1.,2.):
            settings=dict(cache_capacity_bytes=int(cap*scale),cache_bandwidth_bytes_per_cycle=bw*speed)
            if scale==speed==1.:
                r=response;kind='default_reused';seconds=0.
            else:
                r=evaluate(plan,settings,'fixed_plan_grid');kind='nondefault_fixed';seconds=last_cost if r else 0.
            row=dict(**settings,mode=kind,status=r['status'] if r else 'not_admitted',seconds=seconds,
                     makespan=score(r)[0] if r and r['status']=='ok' else None,
                     hit_rate=r['official_result']['cache_stats']['hit_rate'] if r and r['status']=='ok' else None)
            rows.append(row);csv_write(out/'sensitivity.csv',rows)
            if r and r['status']=='ok' and scale==speed and scale!=1.:corners.append((settings,r))
    for settings,initial in corners:
        cfg=model_config(session.cfg,3,settings);g=session.graph;gc=GraphCache(g,cfg);n=len(plan['core_schedules'])
        best=initial;bestplan=plan;context=dict(plan=plan,official_result=initial['official_result']);t=time.monotonic()
        local_deadline=min(deadline,t+10.);pool=[iter(memory(g,n,cfg,3,context,gc,local_deadline)),
                                               iter(propose(g,n,cfg,3,context,local_deadline)),
                                               iter(structure_local(g,n,cfg,3,context,local_deadline))]
        for i in range(9):
            if time.monotonic()>=local_deadline:break
            stream=pool[i%3]
            try:c=next(stream)
            except (StopIteration,ValueError):continue
            r=evaluate(c['plan'],settings,'nondefault_adaptation')
            if r and r['status']=='ok' and score(r)<score(best):best,bestplan=r,c['plan']
        label=f'adapt_{settings["cache_capacity_bytes"]}_{settings["cache_bandwidth_bytes_per_cycle"]}'
        write(out/(label+'_plan.json'),bestplan);write(out/(label+'_response.json.gz'),best)
        rows.append(dict(**settings,mode='nondefault_adapted',status='ok',seconds=time.monotonic()-t,
            makespan=score(best)[0],hit_rate=best['official_result']['cache_stats']['hit_rate']))
        csv_write(out/'sensitivity.csv',rows)
    write(out/'study.json',dict(original_calls=calls,formal_default_unchanged=True,rows=len(rows)))
    return rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--out',required=True)
    p.add_argument('--seconds',type=float,default=60);a=p.parse_args()
    from .report import graph_rows
    job=Path(a.job);req=read(job/'request.json');rows,_,_=graph_rows(job)
    row=max((r for r in rows if r['q']==3),key=lambda r:r['n'])
    session=OfficialSession(req['official'],req['graph'],req['config'])
    study(session,read(row['plan_file']),read(row['result_file']),a.out,time.monotonic()+a.seconds)
if __name__=='__main__':main()
