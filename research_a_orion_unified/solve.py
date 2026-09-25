"""One isolated scheduling job with full official evaluation and a shared incumbent."""
from __future__ import annotations
from collections import Counter
from copy import deepcopy
from pathlib import Path
import sys, time, traceback
from . import VERSION
from .io import ROOT, read, write, plan_key, score, plan_path, set_write_deadline
from . import candidates
from .sources import Sources
from .selector import Selector
from research_a_orion_unified.vendor.orion.worker import audit
from research_a_orion_unified.vendor.orion.engine import OfficialSession, model_config
from research_a_orion_unified.vendor.orion.core import constructors, one_core, bounds, neighbours
from .vendor.structure.plugin import pad_plan


def run(request):
    out = Path(request['out']).resolve(); out.mkdir(parents=True,exist_ok=True)
    runtime=read(out/'runtime.json') if (out/'runtime.json').is_file() else {}
    offset=max(0.,time.time()-runtime.get('launched_epoch',time.time()))
    start=time.monotonic()-offset; q,n=request['q'],request['n']
    cap=float(request.get('job_seconds',request.get('seconds',600)))
    if not 0<cap<=600:raise ValueError('Per configuration wall cap must be in (0,600] seconds')
    total_deadline=start+cap-.20
    set_write_deadline(total_deadline)
    pair_reserve=min(cap*.2,max(2.,request.get('pair_reserve_seconds',60.))) if q==3 and request.get('pair_inline') else 0.
    deadline=total_deadline-pair_reserve
    request={**request,'alternatives':list(request.get('alternatives',[]))+runtime.get('dynamic_alternatives',[])}
    state = {'version':VERSION,'case':request['case'],'q':q,'n':n,'mode':request.get('mode','warm'),
             'components':request['components'],'fifo_module':request.get('fifo_module'),
             'status':'running','phase':'seed_replay','attempts':[], 'generator_notes':[],
             'family_counts':{},'candidate_generation_seconds':0.,'official_eval_seconds':0.,
             'baseline':None,'incumbent':None,'raw_candidate_best':None,'improvement_events':[],
             'phase_events':[], 'io_seconds':0.,'construction_seconds':0., 'job_seconds':cap,'cache_overrides':request.get('cache_overrides'),
             'launched_epoch':runtime.get('launched_epoch'), 'time_scope':'process start through persisted result; includes seed replay'}
    def persist(path,value):
        before=time.monotonic();write(path,value)
        state['io_seconds']+=time.monotonic()-before
    last_saved=0.
    def save(force=False):
        nonlocal last_saved
        now=time.monotonic()
        if not force and now-last_saved<.5:return
        last_saved=now
        state['elapsed_seconds'] = time.monotonic()-start
        persist(out/'progress.json',state)
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
        persist(out/pn,p)
        row={'index':counter,'name':name,'family':family,'status':'running',
             'started_seconds':time.monotonic()-start,'plan_file':pn,'result_file':rn,
             'source':source,'generation_seconds':generation_seconds,'evidence':evidence,'time_source':'local',
             'parent_epoch':context['epoch'], 'parent_makespan':state['incumbent']['makespan'] if state['incumbent'] else None}
        state['attempts'].append(row);family_counts[family]+=1
        state['family_counts']=dict(family_counts);phase('official_evaluation',source,name);save()
        t=time.monotonic()
        try:
            r=session.evaluate(p,q,request.get('cache_overrides')); wall=time.monotonic()-t
            state['official_eval_seconds']+=r.get('eval_seconds',wall)
            if time.monotonic()>=deadline:
                persist(out/rn,r)
                row.update(status='completed_after_search_limit',completed_seconds=time.monotonic()-start,
                           eval_seconds=r.get('eval_seconds'),eval_and_audit_seconds=wall,result_retained=True)
                save();return row
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
                    persist(out/rn,r);meta['ready_seconds']=time.monotonic()-start
                    if time.monotonic()>=deadline:
                        row.update(status='persisted_after_search_limit',accepted=False,completed_seconds=meta['ready_seconds'])
                        save(force=True);return row
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
                row['improved_makespan']=old is None or tval<old['makespan']
                row['gain_fraction']=max(0.,1-tval/old['makespan']) if old and old['makespan'] else 0.
                if better:
                    state['incumbent']=meta
                    context.update(plan=p,official_result=r['official_result'],epoch=context['epoch']+1)
                    state['improvement_events'].append({'elapsed_seconds':meta['ready_seconds'],
                        'makespan':tval,'added_copy_bytes':bytes_,'family':family,'source':source,'name':name,'evaluation':counter})
                    persist(out/f'checkpoints/accepted_{counter:06d}.json',state)
                    save(force=True)
            else:
                persist(out/rn,r);row['result_retained']=True
                row['audit_errors']=r.get('audit',{}).get('errors')
        except Exception as exc:
            row.update(status='error',error=str(exc),traceback=traceback.format_exc())
        row['completed_seconds']=time.monotonic()-start;save()
        return row

    seed = request.get('seed_plan')
    if request.get('fixed_plan'):
        p=read(request['fixed_plan']);evaluate(p,'same_plan_no_l2','pair',True)
        state.update(status='ok' if state['incumbent'] else 'failed',phase='done');save(force=True);return
    if seed:
        p=read(seed)
        if len(p['core_schedules'])!=n: raise ValueError('Baseline seed has wrong target core count')
        stored=request.get('seed_response')
        if stored and request.get('reuse_verified_response') and not request.get('cache_overrides'):
            response=read(stored)
            raw=response['official_result']
            if response.get('status')!='ok' or response.get('audit',{}).get('ok') is not True:
                raise ValueError('Stored seed lacks completed official validation')
            if raw['num_cores']!=n:raise ValueError('Seed core count differs')
            if raw.get('scene')!=('A' if q in (0,1) else 'B'):raise ValueError('Seed scene differs')
            if raw['bandwidth_bytes_per_cycle']!=cfg.bandwidth or raw['capacity_bytes']!=cfg.capacity:
                raise ValueError('Seed hardware configuration differs')
            if q==3 and (raw['cache_capacity_bytes']!=cfg.cache_capacity or raw['cache_bandwidth_bytes_per_cycle']!=cfg.cache_bandwidth):
                raise ValueError('Seed FIFO configuration differs')
            if (q==3)!=(raw.get('problem')==3):raise ValueError('Seed problem/cache semantics differ')
            checked=audit(g,p,raw,q,cfg)
            if not checked['ok']:raise ValueError(str(checked['errors']))
            persist(out/'seed_plan.json',p);persist(out/'seed_result.json.gz',response)
            meta={'makespan':raw['makespan'],'added_copy_bytes':raw['data_movement_bytes']['added_copy_bytes'],
                  'name':'retained_official_reference','family':'seed','plan_file':'seed_plan.json',
                  'result_file':'seed_result.json.gz','ready_seconds':time.monotonic()-start,'certificate':checked['certificate']}
            state['baseline']=dict(meta);state['incumbent']=meta
            state['seed_origin']='retained_original_response_audited_no_resimulation'
            context.update(plan=p,official_result=raw,epoch=1);seen.add(plan_key(p))
            state['improvement_events'].append({'elapsed_seconds':meta['ready_seconds'],'makespan':raw['makespan'],
                'added_copy_bytes':meta['added_copy_bytes'],'family':'seed','source':'seed','name':meta['name'],'evaluation':0})
            save()
        else:evaluate(p,'replayed_reference','seed',True)
    elif q==0:
        evaluate(one_core(g,1),'original_singlecore','seed',True)
    else:
        # Preserve the original cheap coverage before competing sources consume a
        # short cold budget. All three calls still count against the SAME cap.
        before=time.monotonic()
        initial=list(constructors(g,n,cfg,q,diagnostics=state['generator_notes']))
        built=time.monotonic()-before;state['construction_seconds']+=built;state['candidate_generation_seconds']+=built
        coverage_calls=0;coverage_limit=request.get('cold_coverage_calls',3)
        coverage_deadline=min(deadline,start+max(2.,cap*.25))
        while initial and coverage_calls<coverage_limit and time.monotonic()<deadline:
            if state['incumbent'] and time.monotonic()>=coverage_deadline:break
            initial.sort(key=lambda c:(c['proxy'].get('score',0),c['name']))
            c=initial.pop(0)
            if plan_key(c['plan']) in seen:continue
            before=counter
            row=evaluate(c['plan'],c['name'],'base/cold_coverage',True,source='b')
            coverage_calls+=counter-before
            if row and row.get('accepted'):
                before=time.monotonic()
                initial.extend(neighbours(g,context['plan'],cfg,q,context['official_result'],limit=12))
                built=time.monotonic()-before;state['construction_seconds']+=built;state['candidate_generation_seconds']+=built
        state['cold_coverage_calls']=coverage_calls
    if state['incumbent'] is None:
        state.update(status='failed',phase='done',reason='no_valid_initial_plan');save(force=True);return
    if request.get('reference_makespan') is not None and seed:
        state['reference_matches']=state['baseline']['makespan']==request['reference_makespan']
        if not state['reference_matches']:
            state.update(status='reference_mismatch',phase='done');save(force=True);return
    if q==0:
        state.update(status='ok',phase='done');save(force=True);return
    for alt in request.get('baseline_alternatives',[]):
        if time.monotonic()>=deadline:break
        p=read(alt['path'])
        if len(p['core_schedules'])!=n:raise ValueError('Extra baseline target core count differs')
        evaluate(p,alt.get('name','available_track_seed'),'seed/extra',True)
    state['seed_replay_seconds']=time.monotonic()-start
    if state['global_lower'] and 1-state['global_lower']/state['incumbent']['makespan']<=request.get('stop_gap',.0025):
        state.update(stop_reason='certified_relative_gap_before_search')
        if not (q==3 and request.get('pair_inline')):
            state.update(status='ok');phase('done');save(force=True);return
        request={**request,'max_evaluations':counter}

    phase('search');state['search_started_seconds']=time.monotonic()-start
    state['search_deadline_seconds']=deadline-start;state['search_deadline_epoch']=time.time()+max(0,deadline-time.monotonic())
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
    manager=Sources(g,n,cfg,q,context,state['generator_notes'],deadline,active)
    source_stalls=Counter();stall=0;last_gain=time.monotonic()-start
    selector=Selector()
    max_calls=request.get('max_evaluations',2048)
    while time.monotonic()<deadline and counter<max_calls:
        available=manager.available()
        if not available:break
        elapsed=time.monotonic()-start
        source,selection=selector.choose(available,state['attempts'],manager.generation_counts,elapsed,cap,deadline-time.monotonic(),last_gain)
        if source is None:
            state['stop_reason']=selection;break
        state['optimization_stage']='source_intake' if selection=='source_warmup' else 'joint_refinement'
        phase('candidate_generation',source);save();t=time.monotonic()
        try:c=manager.next(source)
        except Exception as exc:
            generation=time.monotonic()-t;state['candidate_generation_seconds']+=generation
            state['generator_notes'].append({'source':source,'status':'generation_error','error':str(exc),'traceback':traceback.format_exc()})
            manager.finished[source]=context['epoch'];save();continue
        generation=time.monotonic()-t;state['candidate_generation_seconds']+=generation
        if c is None:continue
        if c.get('parent_epoch') is None:state['construction_seconds']+=generation
        if time.monotonic()>=deadline:break
        key=plan_key(c['plan'])
        if key in seen:
            state['duplicate_candidates']=state.get('duplicate_candidates',0)+1
            state['duplicate_generation_seconds']=state.get('duplicate_generation_seconds',0.)+generation
            continue
        if c['bounds']['candidate_lower']>state['incumbent']['makespan']:
            seen.add(key);state['generator_notes'].append({'source':source,'status':'certified_pruned','name':c['name']});continue
        ev={'parent_epoch':c.get('parent_epoch'),'selection':selection,**(c.get('evidence') or {})}
        row=evaluate(c['plan'],c['name'],c['family'],source=source,generation_seconds=generation,evidence=ev)
        if row and row.get('improved_makespan'):
            last_gain=time.monotonic()-start;stall=0;source_stalls.clear()
        elif row:
            stall+=1;source_stalls[source]+=1
        if state['global_lower'] and 1-state['global_lower']/state['incumbent']['makespan']<=request.get('stop_gap',.0025):
            state['stop_reason']='certified_relative_gap';break
        available=manager.available()
        if time.monotonic()-start-last_gain>=request.get('stall_seconds',60.) and stall>=request.get('stall_calls',64) and all(source_stalls[x]>=request.get('stall_per_source',16) for x in available):
            state['stop_reason']='all_sources_nonimproving';break
    state['generation_counts']=manager.generation_counts
    state['memory_shape']=manager.static_features
    state['last_makespan_improvement_seconds']=last_gain
    streams={s:None for s in manager.available()}
    state['family_counts']=dict(family_counts);state['source_stalls']=dict(source_stalls)
    state['status']='ok'
    state.setdefault('stop_reason','sources_exhausted' if not streams else 'budget')
    state['search_seconds']=time.monotonic()-start-state['search_started_seconds']
    if q==3 and request.get('pair_inline'):
        phase('same_plan_no_l2');state['pair_status']='running';save()
        before=time.monotonic()
        try:
            paired=session.evaluate(context['plan'],2)
            state['pair_seconds']=time.monotonic()-before
            state['pair_status']=paired['status']
            persist(out/'same_plan_no_l2_plan.json',context['plan'])
            persist(out/'same_plan_no_l2_result.json.gz',paired)
            state['pair_ready_seconds']=time.monotonic()-start
            if time.monotonic()>total_deadline:state['pair_status']='completed_after_wall_limit'
            if paired['status']=='ok':state['no_l2_makespan']=paired['official_result']['makespan']
        except Exception as exc:
            state['pair_status']='error';state['pair_seconds']=time.monotonic()-before
            state['pair_error']={'error':str(exc),'traceback':traceback.format_exc()}
        save()
    phase('done');save(force=True)


def main():
    req=read(sys.argv[1]);out=Path(req['out'])
    try:run(req)
    except Exception as exc:
        set_write_deadline(None)
        write(out/'fatal.json',{'error':str(exc),'traceback':traceback.format_exc()});raise

if __name__=='__main__':main()
