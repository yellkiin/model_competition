"""Fixed-owner memory epochs and convex Task repair; official plan fields only.

No case-name switches, no altered Spill/recomputation/address allocation.
Every yielded plan needs the original evaluator. Peak/frontier proxies are not
capacity certificates, and phase barriers can hurt makespan despite fewer bytes.
"""
from __future__ import annotations
from collections import defaultdict
from copy import deepcopy
import math
import time
from research_a_orion_anytime.core import plan_view, make_plan, bounds, planned_traffic\nfrom .policy import search_state

VERSION = 'memory-reuse-2.2'

def plan_key(p):
    return (tuple(sorted((int(u), s) for u, s in p['node_to_subgraph'].items())),
            tuple(tuple(x) for x in p['core_schedules']))

def fixed_owner_epochs(g, plan, bins, cohort_size=0):
    """Retile the EXISTING mapping into dependency-depth epochs.

    Independent original components may be batched to limit simultaneously live
    activations. No operation is moved to a different NPU core. Components in a
    cohort are evaluated together; external shared weights are tensor sets.
    """
    m, groups, owners, _ = plan_view(g, plan)
    owner = {u: owners[m[u]] for u in g.ops}
    depth = {}
    for u in g.topo:
        depth[u] = 1 + max((depth[v] for v in g.pred[u]), default=-1)
    levels = sorted(set(depth.values())); rank = {d: i for i, d in enumerate(levels)}
    comps = sorted(g.components, key=lambda c: min(c))
    comp_index = {u: i for i, comp in enumerate(comps) for u in comp}
    bins = min(max(1,bins),len(levels))
    band_of = {u:min(bins-1, rank[depth[u]]*bins//max(1,len(levels))) for u in g.ops}
    return _pack_convex_epochs(g, owner, band_of, comp_index, cohort_size, len(plan['core_schedules']))

def convex_coalesce(g, plan, cfg, q, max_nodes, max_rounds=3):
    """Greedily coalesce adjacent SAME-core Tasks only after quotient validation.

    Candidate preference uses exact pre-Spill tensor-set savings; the candidate
    as a whole is not accepted without a makespan evaluation. Core mapping stays.
    """
    p=deepcopy(plan)
    for _ in range(max_rounds):
        m,groups,owner,order=plan_view(g,p)
        choices=[]
        touched={s:set().union(*(g.inputs[u]|g.outputs[u] for u in nodes)) for s,nodes in groups.items()}
        for seq in p['core_schedules']:
            for a,b in zip(seq,seq[1:]):
                if len(groups[a])+len(groups[b]) > max_nodes:continue
                shared=touched[a]&touched[b]
                benefit=sum(g.tensors[t]['size'] for t in shared)
                choices.append((-benefit,a,b))
        changed=False;used=set()
        for _,a,b in sorted(choices):
            if a in used or b in used:continue
            trial=deepcopy(p)
            for u,s in trial['node_to_subgraph'].items():
                if s==b:trial['node_to_subgraph'][u]=a
            for k,seq in enumerate(trial['core_schedules']):
                trial['core_schedules'][k]=[s for s in seq if s!=b]
            try:plan_view(g,trial)
            except ValueError:continue
            p=trial;used.update((a,b));changed=True
        if not changed:break
    return p

def _pack_convex_epochs(g, owner, band_of, comp_index, cohort_size, n):
    # Within an epoch every cross-core edge raises rank. Grouping by
    # (cohort,epoch,rank,core) therefore cannot create an owner-reentry cycle.
    switch_rank={};parts=defaultdict(set)
    for u in g.topo:
        batch=comp_index[u]//cohort_size if cohort_size else 0
        switch_rank[u]=max((switch_rank[v]+int(owner[u]!=owner[v])
                            for v in g.pred[u] if band_of[v]==band_of[u]),default=0)
        parts[batch,band_of[u],switch_rank[u],owner[u]].add(u)
    keys=sorted(parts)
    return make_plan([parts[k] for k in keys],[k[3] for k in keys],n)

def parameter_epochs(g, plan, cfg, fraction):
    m,groups,owners,_=plan_view(g,plan); owner={u:owners[m[u]] for u in g.ops}
    depth={}
    for u in g.topo:depth[u]=1+max((depth[v] for v in g.pred[u]),default=-1)
    by_depth=defaultdict(set)
    for u in g.topo:by_depth[depth[u]].add(u)
    band=0;live_params=set();band_of={}
    for d in sorted(by_depth):
        params={t for u in by_depth[d] for t in g.inputs[u]
                if not g.tp[t] and len(g.tc[t])>1 and g.tensors[t]['pos']=='L1'}
        combined=live_params|params
        if live_params and sum(g.tensors[t]['size'] for t in combined)>cfg.l1*fraction:
            band+=1;live_params=set()
        live_params.update(params)
        for u in by_depth[d]:band_of[u]=band
    comps=sorted(g.components,key=lambda c:min(c));ci={u:i for i,c in enumerate(comps) for u in c}
    return _pack_convex_epochs(g,owner,band_of,ci,0,len(plan['core_schedules']))

def boundary_load_repair(g,plan,cfg,q,max_moves):
    """Local whole-subgraph migrations, trading tensor sets against load.

    Keeps the given partition. Not a global partition constructor. Common
    topological order fixes legal insertion positions on the receiving core.
    """
    from research_a_orion_anytime.core import estimate
    m,groups,owner,order=plan_view(g,plan);n=len(plan['core_schedules'])
    p=plan;score=estimate(g,p,cfg,q)['score']
    for _ in range(max_moves):
        loads=[g.weight(u for u in g.ops if owner[m[u]]==k) for k in range(n)]
        busy=max(range(n),key=lambda k:loads[k]);light=min(range(n),key=lambda k:loads[k])
        if loads[busy]<=loads[light]*1.03:break
        choices=sorted((s for s in order if owner[s]==busy),key=lambda s:abs(g.weight(groups[s])-(loads[busy]-loads[light])/2))[:10]
        best=None
        for sg in choices:
            trial=make_plan([groups[s] for s in order],[light if s==sg else owner[s] for s in order],n)
            val=estimate(g,trial,cfg,q)['score']
            if val<score and (best is None or val<best[0]):best=(val,sg,trial)
        if best is None:break
        score,sg,p=best;owner[sg]=light
    return p

def critical_task_migrations(g,plan,cfg,q,steps=12,deadline=None):
    """Bounded repair of critical Task releases, not total-load-only migration.

    The surrogate includes a tensor-set copy demand for each Task. Its critical
    chain determines a small migration neighbourhood; official makespan decides.
    """
    from research_a_orion_anytime.core import estimate
    m,groups,owner,order=plan_view(g,plan);n=len(plan['core_schedules'])
    pred={s:set() for s in groups}
    for u in g.topo:pred[m[u]].update(m[v] for v in g.pred[u] if m[v]!=m[u])
    weight={s:g.weight(groups[s]) for s in groups}
    reads=defaultdict(int);writes=defaultdict(int)
    for t in g.tensors:
        ps={m[u] for u in g.tp[t]};cs={m[u] for u in g.tc[t]}
        for c in cs-ps:reads[c]+=g.tensors[t]['size']
        for p in ps:
            if g.terminal[t] or cs-{p}:writes[p]+=g.tensors[t]['size']
    p=plan;score=estimate(g,p,cfg,q)['score']
    for step in range(steps):
        if deadline is not None and time.monotonic()>=deadline:return
        finish={};prev_core={};critical_parent={}
        for s in order:
            parents=pred[s]|({prev_core[owner[s]]} if owner[s] in prev_core else set())
            parent=max(parents,key=lambda a:finish[a]+(cfg.same_a if owner[a]==owner[s] else cfg.cross_a),default=None)
            critical_parent[s]=parent
            finish[s]=weight[s]+(reads[s]+writes[s])/cfg.bandwidth+(finish[parent]+(cfg.same_a if owner[parent]==owner[s] else cfg.cross_a) if parent is not None else 0)
            prev_core[owner[s]]=s
        chain=[];u=max(finish,key=finish.get)
        while u is not None:chain.append(u);u=critical_parent[u]
        # Fixed small neighbourhood: expensive critical Tasks first, alternate
        # positions along the chain so equal heavy tasks are not always starved.
        focus=sorted(chain,key=lambda x:-(weight[x]+(reads[x]+writes[x])/cfg.bandwidth))[:20]
        best=None
        for sg in focus:
            for dest in range(n):
                if dest==owner[sg]:continue
                if deadline is not None and time.monotonic()>=deadline:return
                trial=make_plan([groups[s] for s in order],[dest if s==sg else owner[s] for s in order],n)
                val=estimate(g,trial,cfg,q)['score']
                if val < score and (best is None or val<best[0]):best=(val,sg,dest,trial)
        if best is None:return
        score,sg,dest,p=best;owner[sg]=dest
        if step+1 in (1,2,4,8,12):yield step+1,p


def propose(g,n,cfg,q,incumbent=None,feedback=None,deadline=None):
    if incumbent is None:return
    p=incumbent['plan'];seen={plan_key(p)}
    old=sum(planned_traffic(g,p,q))
    m,groups,owner,order=plan_view(g,p)
    if n!=len(p['core_schedules']):raise ValueError('NPU core count mismatch')
    stream=[]
    global_lb=bounds(g,cfg,n,q)['global_lower']
    upper=(incumbent.get('official_result') or {}).get('makespan',math.inf)
    if upper <= 1.04*global_lb:
        return
    # Semantic retiming, NOT a new global partition or a replacement controller.
    for count in (8,16,32,64,4,128):
        stream.append((f'fixed_owner_epochs_{count}',lambda c=count:fixed_owner_epochs(g,p,c),{'bins':count,'cores_unchanged':True}))
    if q==1:
        typical=max(2,len(g.ops)//max(1,len(groups)))
        for scale in (2,4,8):
            stream.insert(0,(f'convex_coalesce_{scale}',lambda s=scale:convex_coalesce(g,p,cfg,q,max_nodes=typical*s),{'scale':scale,'cores_unchanged':True}))
    for fraction in (0.5,0.8,1.0):
        stream.append((f'parameter_capacity_epochs_{fraction}',lambda f=fraction:parameter_epochs(g,p,cfg,f),{'fraction':fraction,'cores_unchanged':True,'capacity_use':'heuristic cuts, not a feasibility certificate'}))
    for count in (2,4,8):
        stream.append((f'boundary_load_repair_{count}',lambda c=count:boundary_load_repair(g,p,cfg,q,c),{'max_moves':count}))
    if len(g.components)>1:
        for cohort in (5,10,20):
            for count in (32,64):
                stream.append((f'cohort_{cohort}_epochs_{count}',lambda c=count,b=cohort:fixed_owner_epochs(g,p,c,b),{'bins':count,'cohort':cohort,'cores_unchanged':True}))
    for name,build,meta in stream:
        if deadline is not None and time.monotonic()>=deadline:return
        started=time.monotonic()
        try:
            candidate=build();plan_view(g,candidate)
            key=plan_key(candidate)
            if key in seen:continue
            seen.add(key)
            bd=bounds(g,cfg,n,q,candidate)
            traffic=sum(planned_traffic(g,candidate,q))
            yield dict(name=name,family='memory/reuse_epoch',plan=candidate,
                       proxy={'score':bd['candidate_lower'],'pre_spill_bytes':traffic,
                              'pre_spill_saved_bytes':old-traffic,'not_a_performance_prediction':True},
                       bounds=bd,mechanism=meta,generation_seconds=time.monotonic()-started)
        except ValueError as exc:
            # A failed construction is kept as feedback, not a scored candidate.
            if feedback is not None:feedback.append(dict(name=name,status='structural_rejected',error=str(exc)))

    if q==1 and upper>1.6*global_lb:
        for step,trial in critical_task_migrations(g,p,cfg,q,deadline=deadline):
            if deadline is not None and time.monotonic()>=deadline:return
            plan_view(g,trial)
            bd=bounds(g,cfg,n,q,trial)
            yield dict(name=f'critical_task_release_moves_{step}',family='memory/task_release',plan=trial,
                       proxy={'score':bd['candidate_lower'],'heuristic':'critical Task copy/compute release'},
                       bounds=bd,mechanism={'local_migrations':step,'partition_unchanged':True})
