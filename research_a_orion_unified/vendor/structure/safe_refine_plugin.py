"""Structure-only local refinement. Proposals never replace a validated incumbent.

No case-name branches, official calls, FIFO model, or new lower-bound claims.
"""
from __future__ import annotations
from collections import defaultdict
from copy import deepcopy
import heapq
import time
from research_a_orion_unified.vendor.orion.core import (PIPES, bounds, estimate, make_plan,
    map_groups, plan_view, topological)
from .plugin import linear_blocks, nonuniform_blocks, pack_within_phase, pad_plan


def signature(plan):
    """Exact tuple equality for candidate deduplication; no file fingerprinting."""
    return (tuple(sorted((int(u), s) for u, s in plan['node_to_subgraph'].items())),
            tuple(tuple(x) for x in plan['core_schedules']))


def reassign(plan, order, assignments):
    """Preserve group IDs and all unaffected relative core orders."""
    position = {s: i for i, s in enumerate(order)}
    p = {'node_to_subgraph': dict(plan['node_to_subgraph']),
         'core_schedules': [[s for s in seq if s not in assignments]
                            for seq in plan['core_schedules']]}
    for s, k in assignments.items():
        p['core_schedules'][k].append(s)
    for seq in p['core_schedules']:
        seq.sort(key=position.__getitem__)
    return p


def local_families(g, n, cfg, q, context):
    """Finite single-group, pair-swap, joint-affinity, and convex split families."""
    plan = context['plan']; raw = context.get('official_result') or {}
    mapping, groups, owner, order = plan_view(g, plan)
    weights = {s: g.loads(us) for s, us in groups.items()}
    loads = [{p: sum(weights[s][p] for s in groups if owner[s] == k)
              for p in PIPES} for k in range(n)]
    ends = defaultdict(float)
    for core in raw.get('per_core_timeline', []):
        for op in core['ops']:
            if op['op_id'] in mapping:
                s = mapping[op['op_id']]
                ends[s] = max(ends[s], op['end'])
    traffic = defaultdict(float)
    for t in g.tensors:
        ps = {mapping[u] for u in g.tp[t]}; cs = {mapping[v] for v in g.tc[t]}
        for a in ps:
            for b in cs:
                if a != b:
                    traffic[a, b] += g.tensors[t]['size']
    near = defaultdict(list)
    for (a, b), size in traffic.items():
        near[a].append((b, size)); near[b].append((a, size))
    maxload = max((max(x.values()) for x in loads), default=0)
    # Inspect all small partitions. Large partitions get a bounded union of late,
    # heavy and high-communication groups; no dependence on a case identifier.
    if len(groups) <= 64:
        selected = list(order)
    else:
        late = sorted(groups, key=lambda s: (-ends[s], s))[:12]
        heavy = sorted(groups, key=lambda s: (-max(weights[s].values()), s))[:12]
        cut = sorted(groups, key=lambda s: (-sum(sz for v, sz in near[s]
                         if owner[v] != owner[s]), s))[:8]
        selected = list(dict.fromkeys(late + heavy + cut))

    def predicted(assign):
        changed = set(assign); trial = [dict(x) for x in loads]
        for s, k in assign.items():
            for p in PIPES:
                trial[owner[s]][p] -= weights[s][p]
                trial[k][p] += weights[s][p]
        delta = 0.
        touched = set()
        for s in changed:
            for v, size in near[s]:
                edge = (min(s, v), max(s, v))
                if edge in touched: continue
                touched.add(edge)
                delta += size * ((assign.get(s, owner[s]) != assign.get(v, owner[v]))
                                  - (owner[s] != owner[v]))
        # Ranking only: this is NOT exact COPY traffic or an official timing model.
        return max(max(x.values()) for x in trial) - maxload + delta / cfg.bandwidth

    moves=[]
    for s in selected:
        for k in range(n):
            if k != owner[s]: moves.append((predicted({s:k}), -ends[s], s, k))
    moves.sort()
    def movement():
        for _, _, s, k in moves:
            yield f'move_g{s}_to{k}', reassign(plan, order, {s:k})

    pairs=[]
    swap_groups = sorted(selected, key=lambda s:(-ends[s], s))[:20]
    for i,a in enumerate(swap_groups):
        for b in swap_groups[i+1:]:
            if owner[a] != owner[b]:
                assign={a:owner[b],b:owner[a]}
                pairs.append((predicted(assign),a,b))
    pairs.sort()
    def swaps():
        for _,a,b in pairs[:64]:
            yield f'swap_g{a}_g{b}',reassign(plan,order,{a:owner[b],b:owner[a]})

    joint=[]
    edges=sorted(traffic,key=lambda e:(-max(ends[e[0]],ends[e[1]]),-traffic[e],e))
    for a,b in edges[:16]:
        if owner[a]==owner[b]:continue
        for k in range(n):
            joint.append((predicted({a:k,b:k}),a,b,k))
    joint.sort()
    def joints():
        for _,a,b,k in joint[:48]:
            yield f'joint_g{a}_g{b}_to{k}',reassign(plan,order,{a:k,b:k})

    def splits():
        busy=sorted(range(n),key=lambda k:(-max(loads[k].values()),k))
        light=sorted(range(n),key=lambda k:(max(loads[k].values()),k))
        cand=sorted((s for s in selected if len(groups[s])>3),
                    key=lambda s:(busy.index(owner[s]),-max(weights[s].values()),s))[:6]
        for s in cand:
            us=sorted(groups[s],key=g.position.__getitem__)
            for frac in (.5,.25,.75):
                split=max(1,min(len(us)-1,round(len(us)*frac)))
                left,right=set(us[:split]),set(us[split:])
                for target in [k for k in light if k!=owner[s]][:2]:
                    # Topological prefix/suffix refines the old block. New full
                    # core-order acyclicity and official execution still checked.
                    gs=[];ks=[]
                    for t in order:
                        if t==s:gs.extend([left,right]);ks.extend([owner[s],target])
                        else:gs.append(groups[t]);ks.append(owner[t])
                    yield f'prefix_split_g{s}_{frac}_to{target}',make_plan(gs,ks,n)
    return {'move':iter(movement()),'swap':iter(swaps()),
            'joint':iter(joints()),'split':iter(splits())}


