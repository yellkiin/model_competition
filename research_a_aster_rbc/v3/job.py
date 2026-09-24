"""One real job, with monotone official incumbent and same-plan cache replay."""
from __future__ import annotations
import json
import math
from pathlib import Path
import shutil
import time
import traceback
from .model import Graph,read_json
from .policy import VERSION,build,recipes,profile,view,bound_and_proxy,neighbors
from .session import Session,dump,settings


def run_job(request,folder,global_deadline):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    dump(folder/'request.json',request)
    started=time.monotonic();deadline=min(global_deadline,started+request['job_seconds'])
    q,n=request['q'],request['n'];cfg=settings(request['config'])
    state=dict(case=request['case'],q=q,n=n,version=VERSION,status='running',attempts=[],incumbent=None,
               fast=None,cache_pair=None,construction_errors=[],stop_reason=None)
    session=Session(request['code'],request['graph'],request['config'],folder)
    best_plan=None;best_key=(math.inf,math.inf);seen=set();calls=0
    def checkpoint():state['solve_seconds']=time.monotonic()-started;dump(folder/'result.json',state)
    checkpoint()
    try:
        g=Graph(read_json(request['graph']));state['features']=g.features(n);state['profile']=profile(g,n,cfg)
        state['global_compute_lower']=g.lower_bound(n);checkpoint()
        def evaluate(plan,label,question,recipe=None):
            nonlocal best_plan,best_key,calls
            if time.monotonic()>=deadline:return None
            index=len(state['attempts']);stem=f'e{index:03d}'
            plan_path=folder/(stem+'_plan.json');raw_path=folder/(stem+'_official.json.gz')
            if plan is not None:
                view(g,plan)
                if question==q:
                    key=json.dumps(plan,sort_keys=True,separators=(',',':'))
                    if key in seen:return None
                    seen.add(key)
                dump(plan_path,plan)
            if question==q and plan is not None and state['incumbent']:
                certificate=bound_and_proxy(g,plan,q,cfg)
                if certificate['certified_candidate_lower']>best_key[0]:
                    state['attempts'].append(dict(label=label,q=question,status='bound_pruned',recipe=recipe,**certificate));checkpoint();return None
            row=dict(label=label,q=question,status='running',recipe=recipe,plan_file=plan_path.name if plan else None,raw_file=raw_path.name)
            state['attempts'].append(row);checkpoint();calls+=1
            call_deadline=search_deadline if q==3 and question==q else deadline
            row.update(session.evaluate(question,plan_path,raw_path,min(request['eval_seconds'],max(.01,call_deadline-time.monotonic()))))
            if row['status']=='ok' and question==q:
                objective=(row['makespan'],row.get('added_copy_bytes') or 0)
                if objective<best_key:
                    best_plan,best_key=plan,objective
                    state['incumbent']=dict(row)
                    if plan is not None:dump(folder/'best_plan.json',plan)
                    tmp=folder/'best_official.json.gz.tmp';shutil.copyfile(raw_path,tmp);tmp.replace(folder/'best_official.json.gz')
                if label=='fast':state['fast']=dict(row,available_seconds=time.monotonic()-started)
            row['best_makespan']=None if state['incumbent'] is None else best_key[0]
            checkpoint();return row
        if q==0:
            evaluate(None,'original_singlecore',0)
            state['status']='complete' if state['incumbent'] else 'failed';state['stop_reason']='baseline';return state
        reserve=min(request['eval_seconds'],request['job_seconds']/3) if q==3 else 0.
        search_deadline=deadline-reserve
        search_cap=request['budget']-int(q==3)
        for i,spec in enumerate(recipes(g,n,q,cfg)):
            if calls>=search_cap or time.monotonic()>=search_deadline:break
            if request.get('mode')=='fast' and i>0 and state['incumbent']:break
            st=time.monotonic()
            try:
                plan=build(g,n,q,cfg,spec)
                construction=time.monotonic()-st
                row=evaluate(plan,'fast' if i==0 else 'constructive',q,spec)
                if row is not None:row['construction_seconds']=construction
            except (ValueError,KeyError,TypeError) as e:
                state['construction_errors'].append(dict(recipe=spec,error=str(e),traceback=traceback.format_exc()))
            checkpoint()
            if state['incumbent'] and best_key[0]<=g.lower_bound(n)*(1+request['gap_tolerance']):
                state['stop_reason']='global_compute_gap';break
        # Fallback is only for genuine construction/evaluation failure.
        if best_plan is None and calls<search_cap and time.monotonic()<search_deadline:
            evaluate(build(g,n,q,cfg,dict(kind='serial',active=n)),'serial_fallback',q)
        while request.get('mode')!='fast' and best_plan is not None and not state['stop_reason'] and calls<search_cap and time.monotonic()<search_deadline:
            before=calls
            for label,proposal,proxy in neighbors(g,best_plan,q,cfg,state['incumbent']):
                if calls>=search_cap or time.monotonic()>=search_deadline:break
                item=evaluate(proposal,'directed_'+label,q)
                if item is not None:item['proxy']=proxy
            if calls==before:state['stop_reason']='neighbourhood_exhausted';break
        if q==3 and best_plan is not None and calls<request['budget'] and time.monotonic()<deadline:
            paired=evaluate(best_plan,'same_plan_no_cache',2)
            if paired and paired['status']=='ok':
                state['cache_pair']=dict(with_cache=best_key[0],without_cache=paired['makespan'],ratio=paired['makespan']/best_key[0] if best_key[0]>0 else None,
                    plan_file='best_plan.json',without_cache_raw_file=paired['raw_file'])
        state['status']='complete' if state['incumbent'] and (q!=3 or state['cache_pair']) else ('partial' if state['incumbent'] else 'failed')
        if state['incumbent']:
            lb=g.lower_bound(n);state['upper_bound']=best_key[0];state['bound_violation']=lb>best_key[0]+1e-8
            state['instance_ratio_upper']=best_key[0]/lb if lb>0 and not state['bound_violation'] else None
        state['stop_reason']=state['stop_reason'] or ('evaluation_cap' if calls>=search_cap else 'wall_or_recipe_limit')
    except Exception:
        state['status']='partial' if state['incumbent'] else 'failed'
        state['error']=traceback.format_exc();dump(folder/'worker_error.json',dict(error=state['error']))
    finally:
        session.close();state['official_calls']=calls;checkpoint()
    return state
