"""Scenario replay of fixed route/resource orders: empirical CVaR, not a forecast."""
import numpy as np


def replay(p,jobs,seed=0,scenarios=200,sigma=.08):
    if scenarios<1 or not np.isfinite(sigma) or sigma<0: raise ValueError("positive scenario count and nonnegative sigma required")
    rng=np.random.default_rng(seed);values=[]
    ordered=sorted(jobs,key=lambda j:(j.start,j.route.id))
    for _ in range(scenarios):
        # Shared weather multiplier + route-specific operation noise.
        weather=float(rng.lognormal(-sigma*sigma/2,sigma));aa={};bb={};late=0.;hard=0;end=0.
        for j in ordered:
            r=j.route;f=p.fleet[r.kind]
            multiplier=weather*float(rng.lognormal(-sigma*sigma/8,sigma/2))
            s=max(j.start,aa.get((r.kind,j.aircraft),0),bb.get((r.kind,j.battery),0))
            duration=f.prepare+(r.duration-f.prepare)*multiplier
            consumed=r.energy*multiplier
            energy_bad=consumed>f.usable_kwh*(1-f.reserve)
            # Report energy violation; replay cannot invent an extra charge in flight.
            for i,o in r.delivery.items():
                t=s+f.prepare+(o-f.prepare)*multiplier;b=p.boxes[i]
                late+=b.weight*max(0,t-b.due)
                hard+=int(b.hard_due is not None and t>b.hard_due)
            aa[(r.kind,j.aircraft)]=s+duration+f.turnaround
            bb[(r.kind,j.battery)]=s+duration+f.charge(consumed)
            end=max(end,s+duration)
            if energy_bad: hard+=1
        values.append([late,end,hard])
    a=np.array(values,float)
    tail=max(1,int(np.ceil(.1*len(a))))
    return {'scenario_assumptions':{'seed':seed,'count':scenarios,'lognormal_sigma':sigma},'mean_tardiness_s':float(a[:,0].mean()),'cvar90_tardiness_s':float(np.sort(a[:,0])[-tail:].mean()),'mean_makespan_s':float(a[:,1].mean()),'fraction_with_deadline_or_energy_violation':float(np.mean(a[:,2]>0)),'note':'synthetic perturbations and fixed resource order; NOT estimated weather probabilities; radio not replayed'}
