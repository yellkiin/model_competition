"""One graph, one original session, shared S/M/F incumbents, one hard time budget.

A Q3 improvement is committed only with its exact same-plan Q2 response. Thus a
hard stop leaves a complete earlier incumbent, not an unpaired headline score.
The parent owns the 600-second process cap, including this module's imports.
"""
from __future__ import annotations
from collections import defaultdict, deque
from dataclasses import dataclass, field
import argparse
import math
import time
import traceback
from pathlib import Path
from statistics import median
from .io import read,write,key,score,utc,resolve
from .sources import GraphCache, structure_global, structure_local, memory, base, wrap
from .fifo import propose as fifo
from .seeds import load_catalog
from research_a_orion_anytime.engine import OfficialSession, model_config
from research_a_orion_anytime.core import bounds,one_core,plan_view,map_groups
from research_a_orion_anytime.worker import audit

@dataclass
class Search:
    q:int
    n:int
    best:dict|None=None
    initial:dict|None=None
    lower:float=0.
    target:float|None=None
    epoch:int=0
    calls:int=0
    spent:float=0.
    generated:int=0
    stopped:str|None=None
    last_gain:float=0.
    last_visit:int=0
    best_raw:float|None=None
    source_history:dict=field(default_factory=lambda:defaultdict(list))
    epoch_calls:dict=field(default_factory=lambda:defaultdict(int))
    streams:dict=field(default_factory=dict)
    global_s:object=None
    global_b:object=None
    alt:deque=field(default_factory=deque)
    seen:set=field(default_factory=set)
    counts:dict=field(default_factory=lambda:defaultdict(int))
    gains:list=field(default_factory=list)
    costs:list=field(default_factory=list)
    source_turn:int=0
    def context(self):
        return dict(plan=self.best['plan'],official_result=self.best['response']['official_result'])

