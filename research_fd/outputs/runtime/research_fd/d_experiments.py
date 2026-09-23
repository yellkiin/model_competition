"""D experiments. Run from repo root: python -m research_fd.d_experiments --help"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json,math,time,platform,csv
from pathlib import Path
import numpy as np
import scipy
from .d_model import Problem,Route,synthetic
from .d_routes import build_pool,greedy_partition,partition_master,dual_expand
from .d_schedule import Job,metrics,score,list_schedule,alns,integrated_milp,cpsat,dispatch
from .d_uncertainty import replay


def clean(x):
    if isinstance(x,dict): return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)): return [clean(v) for v in x]
    if isinstance(x,np.generic): x=x.item()
    return None if isinstance(x,float) and not math.isfinite(x) else x


def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(clean(data),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def save_plan(path,p,jobs,detail=None,sessions=None):
    save(path,{'metadata':p.data.get('metadata',{}),'metrics':metrics(p,jobs),'jobs':[{'route':asdict(j.route),'start':j.start,'aircraft':j.aircraft,'battery':j.battery} for j in jobs],
               'relay_sessions':[] if sessions is None else [{**asdict(s),'aircraft':getattr(s,'aircraft',None),'pack':getattr(s,'pack',None)} for s in sessions],'detail':detail or {}})


def load_plan(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'));jobs=[]
    for j in data['jobs']:
        r=j['route'];r['boxes']=tuple(r['boxes']);r['stops']=tuple(r['stops']);r['delivery']={int(i):o for i,o in r['delivery'].items()}
        r['latest']=math.inf if r['latest'] is None else r['latest']
        jobs.append(Job(Route(**r),j['start'],j['aircraft'],j['battery']))
    from .d_radio import Session
    sessions=[]
    for s in data.get('relay_sessions',[]):
        aa=s.pop('aircraft',None);bb=s.pop('pack',None);ss=Session(**s);ss.aircraft=aa;ss.pack=bb;sessions.append(ss)
    return jobs,sessions


def write_csv(path,rows):
    with Path(path).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def solve_transport(p,out,seed=0,trials=200,rounds=2,lns_iterations=70,time_limit=3.,step=90.,backend='highs',max_routes=600,max_stops=3,max_boxes=8):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);rows=[];solutions={};details={}
    pool=build_pool(p,seed,trials=trials,max_stops=max_stops,max_boxes=max_boxes)
    def add(method,jobs,start,detail):
        m=metrics(p,jobs)
        rows.append({'method':method,'elapsed_s':time.perf_counter()-start,'pool_size':len(pool),'feasible':bool(jobs) and not any(m[k] for k in ('hard_violations','resource_overlaps','unserved','duplicated')),**m})
        solutions[method]=jobs;details[method]=detail;save_plan(out/f'{method}.json',p,jobs,detail)
    t=time.perf_counter();greedy=list_schedule(p,greedy_partition(pool,len(p.boxes)));add('greedy',greedy,t,{})
    t=time.perf_counter();routes,detail=partition_master(pool,len(p.boxes),time_limit);base=list_schedule(p,routes) if routes else [];add('route_milp',base,t,detail)
    t=time.perf_counter();pool,history=dual_expand(p,pool,seed,rounds,trials=max(30,trials//2),max_stops=max_stops,max_boxes=max_boxes);routes,detail=partition_master(pool,len(p.boxes),time_limit);dual=list_schedule(p,routes) if routes else [];add('dual_route_milp',dual,t,{'pricing':history,**detail})
    t=time.perf_counter();dispatched=dispatch(p,pool);add('resource_dispatch',dispatched,t,{})
    start_plan=min([j for j in [greedy,base,dual,dispatched] if j],key=lambda j:score(metrics(p,j)))
    t=time.perf_counter();improved,detail=alns(p,pool,start_plan,seed,iterations=lns_iterations,time_limit=max(3,time_limit*3));add('alns',improved,t,detail)
    if backend!='none':
        t=time.perf_counter();hfix=math.ceil((metrics(p,improved)['makespan_s']+len(improved)*step)/step)*step
        retimed,rdetail=integrated_milp(p,[j.route for j in improved],hfix,step,time_limit)
        add('fixed_route_retime',retimed,t,rdetail)
        required={j.route.id for j in improved}|{r.id for r in pool if len(r.boxes)==1}
        ranked=sorted(pool,key=lambda r:r.aircraft_hold/len(r.boxes));chosen={r.id:r for r in pool if r.id in required}
        for r in ranked:
            if len(chosen)>=max_routes: break
            chosen[r.id]=r
        candidate=list(chosen.values());h=math.ceil((metrics(p,improved)['makespan_s']+len(improved)*step)/step)*step
        t=time.perf_counter()
        if backend=='highs': jobs,detail=integrated_milp(p,candidate,h,step,time_limit)
        else: jobs,detail=cpsat(p,candidate,h,time_limit,seed=seed)
        add('integrated_'+backend,jobs,t,{**detail,'candidate_pruned':len(candidate)<len(pool)})
    best_method=min(solutions,key=lambda k:score(metrics(p,solutions[k])))
    save_plan(out/'best_plan.json',p,solutions[best_method],{'selected_method':best_method,'selection':'coverage/resources, hard count, hard lateness, weighted tardiness, makespan, energy'})
    save(out/'comparison.json',{'input_metadata':p.data.get('metadata',{}),'methods':rows,'best_method':best_method,'details':details});write_csv(out/'comparison.csv',rows)
    print(json.dumps(clean({'best':best_method,'rows':rows}),ensure_ascii=False),flush=True)
    return rows,solutions[best_method]


def small_exact():
    weights=[6,5,3,2,2,2];bins=[]
    for w in weights:
        for i,total in enumerate(bins):
            if total+w<=10: bins[i]+=w;break
        else: bins.append(w)
    data=synthetic(0,1,6);data['terrain']={'kind':'flat','base':0.};data['nodes']=[{'id':'O01','x':0,'y':0,'z':0,'work_height':0},{'id':'S001','x':1000,'y':0,'z':0,'work_height':30}]
    data['fleet']=data['fleet'][:1];data['fleet'][0].update(payload=10.,volume=1.)
    for b,w in zip(data['boxes'],weights): b.update(mass=w,volume=.001,due=10000.,hard_due=None)
    p=Problem(data);pool=build_pool(p,exhaustive=True,max_boxes=6,max_stops=1);selected,info=partition_master(pool,6,10,objective='trips')
    return {'weights':weights,'capacity':10,'ffd_trips':len(bins),'exact_trips':len(selected),'exact_loads':[sum(p.boxes[i].mass for i in r.boxes) for r in selected],'solver':info}


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    s=sub.add_parser('synthetic');s.add_argument('--out',required=True);s.add_argument('--seed',type=int,default=7);s.add_argument('--nodes',type=int,default=15);s.add_argument('--boxes',type=int,default=80)
    t=sub.add_parser('transport');t.add_argument('--input',required=True);t.add_argument('--out',required=True);t.add_argument('--seed',type=int,default=7);t.add_argument('--trials',type=int,default=200);t.add_argument('--rounds',type=int,default=2);t.add_argument('--lns-iterations',type=int,default=70);t.add_argument('--seconds',type=float,default=5);t.add_argument('--step',type=float,default=60);t.add_argument('--backend',choices=['highs','cpsat','none'],default='highs');t.add_argument('--max-routes',type=int,default=600);t.add_argument('--max-stops',type=int,default=3);t.add_argument('--max-boxes',type=int,default=8)
    b=sub.add_parser('benchmark');b.add_argument('--out',required=True);b.add_argument('--seeds',default='7,17,42');b.add_argument('--boxes',type=int,default=80);b.add_argument('--nodes',type=int,default=15);b.add_argument('--seconds',type=float,default=3);b.add_argument('--trials',type=int,default=150);b.add_argument('--backend',choices=['highs','cpsat','none'],default='highs')
    r=sub.add_parser('radio');r.add_argument('--input',required=True);r.add_argument('--plan',required=True);r.add_argument('--out',required=True);r.add_argument('--mode',choices=['fixed','retime','refine'],default='refine');r.add_argument('--seconds',type=float,default=15);r.add_argument('--horizon',type=float,default=7200);r.add_argument('--grid',type=int,default=5);r.add_argument('--sample-step',type=float,default=60);r.add_argument('--max-sessions',type=int,default=18000);r.add_argument('--shift-window',type=float,default=600);r.add_argument('--refine-sites',type=int,default=0)
    v=sub.add_parser('pareto');v.add_argument('--input',required=True);v.add_argument('--plan',required=True);v.add_argument('--out',required=True);v.add_argument('--ratios',default='1,1.1,1.25,1.5');v.add_argument('--seconds',type=float,default=10);v.add_argument('--step',type=float,default=60);v.add_argument('--trials',type=int,default=100);v.add_argument('--seed',type=int,default=7)
    c=sub.add_parser('coopt');c.add_argument('--input',required=True);c.add_argument('--plans',nargs='+',required=True);c.add_argument('--out',required=True);c.add_argument('--seconds',type=float,default=10);c.add_argument('--horizon',type=float,default=7200);c.add_argument('--shift-window',type=float,default=1200);c.add_argument('--max-sessions',type=int,default=6000)
    q=sub.add_parser('partition');q.add_argument('--input',required=True);q.add_argument('--plan',required=True);q.add_argument('--out',required=True);q.add_argument('--groups',type=int,default=2);q.add_argument('--policy',choices=['strict','duplicate'],default='strict');q.add_argument('--seed',type=int,default=7)
    u=sub.add_parser('stress');u.add_argument('--input',required=True);u.add_argument('--plan',required=True);u.add_argument('--out',required=True);u.add_argument('--seed',type=int,default=7);u.add_argument('--scenarios',type=int,default=200);u.add_argument('--sigma',type=float,default=.08)
    a=parser.parse_args()
    if a.command=='synthetic': save(a.out,synthetic(a.seed,a.nodes,a.boxes));return
    if a.command=='benchmark':
        rows=[];out=Path(a.out);out.mkdir(parents=True,exist_ok=True);save(out/'small_exact.json',small_exact())
        for seed in map(int,a.seeds.split(',')):
            data=synthetic(seed,a.nodes,a.boxes);save(out/f'seed_{seed}/instance.json',data);p=Problem(data)
            records,jobs=solve_transport(p,out/f'seed_{seed}',seed=seed,trials=a.trials,time_limit=a.seconds,backend=a.backend)
            rows += [{'seed':seed,**row} for row in records];save(out/f'seed_{seed}/stress.json',replay(p,jobs,seed))
        save(out/'summary.json',{'environment':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__},'source':'synthetic benchmark, not official attachments','records':rows});write_csv(out/'summary.csv',rows);return
    p=Problem.load(a.input)
    if a.command=='transport': solve_transport(p,a.out,a.seed,a.trials,a.rounds,a.lns_iterations,a.seconds,a.step,a.backend,a.max_routes,a.max_stops,a.max_boxes);return
    if a.command=='coopt':
        from .d_radio import candidates,solve_joint_fixed_routes,evaluate_radio
        sites=candidates(p,3);best=None;records=[]
        for i,path in enumerate(a.plans):
            jobs,_=load_plan(path)
            for j in jobs:
                expected=p.route(j.route.boxes,j.route.kind,j.route.stops)
                if expected is None or abs(expected.energy-j.route.energy)>1e-6 or abs(expected.duration-j.route.duration)>1e-6: raise ValueError('candidate plan belongs to different physical inputs')
            jj,ss,detail=solve_joint_fixed_routes(p,[j.route for j in jobs],sites,fixed_starts=jobs,sample_step=40,time_limit=a.seconds,max_sessions=a.max_sessions)
            if not jj:
                jj,ss,detail=solve_joint_fixed_routes(p,[j.route for j in jobs],sites,horizon=a.horizon,reference_jobs=jobs,shift_window=a.shift_window,sample_step=40,time_limit=a.seconds,max_sessions=a.max_sessions)
            record={'candidate':path,'solver':detail}
            if jj:
                check=evaluate_radio(p,jj,ss,10);m=metrics(p,jj);record.update(metrics=m,radio=check)
                feasible=not any(m[k] for k in ('unserved','duplicated','resource_overlaps','hard_violations')) and check['misses']==0
                if feasible:
                    rank=(m['weighted_tardiness_s'],detail['joint_makespan_s'],m['energy_kwh']+detail['relay_energy_kwh'])
                    if best is None or rank<best: best=rank;save_plan(Path(a.out)/'best_joint_plan.json',p,jj,detail,ss)
                save_plan(Path(a.out)/f'candidate_{i}.json',p,jj,detail,ss)
            records.append(record)
        save(Path(a.out)/'coopt.json',{'selected_objectives':best,'candidates':records});return
    jobs,sessions=load_plan(a.plan)
    if a.command=='pareto':
        pool=build_pool(p,a.seed,trials=a.trials);baseline=metrics(p,jobs)['makespan_s'];records=[]
        for ratio in map(float,a.ratios.split(',')):
            cap=baseline*ratio;sol,detail=integrated_milp(p,pool,cap,a.step,a.seconds,energy_first=True)
            records.append({'ratio':ratio,'cap_s':cap,'found':bool(sol),**metrics(p,sol),'solver':detail})
            save_plan(Path(a.out)/f'energy_cap_{ratio:g}.json',p,sol,detail)
        save(Path(a.out)/'pareto.json',records);return
    if a.command=='stress': save(a.out,replay(p,jobs,a.seed,a.scenarios,a.sigma));return
    if a.command=='partition':
        from .d_partition import assign_support,search_partition
        save(a.out,search_partition(p,jobs,sessions,assign_support(p,jobs,sessions),a.groups,a.policy,seed=a.seed));return
    from .d_radio import candidates,solve_joint_fixed_routes,refine_joint,evaluate_radio
    sites=candidates(p,a.grid)
    if a.refine_sites:
        from .d_radio import augment_sites,demands_for_options
        sites,_=augment_sites(p,sites,demands_for_options(p,[(j.route,j.start) for j in jobs],a.sample_step),count=a.refine_sites)
    if a.mode=='refine': jj,ss,detail=refine_joint(p,jobs,sites,a.horizon,time_limit=a.seconds,max_sessions=a.max_sessions,shift_window=a.shift_window)
    else: jj,ss,detail=solve_joint_fixed_routes(p,[j.route for j in jobs],sites,sample_step=a.sample_step,time_limit=a.seconds,fixed_starts=jobs if a.mode=='fixed' else None,horizon=a.horizon,max_sessions=a.max_sessions,reference_jobs=jobs,shift_window=a.shift_window)
    if jj:
        detail['fine_evaluation']=evaluate_radio(p,jj,ss,dt=10);save_plan(Path(a.out)/'joint_plan.json',p,jj,detail,ss)
    save(Path(a.out)/'radio_result.json',detail);print(json.dumps(clean({k:v for k,v in detail.items() if k not in ('fine_evaluation','refinement_history')}),ensure_ascii=False),flush=True)

if __name__=='__main__': main()
