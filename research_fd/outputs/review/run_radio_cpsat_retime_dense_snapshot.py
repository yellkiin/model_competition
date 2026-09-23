"""CP-SAT output-only joint retiming repair with fixed boxes/visit sequences.

Transport starts stay on the 60-second grid. Soft tardiness can be optimized.
Resource holds round up to 1 ms, return objectives up to 1 ms, relay energy to
1e-9 kWh. Every returned plan must pass original continuous arithmetic checks.
"""
from pathlib import Path
import sys,json,runpy,math,time,inspect
from collections import defaultdict
import numpy as np
from ortools.sat.python import cp_model

OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT/'runtime'))
import research_fd.d_radio as radio
from research_fd.d_schedule import metrics,recolor
SITE_POLICY='greedy_double'
ALLOW_SOFT='--allow-soft-lateness' in sys.argv
if ALLOW_SOFT:sys.argv.remove('--allow-soft-lateness')
TRANSPORT_STEP=60.
if '--transport-step' in sys.argv:
    ix=sys.argv.index('--transport-step');TRANSPORT_STEP=float(sys.argv[ix+1]);del sys.argv[ix:ix+2]
COVER_BLOCKS='--cover-blocks' in sys.argv
if COVER_BLOCKS:sys.argv.remove('--cover-blocks')
FEASIBILITY_FIRST='--feasibility-first' in sys.argv
if FEASIBILITY_FIRST:sys.argv.remove('--feasibility-first')
DENSE_SESSIONS='--dense-sessions' in sys.argv
if DENSE_SESSIONS:sys.argv.remove('--dense-sessions')
SITE_FILE=None
if '--site-indices-file' in sys.argv:
    ix=sys.argv.index('--site-indices-file');SITE_FILE=Path(sys.argv[ix+1]);del sys.argv[ix:ix+2]
if '--site-policy' in sys.argv:
    ix=sys.argv.index('--site-policy');SITE_POLICY=sys.argv[ix+1];del sys.argv[ix:ix+2]
if SITE_POLICY not in ('all','greedy_double','greedy_quad'):raise ValueError('bad site policy')
EXPANDED_POOL_SOURCE=None
if DENSE_SESSIONS:
    source=inspect.getsource(radio.session_pool)
    old="ends=sorted(set([int(lo+1),int(lo+2),int(lo+4),int(lo+8),int(lo+16),int(lo+32),int(maxend)]))"
    new="ends=sorted(set(int(s)+1 for s in valid_slots if lo<=s<maxend))"
    if source.count(old)!=1:raise ValueError('Runtime source no longer matches reviewed session-end patch')
    EXPANDED_POOL_SOURCE=source.replace(old,new)
    namespace={}
    exec(compile(EXPANDED_POOL_SOURCE,'outputs-expanded-session-pool','exec'),radio.__dict__,namespace)
    radio.session_pool=namespace['session_pool']

def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def dominant(a,b):
    # Compare the exact coefficients used by the CP-SAT model, not float epsilons.
    return (int(round(a.departure*1000))>=int(round(b.departure*1000)) and
            int(round(a.aircraft_end*1000))<=int(round(b.aircraft_end*1000)) and
            int(round(a.pack_end*1000))<=int(round(b.pack_end*1000)) and
            math.ceil(a.returned*1000)<=math.ceil(b.returned*1000) and
            int(round(a.energy*1e9))<=int(round(b.energy*1e9)))

