"""Shared-battery list scheduling, ALNS repair and integrated route-time MILP.
SciPy/HiGHS is the executed backend. OR-Tools CP-SAT is an optional local backend.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import time
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix, vstack, csr_matrix
from .d_model import Problem, Route

@dataclass
class Job:
    route: Route
    start: float
    aircraft: int
    battery: int


def metrics(p:Problem,jobs:list[Job]):
    counts=np.zeros(len(p.boxes),int); late=0.;hard_late=0.;hard_count=0
    for j in jobs:
        for i,offset in j.route.delivery.items():
            counts[i]+=1;b=p.boxes[i];arrival=j.start+offset
            late+=b.weight*max(0.,arrival-b.due)
            if b.hard_due is not None and arrival>b.hard_due+1e-6:
                hard_count+=1;hard_late+=arrival-b.hard_due
    overlap=0
    for kind in p.fleet:
        group=[j for j in jobs if j.route.kind==kind]
        for resource,hold in [('aircraft','aircraft_hold'),('battery','battery_hold')]:
            for rid in {getattr(j,resource) for j in group}:
                spans=sorted((j.start,j.start+getattr(j.route,hold)) for j in group if getattr(j,resource)==rid)
                overlap+=sum(e1>s2+1e-6 for (_,e1),(s2,_) in zip(spans,spans[1:]))
    return {'trips':len(jobs),'hard_violations':hard_count,'hard_lateness_s':float(hard_late),
            'weighted_tardiness_s':float(late),'makespan_s':float(max((j.start+j.route.duration for j in jobs),default=0)),
            'energy_kwh':float(sum(j.route.energy for j in jobs)),
            'resource_overlaps':int(overlap),'unserved':int(np.sum(counts==0)),'duplicated':int(np.sum(counts>1))}


def score(m):
    return (m['unserved']+m['duplicated']+m['resource_overlaps'],m['hard_violations'],m['hard_lateness_s'],m['weighted_tardiness_s'],m['makespan_s'],m['energy_kwh'])


def list_schedule(p,routes,rule='deadline',jitter=None,release_overrides=None):
    aa={k:np.zeros(f.count) for k,f in p.fleet.items()}
    bb={k:np.zeros(f.batteries) for k,f in p.fleet.items()}
    release_overrides=release_overrides or {};jitter=jitter or {}
    def key(r):
        soft=min(p.boxes[i].due-r.delivery[i] for i in r.boxes)
        primary=r.latest if math.isfinite(r.latest) else soft+1e5
        if rule=='longest': primary=-r.aircraft_hold
        return (primary+jitter.get(r.id,0),soft,r.id)
    jobs=[]
    for r in sorted(routes,key=key):
        k=r.kind;a=int(np.argmin(aa[k]));b=int(np.argmin(bb[k]))
        s=max(float(aa[k][a]),float(bb[k][b]),r.release,release_overrides.get(r.id,0))
        jobs.append(Job(r,s,a,b));aa[k][a]=s+r.aircraft_hold;bb[k][b]=s+r.battery_hold
    return jobs


def recolor(p,route_starts):
    """Color fixed intervals separately: same depot and compatible pooled batteries."""
    assigned={id(pair):{} for pair in route_starts}
    for kind,f in p.fleet.items():
        subset=[pair for pair in route_starts if pair[0].kind==kind]
        for label,hold,cap in [('aircraft','aircraft_hold',f.count),('battery','battery_hold',f.batteries)]:
            ready=np.zeros(cap)
            for pair in sorted(subset,key=lambda x:x[1]):
                r,s=pair;rid=int(np.argmin(ready))
                if ready[rid]>s+1e-5: raise RuntimeError('capacity model / interval assignment mismatch')
                assigned[id(pair)][label]=rid;ready[rid]=s+getattr(r,hold)
    return [Job(r,s,assigned[id(pair)]['aircraft'],assigned[id(pair)]['battery']) for pair in route_starts for r,s in [pair]]


def integrated_milp(p,pool,horizon,step=60.,time_limit=5.,energy_phase=False,energy_first=False):
    """Exact within supplied route pool/start grid/horizon, subject to solver gap.
    Stages: tardiness -> makespan -> optional energy. An unfinished first stage
    yields incumbent-conditioned lexicographic refinement, not global lex optimum.
    """
    if step<=0 or horizon<=0: raise ValueError('positive horizon and grid step required')
    n=len(p.boxes);types=list(p.fleet);ti={k:i for i,k in enumerate(types)}
    options=[]
    for r in pool:
        last=min(r.latest,horizon-r.duration)
        for tick in range(max(0,math.ceil(r.release/step)),math.floor((last+1e-8)/step)+1):
            options.append((r,tick*step))
    if not options: return [],{'status':'no_route_start_options'}
    nv=len(options)+1;z=nv-1
    tail=max(max(r.aircraft_hold,r.battery_hold) for r in pool)
    nt=int(math.ceil((horizon+tail)/step))+1
    ncap=2*len(types)*nt
    rr=[];cc=[];vv=[]
    tard=np.zeros(nv);en=np.zeros(nv)
    def add(row,col,value=1.): rr.append(row);cc.append(col);vv.append(value)
    for col,(r,s) in enumerate(options):
        for i in r.boxes:
            add(i,col)
            add(n+ncap+i,col,s+r.duration)
            tard[col]+=p.boxes[i].weight*max(0,s+r.delivery[i]-p.boxes[i].due)
        en[col]=r.energy
        for u,hold in enumerate([r.aircraft_hold,r.battery_hold]):
            base=n+(2*ti[r.kind]+u)*nt
            for tick in range(int(round(s/step)),math.ceil((s+hold-1e-8)/step)):
                add(base+tick,col)
    for i in range(n): add(n+ncap+i,z,-1.)
    a=coo_matrix((vv,(rr,cc)),shape=(2*n+ncap,nv)).tocsc()
    low=np.r_[np.ones(n),np.full(ncap+n,-np.inf)]
    cap=[]
    for k in types: cap += [p.fleet[k].count]*nt+[p.fleet[k].batteries]*nt
    high=np.r_[np.ones(n),cap,np.zeros(n)]
    bounds=Bounds(np.zeros(nv),np.r_[np.ones(nv-1),horizon])
    integ=np.r_[np.ones(nv-1),0]
    stages=[];incumbent=None
    objectives=[('tardiness',tard),('makespan',np.eye(1,nv,z).ravel())]
    if energy_phase: objectives.append(('energy',en))
    if energy_first: objectives=[('tardiness',tard),('energy',en),('makespan',np.eye(1,nv,z).ravel())]
    for name,c in objectives:
        out=milp(c,integrality=integ,bounds=bounds,constraints=LinearConstraint(a,low,high),options={'time_limit':float(time_limit),'mip_rel_gap':1e-5})
        stages.append({'stage':name,'status':int(out.status),'objective':None if out.fun is None else float(out.fun),'gap':None if out.x is None else float(out.mip_gap),'bound':None if out.x is None else float(out.mip_dual_bound)})
        if out.x is None: break
        incumbent=out.x
        a=vstack([a,csr_matrix(c[None,:])],format='csc');low=np.r_[low,-np.inf];high=np.r_[high,float(c@out.x)+1e-5]
    detail={'backend':'scipy-highs','options':len(options),'routes':len(pool),'step_s':step,'horizon_s':horizon,'stages':stages,'all_stages_optimal':all(s['status']==0 for s in stages) and len(stages)==len(objectives)}
    if incumbent is None: return [],detail
    selected=[options[i] for i in np.flatnonzero(incumbent[:-1]>.5)]
    jobs=recolor(p,selected)
    m=metrics(p,jobs)
    if m['unserved'] or m['duplicated'] or m['resource_overlaps'] or m['hard_violations']:
        raise RuntimeError(f'integrated incumbent inconsistent: {m}')
    return jobs,detail


def alns(p,pool,initial,seed=0,iterations=100,time_limit=15.):
    """Adaptive route-level ruin/recreate. Small repair MILPs + pooled scheduling."""
    rng=np.random.default_rng(seed);current=list(initial);best=list(initial)
    operators=['random','late','geographic'];weights=np.ones(3)
    history=[];t0=time.perf_counter()
    for it in range(iterations):
        if time.perf_counter()-t0>=time_limit: break
        op=int(rng.choice(3,p=weights/weights.sum()))
        count=min(len(current),max(2,int(math.ceil(len(current)*rng.uniform(.15,.4)))))
        if op==0: ids=rng.choice(len(current),count,replace=False)
        elif op==1:
            ids=sorted(range(len(current)),key=lambda k:sum(p.boxes[i].weight*max(0,current[k].start+current[k].route.delivery[i]-p.boxes[i].due) for i in current[k].route.boxes),reverse=True)[:count]
        else:
            center=p.nodes[p.boxes[int(rng.integers(len(p.boxes)))].node]
            ids=sorted(range(len(current)),key=lambda k:min(math.hypot(p.nodes[n].x-center.x,p.nodes[n].y-center.y) for n in current[k].route.stops))[:count]
        destroyed=set(int(i) for i in ids);left=[j.route for k,j in enumerate(current) if k not in destroyed]
        uncovered={i for k in destroyed for i in current[k].route.boxes};mapping={i:k for k,i in enumerate(sorted(uncovered))}
        sub=[r for r in pool if set(r.boxes)<=uncovered]
        rr=[];cc=[]
        for col,r in enumerate(sub):
            for i in r.boxes: rr.append(mapping[i]);cc.append(col)
        a=coo_matrix((np.ones(len(rr)),(rr,cc)),shape=(len(mapping),len(sub))).tocsc()
        # Perturbed costs explore allocations; final comparison uses actual schedules.
        c=np.array([r.aircraft_hold/max(1,p.fleet[r.kind].count)+.15*r.battery_hold/max(1,p.fleet[r.kind].batteries) for r in sub])*rng.uniform(.75,1.25,len(sub))
        fit=milp(c,integrality=np.ones(len(sub)),bounds=Bounds(0,1),constraints=LinearConstraint(a,1,1),options={'time_limit':.25,'mip_rel_gap':.02})
        if fit.x is None: continue
        routes=left+[sub[k] for k in np.flatnonzero(fit.x>.5)]
        candidate=list_schedule(p,routes,jitter={r.id:float(rng.normal(0,120)) for r in routes})
        cm,bm=metrics(p,candidate),metrics(p,best)
        reward=1.
        if score(cm)<score(bm):
            best=candidate;reward=8.;history.append({'iteration':it,'operator':operators[op],**cm})
        def value(m): return m['hard_violations']*1e4+m['hard_lateness_s']*10+m['weighted_tardiness_s']/300+m['makespan_s']/1000
        delta=value(cm)-value(metrics(p,current));temperature=max(.01,.6*(1-it/max(1,iterations)))
        if delta<=0 or rng.random()<np.exp(-min(delta/temperature,700)): current=candidate;reward=max(reward,2.)
        weights[op]=.9*weights[op]+.1*reward
    return best,{'iterations':it+1 if iterations else 0,'history':history,'operator_weights':dict(zip(operators,weights.tolist()))}


def cpsat(p,pool,horizon,time_limit=60.,workers=8,seed=0):
    """Optional CP-SAT backend: flexible one-second starts, no time-index expansion.
    Complete implementation, not executed in the delivery environment (no OR-Tools).
    """
    from ortools.sat.python import cp_model
    model=cp_model.CpModel();h=int(math.ceil(horizon));selected=[];starts=[]
    aircraft={k:[] for k in p.fleet};battery={k:[] for k in p.fleet};arrivals={i:model.new_int_var(0,h,f'arrive_{i}') for i in range(len(p.boxes))}
    active={i:[] for i in range(len(p.boxes))};makespan=model.new_int_var(0,h,'makespan')
    for j,r in enumerate(pool):
        z=model.new_bool_var(f'r{j}');s=model.new_int_var(0,h,f's{j}');selected.append(z);starts.append(s)
        model.add(s>=math.ceil(r.release)).only_enforce_if(z)
        model.add(s+math.ceil(r.duration)<=h).only_enforce_if(z)
        model.add(makespan>=s+math.ceil(r.duration)).only_enforce_if(z)
        for label,hold,target in [('a',r.aircraft_hold,aircraft),('b',r.battery_hold,battery)]:
            length=math.ceil(hold);e=model.new_int_var(0,h+length,f'{label}e{j}')
            target[r.kind].append(model.new_optional_interval_var(s,length,e,z,f'{label}{j}'))
        for i in r.boxes:
            active[i].append(z);model.add(arrivals[i]==s+math.ceil(r.delivery[i])).only_enforce_if(z)
    late=[]
    for i,b in enumerate(p.boxes):
        model.add_exactly_one(active[i]);v=model.new_int_var(0,h,f'late{i}')
        model.add_max_equality(v,[0,arrivals[i]-math.floor(b.due)])
        if b.hard_due is not None: model.add(arrivals[i]<=math.floor(b.hard_due))
        late.append(int(round(b.weight*100))*v)
    for k,f in p.fleet.items():
        model.add_cumulative(aircraft[k],[1]*len(aircraft[k]),f.count)
        model.add_cumulative(battery[k],[1]*len(battery[k]),f.batteries)
    solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=float(time_limit);solver.parameters.num_search_workers=workers;solver.parameters.random_seed=seed
    stages=[];best=None
    for label,objective in [('tardiness',sum(late)),('makespan',makespan)]:
        model.minimize(objective);status=solver.solve(model)
        stages.append({'stage':label,'status':solver.status_name(status),'bound':float(solver.best_objective_bound)})
        if status not in (cp_model.OPTIMAL,cp_model.FEASIBLE): break
        best=[(r,float(solver.value(starts[j]))) for j,r in enumerate(pool) if solver.value(selected[j])]
        model.add(objective<=int(round(solver.objective_value)))
    return ([] if best is None else recolor(p,best)),{'backend':'ortools-cpsat','stages':stages,'time_rounding_s':1}


def dispatch(p,pool):
    """Resource-aware earliest-deadline dispatch; repair for static route grouping.
    An anchor's delivery time competes with batching, using current aircraft AND
    full-battery availability. No global feasibility/optimality claim.
    """
    remaining=set(range(len(p.boxes)));aa={k:np.zeros(f.count) for k,f in p.fleet.items()};bb={k:np.zeros(f.batteries) for k,f in p.fleet.items()};jobs=[]
    bybox={i:[] for i in remaining}
    for r in pool:
        for i in r.boxes: bybox[i].append(r)
    while remaining:
        anchor=min(remaining,key=lambda i:(p.boxes[i].hard_due is None,p.boxes[i].hard_due if p.boxes[i].hard_due is not None else p.boxes[i].due))
        candidates=[]
        for r in bybox[anchor]:
            if not set(r.boxes)<=remaining: continue
            k=r.kind;a=int(np.argmin(aa[k]));b=int(np.argmin(bb[k]));start=max(r.release,float(aa[k][a]),float(bb[k][b]))
            hard=sum(max(0,start+r.delivery[i]-p.boxes[i].hard_due) for i in r.boxes if p.boxes[i].hard_due is not None)
            soft=sum(p.boxes[i].weight*max(0,start+r.delivery[i]-p.boxes[i].due) for i in r.boxes)
            rank=(hard,start+r.delivery[anchor]-min(90.,25.*(len(r.boxes)-1))+.01*r.duration/len(r.boxes),soft,r.duration)
            candidates.append((rank,r,start,a,b))
        if not candidates: raise ValueError('no feasible candidate for remaining anchor')
        _,r,start,a,b=min(candidates,key=lambda v:v[0]);jobs.append(Job(r,start,a,b));remaining.difference_update(r.boxes)
        aa[r.kind][a]=start+r.aircraft_hold;bb[r.kind][b]=start+r.battery_hold
    return jobs
