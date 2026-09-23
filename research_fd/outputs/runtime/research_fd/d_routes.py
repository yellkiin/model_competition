"""Route pool generation, set partitioning and LP-dual-guided expansion."""
from itertools import combinations
import math
import numpy as np
from scipy.optimize import milp, linprog, Bounds, LinearConstraint
from scipy.sparse import coo_matrix
from .d_model import Problem, Route


def unique_routes(routes):
    out={}
    for r in routes:
        if r is not None: out[(r.kind,r.boxes,r.stops)]=r
    ans=list(out.values())
    # Clone IDs; do not overwrite cached objects shared with another pool.
    from dataclasses import replace
    return [replace(r,id=i) for i,r in enumerate(ans)]


def build_pool(p:Problem,seed=0,trials=400,max_stops=3,max_boxes=8,exhaustive=False):
    rng=np.random.default_rng(seed); n=len(p.boxes)
    pool=[]
    for kind in p.fleet:
        pool += [p.route([i],kind) for i in range(n)]
    if exhaustive:
        if n>12: raise ValueError('exhaustive subset generation is limited to 12 boxes')
        for m in range(2,min(n,max_boxes)+1):
            for subset in combinations(range(n),m):
                stops={p.boxes[i].node for i in subset}
                if len(stops)>max_stops: continue
                for kind in p.fleet: pool.append(p.route(subset,kind))
    else:
        for node in sorted({b.node for b in p.boxes}):
            ids=[i for i,b in enumerate(p.boxes) if b.node==node]
            for kind in p.fleet:
                for rule in ('mass','due','random'):
                    left=sorted(ids,key=lambda i: -p.boxes[i].mass if rule=='mass' else p.boxes[i].due)
                    if rule=='random': rng.shuffle(left)
                    while left:
                        group=[left.pop(0)]
                        for i in left.copy():
                            if len(group)<max_boxes and p.route(group+[i],kind): group.append(i); left.remove(i)
                        pool.append(p.route(group,kind))
        for _ in range(trials):
            i=int(rng.integers(n)); kind=str(rng.choice(list(p.fleet))); group=[i]
            u=p.nodes[p.boxes[i].node]
            # Geography, deadline, random exploration are all represented.
            mode=int(rng.integers(3))
            scores=[]
            for j,b in enumerate(p.boxes):
                v=p.nodes[b.node]
                score=math.hypot(u.x-v.x,u.y-v.y) if mode==0 else abs(b.due-p.boxes[i].due) if mode==1 else rng.uniform(0,5000)
                scores.append(score+rng.uniform(0,500))
            for j in np.argsort(scores):
                j=int(j)
                if j in group or len(group)>=max_boxes: continue
                if len({p.boxes[k].node for k in group+[j]})>max_stops: continue
                r=p.route(group+[j],kind)
                if r: group.append(j); pool.append(r)
            pool.append(p.route(group,kind))
    pool=unique_routes(pool)
    covered={i for r in pool for i in r.boxes}
    if len(covered)<n:
        raise ValueError(f'boxes with no feasible route: {[p.boxes[i].id for i in set(range(n))-covered]}')
    return pool


def incidence(pool,n):
    rr=[];cc=[]
    for j,r in enumerate(pool):
        rr.extend(r.boxes);cc.extend([j]*len(r.boxes))
    return coo_matrix((np.ones(len(rr)),(rr,cc)),shape=(n,len(pool))).tocsc()


def route_cost(pool,objective='work'):
    if objective=='trips': return np.ones(len(pool))
    if objective=='energy': return np.array([r.energy for r in pool])
    return np.array([r.aircraft_hold for r in pool])


def partition_master(pool,n,time_limit=10.,objective='work'):
    a=incidence(pool,n); c=route_cost(pool,objective)
    r=milp(c,integrality=np.ones(len(pool)),bounds=Bounds(0,1),constraints=LinearConstraint(a,1,1),options={'time_limit':time_limit,'mip_rel_gap':1e-6})
    if r.x is None: return [],{'status':int(r.status),'message':r.message}
    chosen=[pool[i] for i in np.flatnonzero(r.x>.5)]
    cover=np.asarray(a@(r.x>.5)).ravel()
    if not np.all(cover==1): raise RuntimeError('nonintegral incumbent does not partition boxes')
    return chosen,{'status':int(r.status),'objective':float(r.fun),'gap':float(r.mip_gap),'bound':float(r.mip_dual_bound),'scope':'restricted candidate pool; not a global VRP bound'}


def dual_expand(p,pool,seed=0,rounds=3,trials=180,max_stops=3,max_boxes=8):
    rng=np.random.default_rng(seed); history=[]
    for iteration in range(rounds):
        a=incidence(pool,len(p.boxes)); c=route_cost(pool)
        lp=linprog(c,A_eq=a,b_eq=np.ones(len(p.boxes)),bounds=(0,None),method='highs')
        if not lp.success: raise RuntimeError(lp.message)
        dual=np.asarray(lp.eqlin.marginals)
        candidates=[]
        for _ in range(trials):
            kind=str(rng.choice(list(p.fleet)))
            start=int(rng.choice(len(dual),p=np.maximum(dual,1)/np.maximum(dual,1).sum()))
            group=[start]; old=p.route(group,kind)
            if old is None: continue
            left=set(range(len(dual)))-{start}
            while left and len(group)<max_boxes:
                possibilities=[]
                for j in rng.permutation(sorted(left))[:30]:
                    j=int(j)
                    if len({p.boxes[k].node for k in group+[j]})>max_stops: continue
                    r=p.route(group+[j],kind)
                    if r:
                        gain=dual[j]-(r.aircraft_hold-old.aircraft_hold)
                        possibilities.append((gain+rng.normal(0,30),j,r))
                if not possibilities: break
                _,j,old=max(possibilities,key=lambda z:z[0]); group.append(j);left.remove(j)
                if old.aircraft_hold-sum(dual[k] for k in old.boxes)<-1e-6: candidates.append(old)
        oldn=len(pool);pool=unique_routes(pool+candidates)
        history.append({'round':iteration,'restricted_lp':float(lp.fun),'columns_added':len(pool)-oldn})
        if len(pool)==oldn: break
    return pool,history


def greedy_partition(pool,n):
    left=set(range(n));chosen=[]
    while left:
        options=[r for r in pool if set(r.boxes)<=left]
        if not options: raise ValueError('no route for remaining boxes')
        r=min(options,key=lambda r:(r.aircraft_hold/len(r.boxes),-len(r.boxes),r.id))
        chosen.append(r);left.difference_update(r.boxes)
    return chosen