def solve(p,routes,sites,step=60.,sample_step=60.,time_limit=60.,fixed_starts=None,horizon=None,max_sessions=18000,reference_jobs=None,shift_window=1200.):
    if fixed_starts is not None:raise ValueError('Use mode retime')
    out=Path(sys.argv[sys.argv.index('--out')+1]);began=time.monotonic()
    if EXPANDED_POOL_SOURCE is not None:
        out.mkdir(parents=True,exist_ok=True)
        (out/'expanded_session_pool.py').write_text(EXPANDED_POOL_SOURCE,encoding='utf-8')
    reference={j.route.id:j.start for j in reference_jobs}
    options=[]
    for r in routes:
        soft_latest=min(p.boxes[b].due-r.delivery[b] for b in r.boxes)
        lo=max(r.release,reference[r.id]-shift_window,0)
        hi=min(r.latest,math.inf if ALLOW_SOFT else soft_latest,reference[r.id]+shift_window,horizon-r.duration)
        options.extend((r,t*TRANSPORT_STEP) for t in range(math.ceil(lo/TRANSPORT_STEP),math.floor((hi+1e-8)/TRANSPORT_STEP)+1))
    demands=radio.demands_for_options(p,options,sample_step)
    original_sites=len(sites);indices=list(range(len(sites)))
    if SITE_FILE is not None:
        indices=json.loads(SITE_FILE.read_text(encoding='utf-8'))['selected_site_indices']
        sites=[sites[i] for i in indices]
    elif SITE_POLICY!='all':
        masks=[];cache={}
        for i,site in enumerate(sites):
            mask=0
            for j,d in enumerate(demands):
                key=(i,tuple(d['xyz']))
                if key not in cache:cache[key]=radio.margin(p,site,d['xyz'],p.data['radio']['access_budget_db'])>=0
                if cache[key]:mask|=1<<j
            masks.append(mask)
        indices=[];target=(1<<len(demands))-1
        for rr in range(2 if SITE_POLICY=='greedy_double' else 4):
            uncovered=target
            while uncovered:
                allowed=[i for i in range(len(sites)) if i not in indices]
                if not allowed:break
                i=max(allowed,key=lambda i:((masks[i]&uncovered).bit_count(),sites[i][2]))
                if not masks[i]&uncovered:break
                indices.append(i);uncovered &= ~masks[i]
        sites=[sites[i] for i in indices]
    print(json.dumps({'event':'retime_geometry','routes':len(routes),'options':len(options),'requirements':len(demands),'sites':len(sites),'site_policy':SITE_POLICY,'shift_window':shift_window,'elapsed_s':time.monotonic()-began}),flush=True)
    pool,info=radio.session_pool(p,demands,sites,step,1000000)
    if info.get('pool_truncated'):raise MemoryError('Raw column guard reached')
    raw=len(pool);groups=defaultdict(list)
    for s in pool:groups[tuple(s.covers)].append(s)
    pool=[]
    for group in groups.values():
        frontier=[]
        for s in sorted(group,key=lambda x:(-x.departure,x.aircraft_end,x.pack_end,x.returned,x.energy)):
            if any(dominant(a,s) for a in frontier):continue
            frontier=[a for a in frontier if not dominant(s,a)];frontier.append(s)
        pool.extend(frontier)
    info.update(backend='ortools-cpsat-joint-fixed-routes',raw_sessions=raw,sessions=len(pool),pool_truncated=False,
                options=len(options),routes=len(routes),sample_step_s=sample_step,schedule_step_s=step,
                shift_window_s=shift_window,transport_horizon_s=horizon,soft_tardiness_fixed_s=None if ALLOW_SOFT else 0,
                transport_start_step_s=TRANSPORT_STEP,cover_block_restriction=COVER_BLOCKS,site_indices_file=None if SITE_FILE is None else str(SITE_FILE),
                session_end_generation='all covered demand slot ends within energy limit' if DENSE_SESSIONS else 'legacy 1,2,4,8,16,32 slots and energy maximum',
                site_policy=SITE_POLICY,original_sites=original_sites,retained_site_indices=indices,
                resource_resolution_s=.001,return_objective_resolution_s=.001,energy_objective_resolution_kwh=1e-9,
                dominance='identical finite sampled covers, integer CP coefficient comparison')
    save(out/'model_build.json',info)
    model=cp_model.CpModel();xx=[model.new_bool_var(f't{i}') for i in range(len(options))]
    zz=[model.new_bool_var(f'r{i}') for i in range(len(pool))]
    route_opts=defaultdict(list);body={k:[] for k in p.fleet};battery={k:[] for k in p.fleet}
    upper=max([math.ceil(s.returned*1000) for s in pool]+[math.ceil((r.duration+t)*1000) for r,t in options])
    cmax=model.new_int_var(0,upper,'joint_return_ms')
    for i,(r,t) in enumerate(options):
        route_opts[r.id].append(xx[i]);start=int(round(t*1000))
        for hold,target,label in [(r.aircraft_hold,body,'a'),(r.battery_hold,battery,'b')]:
            length=math.ceil(hold*1000)
            target[r.kind].append(model.new_optional_interval_var(start,length,start+length,xx[i],f'{label}{i}'))
        model.add(cmax>=math.ceil((t+r.duration)*1000)).only_enforce_if(xx[i])
    for r in routes:model.add_exactly_one(route_opts[r.id])
    hinted={}
    for r in routes:
        choices=[i for i,(rr,t) in enumerate(options) if rr.id==r.id]
        if choices:hinted[r.id]=min(choices,key=lambda i:abs(options[i][1]-reference[r.id]))
    for i,(r,t) in enumerate(options):model.add_hint(xx[i],int(hinted.get(r.id)==i))
    for k,f in p.fleet.items():
        model.add_cumulative(body[k],[1]*len(body[k]),f.count)
        model.add_cumulative(battery[k],[1]*len(battery[k]),f.batteries)
    by_req=[[] for _ in demands];aa=[];bb=[]
    for i,s in enumerate(pool):
        for d in s.covers:by_req[d].append(i)
        start=int(round(s.departure*1000));ae=int(round(s.aircraft_end*1000));be=int(round(s.pack_end*1000))
        aa.append(model.new_optional_interval_var(start,ae-start,ae,zz[i],f'ra{i}'))
        bb.append(model.new_optional_interval_var(start,be-start,be,zz[i],f'rb{i}'))
        model.add(cmax>=math.ceil(s.returned*1000)).only_enforce_if(zz[i])
    if COVER_BLOCKS:
        owner_demands=defaultdict(list)
        for i,d in enumerate(demands):owner_demands[d['owner']].append(i)
        blocks=[]
        for owner,ids in owner_demands.items():
            current=[]
            for i in ids:
                if current and (demands[i]['time']-demands[current[-1]]['time']>sample_step*1.01 or demands[i]['time']-demands[current[0]]['time']>120.):
                    blocks.append((owner,current));current=[]
                current.append(i)
            if current:blocks.append((owner,current))
        deactivated=set()
        for owner,ids in blocks:
            ids.sort(key=lambda i:len(by_req[i]));common=set(by_req[ids[0]])
            for i in ids[1:]:common.intersection_update(by_req[i])
            if not common:deactivated.add(owner)
            model.add(sum(zz[j] for j in common)>=xx[owner])
        info.update(communication_blocks=len(blocks),options_deactivated_by_single_session_block=len(deactivated),
                    cover_block_scope='All original sample requirements retained; one selected session must cover each <=120 s contiguous bad-link block, a conservative restriction')
    else:
        for i,d in enumerate(demands):model.add(sum(zz[j] for j in by_req[i])>=xx[d['owner']])
    model.add_cumulative(aa,[1]*len(aa),p.data['relay']['count'])
    model.add_cumulative(bb,[1]*len(bb),p.data['relay']['packs'])
    cp=cp_model.CpSolver();cp.parameters.max_time_in_seconds=float(time_limit)
    cp.parameters.num_search_workers=4;cp.parameters.random_seed=7
    stages=[];best=None
    print(json.dumps({'event':'retime_cp_model_ready','sessions':len(pool),'options':len(options),'elapsed_s':time.monotonic()-began}),flush=True)
    energy=sum(int(round(s.energy*1e9))*zz[i] for i,s in enumerate(pool))
    tardiness=sum(math.ceil(1000*sum(p.boxes[b].weight*max(0,t+r.delivery[b]-p.boxes[b].due) for b in r.boxes))*xx[i] for i,(r,t) in enumerate(options))
    objectives=([('feasibility_seed',0)] if FEASIBILITY_FIRST else [])+([('weighted_tardiness_milliseconds',tardiness)] if ALLOW_SOFT else [])+[('joint_makespan',cmax),('relay_energy',energy)]
    for stage,obj in objectives:
        cp.parameters.stop_after_first_solution=(stage=='feasibility_seed')
        model.minimize(obj)
        class Callback(cp_model.CpSolverSolutionCallback):
            def on_solution_callback(self):
                ids=[i for i,z in enumerate(zz) if self.value(z)];opts=[i for i,x in enumerate(xx) if self.value(x)]
                record={'stage':stage,'objective':self.objective_value,'elapsed_s':time.monotonic()-began,'sessions':ids,'transport_options':opts}
                save(out/f'{stage}_latest_incumbent.json',record)
                print(json.dumps({k:v for k,v in record.items() if k not in ('sessions','transport_options')}),flush=True)
        status=cp.solve(model,Callback())
        record={'stage':stage,'status':cp.status_name(status),'objective':float(cp.objective_value) if status in (cp_model.OPTIMAL,cp_model.FEASIBLE) else None,'bound':float(cp.best_objective_bound),'elapsed_s':time.monotonic()-began}
        stages.append(record);print(json.dumps(record),flush=True)
        if status not in (cp_model.OPTIMAL,cp_model.FEASIBLE):break
        opts=[i for i,x in enumerate(xx) if cp.value(x)];ids=[i for i,z in enumerate(zz) if cp.value(z)];best=(opts,ids)
        model.add(obj<=int(round(cp.objective_value)))
        model.clear_hints()
        for i,x in enumerate(xx):model.add_hint(x,int(i in opts))
        for i,z in enumerate(zz):model.add_hint(z,int(i in ids))
    info.update(stages=stages,status='feasible' if best is not None else 'no_incumbent',elapsed_s=time.monotonic()-began)
    if best is None:return [],[],info
    opts,ids=best;jobs=recolor(p,[options[i] for i in opts]);sessions=[pool[i] for i in ids]
    mm=metrics(p,jobs)
    if any(mm[k] for k in ('hard_violations','resource_overlaps','unserved','duplicated')) or (not ALLOW_SOFT and mm['weighted_tardiness_s']>1e-5):raise RuntimeError(mm)
    for label,endattr,count in [('aircraft','aircraft_end',p.data['relay']['count']),('pack','pack_end',p.data['relay']['packs'])]:
        ready=np.zeros(count)
        for s in sorted(sessions,key=lambda s:s.departure):
            k=int(np.argmin(ready))
            if ready[k]>s.departure+1e-6:raise RuntimeError('relay coloring mismatch')
            setattr(s,label,k);ready[k]=getattr(s,endattr)
    info.update(joint_makespan_s=max([mm['makespan_s']]+[s.returned for s in sessions]),relay_energy_kwh=sum(s.energy for s in sessions),relay_trips=len(sessions))
    return jobs,sessions,info

radio.solve_joint_fixed_routes=solve
sys.argv=[str(OUT/'run_official.py'),*sys.argv[1:]]
runpy.run_path(str(OUT/'run_official.py'),run_name='__main__')
