"""Shared-plan adapters for the completed structure and memory tracks.

A candidate is evaluated by the host, never by these generators. A successful
S candidate becomes the parent of M and vice versa; this is not score splicing.
"""
from __future__ import annotations
from collections import defaultdict
from copy import copy
import importlib
import time
from research_a_orion_anytime.core import (bounds, estimate, make_plan, map_groups,
    plan_view, planned_traffic, memory_proxy, neighbours)
from research_a_orion_track_structure.plugin import (linear_blocks, nonuniform_blocks,
    pack_within_phase)
from research_a_orion_track_structure.safe_refine_plugin import local_families, constructive_family
from research_a_orion_track_memory.coherent_v4 import candidates as mem


def expired(deadline):
    return time.monotonic() >= deadline


def wrap(g, n, cfg, q, plan, name, family, context, memory_score=False):
    # The unified host chooses a SOURCE using observed gains/costs, not this
    # candidate's old full FIFO/live-memory proxy. Preserve candidate order and
    # all necessary-condition bounds; avoid computing an unused full proxy.
    bd = bounds(g, cfg, n, q, plan)
    return {'plan': plan, 'name': name, 'family': family, 'bounds': bd,
            'proxy': {'score': bd['candidate_lower'], 'used_for_ranking': False}}


def local_structure(g,n,cfg,q,context,feedback,deadline):
    """Same source cycle/primitives as safe_refine_plugin.propose, cheap wrapper."""
    for i,seed in enumerate(context.get('effective_core_seeds',[])):
        if expired(deadline):return
        from research_a_orion_track_structure.plugin import pad_plan
        yield wrap(g,n,cfg,q,pad_plan(seed['plan'],n),'validated_alternative_'+str(i),'structure/seed_reuse',context)
    constructors=iter(constructive_family(g,n,cfg,q));done=False;previous=None;streams={}
    cycle=('move','joint','constructor','swap','move','split');turn=0
    while not expired(deadline):
        live=context.get('plan')
        if live is None:return
        if live is not previous:streams=local_families(g,n,cfg,q,context);previous=live
        if not any(v is not None for v in streams.values()) and done:return
        family=cycle[turn%len(cycle)];turn+=1
        if family=='constructor':
            if done:continue
            stream=constructors
        else:
            stream=streams.get(family)
            if stream is None:continue
        try:name,p=next(stream)
        except StopIteration:
            if family=='constructor':done=True
            else:streams[family]=None
            continue
        try:yield wrap(g,n,cfg,q,p,name,'structure/'+family,context)
        except ValueError as exc:feedback.append({'name':name,'family':'structure/'+family,'status':'structural_invalid','error':str(exc)})


def structure(g, n, cfg, q, context, feedback, deadline):
    # Expose the demonstrated cold chain constructor before long local searches.
    chain = map_groups(g, linear_blocks(g), n, cfg, q)
    if not expired(deadline):
        yield wrap(g,n,cfg,q,chain,'chain_rank_eft','structure/constructor',context)
    if expired(deadline): return
    groups, phase = nonuniform_blocks(g)
    mapped = map_groups(g, groups, n, cfg, q)
    for name, p in [('width_valley_packed',pack_within_phase(g,mapped,phase)),
                    ('width_valley_ordered',mapped)]:
        if expired(deadline): return
        yield wrap(g,n,cfg,q,p,name,'structure/constructor',context)
    # The upstream local source observes replacement of context['plan'].
    yield from local_structure(g,n,cfg,q,context,feedback,deadline)


