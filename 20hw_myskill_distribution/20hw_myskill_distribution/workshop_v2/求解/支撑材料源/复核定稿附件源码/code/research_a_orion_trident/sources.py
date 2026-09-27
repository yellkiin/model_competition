# 本程序及代码是在人工智能工具辅助下完成的。
# 人工智能工具名称及版本/型号：GPT-6、GPT-6 Sol、GPT-6 Luna（论文参考文献[11]）。
# 开发机构/公司：OpenAI。
# 版本颁布日期：GPT-6（Astra）2026-09-03；GPT-6 Sol、GPT-6 Luna 2026-09-22。

"""Lazy S/M/F sources. Every proposal names its actual parent epoch.

S: frozen chain/valley/effective-core and convex local moves.
M: frozen coherent-v4 waves, owner bands, release and tensor transactions.
F: PR34 event moves through PR37's cheaper FIFO adapter.
No source calls the evaluator, accepts a solution or owns a wall deadline.
"""
from __future__ import annotations
from collections import deque
from itertools import islice
import time
from research_a_orion_trident.vendor.orion.core import bounds, plan_view, map_groups, neighbours
from research_a_orion_trident.vendor.orion.strategies import stage_candidates, fine_candidates
from .vendor.structure.plugin import linear_blocks, nonuniform_blocks, pack_within_phase
from .vendor.structure.safe_refine_plugin import local_families, constructive_family
from .vendor.memory.coherent_v4 import candidates as mem
from .candidates import WaveCache
from .fifo import proposed_moves


def wrap(g,n,cfg,q,p,name,family,epoch):
    # Source-specific ordering already exists upstream. A full memory/timing proxy
    # that the source selector never reads is pure overhead, so compute only bounds.
    bd=bounds(g,cfg,n,q,p)
    return dict(plan=p,name=name,family=family,bounds=bd,
                proxy={'score':bd['candidate_lower'],'ranking_only':True},parent_epoch=epoch)


