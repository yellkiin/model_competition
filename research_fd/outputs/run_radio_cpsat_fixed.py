"""Executed CP-SAT repair for fixed transport / physical relay session selection.

Uses official bootstrap and unchanged physical session columns; outputs only.
Resource time intervals are exact seconds on the existing 60-second grid.
Return objective rounds up to milliseconds; energy objective rounds to 1e-9 kWh.
"""
from pathlib import Path
import sys,json,runpy,math,time
from collections import defaultdict
import numpy as np
from ortools.sat.python import cp_model

OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT/'runtime'))
import research_fd.d_radio as radio
from research_fd.d_schedule import metrics
SITE_POLICY='all'
if '--site-policy' in sys.argv:
    ix=sys.argv.index('--site-policy');SITE_POLICY=sys.argv[ix+1];del sys.argv[ix:ix+2]
    if SITE_POLICY not in ('all','greedy_double'):raise ValueError('invalid site policy')

def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def dominant(a,b):
    return (a.departure>=b.departure-1e-9 and a.aircraft_end<=b.aircraft_end+1e-9
            and a.pack_end<=b.pack_end+1e-9 and a.returned<=b.returned+1e-9 and a.energy<=b.energy+1e-12)

def solver(p,routes,sites,step=60.,sample_step=60.,time_limit=60.,fixed_starts=None,horizon=None,max_sessions=18000,reference_jobs=None,shift_window=600.):
    if fixed_starts is None:raise ValueError('This repair backend only supports fixed transport starts')
    out=Path(sys.argv[sys.argv.index('--out')+1]);began=time.monotonic()
    mm=metrics(p,fixed_starts)
    if any(mm[k] for k in ('hard_violations','resource_overlaps','unserved','duplicated')):raise ValueError('incomplete/infeasible fixed transport')
    demands=radio.demands_for_options(p,[(j.route,j.start) for j in fixed_starts],sample_step)
    original_site_count=len(sites);chosen_site_ids=list(range(len(sites)))
    if SITE_POLICY=='greedy_double':
        masks=[];cache={}
        for i,site in enumerate(sites):
            mask=0
            for j,d in enumerate(demands):
                key=(i,tuple(d['xyz']))
                if key not in cache:cache[key]=radio.margin(p,site,d['xyz'],p.data['radio']['access_budget_db'])>=0
                if cache[key]:mask|=1<<j
            masks.append(mask)
        chosen_site_ids=[];target=(1<<len(demands))-1
        for round_id in range(2):
            uncovered=target
            while uncovered:
                allowed=[i for i in range(len(sites)) if i not in chosen_site_ids]
                if not allowed:break
                i=max(allowed,key=lambda i:((masks[i]&uncovered).bit_count(),sites[i][2]))
                gain=masks[i]&uncovered
                if not gain:break
                chosen_site_ids.append(i);uncovered &= ~masks[i]
        sites=[sites[i] for i in chosen_site_ids]
        print(json.dumps({'event':'reduced_candidate_sites','policy':SITE_POLICY,'original_sites':original_site_count,'retained_sites':len(sites),'indices':chosen_site_ids}),flush=True)
    print(json.dumps({'event':'cpsat_build_start','demands':len(demands),'sites':len(sites)}),flush=True)
    pool,info=radio.session_pool(p,demands,sites,step,1000000)
    if info.get('pool_truncated'):raise MemoryError('Untruncated session generation guard reached')
    raw=len(pool);groups=defaultdict(list)
    for s in pool:groups[tuple(s.covers)].append(s)
    pool=[]
    for group in groups.values():
        frontier=[]
        for s in sorted(group,key=lambda x:(-x.departure,x.aircraft_end,x.pack_end,x.returned,x.energy)):
            if any(dominant(a,s) for a in frontier):continue
            frontier=[a for a in frontier if not dominant(s,a)];frontier.append(s)
        pool.extend(frontier)
    info.update(raw_sessions=raw,sessions=len(pool),pool_truncated=False,backend='ortools-cpsat-fixed-relay',
                sample_step_s=sample_step,schedule_step_s=step,return_objective_resolution_s=.001,energy_objective_resolution_kwh=1e-9,
                site_policy=SITE_POLICY,original_sites=original_site_count,retained_site_indices=chosen_site_ids)
    model=cp_model.CpModel();z=[model.new_bool_var(f's{i}') for i in range(len(pool))]
    by_req=[[] for _ in demands];aa=[];bb=[]
    for i,s in enumerate(pool):
        for d in s.covers:by_req[d].append(z[i])
        start=int(round(s.departure));ae=int(round(s.aircraft_end));be=int(round(s.pack_end))
        if abs(start-s.departure)>1e-7 or abs(ae-s.aircraft_end)>1e-7 or abs(be-s.pack_end)>1e-7:raise ValueError('Noninteger resource interval')
        aa.append(model.new_optional_interval_var(start,ae-start,ae,z[i],f'a{i}'))
        bb.append(model.new_optional_interval_var(start,be-start,be,z[i],f'b{i}'))
    for arr in by_req:model.add(sum(arr)>=1)
    model.add_cumulative(aa,[1]*len(aa),p.data['relay']['count'])
    model.add_cumulative(bb,[1]*len(bb),p.data['relay']['packs'])
    lower=math.ceil(mm['makespan_s']*1000);upper=max([math.ceil(s.returned*1000) for s in pool]+[lower])
    cmax=model.new_int_var(lower,upper,'joint_return_milliseconds')
    for i,s in enumerate(pool):model.add(cmax>=math.ceil(s.returned*1000)).only_enforce_if(z[i])
    cp=cp_model.CpSolver();cp.parameters.max_time_in_seconds=float(time_limit)
    cp.parameters.num_search_workers=4;cp.parameters.random_seed=7
    cp.parameters.log_search_progress=False
    stages=[];chosen_ids=None
    print(json.dumps({'event':'cpsat_model_ready','columns':len(pool),'elapsed_s':time.monotonic()-began}),flush=True)
    energy=sum(int(round(s.energy*1e9))*z[i] for i,s in enumerate(pool))
    for stage,obj in [('joint_makespan',cmax),('relay_energy',energy)]:
        model.minimize(obj)
        class Callback(cp_model.CpSolverSolutionCallback):
            def on_solution_callback(self):
                ids=[i for i,v in enumerate(z) if self.value(v)]
                value={'event':'incumbent','stage':stage,'sessions':ids,'objective':self.objective_value,'elapsed_s':time.monotonic()-began}
                save(out/f'{stage}_latest_incumbent.json',value)
                print(json.dumps({k:v for k,v in value.items() if k!='sessions'},ensure_ascii=False),flush=True)
        status=cp.solve(model,Callback())
        record={'stage':stage,'status':cp.status_name(status),'objective':float(cp.objective_value) if status in (cp_model.FEASIBLE,cp_model.OPTIMAL) else None,'bound':float(cp.best_objective_bound),'elapsed_s':time.monotonic()-began}
        stages.append(record);print(json.dumps(record),flush=True)
        if status not in (cp_model.FEASIBLE,cp_model.OPTIMAL):break
        chosen_ids=[i for i,v in enumerate(z) if cp.value(v)]
        model.add(obj<=int(round(cp.objective_value)))
        for i,v in enumerate(z):model.add_hint(v,int(i in chosen_ids))
    info.update(stages=stages,status='no_incumbent' if chosen_ids is None else 'feasible',elapsed_s=time.monotonic()-began)
    if chosen_ids is None:return [],[],info
    chosen=[pool[i] for i in chosen_ids]
    for label,endattr,count in [('aircraft','aircraft_end',p.data['relay']['count']),('pack','pack_end',p.data['relay']['packs'])]:
        ready=np.zeros(count)
        for s in sorted(chosen,key=lambda s:s.departure):
            k=int(np.argmin(ready))
            if ready[k]>s.departure+1e-6:raise RuntimeError('CP-SAT interval coloring mismatch')
            setattr(s,label,k);ready[k]=getattr(s,endattr)
    info.update(joint_makespan_s=max([mm['makespan_s']]+[s.returned for s in chosen]),relay_energy_kwh=sum(s.energy for s in chosen),relay_trips=len(chosen))
    return fixed_starts,chosen,info

radio.solve_joint_fixed_routes=solver
sys.argv=[str(OUT/'run_official.py'),*sys.argv[1:]]
runpy.run_path(str(OUT/'run_official.py'),run_name='__main__')