class Runner:
    def __init__(self, req, shared=None):
        self.req=req; self.out=Path(req['out']);self.out.mkdir(parents=True,exist_ok=True)
        self.boot=time.monotonic()
        self.offset=max(0.,time.time()-req.get('launch_epoch',time.time()))
        self.deadline=self.boot+max(0.,req['seconds']-self.offset-.2)
        self.events_path=self.out/'events.jsonl';self.events_path.touch()
        self.calls=0;self.iteration=0;self.cache={};self.states={};self.receipts=[]
        self.current=None;self.session=None;self.cfg=None;self.gc=None;self.shared=shared
        self.timings=defaultdict(float);self.pairs=0;self.baseline=None
        self.mode=req.get('mode','SMF');self.graph=req['case']
        self.event('start',policy='concord-1.2',mode=self.mode,graph_budget=req['seconds'])

    def elapsed(self):return self.offset+time.monotonic()-self.boot
    def left(self):return max(0.,self.deadline-time.monotonic())
    def event(self,kind,**data):
        row={**data, 'event':kind, 'elapsed_seconds':self.elapsed(), 'case':self.graph}
        with self.events_path.open('a',encoding='utf-8') as f:
            import json
            f.write(json.dumps(row,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
        return row

    def check_seed(self,plan,r,q,n):
        if r.get('status')!='ok' or r.get('audit',{}).get('ok') is not True:return False
        raw=r['official_result']
        if raw['num_cores']!=n or len(plan['core_schedules'])!=n:return False
        if q==3 and raw.get('problem')!=3:return False
        if q==2 and (raw.get('scene')!='B' or raw.get('problem')==3):return False
        if q in (0,1) and raw.get('scene')!='A':return False
        for attr,wanted in [('bandwidth_bytes_per_cycle',self.cfg.bandwidth),('capacity_bytes',self.cfg.capacity)]:
            if raw.get(attr)!=wanted:return False
        if q==3 and (raw.get('cache_capacity_bytes')!=self.cfg.cache_capacity or
                     raw.get('cache_bandwidth_bytes_per_cycle')!=self.cfg.cache_bandwidth):return False
        return audit(self.session.graph,plan,raw,q,self.cfg)['ok']

    def save_best(self,st,c,response,pair=None,seed=None,source='seed',name='archived_incumbent'):
        before=time.monotonic();folder=self.out/'incumbents'/f'q{st.q}_n{st.n}'/f'v{st.epoch:04d}'
        write(folder/'plan.json',c['plan']);write(folder/'response.json.gz',response)
        if pair:
            write(folder/'no_l2.json.gz',pair);write(folder/'no_l2_plan.json',c['plan'])
        meta=dict(q=st.q,n=st.n,makespan=score(response)[0],added_copy_bytes=score(response)[1],
            source=source,name=name,plan_file=str((folder/'plan.json').relative_to(self.out)),
            result_file=str((folder/'response.json.gz').relative_to(self.out)),
            pair_file=str((folder/'no_l2.json.gz').relative_to(self.out)) if pair else None,
            pair_plan_file=str((folder/'no_l2_plan.json').relative_to(self.out)) if pair else None,
            seed_solve_seconds=seed.get('seed_solve_seconds') if seed else st.initial.get('seed_solve_seconds') if st.initial else None,
            origin=seed.get('origin') if seed else None,elapsed_seconds=self.elapsed(),epoch=st.epoch)
        st.best=dict(plan=c['plan'],response=response,pair=pair,meta=meta)
        self.timings['io_seconds']+=time.monotonic()-before
        # Metadata is published only after the complete immutable files exist.
        self.event('incumbent',**meta,official_calls=self.calls)
        self.checkpoint()

    def checkpoint(self,phase=None):
        write(self.out/'progress.json',dict(case=self.graph,phase=phase or 'search',
            elapsed_seconds=self.elapsed(),current=self.current,official_calls=self.calls,
            selected=[s.best['meta'] for s in self.states.values() if s.best],
            missing=[dict(q=s.q,n=s.n) for s in self.states.values() if not s.best]))

    def original(self,st,plan,q,source,name):
        ck=(q,st.n,key(plan)); hit=self.cache.get(ck)
        if hit:
            self.event('evaluation_reused',q=q,n=st.n,source=source,name=name,result_file=hit,
                       reused_from='same_graph_same_configuration_exact_plan')
            return read(self.out/hit)
        self.calls+=1;index=self.calls; prefix=self.out/'attempts'/f'{index:05d}'
        write(str(prefix)+'_plan.json',plan)
        self.current=dict(index=index,q=q,n=st.n,source=source,name=name,started_seconds=self.elapsed())
        self.event('evaluation_start',**self.current);self.checkpoint('official_evaluation')
        started=time.monotonic()
        try:res=self.session.evaluate(plan,q,self.req.get('cache_overrides') if q==3 else None)
        except Exception as exc:
            res=dict(status='error',error=str(exc),traceback=traceback.format_exc())
        spent=time.monotonic()-started
        self.timings['official_eval_audit_seconds']+=spent
        path=str(prefix)+'_response.json.gz';t=time.monotonic();write(path,res)
        self.timings['io_seconds']+=time.monotonic()-t
        self.event('evaluation_end',index=index,q=q,n=st.n,source=source,name=name,
            status=res['status'],eval_audit_seconds=spent,original_eval_seconds=res.get('eval_seconds'),
            makespan=score(res)[0] if res['status']=='ok' else None,
            result_file=str(Path(path).relative_to(self.out)),
            plan_file=str(Path(str(prefix)+'_plan.json').relative_to(self.out)))
        if res['status']=='ok':self.cache[ck]=str(Path(path).relative_to(self.out))
        self.current=None
        return res

    def adopt(self,st,c,res,source,name,seed=None,pair=None):
        if res['status']!='ok':return False
        new=score(res);old=score(st.best['response']) if st.best else (math.inf,math.inf)
        if new>=old:return False
        if st.q==3 and pair is None:
            # Pair before promotion. One feasible earlier seed always survives.
            estimate=max(st.costs[-3:],default=.05)
            if self.left()<=max(.1,estimate*1.25):
                self.event('unpaired_proposal',q=3,n=st.n,makespan=new[0],source=source,name=name)
                return False
            pair=self.original(st,c['plan'],2,'PAIR',name)
            if pair['status']!='ok':return False
            self.pairs+=1
        if new[0]<old[0]:st.last_gain=self.elapsed()
        st.epoch+=1; st.streams.clear();st.epoch_calls.clear()
        self.save_best(st,c,res,pair,seed,source,name)
        if math.isfinite(old[0]):
            gain=(old[0]-new[0])/max(1,old[0]);st.gains.append(gain)
            self.event('improvement',q=st.q,n=st.n,source=source,name=name,
                       before=old[0],after=new[0],gain_fraction=gain,epoch=st.epoch)
        # Newly improved plans are proposals to other questions/core counts, never scores.
        if source != 'BASELINE':
            from research_a_orion_track_structure.plugin import pad_plan
            for other in self.states.values():
                if other is st or other.q == 0 or other.n < st.n:continue
                proposal=pad_plan(c['plan'],other.n)
                if key(proposal) not in other.seen:
                    other.alt.appendleft(dict(plan=proposal,from_q=st.q,from_n=st.n,origin='live_incumbent'))
                    if other.streams.get('S') is False:other.streams.pop('S')
                    while len(other.alt)>8:other.alt.pop()
                    if other.stopped in ('candidate_families_exhausted','all_sources_stagnant'):
                        other.stopped=None;other.streams.pop('S',None)
        return True

    def initialize(self):
        t=time.monotonic()
        if self.shared:
            self.session,self.cfg,self.gc=self.shared
        else:
            self.session=OfficialSession(self.req['official'],self.req['graph'],self.req['config'])
            self.cfg=model_config(self.session.cfg,3 if self.req.get('cache_overrides') else 1,self.req.get('cache_overrides'))
            self.gc=GraphCache(self.session.graph,self.cfg)
        self.event('graph_features',**self.gc.features)
        catalog=load_catalog(self.req['catalog']) if self.req.get('catalog') else dict(entries=[],targets=[])
        rows=[r for r in catalog['entries'] if r['case']==self.graph]
        rows=sorted(rows,key=lambda r:(r['q']!=0,r['makespan']))
        wanted={(int(q),int(n)) for q,n in self.req['keys']}|{(0,1)}
        for q,n in wanted:
            self.states[q,n]=Search(q,n,lower=bounds(self.session.graph,self.cfg,n,max(q,1))['global_lower'])
        target_rows={}
        for r in catalog.get('targets',[]):
            if r.get('case')!=self.graph:continue
            try:
                k=int(r['q']),int(r['n']);v=float(r.get('makespan') or r.get('new_makespan'))
                if k not in target_rows or v<target_rows[k]:target_rows[k]=v
            except (ValueError,TypeError,KeyError):continue
        for k,st in self.states.items():st.target=target_rows.get(k)
        self.event('published_targets',targets=[dict(q=q,n=n,makespan=v) for (q,n),v in target_rows.items()])
        seed_pairs={}
        # Archive restoration is outside the solve; loading, checking and saving are inside.
        for row in rows:
            if self.left()<=.2:break
            q,n=row['q'],row['n'];st=self.states.get((q,n))
            if st is None or st.best:continue
            try:
                plan=read(row['plan_file']);res=read(row['result_file'])
                if not self.check_seed(plan,res,q,n):
                    self.event('seed_rejected',q=q,n=n,origin=row['origin']);continue
                pair=read(row['pair_file']) if row.get('pair_file') and q==3 else None
                if pair and not self.check_seed(plan,pair,2,n):pair=None
                st.initial=dict(row)
                st.seen.add(key(plan))
                # Warm reference remains valid even before its optional paired record loads.
                st.epoch=0;self.save_best(st,dict(plan=plan),res,pair,row)
                self.cache[q,n,key(plan)]=st.best['meta']['result_file']
                if pair:self.cache[2,n,key(plan)]=st.best['meta']['pair_file']
                if q==0:self.baseline=score(res)[0]
            except (ValueError,OSError,KeyError) as e:
                self.event('seed_error',q=q,n=n,error=str(e))
        # Published selected plans lacking traces: acquire that trace once, inside
        # this graph's budget, before algorithm search. Do not count as new gain.
        for row in sorted(catalog.get('pending',[]),key=lambda r:r['makespan']):
            if row['case']!=self.graph or self.left()<1.:continue
            st=self.states.get((row['q'],row['n']))
            if not st or (st.best and score(st.best['response'])[0]<=row['makespan']):continue
            plan=read(row['plan_file']);res=self.original(st,plan,st.q,'SEED_TRACE','published_plan_trace')
            if res['status']!='ok' or (st.best and score(res)>=score(st.best['response'])):continue
            pair=self.original(st,plan,2,'PAIR','published_plan_trace') if st.q==3 else None
            if pair and pair['status']!='ok':continue
            st.initial=dict(row,makespan=score(res)[0],added_copy_bytes=score(res)[1]);st.seen.add(key(plan));st.epoch+=1
            self.save_best(st,dict(plan=plan),res,pair,st.initial,source='seed',name='published_plan_trace')
            self.event('reference_upgrade',q=st.q,n=st.n,recorded_makespan=row['makespan'],actual_makespan=score(res)[0])
        st=self.states[0,1]
        if not st.best and self.left()>.2:
            plan=one_core(self.session.graph,1);res=self.original(st,plan,0,'BASELINE','original_singlecore')
            if res['status']=='ok':
                self.adopt(st,dict(plan=plan),res,'BASELINE','original_singlecore');self.baseline=score(res)[0]
        st.stopped='fixed_original_singlecore'
        # A different q/n is only a proposal; its score is never copied to a target.
        for st in self.states.values():
            if st.q==0:continue
            alternatives=[r for r in rows if r['q']>0 and r['n']<=st.n and (r['q'],r['n'])!=(st.q,st.n)]
            alternatives.sort(key=lambda r:(r['n']!=st.n,r['q']!=st.q,r['makespan']))
            for r in alternatives[:4]:
                st.alt.append(dict(row=r))
        self.timings['initialization_seconds']=time.monotonic()-t
        self.checkpoint('initialized')

    def pull(self,st,source):
        g=self.session.graph;n=st.n;q=st.q
        if not st.best:
            p=map_groups(g,g.components,n,self.cfg,q)
            return wrap(g,n,self.cfg,q,p,'cold_component_seed','base/initial')
        if source=='S':
            if st.alt:
                entry=st.alt.popleft()
                from research_a_orion_track_structure.plugin import pad_plan
                if 'row' in entry:
                    r=entry['row'];p=pad_plan(read(r['plan_file']),n);fq,fn,origin=r['q'],r['n'],r['origin']
                else:p=entry['plan'];fq,fn,origin=entry['from_q'],entry['from_n'],entry['origin']
                return wrap(g,n,self.cfg,q,p,f'reuse_q{fq}_n{fn}','structure/reuse',{'origin':origin})
            st.source_turn+=1
            if st.global_s is None:st.global_s=iter(structure_global(g,n,self.cfg,q,self.gc,self.deadline))
            if st.source_turn%3==1 and st.global_s is not False:
                try:return next(st.global_s)
                except StopIteration:st.global_s=False
            if 'S' not in st.streams:st.streams['S']=iter(structure_local(g,n,self.cfg,q,st.context(),self.deadline))
            try:return next(st.streams['S'])
            except StopIteration:
                if st.global_s is not False:
                    try:return next(st.global_s)
                    except StopIteration:st.global_s=False
                raise
        if source=='B':
            if st.global_b is None:st.global_b=iter(base(g,n,self.cfg,q,self.deadline))
            return next(st.global_b)
        if source not in st.streams:
            st.streams[source]=iter(memory(g,n,self.cfg,q,st.context(),self.gc,self.deadline) if source=='M'
                                    else fifo(g,n,self.cfg,q,st.context(),self.deadline))
        return next(st.streams[source])

    def active_sources(self,st):
        if not st.best:return ['S' if 'S' in self.mode else 'B']
        out=[s for s in 'SM' if s in self.mode]
        # Micro-wave belongs to M; avoid all-islands-open base stages on this shape.
        if not self.gc.features['private_islands']:out+=['B']
        out=[s for s in out if st.streams.get(s) is not False and not (s=='B' and st.global_b is False)]
        if st.q==3 and 'F' in self.mode and (st.calls>=4 or not out) and st.streams.get('F') is not False:out+=['F']
        return out

    def select_source(self,st,sources):
        fresh=[s for s in sources if st.counts[s]<1]
        if fresh:return fresh[0]
        # At least one real proposal from each source in a new parent epoch.
        fresh=[s for s in sources if st.epoch_calls[s]<1]
        if fresh:return min(fresh,key=lambda s:st.counts[s])
        if 'F' not in self.mode:return min(sources,key=lambda s:st.counts[s])
        def priority(s):
            hs=st.source_history[s][-8:]
            cost=median([h['seconds'] for h in hs]) if hs else .1
            gain=sum(h['gain'] for h in hs)/max(1,len(hs))
            bonus=.02*math.sqrt(math.log(2+st.calls)/(1+st.counts[s]))
            return (gain+bonus)/max(.01,cost)
        # Explicit starvation prevention; cheap duplicate generation is charged.
        if st.calls%7==6:return min(sources,key=lambda s:st.counts[s])
        return max(sources,key=priority)

    def step(self,st):
        sources=self.active_sources(st)
        if not sources:st.stopped='candidate_families_exhausted';return
        s=self.select_source(st,sources);start=time.monotonic();old=score(st.best['response'])[0] if st.best else None
        generated_start=time.monotonic();c=None
        for _ in range(4):
            try:c=self.pull(st,s)
            except StopIteration:
                st.streams[s]=False
                if s=='B':st.global_b=False
                self.event('source_exhausted',q=st.q,n=st.n,source=s,epoch=st.epoch);c=None;break
            except Exception as exc:
                self.event('generation_error',q=st.q,n=st.n,source=s,error=str(exc))
                st.streams[s]=False;c=None;break
            st.generated+=1;pk=key(c['plan'])
            if pk in st.seen:
                self.event('duplicate',q=st.q,n=st.n,source=s,name=c['name']);c=None;continue
            st.seen.add(pk)
            if st.best and c['bounds']['candidate_lower']>score(st.best['response'])[0]:
                self.event('bound_pruned',q=st.q,n=st.n,source=s,name=c['name'],lower=c['bounds']['candidate_lower']);c=None;continue
            break
        generation=time.monotonic()-generated_start;self.timings['generation_seconds']+=generation
        gain=0.
        if c:
            if self.left()<max(.1,1.25*max(st.costs[-3:],default=.01)):
                st.stopped='remaining_time_admission';return
            epoch=st.epoch;st.calls+=1;st.counts[s]+=1;st.epoch_calls[s]+=1
            self.event('candidate',q=st.q,n=st.n,source=s,family=c['family'],name=c['name'],
                generation_seconds=generation,parent_epoch=epoch,
                parent_makespan=old,proxy=c['proxy'],evidence=c.get('evidence',{}))
            before=time.monotonic();res=self.original(st,c['plan'],st.q,s,c['name'])
            st.costs.append(time.monotonic()-before)
            if res['status']=='ok':
                st.best_raw=min(st.best_raw or math.inf,score(res)[0])
                if self.adopt(st,c,res,s,c['name']):
                    gain=(old-score(res)[0])/max(1,old) if old else 0.
        spent=time.monotonic()-start;st.spent+=spent
        st.source_history[s].append(dict(seconds=spent,gain=gain))
        st.last_visit=self.iteration;self.iteration+=1
        self.event('step',q=st.q,n=st.n,source=s,seconds=spent,generation_seconds=generation,
                   improved=gain>0,gain_fraction=gain,epoch=st.epoch,calls=st.calls)
        if st.generated>=self.req.get('max_proposals',256):st.stopped='finite_proposal_cap'
        if st.calls>=self.req.get('max_evaluations',64):st.stopped='evaluation_cap'
        if st.best:
            gap=(score(st.best['response'])[0]-st.lower)/max(1,score(st.best['response'])[0])
            if gap<=self.req.get('gap_tolerance',.001):st.stopped='certified_gap'
        active=self.active_sources(st)
        if (st.calls>=24 and st.spent>=20 and self.elapsed()-st.last_gain>=30 and
            all(st.epoch_calls[x]>=4 for x in active) and not any(h['gain']>0 for s0 in active for h in st.source_history[s0][-4:])):
            st.stopped='all_sources_stagnant'
        self.checkpoint()

    def choose(self):
        active=[s for s in self.states.values() if not s.stopped and s.q!=0]
        if not active:return None
        cold=[s for s in active if s.best is None]
        if cold:return max(cold,key=lambda s:s.n)
        cover=[s for s in active if s.calls<2]
        if cover:return min(cover,key=lambda s:(s.calls,-s.n,s.q))
        aged=[s for s in active if self.iteration-s.last_visit>=2*len(active)]
        if aged:return min(aged,key=lambda s:s.last_visit)
        def priority(st):
            u=score(st.best['response'])[0];lb=st.lower
            potential=max(0.,(u-lb)/max(1,u))
            reward=sum(st.gains[-8:])/max(1,min(st.calls,8))
            bonus=.03*math.sqrt(math.log(2+self.iteration)/(1+st.calls))
            return min(potential,reward+bonus)/max(.02,median(st.costs[-5:]) if st.costs else .1)
        return max(active,key=priority)

    def finish(self):
        # Ensure inherited Q3 selections also have an exact-plan pair.
        for st in self.states.values():
            if st.q==3 and st.best and st.best.get('pair') is None and self.left()>.1:
                p=st.best['plan'];res=self.original(st,p,2,'PAIR','inherited_pair')
                if res['status']=='ok':
                    st.epoch+=1;self.save_best(st,dict(plan=p),st.best['response'],res,source=st.best['meta']['source'],name=st.best['meta']['name'])
        rows=[]
        for st in sorted(self.states.values(),key=lambda s:(s.q,s.n)):
            meta=st.best['meta'] if st.best else {};raw=st.best['response']['official_result'] if st.best else {}
            pair=st.best.get('pair') if st.best else None
            rows.append(dict(case=self.graph,q=st.q,n=st.n,mode='warm_start' if st.initial else 'cold_start',
                method=self.mode,status='ok' if st.best else 'missing',baseline=self.baseline,
                old_makespan=st.initial.get('makespan') if st.initial else None,
                new_makespan=meta.get('makespan'),best_unprotected_makespan=st.best_raw,
                old_added_copy_bytes=st.initial.get('added_copy_bytes') if st.initial else None,
                new_added_copy_bytes=meta.get('added_copy_bytes'),
                seed_solve_seconds=meta.get('seed_solve_seconds'),added_solve_seconds=self.elapsed(),
                total_solve_seconds=meta['seed_solve_seconds']+self.elapsed() if meta.get('seed_solve_seconds') is not None else None,
                cost_scope='shared_graph_wall_not_additive',config_active_seconds=st.spent,
                evaluations=st.calls,lower=st.lower,source=meta.get('source'),candidate=meta.get('name'),
                no_l2_makespan=score(pair)[0] if pair else None,
                pair_status='ok' if pair else 'missing' if st.q==3 else None,
                cache_hit_rate=raw.get('cache_stats',{}).get('hit_rate'),
                spill_added_copy_bytes=raw.get('data_movement_bytes',{}).get('spill_added_copy_bytes'),
                plan_file=meta.get('plan_file'),result_file=meta.get('result_file'),pair_file=meta.get('pair_file'),
                stopped=st.stopped or 'shared_graph_deadline',graph_seconds=self.elapsed()))
        complete=all(r['status']=='ok' and (r['q']!=3 or r['pair_status']=='ok') for r in rows)
        self.event('stop',official_calls=self.calls,complete=complete,timings=dict(self.timings))
        write(self.out/'summary.json',dict(case=self.graph,created_utc=utc(),rows=rows,
            graph_seconds=self.elapsed(),official_calls=self.calls,complete=complete,
            timings=dict(self.timings),policy='concord-1.2',mode=self.mode))
        self.checkpoint('stopped')

    def run(self):
        self.initialize()
        # Do not spend the whole graph budget when the bound already certifies it.
        for st in self.states.values():
            if st.best and st.q and (score(st.best['response'])[0]-st.lower)/max(1,score(st.best['response'])[0])<=self.req.get('gap_tolerance',.001):
                st.stopped='certified_gap'
        diagnostic_reserve=min(90.,self.req['seconds']*.15) if self.req.get('diagnostics') and self.mode=='SMF' else 0.
        study_reserve=min(60.,self.req['seconds']*.1) if self.req.get('cache_study') else 0.
        while self.left()>max(.25,diagnostic_reserve+study_reserve) and self.calls<self.req.get('graph_evaluations',4096):
            st=self.choose()
            if st is None:break
            self.step(st)
        self.finish()
        if diagnostic_reserve and self.left()>3:
            from .diagnose import conditional
            conditional(self)
        if self.req.get('cache_study') and self.left()>1:
            from .cache_study import study
            choices=[s for s in self.states.values() if s.q==3 and s.best]
            if choices:
                st=max(choices,key=lambda s:s.n)
                study(self.session,st.best['plan'],st.best['response'],self.out/'cache_study',self.deadline,self.event)

def main():
    p=argparse.ArgumentParser();p.add_argument('request');a=p.parse_args();req=read(a.request)
    runner=Runner(req)
    try:runner.run()
    except Exception as exc:
        write(Path(req['out'])/'error.json',dict(error=str(exc),traceback=traceback.format_exc()))
        runner.event('fatal',error=str(exc));raise

if __name__=='__main__':main()