class Sources:
    def __init__(self,g,n,cfg,q,context,feedback,deadline,active='smf'):
        self.g,self.n,self.cfg,self.q=g,n,cfg,q
        self.context,self.feedback,self.deadline=context,feedback,deadline
        self.active=[s for s in 'smfb' if s=='b' or s in active and (s!='f' or q==3)]
        self.streams={};self.epochs={};self.finished={};self.memory_cursor=0
        self.global_structure_done=False;self.base_global_done=False
        self.wave=None;self.static_features=None;self.generation_counts={s:0 for s in self.active}
        self.global_struct=iter(constructive_family(g,n,cfg,q))
        self.initial={'s':iter(self._initial_s()),'b':iter(self._initial_b())}

    def available(self):
        return [s for s in self.active if self.finished.get(s,-1)<self.context['epoch']]

    def _initial_s(self):
        g,n,cfg,q=self.g,self.n,self.cfg,self.q
        p=map_groups(g,linear_blocks(g),n,cfg,q)
        yield wrap(g,n,cfg,q,p,'chain_rank_eft','structure/constructor',None)
        gs,ph=nonuniform_blocks(g);p=map_groups(g,gs,n,cfg,q)
        for name,plan in [('width_valley_packed',pack_within_phase(g,p,ph)),('width_valley_ordered',p)]:
            yield wrap(g,n,cfg,q,plan,name,'structure/constructor',None)

    def _initial_b(self):
        g,n,cfg,q=self.g,self.n,self.cfg,self.q
        streams=deque([iter(stage_candidates(g,n,cfg,q)),iter(fine_candidates(g,n,cfg,q))])
        for _ in range(12):
            if not streams or time.monotonic()>=self.deadline:return
            it=streams.popleft()
            try:c=next(it)
            except StopIteration:continue
            streams.append(it)
            yield dict(c,parent_epoch=None,family='base/'+c.get('family','constructor'))

    def _s(self,parent,epoch):
        g,n,cfg,q=self.g,self.n,self.cfg,self.q
        families=local_families(g,n,cfg,q,parent)
        cycle=deque(['move','joint','constructor','swap','split'])
        emitted=0
        while cycle and emitted<72 and time.monotonic()<self.deadline:
            family=cycle.popleft()
            stream=self.global_struct if family=='constructor' else families[family]
            try:name,p=next(stream)
            except StopIteration:continue
            cycle.append(family)
            try:
                c=wrap(g,n,cfg,q,p,name,'structure/'+family,epoch)
                emitted+=1;yield c
            except ValueError as exc:
                self.feedback.append(dict(source='s',status='order_invalid',name=name,error=str(exc)))

    def _m(self,parent,epoch):
        g,n,cfg,q=self.g,self.n,self.cfg,self.q
        feature=mem.assess(g,n,cfg,q,parent)
        self.static_features={k:v for k,v in feature.items() if not isinstance(v,dict)}
        if feature['private_islands']:
            if q==1:return
            if self.wave is None:self.wave=WaveCache(g,cfg)
            # Cursor survives accepted parents, so early improving recipes do not
            # continually restart at envelope=1 and starve wider waves.
            recipes=[(1.,2),(1.5,2),(2.,2),(1.,3),(2.5,2),(1.5,3),(2.,3),(2.5,3)]
            start=self.memory_cursor%len(recipes)
            for j in range(len(recipes)):
                if time.monotonic()>=self.deadline:return
                e,st=recipes[(start+j)%len(recipes)];self.memory_cursor+=1
                p=self.wave.plan(parent['plan'],n,e,st)
                yield wrap(g,n,cfg,q,p,f'micro_wave_e{e:g}_s{st}','memory/coherent_micro_wave',epoch)
        else:
            recipes=(16,32,64,8);start=self.memory_cursor%len(recipes)
            for j in range(len(recipes)):
                if time.monotonic()>=self.deadline:return
                bins=recipes[(start+j)%len(recipes)];self.memory_cursor+=1
                try:
                    p=mem.fixed_owner_bands(g,parent['plan'],bins)
                    yield wrap(g,n,cfg,q,p,f'fixed_owner_bands_{bins}','memory/reuse_bands',epoch)
                except ValueError as exc:self.feedback.append(dict(source='m',status='order_invalid',error=str(exc)))
            families=deque([
                ('producer_release',iter(mem.producer_release_cuts(g,n,cfg,q,parent,self.deadline,4))),
                ('tensor_transaction',iter(mem.tensor_transactions(g,n,cfg,q,parent,self.deadline,mem.Options(stop_ratio=1.0))))])
            emitted=0
            while families and emitted<20 and time.monotonic()<self.deadline:
                fam,it=families.popleft()
                try:p,name,mechanism=next(it)
                except StopIteration:continue
                families.append((fam,it))
                try:
                    c=wrap(g,n,cfg,q,p,name,'memory/'+fam,epoch);c['evidence']={'mechanism':mechanism}
                    emitted+=1;yield c
                except ValueError as exc:self.feedback.append(dict(source='m',status='order_invalid',error=str(exc)))

    def _b(self,parent,epoch):
        g,n,cfg,q=self.g,self.n,self.cfg,self.q
        for c in neighbours(g,parent['plan'],cfg,q,parent['official_result'],limit=12):
            if time.monotonic()>=self.deadline:return
            yield dict(c,parent_epoch=epoch,family='base/'+c.get('family','local'))

    def next(self,source):
        epoch=self.context['epoch']
        # The global streams have no incumbent parent and survive every epoch.
        if source in self.initial:
            try:
                c=next(self.initial[source]);self.generation_counts[source]+=1
                return c
            except StopIteration:del self.initial[source]
        if source not in self.streams or self.epochs[source]!=epoch:
            # Snapshot the exact accepted parent. Never mix a pre-change request's
            # cache trace with a post-change mapping while a generator is suspended.
            parent={'plan':self.context['plan'],'official_result':self.context['official_result'],'epoch':epoch}
            fn={'s':self._s,'m':self._m,'b':self._b}.get(source)
            self.streams[source]=iter(fn(parent,epoch)) if fn else iter(proposed_moves(self.g,self.n,self.cfg,self.q,parent,self.feedback,self.deadline))
            self.epochs[source]=epoch
        try:
            c=next(self.streams[source]);self.generation_counts[source]+=1
            c['parent_epoch']=self.epochs[source];return c
        except StopIteration:
            self.finished[source]=epoch;self.streams.pop(source,None);return None
