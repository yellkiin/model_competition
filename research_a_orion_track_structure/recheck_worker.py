"""Independent execution adapter; published/common/official source stays unchanged."""
from __future__ import annotations
import argparse,json,math,time,traceback
from pathlib import Path
from collections import deque
from research_a_orion_anytime.core import Graph,plan_view
from research_a_orion_anytime.engine import OfficialSession
from research_a_orion_anytime.worker import atomic_json
from .recheck_evidence import read,gzwrite,metrics
from .plugin_recheck import propose,local_proposals


def corrected(req):
    out=Path(req['job']);out.mkdir(parents=True,exist_ok=True)
    start=time.monotonic();deadline=start+req['seconds']
    q,n=req['q'],req['n']
    s=dict(case=req['case'],q=q,n=n,status='initializing',attempts=[],incumbent=None,construction_errors=[],candidate_generation_seconds=0.,evaluations=0,actual_route='structure_v2',identity=req['identity'])
    def save():s['elapsed_seconds']=time.monotonic()-start;atomic_json(out/'progress.json',s)
    save();t=time.monotonic();session=OfficialSession(req['official'],req['graph'],req['config']);g,cfg=session.graph,session.cfg
    s['construction_seconds']=time.monotonic()-t;context={};best=(math.inf,math.inf);seen=set()
    if req.get('seed_job'):
        d=Path(req['seed_job']);seed=read(d/'progress.json')['incumbent'];plan=read(d/seed['plan_file']);res=read(d/seed['result_file'])
        # Shared prep re-evaluates this exact target-n seed before giving it to all arms.
        if len(plan['core_schedules'])!=n or res['status']!='ok':raise ValueError('invalid common seed')
        atomic_json(out/'seed_plan.json',plan);gzwrite(out/'seed_result.json.gz',res)
        best=(res['official_result']['makespan'],res['official_result']['data_movement_bytes']['added_copy_bytes'])
        s['incumbent']={**seed,'plan_file':'seed_plan.json','result_file':'seed_result.json.gz','elapsed_seconds':0.,'from_seed':True,'evaluation':0}
        context.update(plan=plan,official_result=res['official_result']);save()
    initial=iter(propose(g,n,cfg,q,context,s['attempts'],deadline));locals_=deque();initial_done=False;iteration=0;no_gain=0
    while time.monotonic()<deadline and s['evaluations']<req['max_evaluations']:
        tick=time.monotonic();c=None
        try:
            if locals_ and (iteration%3!=0 or initial_done):c=locals_.popleft()
            elif not initial_done:
                try:c=next(initial)
                except StopIteration:initial_done=True
            if c is None and locals_:c=locals_.popleft()
            if c is None and initial_done:s['stopped']='candidate_space_exhausted';break
        except Exception as e:
            s['construction_errors'].append({'error':str(e),'traceback':traceback.format_exc()});initial_done=True;save();continue
        dt=time.monotonic()-tick;s['candidate_generation_seconds']+=dt
        if c is None:continue
        iteration+=1
        if time.monotonic()>=deadline:s['stopped']='deadline_after_generation';break
        p=c['plan']
        try:plan_view(g,p)
        except ValueError as e:s['attempts'].append({'name':c['name'],'status':'construction_invalid','error':str(e)});save();continue
        key=(tuple(sorted(p['node_to_subgraph'].items())),tuple(map(tuple,p['core_schedules'])))
        if key in seen:s['attempts'].append({'name':c['name'],'family':c['family'],'status':'duplicate','generation_seconds':dt});continue
        seen.add(key)
        if c['bounds']['candidate_lower']>best[0]:
            s['attempts'].append({'name':c['name'],'family':c['family'],'status':'certified_pruned','lower':c['bounds']['candidate_lower'],'generation_seconds':dt});save();continue
        i=s['evaluations']+1;s['evaluations']=i
        pn=f'attempts/e{i:04d}_plan.json';rn=f'attempts/e{i:04d}_result.json.gz'
        a=dict(index=i,name=c['name'],family=c['family'],status='running',started_seconds=time.monotonic()-start,generation_seconds=dt,plan_file=pn,result_file=rn,proxy=c['proxy']['score'])
        s['attempts'].append(a);atomic_json(out/pn,p);save();t=time.monotonic()
        try:
            r=session.evaluate(p,q);evaluation_wall=time.monotonic()-t
            a.update(status=r['status'],eval_seconds=r['eval_seconds'],audit_seconds=evaluation_wall-r['eval_seconds'])
            gzwrite(out/rn,r)
            if r['status']=='ok':
                raw=r['official_result'];score=(raw['makespan'],raw['data_movement_bytes']['added_copy_bytes'])
                a.update(makespan=score[0],added_copy_bytes=score[1],improved=score<best)
                if score<best:
                    best=score;no_gain=0;context.update(plan=p,official_result=raw)
                    s['incumbent']=dict(name=c['name'],makespan=score[0],added_copy_bytes=score[1],plan_file=pn,result_file=rn,elapsed_seconds=time.monotonic()-start,evaluation=i,certificate=r['audit']['certificate']);save()
                    t2=time.monotonic();locals_.extend(local_proposals(g,n,cfg,q,context,i,deadline));s['candidate_generation_seconds']+=time.monotonic()-t2
                else:no_gain+=1
            else:a['audit_errors']=r['audit']['errors']
        except Exception as e:a.update(status='error',error=str(e),traceback=traceback.format_exc())
        a['completed_seconds']=time.monotonic()-start;a['wall_seconds']=time.monotonic()-t;a['best_makespan']=best[0] if math.isfinite(best[0]) else None;save()
        if initial_done and no_gain>=16:s['stopped']='sixteen_completed_nonimproving_attempts';break
    s['status']='ok' if s['incumbent'] else 'no_valid_solution';s.setdefault('stopped','evaluation_cap' if s['evaluations']>=req['max_evaluations'] else 'time_budget');save();return s


def main():
    a=argparse.ArgumentParser();a.add_argument('request');req=read(a.parse_args().request)
    out=Path(req['job']);out.mkdir(parents=True,exist_ok=True);t=time.monotonic()
    try:
        if req['method']=='old':
            route='legacy';from research_a_orion_anytime.solver import solve
        elif req['method']=='published':
            from .worker import solve_structure
            route='structure_published';g=Graph(read(req['graph']))
            if not req.get('seed_plan') and len(g.components)>1 and max(g.weight(c) for c in g.components)<=g.weight(g.ops)/req['n']:
                route='legacy';from research_a_orion_anytime.solver import solve
            else:solve=solve_structure
            del g
        elif req['method']=='corrected':route='structure_v2';solve=corrected
        else:raise ValueError('unknown method')
        seconds=time.monotonic()-t
        atomic_json(out/'routing.json',dict(requested_method=req['method'],actual_route=route,routing_seconds=seconds))
        inner=dict(req);inner['seconds']=max(.001,req['seconds']-seconds)
        s=solve(inner)
        return 0 if s.get('incumbent') else 1
    except Exception as e:
        atomic_json(out/'worker_error.json',dict(error=str(e),traceback=traceback.format_exc()));return 1

if __name__=='__main__':raise SystemExit(main())