class WaveCache:
    """Exact generator speedup: scan global topological order ONCE, not per island.

    Original memory-v4 plans are unchanged for a fixed parent/envelope/stages.
    Only data independent of the proposed envelope is reused.
    """
    def __init__(self, g, cfg):
        self.g, self.cfg = g, cfg
        self.comps = sorted(g.components, key=min)
        of = {u:i for i,c in enumerate(self.comps) for u in c}
        self.orders = [[] for _ in self.comps]
        for u in g.topo: self.orders[of[u]].append(u)
        self.peaks, self.depths = [], []
        for comp, order in zip(self.comps,self.orders):
            view = copy(g); view.topo = order
            self.peaks.append(mem._component_live_peak(view,comp))
            depth = {}
            for u in order: depth[u] = 1+max((depth[p] for p in g.pred[u] if p in comp),default=-1)
            self.depths.append(depth)
        max_peak = {pos:max((p.get(pos,0) for p in self.peaks),default=0) for pos in cfg.capacity}
        self.safe = min((cfg.capacity[p]/max(1,max_peak[p]) for p in cfg.capacity),default=1)
        self.last_parent = None

    def plan(self, parent, n, envelope, stages):
        if parent is not self.last_parent:
            owners = mem._balanced_component_owners(self.g,parent,n)
            self.assigned = [[] for _ in range(n)]
            for i,c in enumerate(self.comps): self.assigned[owners[min(c)]].append(i)
            self.last_parent = parent
        width = max(1,int(max(1.,self.safe*envelope)))
        groups, cores = [], []
        for k, indices in enumerate(self.assigned):
            for start in range(0,len(indices),width):
                batch = indices[start:start+width]
                for stage in range(stages):
                    part = set()
                    for i in batch:
                        depth = self.depths[i]; levels = max(depth.values(),default=0)+1
                        part.update(u for u,d in depth.items() if min(stages-1,d*stages//max(1,levels))==stage)
                    if part: groups.append(part); cores.append(k)
        return make_plan(groups,cores,n)


def memory(g, n, cfg, q, context, feedback, deadline):
    wave = None; previous = None; opt = mem.Options(stop_ratio=1.0)
    while not expired(deadline):
        parent = context['plan']
        if parent is previous: return
        previous = parent
        features = mem.assess(g,n,cfg,q,context)
        # Structural mapping and memory micro-wave BOTH need migration enabled.
        # Disabling all memory migration would also remove the tested 084 benefit.
        if features['private_islands']:
            if q == 1: return
            if wave is None: wave = WaveCache(g,cfg)
            # Yield before constructing the next wave; no eager 8-plan barrier.
            for envelope in (1.,1.5,2.,2.5):
                for stages in (2,3):
                    if expired(deadline): return
                    p = wave.plan(context['plan'],n,envelope,stages)
                    yield wrap(g,n,cfg,q,p,f'micro_wave_e{envelope:g}_s{stages}',
                               'memory/coherent_micro_wave',context,True)
        else:
            for bins in (16,32,64,8):
                if expired(deadline): return
                p = mem.fixed_owner_bands(g,context['plan'],bins)
                yield wrap(g,n,cfg,q,p,f'fixed_owner_bands_{bins}','memory/reuse_bands',context,True)
            streams = [('memory/producer_release',mem.producer_release_cuts(g,n,cfg,q,context,deadline,4)),
                       ('memory/tensor_transaction',mem.tensor_transactions(g,n,cfg,q,context,deadline,opt))]
            for family, stream in streams:
                for i,(p,name,mechanism) in enumerate(stream):
                    if expired(deadline) or i>=12: break
                    try: yield wrap(g,n,cfg,q,p,name,family,context,True)
                    except ValueError as exc: feedback.append({'status':'structural_rejected','name':name,'error':str(exc)})


def base(g,n,cfg,q,context,feedback,deadline):
    previous = None
    while not expired(deadline) and context['plan'] is not previous:
        previous = context['plan']
        for c in neighbours(g,previous,cfg,q,context['official_result'],limit=12):
            if expired(deadline): return
            c = dict(c); c['family'] = 'base/'+c.get('family','local')
            yield c


def fifo_module(spec):
    """Explicit future hook. No automatic checkout or import of unfinished PRs."""
    if not spec: return None
    module = importlib.import_module(spec)
    if getattr(module,'FUSION_API',None) != 1:
        raise ValueError('FIFO adapter must declare FUSION_API=1; see FIFO_INTERFACE.md')
    if not callable(getattr(module,'propose',None)):
        raise ValueError('FIFO adapter missing propose')
    return module
