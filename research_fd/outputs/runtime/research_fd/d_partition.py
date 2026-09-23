"""Q4: frozen-route hypergraph partitioning and independent resource demand."""
from itertools import product
import numpy as np


def peak(intervals):
    events=[]
    for a,b in intervals:
        if b>a: events.extend([(a,1),(b,-1)])
    active=answer=0
    for _,delta in sorted(events,key=lambda e:(e[0],e[1])):
        active+=delta;answer=max(answer,active)
    return answer


def components(nodes,edges):
    parent={n:n for n in nodes}
    def root(n):
        while parent[n]!=n: parent[n]=parent[parent[n]];n=parent[n]
        return n
    for e in edges:
        e=list(e)
        for n in e[1:]: parent[root(n)]=root(e[0])
    groups={}
    for n in nodes: groups.setdefault(root(n),[]).append(n)
    return list(groups.values())


def resource_vector(p,jobs,sessions):
    out={}
    for k in p.fleet:
        js=[j for j in jobs if j.route.kind==k]
        out[k+'_aircraft']=peak([(j.start,j.start+j.route.aircraft_hold) for j in js])
        out[k+'_battery']=peak([(j.start,j.start+j.route.battery_hold) for j in js])
    out['relay']=peak([(s.departure,s.aircraft_end) for s in sessions])
    out['relay_pack']=peak([(s.departure,s.pack_end) for s in sessions])
    return out


def search_partition(p,jobs,sessions,demands,k=2,policy='strict',trials=20000,seed=0):
    """Strict: a relay session is indivisible. Duplicate: each group repeats its
    supporting session with its own relay and pack. No task time is moved.
    demands must be regenerated for the SELECTED jobs in the same order.
    Session coverage is recomputed geometrically by the caller before this call.
    """
    if policy not in ('strict','duplicate') or k<2: raise ValueError('invalid partition policy or k')
    nodes=sorted({n for j in jobs for n in j.route.stops})
    supporting=[]
    for s in sessions:
        owner_nodes=set()
        for d in demands:
            if d.get('assigned_session')==id(s): owner_nodes.update(jobs[d['owner']].route.stops)
        supporting.append(owner_nodes)
    edges=[set(j.route.stops) for j in jobs]
    if policy=='strict': edges+=supporting
    units=components(nodes,edges)
    if len(units)<k: return {'feasible':False,'reason':'fewer indivisible components than groups','components':units,'policy':policy,'k':k}
    global_resources=resource_vector(p,jobs,sessions);keys=list(global_resources)
    rng=np.random.default_rng(seed)
    def labelings():
        if len(units)<=9:
            # Restricted growth strings enumerate set partitions without label symmetry.
            def grow(labels):
                if len(labels)==len(units):
                    if max(labels)==k-1: yield labels
                    return
                for a in range(min(k-1,max(labels)+1)+1): yield from grow(labels+[a])
            yield from grow([0])
        else:
            for _ in range(trials):
                labels=rng.integers(0,k,len(units)).tolist()
                if len(set(labels))==k: yield labels
    best=None;frontier=[];evaluated=0
    for labels in labelings():
        evaluated+=1;group={n:labels[i] for i,u in enumerate(units) for n in u}
        resources=[];work=[]
        for g in range(k):
            js=[j for j in jobs if group[j.route.stops[0]]==g]
            ss=[s for s,support in zip(sessions,supporting) if any(group[n]==g for n in support)]
            resources.append(resource_vector(p,js,ss));work.append(sum(j.route.duration for j in js))
        total={key:sum(r[key] for r in resources) for key in keys}
        extra={key:total[key]-global_resources[key] for key in keys}
        # Dimensionless reporting objective; raw resource vector also retained.
        redundancy=sum(extra[key]/max(1,global_resources[key]) for key in keys)
        imbalance=float(np.std(work)/max(np.mean(work),1e-9))
        rank=(round(redundancy,10),imbalance)
        if best is None or rank<best[0]:
            best=(rank,{'groups':[[n for n in nodes if group[n]==g] for g in range(k)],'resources':resources,'extra':extra,'normalized_redundancy':redundancy,'workload_cv':imbalance})
    return {'feasible':best is not None,'policy':policy,'k':k,'components':units,'enumeration_exact':len(units)<=9,'evaluated':evaluated,'global_resources':global_resources,**({} if best is None else best[1])}


def assign_support(p,jobs,sessions,dt=20.):
    from .d_radio import demands_for_options,margin
    demands=demands_for_options(p,[(j.route,j.start) for j in jobs],dt)
    for d in demands:
        active=[s for s in sessions if s.ready-1e-7<=d['time']<=s.stop+1e-7 and margin(p,d['xyz'],s.xyz,p.data['radio']['access_budget_db'])>=-1e-7]
        if not active: raise ValueError('radio requirement uncovered; cannot partition an incomplete Q3 plan')
        s=max(active,key=lambda s:margin(p,d['xyz'],s.xyz,p.data['radio']['access_budget_db']))
        d['assigned_session']=id(s)
    return demands
