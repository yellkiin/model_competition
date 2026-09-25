"""One isolated scheduling job with full official evaluation and a shared incumbent."""
from __future__ import annotations
from collections import Counter
from copy import deepcopy
from pathlib import Path
import sys, time, traceback
from . import VERSION
from .io import ROOT, read, write, plan_key, score, plan_path
from . import candidates
from research_a_orion_anytime.engine import OfficialSession
from research_a_orion_anytime.core import constructors, one_core, bounds
from research_a_orion_track_structure.plugin import pad_plan


def run(request):
    out = Path(request['out']).resolve(); out.mkdir(parents=True,exist_ok=True)
    start = time.monotonic(); q,n = request['q'],request['n']
    state = {'version':VERSION,'case':request['case'],'q':q,'n':n,'mode':request.get('mode','warm'),
             'components':request['components'],'fifo_module':request.get('fifo_module'),
             'status':'running','phase':'seed_replay','attempts':[], 'generator_notes':[],
             'family_counts':{},'candidate_generation_seconds':0.,'official_eval_seconds':0.,
             'baseline':None,'incumbent':None,'raw_candidate_best':None,'improvement_events':[]}
    def save():
        state['elapsed_seconds'] = time.monotonic()-start
        write(out/'progress.json',state)
    save()
    t=time.monotonic(); session=OfficialSession(request['official'],request['graph'],request['config'])
    g,cfg=session.graph,session.cfg
    state['parse_seconds']=time.monotonic()-t
    state['global_lower']=bounds(g,cfg,n,max(1,q))['global_lower']
    context={'plan':None,'official_result':None,'effective_core_seeds':[]}
    seen=set(); counter=0; family_counts=Counter()

    def evaluate(p,name,family,is_baseline=False):
        nonlocal counter
        key=plan_key(p)
        if key in seen: return None
        seen.add(key); counter+=1
        pn=f'attempts/e{counter:04d}_plan.json';rn=f'attempts/e{counter:04d}_result.json.gz'
        write(out/pn,p)
        row={'index':counter,'name':name,'family':family,'status':'running',
             'started_seconds':time.monotonic()-start,'plan_file':pn,'result_file':rn}
        state['attempts'].append(row);family_counts[family]+=1;save()
        t=time.monotonic()
        try:
            r=session.evaluate(p,q); wall=time.monotonic()-t
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
                if better:
                    state['incumbent']=meta
                    context.update(plan=p,official_result=r['official_result'])
                    state['improvement_events'].append({'elapsed_seconds':meta['ready_seconds'],
                        'makespan':tval,'added_copy_bytes':bytes_,'family':family,'name':name,'evaluation':counter})
                    save()  # Persist before another generator can consume the budget.
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
        p=read(alt['path'])
        if len(p['core_schedules'])!=n:raise ValueError('Extra baseline target core count differs')
        evaluate(p,alt.get('name','available_track_seed'),'seed/extra',True)
    state['seed_replay_seconds']=time.monotonic()-start
    state['phase']='search';state['search_started_seconds']=time.monotonic()-start
    deadline=time.monotonic()+request['seconds'];state['search_deadline_seconds']=deadline-start;state['search_deadline_epoch']=time.time()+request['seconds']
    save()
    active=request['components']
    if 's' in active:
        # Best lower-core historical seeds and this campaign's completed lower-core solutions.
        for alt in request.get('alternatives',[]):
            if time.monotonic()>=deadline:break
            try:
                p=pad_plan(read(alt['path']),n)
                evaluate(p,alt.get('name','effective_core_seed'),'structure/effective_cores')
            except Exception as exc:
                state['generator_notes'].append({'status':'seed_error','path':alt['path'],'error':str(exc)})
    streams={'b':iter(candidates.base(g,n,cfg,q,context,state['generator_notes'],deadline))}
    if 's' in active:streams['s']=iter(candidates.structure(g,n,cfg,q,context,state['generator_notes'],deadline))
    if 'm' in active:streams['m']=iter(candidates.memory(g,n,cfg,q,context,state['generator_notes'],deadline))
    fifo=candidates.fifo_module(request.get('fifo_module')) if 'f' in active else None
    if 'f' in active and fifo is None:raise ValueError('F component requested without an explicit completed FIFO adapter')
    if fifo:streams['f']=iter(fifo.propose(g,n,cfg,q,context,state['attempts'],deadline))
    # Each live source gets a slot, not an uncalibrated cross-source proxy contest.
    order=[x for x in ('s','m','f','b') if x in streams];turn=0
    stall=0;source_stalls=Counter();max_calls=request.get('max_evaluations',96)
    while streams and time.monotonic()<deadline and counter<max_calls:
        source=order[turn%len(order)];turn+=1
        if source not in streams:continue
        if fifo and callable(getattr(fifo,'select_source',None)):
            decision=fifo.select_source(tuple(streams),state,context,max(0.,deadline-time.monotonic()))
            if decision is None:
                state['stop_reason']='fifo_selector_stop';break
            if decision not in streams:raise ValueError('FIFO select_source returned an unavailable source')
            source=decision
        t=time.monotonic()
        try: c=next(streams[source])
        except StopIteration:
            del streams[source];continue
        except Exception as exc:
            state['generator_notes'].append({'source':source,'status':'generation_error',
                'error':str(exc),'traceback':traceback.format_exc()});del streams[source];save();continue
        state['candidate_generation_seconds']+=time.monotonic()-t
        if time.monotonic()>=deadline:break
        key=plan_key(c['plan'])
        if key in seen:continue
        if c['bounds']['candidate_lower']>state['incumbent']['makespan']:
            seen.add(key);state['generator_notes'].append({'source':source,'status':'certified_pruned','name':c['name']});continue
        row=evaluate(c['plan'],c['name'],c['family'])
        stall=0 if row and row.get('accepted') else stall+1
        if row and row.get('accepted'):source_stalls.clear()
        elif row:source_stalls[source]+=1
        if state['global_lower'] and state['incumbent']['makespan']/state['global_lower']<=request.get('stop_ratio',1.005):
            state['stop_reason']='certificate_target';break
        if stall>=request.get('stall_calls',32) and all(source_stalls[x]>=request.get('stall_per_source',16) for x in streams):
            state['stop_reason']='all_sources_nonimproving';break
    state['family_counts']=dict(family_counts);state['source_stalls']=dict(source_stalls)
    state['status']='ok';state['phase']='done'
    state.setdefault('stop_reason','sources_exhausted' if not streams else 'budget')
    state['search_seconds']=time.monotonic()-start-state['search_started_seconds']
    save()


def main():
    req=read(sys.argv[1]);out=Path(req['out'])
    try:run(req)
    except Exception as exc:
        write(out/'fatal.json',{'error':str(exc),'traceback':traceback.format_exc()});raise

if __name__=='__main__':main()
