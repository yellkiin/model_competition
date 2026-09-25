"""One isolated scheduling job with full official evaluation and a shared incumbent."""
from __future__ import annotations
from collections import Counter
from copy import deepcopy
from pathlib import Path
import sys, time, traceback
from . import VERSION
from .io import ROOT, read, write, plan_key, score, plan_path
from . import candidates
from research_a_orion_anytime.engine import OfficialSession, model_config
from research_a_orion_anytime.core import constructors, one_core, bounds
from research_a_orion_track_structure.plugin import pad_plan


def run(request):
    out = Path(request['out']).resolve(); out.mkdir(parents=True,exist_ok=True)
    runtime=read(out/'runtime.json') if (out/'runtime.json').is_file() else {}
    offset=max(0.,time.time()-runtime.get('launched_epoch',time.time()))
    start=time.monotonic()-offset; q,n=request['q'],request['n']
    cap=float(request.get('job_seconds',request.get('seconds',600)))
    if not 0<cap<=600:raise ValueError('Per configuration wall cap must be in (0,600] seconds')
    deadline=start+cap-.20
    request={**request,'alternatives':list(request.get('alternatives',[]))+runtime.get('dynamic_alternatives',[])}
    state = {'version':VERSION,'case':request['case'],'q':q,'n':n,'mode':request.get('mode','warm'),
             'components':request['components'],'fifo_module':request.get('fifo_module'),
             'status':'running','phase':'seed_replay','attempts':[], 'generator_notes':[],
             'family_counts':{},'candidate_generation_seconds':0.,'official_eval_seconds':0.,
             'baseline':None,'incumbent':None,'raw_candidate_best':None,'improvement_events':[],
             'phase_events':[], 'job_seconds':cap,'cache_overrides':request.get('cache_overrides'),
             'launched_epoch':runtime.get('launched_epoch'), 'time_scope':'process start through persisted result; includes seed replay'}
    def save():
        state['elapsed_seconds'] = time.monotonic()-start
        write(out/'progress.json',state)
    def phase(name,source=None,candidate=None):
        state['phase']=name
        state['phase_events'].append({'elapsed_seconds':time.monotonic()-start,'phase':name,
                                      'source':source,'candidate':candidate,'optimization_stage':state.get('optimization_stage')})
    phase('parse')
    save()
    t=time.monotonic(); session=OfficialSession(request['official'],request['graph'],request['config'])
    g,cfg=session.graph,model_config(session.cfg,q,request.get('cache_overrides'))
    state['parse_seconds']=time.monotonic()-t
    global_bd=bounds(g,cfg,n,max(1,q))
    state['global_lower']=global_bd['global_lower']
    state['graph_features']={'ops':len(g.ops),'tensors':len(g.tensors),'components':len(g.components),
        'max_component':max(map(len,g.components),default=0),**global_bd}
    phase('seed_replay')
    context={'plan':None,'official_result':None,'effective_core_seeds':[], 'epoch':0}
    seen=set(); counter=0; family_counts=Counter()

    def evaluate(p,name,family,is_baseline=False,source=None,generation_seconds=0.,evidence=None):
        nonlocal counter
        if time.monotonic()>=deadline:return None
        source=source or ('seed' if is_baseline else family.split('/')[0])
        key=plan_key(p)
        if key in seen: return None
        seen.add(key); counter+=1
        pn=f'attempts/e{counter:04d}_plan.json';rn=f'attempts/e{counter:04d}_result.json.gz'
        write(out/pn,p)
        row={'index':counter,'name':name,'family':family,'status':'running',
             'started_seconds':time.monotonic()-start,'plan_file':pn,'result_file':rn,
             'source':source,'generation_seconds':generation_seconds,'evidence':evidence,'time_source':'local'}
        state['attempts'].append(row);family_counts[family]+=1
        state['family_counts']=dict(family_counts);phase('official_evaluation',source,name);save()
        t=time.monotonic()
        try:
            r=session.evaluate(p,q,request.get('cache_overrides')); wall=time.monotonic()-t
            if time.monotonic()>=deadline:
                row.update(status='completed_after_wall_limit',completed_seconds=time.monotonic()-start)
                save();return row
            state['official_eval_seconds']+=r['eval_seconds']
            row.update(status=r['status'],eval_seconds=r['eval_seconds'],eval_and_audit_seconds=wall)
            if r['status']=='ok':
                tval,bytes_=score(r)
                row.update(makespan=tval,added_copy_bytes=bytes_)
                meta={'makespan':tval,'added_copy_bytes':bytes_,'name':name,'family':family,
                      'plan_file':pn,'result_file':rn,'ready_seconds':time.monotonic()-start,
                      'certificate':r['audit']['certificate']}
                old_baseline=state['baseline']
                old_raw=state['raw_candidate_best']
                old_inc=state['incumbent']
                keep = is_baseline or old_inc is None or (tval,bytes_)<(old_inc['makespan'],old_inc['added_copy_bytes']) or old_raw is None or (tval,bytes_)<(old_raw['makespan'],old_raw['added_copy_bytes']) or request.get('keep_all_responses',False)
                row['result_retained']=keep
                if keep:
                    write(out/rn,r);meta['ready_seconds']=time.monotonic()-start
                else: row['result_file']=None
                if is_baseline:
                    if old_baseline is None or (tval,bytes_)<(old_baseline['makespan'],old_baseline['added_copy_bytes']): state['baseline']=dict(meta)
                else:
                    raw=state['raw_candidate_best']
                    if raw is None or (tval,bytes_)<(raw['makespan'],raw['added_copy_bytes']):
                        state['raw_candidate_best']=dict(meta)
                old=state['incumbent']
                better=old is None or (tval,bytes_)<(old['makespan'],old['added_copy_bytes'])
                row['accepted']=better
                row['gain_fraction']=max(0.,1-tval/old['makespan']) if old and old['makespan'] else 0.
                if better:
                    state['incumbent']=meta
                    context.update(plan=p,official_result=r['official_result'],epoch=context['epoch']+1)
                    state['improvement_events'].append({'elapsed_seconds':meta['ready_seconds'],
                        'makespan':tval,'added_copy_bytes':bytes_,'family':family,'source':source,'name':name,'evaluation':counter})
                    save()
            else:
                write(out/rn,r);row['result_retained']=True
                row['audit_errors']=r.get('audit',{}).get('errors')
        except Exception as exc:
            row.update(status='error',error=str(exc),traceback=traceback.format_exc())
        row['completed_seconds']=time.monotonic()-start;save()
        return row

    seed = request.get('seed_plan')
    if request.get('fixed_plan'):
        p=read(request['fixed_plan']);evaluate(p,'same_plan_no_l2','pair',True)
        state.update(status='ok' if state['incumbent'] else 'failed',phase='done');save();return
    if seed:
        p=read(seed)
        if len(p['core_schedules'])!=n: raise ValueError('Baseline seed has wrong target core count')
        evaluate(p,'replayed_reference','seed',True)
    elif q==0:
        evaluate(one_core(g,1),'original_singlecore','seed',True)
    else:
        for c in constructors(g,n,cfg,q,diagnostics=state['generator_notes'])[:2]:
            evaluate(c['plan'],c['name'],'base/construct',True)
            if state['incumbent']:break
    if state['incumbent'] is None:
        state.update(status='failed',phase='done',reason='no_valid_initial_plan');save();return
    if request.get('reference_makespan') is not None and seed:
        state['reference_matches']=state['baseline']['makespan']==request['reference_makespan']
        if not state['reference_matches']:
            state.update(status='reference_mismatch',phase='done');save();return
    if q==0:
        state.update(status='ok',phase='done');save();return
    for alt in request.get('baseline_alternatives',[]):
        if time.monotonic()>=deadline:break
        p=read(alt['path'])
        if len(p['core_schedules'])!=n:raise ValueError('Extra baseline target core count differs')
        evaluate(p,alt.get('name','available_track_seed'),'seed/extra',True)
    state['seed_replay_seconds']=time.monotonic()-start
    if state['global_lower'] and 1-state['global_lower']/state['incumbent']['makespan']<=request.get('stop_gap',.0025):
        state.update(status='ok',stop_reason='certified_relative_gap_before_search');phase('done');save();return
    phase('search');state['search_started_seconds']=time.monotonic()-start
    state['search_deadline_seconds']=cap;state['search_deadline_epoch']=time.time()+max(0,deadline-time.monotonic())
    save()
    active=request['components']
    if 's' in active:
        for alt in request.get('alternatives',[]):
            if time.monotonic()>=deadline:break
            try:
                p=pad_plan(read(alt['path']),n)
                evaluate(p,alt.get('name','effective_core_seed'),'structure/effective_cores',source='s')
            except Exception as exc:
                state['generator_notes'].append({'status':'seed_error','path':alt['path'],'error':str(exc)})
    fifo=candidates.fifo_module(request.get('fifo_module') or 'research_a_orion_fusion.fifo') if 'f' in active else None
    factories={'b':lambda:candidates.base(g,n,cfg,q,context,state['generator_notes'],deadline)}
    if 's' in active:factories['s']=lambda:candidates.structure(g,n,cfg,q,context,state['generator_notes'],deadline)
    if 'm' in active:factories['m']=lambda:candidates.memory(g,n,cfg,q,context,state['generator_notes'],deadline)
    if fifo and q==3:factories['f']=lambda:fifo.propose(g,n,cfg,q,context,state['generator_notes'],deadline)
    order=[x for x in ('s','m','f','b') if x in factories]
    streams={s:iter(factories[s]()) for s in order};retired={};turn=0
    stall=0;source_stalls=Counter();max_calls=request.get('max_evaluations',2048)
    while time.monotonic()<deadline and counter<max_calls:
        for s in order:
            if s not in streams and retired.get(s,-1)<context['epoch']:
                streams[s]=iter(factories[s]())
        if not streams:break
        policy=request.get('source_policy','staged')
        elapsed=time.monotonic()-start
        genuine=[e for i,e in enumerate(state['improvement_events']) if i==0 or e['makespan']<state['improvement_events'][i-1]['makespan']]
        last_gain=genuine[-1]['elapsed_seconds'] if genuine else 0.
        prelude=min(60.,cap*.5)
        extend=min(cap*.70,prelude+20.)
        warming=bool(fifo and 'f' in streams and policy=='staged' and
                     (elapsed<prelude or elapsed<extend and elapsed-last_gain<10.) and
                     any(x in streams for x in ('s','m','b')))
        eligible=[x for x in order if x in streams and (not warming or x!='f')]
        state['optimization_stage']='structure_memory_descent' if warming else 'joint_refinement'
        source=eligible[turn%len(eligible)];turn+=1
        if fifo and policy in ('feedback','staged') and not warming:
            source=fifo.select_source(tuple(eligible),state,context,max(0.,deadline-time.monotonic()))
            if source not in eligible:raise ValueError('Source selector returned an unavailable source')
        phase('candidate_generation',source);save();t=time.monotonic()
        try:c=next(streams[source])
        except StopIteration:
            retired[source]=context['epoch'];del streams[source];continue
        except Exception as exc:
            state['generator_notes'].append({'source':source,'status':'generation_error','error':str(exc),'traceback':traceback.format_exc()})
            retired[source]=context['epoch'];del streams[source];save();continue
        generation=time.monotonic()-t;state['candidate_generation_seconds']+=generation
        if time.monotonic()>=deadline:break
        key=plan_key(c['plan'])
        if key in seen:continue
        if c['bounds']['candidate_lower']>state['incumbent']['makespan']:
            seen.add(key);state['generator_notes'].append({'source':source,'status':'certified_pruned','name':c['name']});continue
        row=evaluate(c['plan'],c['name'],c['family'],source=source,generation_seconds=generation,evidence=c.get('evidence'))
        stall=0 if row and row.get('accepted') else stall+1
        if row and row.get('accepted'):source_stalls.clear()
        elif row:source_stalls[source]+=1
        if state['global_lower'] and 1-state['global_lower']/state['incumbent']['makespan']<=request.get('stop_gap',.0025):
            state['stop_reason']='certified_relative_gap';break
        if time.monotonic()-start-last_gain>=request.get('stall_seconds',60.) and stall>=request.get('stall_calls',64) and all(source_stalls[x]>=request.get('stall_per_source',24) for x in streams):
            state['stop_reason']='all_sources_nonimproving';break
    state['family_counts']=dict(family_counts);state['source_stalls']=dict(source_stalls)
    state['status']='ok';phase('done')
    state.setdefault('stop_reason','sources_exhausted' if not streams else 'budget')
    state['search_seconds']=time.monotonic()-start-state['search_started_seconds']
    save()


def main():
    req=read(sys.argv[1]);out=Path(req['out'])
    try:run(req)
    except Exception as exc:
        write(out/'fatal.json',{'error':str(exc),'traceback':traceback.format_exc()});raise

if __name__=='__main__':main()
