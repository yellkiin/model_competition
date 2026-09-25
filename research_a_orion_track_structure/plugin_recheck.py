"""Structural proposals v2: retain cheap fallback, pack Q1 phases first, sweep core counts.

This is a proposal generator, not an official timing or FIFO replacement.
"""
from __future__ import annotations
import time
from collections import defaultdict
from research_a_orion_anytime.core import constructors, make_plan, map_groups, plan_view, estimate, bounds, neighbours
from research_a_orion_anytime.strategies import stage_candidates
from .plugin import nonuniform_blocks, linear_blocks, pack_within_phase, pad_plan, incumbent_moves


def propose(g,n,cfg,q,incumbent=None,feedback=None,deadline=None):
    """COMMON-compatible interface. No case IDs, no official calls, no new bounds."""
    expired=lambda: deadline is not None and time.monotonic()>=deadline
    seen=set()
    def wrap(plan,name,family):
        plan_view(g,plan)
        key=(tuple(sorted(plan['node_to_subgraph'].items())),tuple(map(tuple,plan['core_schedules'])))
        if key in seen:return None
        seen.add(key)
        return dict(name=name,family='structure/'+family,plan=plan,proxy=estimate(g,plan,cfg,q),bounds=bounds(g,cfg,n,q,plan))
    context=incumbent if incumbent is not None else {}
    for seed in context.get('effective_core_seeds',[]):
        if expired():return
        if len(seed['plan']['core_schedules'])<=n:
            c=wrap(pad_plan(seed['plan'],n),'validated_effective_seed','effective_cores')
            if c:yield c
    # This threshold is a heuristic about granularity, NOT a certified bound.
    # Short operations and already-small independent blocks favour the existing coarse constructors.
    independent=max((g.weight(c) for c in g.components),default=0)<=g.weight(g.ops)/n
    short_ops=sum(g.loads(g.ops).values())/max(1,len(g.ops))<= (cfg.same_a if q==1 else cfg.cross_b/5)
    fallback=None
    def legacy(limit=3):
        nonlocal fallback
        if fallback is None:fallback=constructors(g,n,cfg,q,diagnostics=[])
        for c in fallback[:limit]:
            if expired():return
            x=wrap(c['plan'],'fallback_'+c['name'],'existing_constructor')
            if x:yield x
    if short_ops:
        yield from legacy(1)
        if expired():return
        # Preserve the pre-existing stage/DP construction omitted by the first structure version.
        # Candidate selection still uses a proxy; all winners require full official evaluation.
        stages=[]
        for c in stage_candidates(g,n,cfg,q,include_dp=True):
            if expired():return
            stages.append(c)
        for c in sorted(stages,key=lambda c:(c['proxy']['score'],c['name']))[:2]:
            x=wrap(c['plan'],'retained_'+c['name'],'existing_stage_dp')
            if x:yield x
    elif independent:yield from legacy()
    if expired():return
    groups,phase=nonuniform_blocks(g)
    plan=map_groups(g,groups,n,cfg,q)
    # Q1: phase packing is a different Task partition, not merely a FIFO reorder.
    variants=[(pack_within_phase(g,plan,phase),'nonuniform_packed'),(plan,'nonuniform_ordered')] if q==1 else [(plan,'nonuniform_ordered'),(pack_within_phase(g,plan,phase),'nonuniform_packed')]
    for p,name in variants:
        if expired():return
        c=wrap(p,name,'nonuniform_phases')
        if c:yield c
    if expired():return
    c=wrap(map_groups(g,linear_blocks(g),n,cfg,q),'linear_chain_eft','chain_partition')
    if c:yield c
    if not independent and not short_ops:yield from legacy()
    # Do not hard-code 3->5 or any case. Candidate generation at every smaller active count
    # is charged to this run; target-n official evaluation remains mandatory.
    for k in range(n-1,0,-1):
        if expired():return
        cs=constructors(g,k,cfg,q,diagnostics=[])
        for c in cs[:1]:
            x=wrap(pad_plan(c['plan'],n),f'effective_{k}_{c["name"]}','effective_cores')
            if x:yield x


def local_proposals(g,n,cfg,q,incumbent,round_no=0,deadline=None):
    """Existing structural neighbours + joint affinity. Does not search FIFO orders."""
    if not incumbent:return
    if deadline is not None and time.monotonic()>=deadline:return
    plan=incumbent['plan'];raw=incumbent.get('official_result')
    for c in neighbours(g,plan,cfg,q,raw,limit=18):
        if 'order' in c['name'] or 'fifo' in c['name']:continue
        yield {**c,'family':'structure/existing_local'}
    for name,p in incumbent_moves(g,plan,limit=8):
        if deadline is not None and time.monotonic()>=deadline:return
        try:
            plan_view(g,p)
            yield dict(name=name,family='structure/critical_joint',plan=p,proxy=estimate(g,p,cfg,q),bounds=bounds(g,cfg,n,q,p))
        except ValueError:
            continue