def chain_eft(g,groups,n,cfg,q,communication=1.,sum_cost=False):
    """A rank/EFT candidate with explicit dependency-byte delay; only a heuristic."""
    member={u:s for s,us in enumerate(groups) for u in us}
    preds={s:set() for s in range(len(groups))}
    for u,ps in g.pred.items():preds[member[u]].update(member[p] for p in ps if member[p]!=member[u])
    edge_bytes=defaultdict(float)
    for t in g.tensors:
        for a in {member[u] for u in g.tp[t]}:
            for b in {member[u] for u in g.tc[t]}:
                if a!=b:edge_bytes[a,b]+=g.tensors[t]['size']
    order=topological(preds,preds,key=lambda s:(-max(g.rank[u] for u in groups[s]),min(groups[s])))
    finish={};owner={};free=[[0.]*len(PIPES) for _ in range(n)]
    for s in order:
        w=g.loads(groups[s]);duration=sum(w.values()) if sum_cost else max(w.values())
        trial=[]
        for k in range(n):
            ready=max((finish[p] + (cfg.cross_a if q==1 else cfg.cross_b)*communication
                + (2*edge_bytes[p,s]/cfg.bandwidth)*communication
                if owner[p]!=k else finish[p]+(cfg.same_a if q==1 else 0)
                for p in preds[s]),default=0.)
            end=max(ready,max((free[k][i] for i,p in enumerate(PIPES) if w[p]),default=0.))+duration
            trial.append((end,sum(free[k]),k))
        end,_,k=min(trial);owner[s]=k;finish[s]=end
        for i,p in enumerate(PIPES):
            if w[p]:free[k][i]=end
    return make_plan([groups[s] for s in order],[owner[s] for s in order],n)


def constructive_family(g,n,cfg,q):
    blocks=linear_blocks(g)
    # Full chains are retained: splitting their large intermediate tensors was
    # rejected in the real pilot. Explore mapping, not mandatory fine splitting.
    for effective in list(dict.fromkeys([max(1,n-1),n,max(1,n-2)])):
        for comm in (.5,1.,2.):
            for serial in (True,False):
                p=chain_eft(g,blocks,effective,cfg,q,comm,serial)
                yield f'chain_eft_k{effective}_c{comm}_sum{int(serial)}',pad_plan(p,n)
        yield f'chain_existing_k{effective}',pad_plan(map_groups(g,blocks,effective,cfg,q),n)


def propose(g,n,cfg,q,incumbent=None,feedback=None,deadline=None):
    """COMMON generator. Keep seed context mutable for genuine iterative search."""
    context=incumbent if incumbent is not None else {}
    def expired():return deadline is not None and time.monotonic()>=deadline
    def wrap(name,p,family):
        plan_view(g,p)
        return dict(name=name,family='structure/'+family,plan=p,
            proxy=estimate(g,p,cfg,q),bounds=bounds(g,cfg,n,q,p))
    for i,seed in enumerate(context.get('effective_core_seeds',[])):
        if expired():return
        yield wrap('validated_alternative_'+str(i),pad_plan(seed['plan'],n),'seed_reuse')
    constructors=iter(constructive_family(g,n,cfg,q));done_construct=False
    previous=None;streams={};cycle=('move','joint','constructor','swap','move','split')
    turn=0;rounds=0
    while not expired():
        live=context.get('plan')
        if live is None:return
        if live is not previous:
            streams=local_families(g,n,cfg,q,context);previous=live;rounds+=1
        active=[k for k,v in streams.items() if v is not None]
        if not active and done_construct:return
        family=cycle[turn%len(cycle)];turn+=1
        if family=='constructor':
            if done_construct:continue
            stream=constructors
        else:
            stream=streams.get(family)
            if stream is None:continue
        try:name,p=next(stream)
        except StopIteration:
            if family=='constructor':done_construct=True
            else:streams[family]=None
            continue
        try:yield wrap(name,p,family)
        except ValueError as exc:
            if feedback is not None:feedback.append(dict(name=name,family='structure/'+family,status='structural_invalid',error=str(exc)))
