"""ORION-A: monotone-incumbent, time-bounded multiresolution local search.

First 3 evaluations reproduce the v1 selection logic (unless a seed is supplied).
Then stage/fine candidates and joint windows expand its search space. Every
completed incumbent is independently checked and checkpointed before continuing.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import gzip
import json
import math
from pathlib import Path
import statistics
import sys
import time
import traceback
from .core import constructors,neighbours,fingerprint,bounds,one_core,estimate
from .strategies import stage_candidates,fine_candidates,joint_window,memory_window_order,mutations
from .engine import OfficialSession,model_config
from .worker import atomic_json


def read(path):
    p=Path(path)
    if p.suffix=='.gz':
        with gzip.open(p,'rt',encoding='utf8') as f:return json.load(f)
    return json.loads(p.read_text(encoding='utf-8-sig'))


def compressed(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp')
    with gzip.open(tmp,'wt',encoding='utf8',compresslevel=3) as f:json.dump(value,f,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    tmp.replace(p)


def solve(request):
    out=Path(request['job']);out.mkdir(parents=True,exist_ok=True)
    started=time.monotonic();deadline=started+request['seconds'];q=request['q'];n=request['n']
    state=dict(status='initializing',q=q,n=n,case=request['case'],identity=request['identity'],attempts=[],
               construction_errors=[],incumbent=None,stopped=None,cache_overrides=request.get('cache_overrides'),source='unmodified official evaluator')
    atomic_json(out/'progress.json',state)
    session=OfficialSession(request['official'],request['graph'],request['config'])
    g,cfg=session.graph,model_config(session.cfg,q,request.get('cache_overrides'))
    state['graph_features']={'ops':len(g.ops),'components':len(g.components),'max_component':max(map(len,g.components),default=0)}
    best=None;seen=set();ratios=defaultdict(list);family_calls=defaultdict(int);pool=[]
    seed=request.get('seed_job')
    if seed:
        sp=read(Path(seed)/'progress.json');meta=sp.get('incumbent')
        if meta:
            seed_result=read(Path(seed)/meta['result_file']);seed_plan=read(Path(seed)/meta['plan_file'])
            # Controller verifies all content/version identities before sending this seed.
            best=dict(meta=meta,result=seed_result,plan=seed_plan,name='seed_incumbent')
            new_result='incumbents/seed_result.json.gz';new_plan='incumbents/seed_plan.json'
            compressed(out/new_result,seed_result);atomic_json(out/new_plan,seed_plan)
            state['incumbent']={**meta,'result_file':new_result,'plan_file':new_plan,'elapsed_seconds':0.0,'from_seed':True}
            state['seed_hash']=fingerprint(seed_plan)
            seen={a['plan_hash'] for a in sp['attempts'] if a['status'] in ('ok','certified_pruned')}
            seen.add(fingerprint(seed_plan))
    def add(cs):
        existing={fingerprint(c['plan']) for c in pool}
        for c in cs:
            h=fingerprint(c['plan'])
            if h not in existing and h not in seen:
                c.setdefault('family','frontier');pool.append(c);existing.add(h)
        # Bounded memory. Pruning this queue is heuristic, NOT optimality certification.
        if len(pool)>96:
            ordered=sorted(pool,key=lambda c:(c['proxy'].get('score',0),c['name']))
            # Keep representatives even when an uncalibrated family looks expensive.
            # Otherwise low-biased local proxies can evict an entire new constructor.
            quota=defaultdict(int);retained=[];rest=[]
            for c in ordered:
                if quota[c['family']]<2:retained.append(c);quota[c['family']]+=1
                else:rest.append(c)
            pool[:]=retained+rest[:max(0,96-len(retained))]
    if request.get('fixed_plan'):
        plan=read(request['fixed_plan'])
        add([dict(name='fixed_plan_counterfactual',plan=plan,proxy={},bounds=bounds(g,cfg,n,max(q,1),plan),family='fixed')])
    elif q==0:
        plan=one_core(g,1)
        add([dict(name='official_original_singlecore',plan=plan,proxy={},bounds=bounds(g,cfg,1,1,plan),family='singlecore')])
    else:
        add(constructors(g,n,cfg,q,diagnostics=state['construction_errors']))
        if best:add(neighbours(g,best['plan'],cfg,q,best['result']['official_result']))
    state['construction_seconds']=time.monotonic()-started
    enhanced=request.get('strategy','anytime')=='anytime' and q>0 and not request.get('fixed_plan')
    expanded=False;calls=0;round_no=0;stall=0;elite=[]
    def checkpoint():
        state['elapsed_seconds']=time.monotonic()-started
        state['evaluations']=calls
        atomic_json(out/'progress.json',state)
    while time.monotonic()<deadline and calls<request.get('max_evaluations',64):
        if enhanced and (calls>=3 or seed) and not expanded:
            expanded=True
            expansion_started=time.monotonic()
            # Finite new constructor pool, generated lazily with time checks.
            streams=[]
            if not request.get('no_stage'):streams.append(stage_candidates(g,n,cfg,q,not request.get('no_dp')))
            streams.append(fine_candidates(g,n,cfg,q))
            for stream in streams:
                for c in stream:
                    if time.monotonic()>=deadline:break
                    add([c])
            state['expanded_construction_seconds']=time.monotonic()-expansion_started
        if not pool:
            if not enhanced or best is None:state['stopped']='candidate_space_exhausted';break
            round_no+=1
            if round_no>32:state['stopped']='neighbourhood_round_cap';break
            add(list(mutations(g,best['plan'],cfg,q,best['result']['official_result'],round_no)))
            if not request.get('no_window'):
                add(joint_window(g,best['plan'],cfg,q,best['result']['official_result'],round_no))
            if not pool:continue
        if calls<3 and not seed or not enhanced:
            pool.sort(key=lambda c:(c['proxy'].get('score',0),c['name']))
            index=0;reason='legacy_proxy'
        else:
            def acquisition(c):
                fam=c['family'];cal=statistics.median(ratios[fam]) if ratios[fam] else 1.0
                cal=max(.25,min(4,cal))
                return c['proxy'].get('score',0)*cal
            untouched=[i for i,c in enumerate(pool) if c['family'] in ('stage','stage_dp','finer') and family_calls[c['family']]==0]
            if untouched:
                index=min(untouched,key=lambda i:(acquisition(pool[i]),pool[i]['name']))
                reason='constructive_family_warmup'
            elif calls%4==3:
                index=min(range(len(pool)),key=lambda i:(family_calls[pool[i]['family']],acquisition(pool[i]),pool[i]['name']))
                reason='family_diversity'
            else:
                index=min(range(len(pool)),key=lambda i:(acquisition(pool[i]),pool[i]['name']))
                reason='within_instance_calibrated_proxy'
        c=pool.pop(index);h=fingerprint(c['plan'])
        if h in seen:continue
        seen.add(h)
        if best and c['bounds']['candidate_lower']>best['result']['official_result']['makespan']:
            state['attempts'].append(dict(name=c['name'],family=c['family'],plan_hash=h,status='certified_pruned',lower=c['bounds']['candidate_lower']))
            continue
        calls+=1;family_calls[c['family']]+=1
        row=dict(index=calls,name=c['name'],family=c['family'],plan_hash=h,status='running',selection=reason,
                 proxy=c['proxy'].get('score'),started_seconds=time.monotonic()-started)
        state['attempts'].append(row);atomic_json(out/'current_plan.json',c['plan']);checkpoint()
        st=time.monotonic()
        try:
            r=session.evaluate(c['plan'],q,request.get('cache_overrides'))
            row.update(status=r['status'],eval_seconds=r['eval_seconds'],completed_seconds=time.monotonic()-started)
            generation_started=time.monotonic()
            if r['status']=='ok':
                raw=r['official_result'];score=(raw['makespan'],raw['data_movement_bytes']['added_copy_bytes'])
                row.update(makespan=score[0],added_copy_bytes=score[1])
                if row['proxy'] and row['proxy']>0:ratios[c['family']].append(score[0]/row['proxy'])
                previous=(best['result']['official_result']['makespan'],best['result']['official_result']['data_movement_bytes']['added_copy_bytes']) if best else (math.inf,math.inf)
                improved=score<previous
                if improved:
                    rn=f'incumbents/e{calls:04d}_result.json.gz';pn=f'incumbents/e{calls:04d}_plan.json'
                    compressed(out/rn,r);atomic_json(out/pn,c['plan'])
                    meta=dict(result_file=rn,plan_file=pn,plan_hash=h,makespan=score[0],added_copy_bytes=score[1],
                              name=c['name'],elapsed_seconds=time.monotonic()-started,evaluation=calls,certificate=r['audit']['certificate'])
                    state['incumbent']=meta;best=dict(result=r,plan=c['plan'],meta=meta,name=c['name']);stall=0
                    row['best_makespan']=score[0]
                    checkpoint()  # Commit the validated incumbent BEFORE any neighbourhood generation.
                    if not request.get('fixed_plan') and q>0:
                        add(neighbours(g,c['plan'],cfg,q,raw))
                else:stall+=1
                if enhanced and calls>=3:
                    # A few off-incumbent parents allow crossing local score barriers.
                    elite.append((score,c['plan'],r));elite.sort(key=lambda e:e[0]);elite=elite[:3]
                    parent=best if improved or calls%4 else dict(plan=elite[-1][1],result=elite[-1][2])
                    if calls%2==1 or improved:
                        round_no+=1
                        add(list(mutations(g,parent['plan'],cfg,q,parent['result']['official_result'],round_no)))
                        if not request.get('no_window'):
                            add(joint_window(g,parent['plan'],cfg,q,parent['result']['official_result'],round_no))
                        if not request.get('no_dp'):
                            cc=memory_window_order(g,parent['plan'],cfg,q,round_no)
                            if cc:add([cc])
            else:
                row['audit_errors']=r['audit']['errors']
                compressed(out/f'failures/e{calls:04d}_result.json.gz',r)
                atomic_json(out/f'failures/e{calls:04d}_plan.json',c['plan'])
        except Exception as e:
            row.update(status='error',error_type=type(e).__name__,error=str(e),traceback=traceback.format_exc())
            atomic_json(out/f'failures/e{calls:04d}_plan.json',c['plan'])
        row['wall_seconds']=time.monotonic()-st
        row.setdefault('completed_seconds',time.monotonic()-started)
        row['generation_and_io_seconds']=max(0,row['wall_seconds']-row.get('eval_seconds',0))
        row['best_makespan']=state['incumbent']['makespan'] if state['incumbent'] else None
        checkpoint()
        if q==0 or request.get('fixed_plan'):state['stopped']='single_official_evaluation';break
        if best:
            cert=best['result']['audit']['certificate'];lb=cert['global_lower']
            if lb>0 and best['result']['official_result']['makespan']/lb<=1+request.get('gap_tolerance',0):
                state['stopped']='certified_requested_gap';break
    state.update(status='ok' if best else 'no_valid_solution',stopped=state['stopped'] or ('evaluation_cap' if calls>=request.get('max_evaluations',64) else 'time_budget'))
    checkpoint()
    return state


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('request');args=p.parse_args(argv);req=read(args.request)
    try:
        s=solve(req);return 0 if s['status']=='ok' else 1
    except Exception as e:
        atomic_json(Path(req['job'])/'worker_error.json',dict(status='error',error=str(e),traceback=traceback.format_exc()))
        return 1

if __name__=='__main__':raise SystemExit(main())
