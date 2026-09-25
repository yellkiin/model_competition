"""S and M candidate adapters. Imported research algorithms, shared live parent.

All proposals are ordinary official plans. Component topology is indexed once
per graph instead of re-scanning all V operations for every micro-component.
"""
from __future__ import annotations
from collections import defaultdict
from copy import copy
import time
from research_a_orion_anytime.core import (bounds, make_plan, map_groups, plan_view,
    planned_traffic, one_core, estimate)
from research_a_orion_track_structure.plugin import linear_blocks, nonuniform_blocks, pack_within_phase, pad_plan
from research_a_orion_track_structure.safe_refine_plugin import local_families, chain_eft
from research_a_orion_track_memory.coherent_v4 import candidates as mem

class GraphCache:
    def __init__(self, g, cfg):
        self.g, self.cfg = g, cfg
        self.components = sorted(g.components, key=min)
        self.component_of = {u:i for i,c in enumerate(self.components) for u in c}
        self.orders = [[] for _ in self.components]
        for u in g.topo: self.orders[self.component_of[u]].append(u)
        private = shared = 0
        for t in g.tensors:
            if not g.tp[t] and g.tc[t]:
                if len({self.component_of[u] for u in g.tc[t]}) > 1:
                    shared += g.tensors[t]['size']
                else: private += g.tensors[t]['size']
        tiny = sum(len(c) for c in self.components if len(c) <= 32)/max(1,len(g.ops))
        self.features = dict(ops=len(g.ops), components=len(g.components),
            dominant_fraction=max(map(len,g.components),default=0)/max(1,len(g.ops)),
            tiny_fraction=tiny, shared_input_bytes=shared, private_input_bytes=private,
            private_islands=len(self.components)>=8 and tiny>=.75 and shared < .1*max(1,private))
        self.blocks = None; self.wave_cache = None

    def linear(self):
        if self.blocks is None: self.blocks = linear_blocks(self.g)
        return self.blocks

    def wave(self, parent, n, envelope, stages):
        if self.wave_cache is None:
            peaks, depths = [], []
            for comp, order in zip(self.components,self.orders):
                local = copy(self.g); local.topo = order
                peaks.append(mem._component_live_peak(local,comp))
                ds = {}
                for u in order: ds[u] = 1+max((ds[v] for v in self.g.pred[u] if v in comp),default=-1)
                depths.append(ds)
            maximum = {p:max((x.get(p,0) for x in peaks),default=0) for p in self.cfg.capacity}
            safe = min(self.cfg.capacity[p]/max(1,maximum[p]) for p in maximum)
            self.wave_cache = safe, depths
        safe, depths = self.wave_cache
        owners = mem._balanced_component_owners(self.g,parent,n)
        assigned = [[] for _ in range(n)]
        for i,c in enumerate(self.components): assigned[owners[min(c)]].append(i)
        width = max(1,int(max(1.,safe*envelope)))
        groups, cores = [], []
        for k, indices in enumerate(assigned):
            for start in range(0,len(indices),width):
                batch = indices[start:start+width]
                for stage in range(stages):
                    part = set()
                    for i in batch:
                        d = depths[i]; levels = max(d.values(),default=0)+1
                        part.update(u for u,v in d.items() if min(stages-1,v*stages//max(1,levels))==stage)
                    if part: groups.append(part); cores.append(k)
        return make_plan(groups,cores,n)

def wrap(g,n,cfg,q,p,name,family,evidence=None):
    plan_view(g,p)
    bd = bounds(g,cfg,n,q,p)
    # A ranking relaxation, not a substitute for the original evaluator.
    return dict(plan=p,name=name,family=family,bounds=bd,
                proxy={'score':bd['candidate_lower']},evidence=evidence or {})

def structure_global(g,n,cfg,q,cache,deadline):
    blocks = cache.linear()
    for effective in dict.fromkeys((n,max(1,n-1),max(1,n-2))):
        if time.monotonic()>=deadline: return
        p = pad_plan(map_groups(g,blocks,effective,cfg,q),n)
        yield wrap(g,n,cfg,q,p,f'linear_eft_k{effective}','structure/chain')
    if cache.features['private_islands']: return  # M owns this structure, not F.
    gs, phase = nonuniform_blocks(g)
    p = map_groups(g,gs,n,cfg,q)
    for label,trial in [('packed',pack_within_phase(g,p,phase)),('ordered',p)]:
        if time.monotonic()>=deadline: return
        yield wrap(g,n,cfg,q,trial,'nonuniform_'+label,'structure/width_valley')
    for effective in dict.fromkeys((n,max(1,n-1))):
        for comm in (.5,1.,2.):
            if time.monotonic()>=deadline:return
            p = pad_plan(chain_eft(g,blocks,effective,cfg,q,comm,True),n)
            yield wrap(g,n,cfg,q,p,f'chain_cost_k{effective}_{comm}','structure/chain_cost')

def structure_local(g,n,cfg,q,context,deadline):
    fams = local_families(g,n,cfg,q,context)
    sequence = ('move','joint','swap','move','split')
    turns = 0
    while fams and time.monotonic()<deadline:
        family = sequence[turns%len(sequence)]; turns+=1
        if family not in fams: continue
        try: name,p = next(fams[family])
        except StopIteration: del fams[family]; continue
        try: yield wrap(g,n,cfg,q,p,name,'structure/'+family)
        except ValueError: continue

def memory(g,n,cfg,q,context,cache,deadline):
    parent = context['plan']
    if cache.features['private_islands']:
        if q==1: return
        for envelope,stages in ((2.,2),(1.,2),(1.5,2),(2.5,2),(1.,3),(2.,3)):
            if time.monotonic()>=deadline:return
            p = cache.wave(parent,n,envelope,stages)
            yield wrap(g,n,cfg,q,p,f'wave_e{envelope}_s{stages}','memory/micro_wave')
        return
    for bins in (16,32,64,8):
        if time.monotonic()>=deadline:return
        p = mem.fixed_owner_bands(g,parent,bins)
        yield wrap(g,n,cfg,q,p,f'bands_{bins}','memory/reuse_bands')
    opt = mem.Options(stop_ratio=1.,max_candidates=20)
    streams = [('release',mem.producer_release_cuts(g,n,cfg,q,context,deadline,4)),
               ('tensor',mem.tensor_transactions(g,n,cfg,q,context,deadline,opt))]
    for family,stream in streams:
        for i,(p,name,mechanism) in enumerate(stream):
            if i>=12 or time.monotonic()>=deadline:return
            try: yield wrap(g,n,cfg,q,p,name,'memory/'+family,mechanism)
            except ValueError: continue

def base(g,n,cfg,q,deadline):
    from research_a_orion_anytime.strategies import stage_candidates,fine_candidates
    # Preserve original coarse/frontier coverage: fine blocks alone regress Q1.
    from research_a_orion_anytime.core import partition
    roots=map_groups(g,g.components,n,cfg,q)
    yield wrap(g,n,cfg,q,roots,'component_order','base/frontier')
    m,_,owner,_=plan_view(g,roots)
    packed=[{u for u in g.ops if owner[m[u]]==k} for k in range(n)]
    yield wrap(g,n,cfg,q,make_plan(packed,list(range(n)),n),'component_pack','base/frontier')
    for grain in (2,4,8):
        if time.monotonic()>=deadline:return
        p=map_groups(g,partition(g,n,cfg,q,grain),n,cfg,q)
        yield wrap(g,n,cfg,q,p,f'frontier_g{grain}','base/frontier')
    # Do not remove a whole family on an uncalibrated global surrogate rank.
    for s in (stage_candidates(g,n,cfg,q,include_dp=False),fine_candidates(g,n,cfg,q)):
        for c in s:
            if time.monotonic()>=deadline:return
            c = dict(c); c['family'] = 'base/'+c['family']; yield c
