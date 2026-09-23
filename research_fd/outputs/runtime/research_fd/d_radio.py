"""DEM-based radio maps, depot-return relay sessions, and joint retiming MILP.
Communication is evaluated on phase boundaries + a configurable temporal grid.
This is numerical radio optimization, not an all-real-time propagation theorem.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import math
from functools import lru_cache
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix, vstack, csr_matrix
from .d_model import Problem
from .d_schedule import Job, recolor, metrics

@dataclass
class Session:
    site: int
    xyz: list[float]
    departure: float
    ready: float
    stop: float
    returned: float
    aircraft_end: float
    pack_end: float
    energy: float
    covers: list[int]
    # Legacy synthetic data has zero ground preparation. Official sessions keep
    # departure as the resource-occupation start and report physical takeoff.
    preparation_s: float = 0.0
    departure_semantics: str = 'airborne_departure'
    takeoff: float | None = None
    arrival: float | None = None
    flight_energy_kwh: float | None = None
    cruise_energy_kwh: float | None = None
    climb_energy_kwh: float | None = None
    hover_energy_kwh: float | None = None
    communication_energy_kwh: float | None = None


def relay_flight_components(p, xyz):
    """Times and energy for one out-and-back physical relay trip.

    The official rule bills horizontal cruise and climb potential separately.
    The original constant-power flight model is retained for synthetic inputs.
    """
    cfg=p.data['relay'];depot=p.nodes[p.depot]
    base=[depot.x,depot.y,depot.z]
    horizontal=float(np.linalg.norm(np.asarray(xyz[:2])-base[:2]))
    peak=max(p.terrain.peak(xyz[:2],base[:2],p.arc_step)+p.clearance,xyz[2],base[2])
    outbound=(peak-base[2])/cfg['climb_speed']+horizontal/cfg['speed']+(peak-xyz[2])/cfg['descend_speed']
    inbound=(peak-xyz[2])/cfg['climb_speed']+horizontal/cfg['speed']+(peak-base[2])/cfg['descend_speed']
    official=cfg.get('energy_model')=='official_horizontal_climb'
    if official:
        cruise=cfg['travel_kw']*(2*horizontal/cfg['speed'])/3600
        climb=cfg['takeoff_mass_kg']*cfg.get('gravity_m_s2',9.80665)*((peak-base[2])+(peak-xyz[2]))/(cfg['climb_efficiency']*3.6e6)
        flight=cruise+climb
        hover=cfg['hover_only_kw']+cfg['communication_kw']
        if abs(hover-cfg['hover_kw'])>1e-10:
            raise ValueError('official hover_kw must equal hover_only_kw + communication_kw')
    else:
        cruise=climb=None
        flight=cfg['travel_kw']*(outbound+inbound)/3600
        hover=cfg['hover_kw']
    if hover<=0 or cfg.get('prepare',0)<0:
        raise ValueError('relay hover power must be positive and preparation nonnegative')
    return dict(horizontal_m=horizontal,peak_m=peak,outbound_s=outbound,inbound_s=inbound,
                flight_energy_kwh=flight,cruise_energy_kwh=cruise,climb_energy_kwh=climb,
                hover_total_kw=hover,official=official)


def margin(p:Problem,a,b,budget):
    spec=p.data['radio'];d=max(1.,float(np.linalg.norm(np.asarray(a)-b)))
    loss=32.45+20*math.log10(spec['frequency_mhz'])+20*math.log10(d/1000)
    loss+=spec['obstruction_db']*p.terrain.blocked(a,b,spec.get('ray_step_m',30.))
    return budget-loss


def ground(p):
    n=p.nodes[p.depot]
    return [n.x,n.y,n.z+p.data['radio'].get('ground_antenna_m',0.)]


def candidates(p,grid=5):
    cfg=p.data['relay'];n=list(p.nodes.values());points=[(x.x,x.y) for x in n]
    points += [(x.x/2+p.nodes[p.depot].x/2,x.y/2+p.nodes[p.depot].y/2) for x in n]
    for x in np.linspace(min(v.x for v in n),max(v.x for v in n),grid):
        for y in np.linspace(min(v.y for v in n),max(v.y for v in n),grid): points.append((float(x),float(y)))
    out=[]
    for x,y in sorted(set(points)):
        try: z=float(p.terrain.height([[x,y]])[0])
        except ValueError: continue  # candidate grid can extend beyond raster polygon
        for h in cfg['heights_m']:
            if h<0 or h>300: raise ValueError('relay candidate height outside [0,300] m AGL')
            xyz=[x,y,z+h]
            if margin(p,xyz,ground(p),p.data['radio']['backhaul_budget_db'])>=0: out.append(xyz)
    return out


def route_samples(route,start,dt=60.):
    samples=[]
    for seg in route.segments:
        span=seg['t1']-seg['t0'];steps=max(1,int(math.ceil(span/dt)))
        for u in np.linspace(0.,1.,steps+1):
            samples.append((start+seg['t0']+u*span,((1-u)*np.asarray(seg['a'])+u*np.asarray(seg['b'])).tolist()))
    # Phase boundaries can be duplicated; preserve one value per identical event.
    return sorted({(round(t,7),tuple(x)) for t,x in samples})


def demands_for_options(p,options,sample_step=60.):
    out=[];base=ground(p);budget=p.data['radio']['direct_budget_db']
    cached={}
    for owner,(r,start) in enumerate(options):
        for t,xyz in route_samples(r,start,sample_step):
            key=tuple(xyz)
            if key not in cached: cached[key]=margin(p,xyz,base,budget)
            if cached[key]<0:
                out.append({'time':float(t),'xyz':list(xyz),'owner':owner,'route_id':r.id,'direct_margin_db':float(cached[key])})
    return out


def session_pool(p,demands,sites,step=60.,max_sessions=18000):
    if not demands: return [],{'requirements':0,'unreachable':[],'sites':len(sites)}
    cfg=p.data['relay'];depot=p.nodes[p.depot];base=[depot.x,depot.y,depot.z]
    cover=np.zeros((len(sites),len(demands)),bool);cache={}
    for s,xyz in enumerate(sites):
        for i,d in enumerate(demands):
            key=(s,tuple(d['xyz']))
            if key not in cache: cache[key]=margin(p,xyz,d['xyz'],p.data['radio']['access_budget_db'])>=0
            cover[s,i]=cache[key]
    unreachable=np.flatnonzero(~cover.any(axis=0)).tolist()
    times=np.array([d['time'] for d in demands]);slots=np.floor(times/step+1e-9).astype(int)
    sessions=[]
    for site,xyz in enumerate(sites):
        ids=np.flatnonzero(cover[site]);valid_slots=np.unique(slots[ids])
        physical=relay_flight_components(p,xyz)
        outbound=physical['outbound_s'];inbound=physical['inbound_s']
        prepare=float(cfg.get('prepare',0.))
        for lo in valid_slots:
            lead=math.ceil((prepare+outbound+cfg['setup'])/step)
            departure=(lo-lead)*step
            if departure<0: continue
            ready=lo*step
            # Include short windows, powers of two and the longest energy-feasible one.
            maxhover=(cfg['energy_kwh']*(1-cfg['reserve'])-physical['flight_energy_kwh'])*3600/physical['hover_total_kw']
            takeoff=departure+prepare;arrival=takeoff+outbound
            maxend=math.floor((arrival+maxhover)/step)
            ends=sorted(set([int(lo+1),int(lo+2),int(lo+4),int(lo+8),int(lo+16),int(lo+32),int(maxend)]))
            for hi in ends:
                if hi<=lo or hi>maxend: continue
                ids2=ids[(slots[ids]>=lo)&(slots[ids]<hi)]
                if len(ids2)==0: continue
                stop=hi*step;returned=stop+inbound
                hover_duration=stop-arrival
                energy=physical['flight_energy_kwh']+physical['hover_total_kw']*hover_duration/3600
                soc=max(0.,1-energy/cfg['energy_kwh']);a=cfg['charge_knee'];k=cfg['charge_slow']
                charge=cfg['full_charge']*(max(a-soc,0)+k*(1-max(a,soc)))/(a+k*(1-a))
                if cfg.get('charge_table') is not None:
                    table=np.asarray(cfg['charge_table'],float);charge=float(table[-1,1]-np.interp(soc,table[:,0],table[:,1]))
                sessions.append(Session(site,list(xyz),departure,ready,stop,returned,math.ceil((returned+cfg['turnaround'])/step)*step,math.ceil((returned+charge)/step)*step,energy,ids2.tolist(),
                    preparation_s=prepare,
                    departure_semantics='resource_start_before_preparation' if prepare else 'airborne_departure',
                    takeoff=takeoff,arrival=arrival,
                    flight_energy_kwh=physical['flight_energy_kwh'],
                    cruise_energy_kwh=physical['cruise_energy_kwh'],climb_energy_kwh=physical['climb_energy_kwh'],
                    hover_energy_kwh=(cfg['hover_only_kw'] if physical['official'] else cfg['hover_kw'])*hover_duration/3600,
                    communication_energy_kwh=cfg['communication_kw']*hover_duration/3600 if physical['official'] else 0.))
    # Cap is only computational. A truncated pool may miss a feasible solution.
    truncated=len(sessions)>max_sessions
    if truncated:
        sessions=sorted(sessions,key=lambda s:(-len(s.covers)/(1+(s.aircraft_end-s.departure)/step),s.energy))[:max_sessions]
    return sessions,{'requirements':len(demands),'unreachable':unreachable,'sites':len(sites),'sessions':len(sessions),'pool_truncated':truncated}


def solve_joint_fixed_routes(p,routes,sites,step=60.,sample_step=60.,time_limit=10.,fixed_starts=None,horizon=None,max_sessions=18000,reference_jobs=None,shift_window=600.):
    """Choose one start per fixed route and physically scheduled relay sessions.
    fixed_starts activates the sequential baseline; otherwise it jointly retimes
    transport and relay while retaining every box group and node visit order.
    """
    options=[]
    if fixed_starts is not None:
        if metrics(p,fixed_starts)['resource_overlaps']:
            raise ValueError('fixed transport schedule has resource overlaps')
        options=[(j.route,j.start) for j in fixed_starts]
    else:
        if horizon is None: raise ValueError('horizon required for retiming')
        reference={} if reference_jobs is None else {j.route.id:j.start for j in reference_jobs}
        for r in routes:
            lo=r.release;hi=min(horizon-r.duration,r.latest)
            if r.id in reference:
                lo=max(lo,reference[r.id]-shift_window);hi=min(hi,reference[r.id]+shift_window)
            options += [(r,t*step) for t in range(math.ceil(lo/step),math.floor((hi+1e-8)/step)+1)]
    if not options: return [],[],{'status':'no_start_options'}
    demands=demands_for_options(p,options,sample_step);sessions,info=session_pool(p,demands,sites,step,max_sessions)
    # Unreachable requirements imply impossibility for a fixed plan; in retiming
    # they deactivate their option and may leave another option usable.
    no=len(options);ns=len(sessions);z=no+ns;nv=z+1
    rows=[];cols=[];values=[];lower=[];upper=[]
    def row(entries,lo=-np.inf,hi=np.inf):
        k=len(lower);lower.append(lo);upper.append(hi)
        for c,v in entries: rows.append(k);cols.append(c);values.append(v)
    for r in routes: row([(i,1.) for i,(r2,_) in enumerate(options) if r.id==r2.id],1,1)
    by_req=[[] for _ in demands]
    for j,s in enumerate(sessions):
        for d in s.covers: by_req[d].append((no+j,1.))
    for i,d in enumerate(demands): row([(d['owner'],-1.),*by_req[i]],0,np.inf)
    end=max([s.pack_end for s in sessions]+[start+max(r.aircraft_hold,r.battery_hold) for r,start in options])
    ticks=int(math.ceil(end/step))+1
    caps={}
    for k,f in p.fleet.items(): caps[('a',k)]=f.count;caps[('b',k)]=f.batteries
    caps[('relay','R')]=p.data['relay']['count'];caps[('pack','R')]=p.data['relay']['packs']
    occup={key:{} for key in caps}
    def occupy(key,col,start,end):
        for t in range(math.floor(start/step+1e-9),math.ceil((end-1e-8)/step)):
            occup[key].setdefault(t,[]).append((col,1.))
    for i,(r,start) in enumerate(options):
        if fixed_starts is None:
            occupy(('a',r.kind),i,start,start+r.aircraft_hold);occupy(('b',r.kind),i,start,start+r.battery_hold)
        row([(i,start+r.duration),(z,-1.)],hi=0)
    for j,s in enumerate(sessions):
        occupy(('relay','R'),no+j,s.departure,s.aircraft_end);occupy(('pack','R'),no+j,s.departure,s.pack_end)
        row([(no+j,s.returned),(z,-1.)],hi=0)
    for key,entries in occup.items():
        for vals in entries.values(): row(vals,hi=caps[key])
    a=coo_matrix((values,(rows,cols)),shape=(len(lower),nv)).tocsc();lower=np.array(lower);upper=np.array(upper)
    h=float(end);bounds=Bounds(np.zeros(nv),np.r_[np.ones(z),h]);integ=np.r_[np.ones(z),0.]
    tard=np.zeros(nv);makespan=np.zeros(nv);makespan[z]=1.
    energy=np.zeros(nv)
    for i,(r,start) in enumerate(options):
        tard[i]=sum(p.boxes[b].weight*max(0,start+r.delivery[b]-p.boxes[b].due) for b in r.boxes);energy[i]=r.energy
    for j,s in enumerate(sessions): energy[no+j]=s.energy
    stages=[];last=None
    for label,c in [('tardiness',tard),('joint_makespan',makespan),('total_energy',energy)]:
        fit=milp(c,integrality=integ,bounds=bounds,constraints=LinearConstraint(a,lower,upper),options={'time_limit':time_limit,'mip_rel_gap':1e-4})
        stages.append({'stage':label,'status':int(fit.status),'value':None if fit.fun is None else float(fit.fun),'gap':None if fit.x is None else float(fit.mip_gap)})
        if fit.x is None: break
        last=fit.x;a=vstack([a,csr_matrix(c[None,:])],format='csc');lower=np.r_[lower,-np.inf];upper=np.r_[upper,float(c@last)+1e-5]
    detail={**info,'options':no,'stages':stages,'sample_step_s':sample_step,'schedule_step_s':step,'status':'feasible' if last is not None else 'no_incumbent'}
    if last is None: return [],[],detail
    jobs=recolor(p,[options[i] for i in np.flatnonzero(last[:no]>.5)])
    chosen=[sessions[i] for i in np.flatnonzero(last[no:z]>.5)]
    # Assign relay entities and energy components independently after cumulative solve.
    for label,endattr,count in [('aircraft','aircraft_end',p.data['relay']['count']),('pack','pack_end',p.data['relay']['packs'])]:
        ready=np.zeros(count)
        for s in sorted(chosen,key=lambda s:s.departure):
            k=int(np.argmin(ready))
            if ready[k]>s.departure+1e-6: raise RuntimeError('relay interval assignment mismatch')
            setattr(s,label,k);ready[k]=getattr(s,endattr)
    detail['joint_makespan_s']=max([j.start+j.route.duration for j in jobs]+[s.returned for s in chosen])
    detail['relay_energy_kwh']=float(sum(s.energy for s in chosen));detail['relay_trips']=len(chosen)
    return jobs,chosen,detail


def evaluate_radio(p,jobs,sessions,dt=10.):
    base=ground(p);cfg=p.data['radio'];misses=[];minimum=math.inf;count=0
    for j in jobs:
        for t,xyz in route_samples(j.route,j.start,dt):
            best=margin(p,xyz,base,cfg['direct_budget_db'])
            for s in sessions:
                if s.ready-1e-7<=t<=s.stop+1e-7:
                    best=max(best,min(margin(p,xyz,s.xyz,cfg['access_budget_db']),margin(p,s.xyz,base,cfg['backhaul_budget_db'])))
            minimum=min(minimum,best);count+=1
            if best<-1e-7: misses.append({'route_id':j.route.id,'time':float(t),'margin_db':float(best),'xyz':list(xyz)})
    return {'samples':count,'misses':len(misses),'minimum_margin_db':None if count==0 else float(minimum),'sample_step_s':dt,'details':misses,'scope':'numerical trajectory samples, including every phase boundary'}


def refine_joint(p,jobs,sites,horizon,steps=(60.,20.,5.),time_limit=10.,fixed=False,max_sessions=18000,shift_window=600.):
    """Explicit repair for coarse-radio false feasibility: rebuild at finer dt.
    Stops on a plan passing the next finer numerical evaluation, not a theorem.
    """
    history=[];last=([],[],{})
    for k,dt in enumerate(steps):
        out=solve_joint_fixed_routes(p,[j.route for j in jobs],sites,step=60.,sample_step=dt,time_limit=time_limit,fixed_starts=jobs if fixed else None,horizon=horizon,max_sessions=max_sessions,reference_jobs=jobs,shift_window=shift_window)
        jj,ss,detail=out
        if not jj:
            history.append({'dt':dt,'solver':detail});last=out;break
        check=evaluate_radio(p,jj,ss,steps[min(k+1,len(steps)-1)])
        history.append({'dt':dt,'solver':detail,'fine_check':{x:y for x,y in check.items() if x!='details'}});last=out
        if check['misses']==0: break
    last[2]['refinement_history']=history
    return last


def augment_sites(p,sites,demands,count=6,seed=0):
    """Derivative-free refinement at difficult spatial requirements; budgets unchanged.
    Optimizes min(access margin, backhaul margin) over local x,y,AGL.
    """
    from scipy.optimize import differential_evolution
    cfg=p.data['radio'];base=ground(p);ranked=[]
    for d in demands:
        best=max((margin(p,s,d['xyz'],cfg['access_budget_db']) for s in sites),default=-1000.)
        ranked.append((best,d))
    nodes=list(p.nodes.values());bounds=[(min(n.x for n in nodes),max(n.x for n in nodes)),(min(n.y for n in nodes),max(n.y for n in nodes)),(30.,300.)]
    added=[];used=set()
    for _,d in sorted(ranked,key=lambda a:a[0]):
        key=tuple(np.round(np.asarray(d['xyz'])/200).astype(int))
        if key in used: continue
        used.add(key)
        def point(x): return [float(x[0]),float(x[1]),float(p.terrain.height([x[:2]])[0]+x[2])]
        def objective(x):
            try:
                v=point(x)
                return -min(margin(p,v,d['xyz'],cfg['access_budget_db']),margin(p,v,base,cfg['backhaul_budget_db']))
            except ValueError: return 1e6
        sol=differential_evolution(objective,bounds,seed=seed+len(used),maxiter=25,popsize=8,polish=False)
        if sol.fun<=0:
            v=point(sol.x);sites.append(v);added.append({'xyz':v,'min_margin_db':float(-sol.fun),'solver_converged':bool(sol.success)})
        if len(used)>=count: break
    return sites,added
