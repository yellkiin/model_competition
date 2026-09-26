"""One bounded Q3-only supplement; the parent controls the process lifetime."""
from __future__ import annotations
from pathlib import Path
import sys,time,traceback
from .common import read,write,plan_key,score,engine
from .proposals import generate

def run(req):
    out=Path(req['out']);out.mkdir(parents=True,exist_ok=True)
    start=time.monotonic()-max(0,time.time()-req.get('launch_epoch',time.time()));deadline=start+req['seconds'];Session,core,auditor=engine(req['backend'])
    state={'case':req['case'],'q':3,'n':req['n'],'status':'running','phase':'parse','attempts':[],
           'events':[],'notes':[],'baseline':None,'best':None,'selected':None,'pair':None,
           'seconds_limit':req['seconds'],'min_gain':req['min_gain'],'method':'selective_l2_overlay_v1',
           'backend':req['backend'],'base_method':'Trident #38 retained; only Q3 output supplemented'}
    def save():state['elapsed_seconds']=time.monotonic()-start;write(out/'progress.json',state)
    save();session=Session(req['official'],req['graph'],req['config']);g,cfg=session.graph,session.cfg
    baseline_plan=read(req['plan']);n=req['n']
    if len(baseline_plan['core_schedules'])!=n:raise ValueError('Q3 baseline core count differs')
    context={'plan':baseline_plan};seen=set();index=0;recent_cost=[]
    def search_deadline():
        reserve=max(2.,min(req['seconds']*.35,1.5*max(recent_cost[-3:],default=1.)+1.))
        return deadline-reserve
    def checked_saved(path,p,q):
        r=read(path);raw=r.get('official_result',r)
        if raw.get('makespan') is None:raise ValueError('Saved file has no official result')
        if q==3 and raw.get('problem')!=3:raise ValueError('Saved Q3 result is not problem 3')
        if q==2 and (raw.get('scene')!='B' or raw.get('problem')==3):raise ValueError('Saved no-L2 is not an un-cached B evaluation')
        expected={'num_cores':n,'bandwidth_bytes_per_cycle':cfg.bandwidth,'capacity_bytes':cfg.capacity,'cross_core_copy_delay_cycles':cfg.cross_b}
        if q==3:expected.update(cache_capacity_bytes=cfg.cache_capacity,cache_bandwidth_bytes_per_cycle=cfg.cache_bandwidth)
        if any(raw.get(k)!=v for k,v in expected.items()):raise ValueError('Saved result uses different official settings')
        a=auditor.audit(g,p,raw,q,cfg)
        if not a.get('ok') or a.get('errors'):raise ValueError('Saved response does not verify against this plan')
        return {'status':'ok','official_result':raw,'audit':a,'eval_seconds':0,'reused_saved_response':True}
    def eval3(p,name,baseline=False,saved=None):
        nonlocal index
        if time.monotonic()>=(deadline-.5 if baseline else search_deadline()) or (not baseline and index>=req['max_calls']):return None
        signature=plan_key(p)
        if signature in seen:return None
        seen.add(signature);index+=1
        row={'index':index,'name':name,'status':'running','start_seconds':time.monotonic()-start}
        state['attempts'].append(row);state['phase']=name;save();t=time.monotonic()
        try:
            core.plan_view(g,p)
            r=checked_saved(saved,p,3) if saved else session.evaluate(p,3)
            if r.get('status')!='ok' or r.get('audit',{}).get('ok') is not True or r['audit'].get('errors'):
                raise ValueError('Official evaluation/audit did not pass')
            if not saved:recent_cost.append(time.monotonic()-t)
            value,traffic=score(r)
            if baseline and req.get('old_makespan') is not None and value!=req['old_makespan']:raise ValueError('Baseline metadata differs from its actual Q3 response')
            row.update(status='ok',makespan=value,added_copy_bytes=traffic,
                   eval_seconds=r.get('eval_seconds'),reused=bool(saved))
            old=state['best'];better=old is None or (value,traffic)<(old['makespan'],old['added_copy_bytes'])
            row['accepted_for_search']=better
            if baseline or better:
                pn=f'accepted/{index:03d}_plan.json';rn=f'accepted/{index:03d}_response.json.gz'
                write(out/pn,p);write(out/rn,r)
                if time.monotonic()>=deadline:
                    row['status']='saved_after_budget_not_selected';return row
                meta={'makespan':value,'added_copy_bytes':traffic,'plan':pn,'response':rn,'name':name,
                      'ready_seconds':time.monotonic()-start,'certificate':r['audit'].get('certificate')}
                if baseline:state['baseline']=dict(meta)
                if better:
                    state['best']=meta;context['plan']=p
                    state['events'].append({'seconds':meta['ready_seconds'],'makespan':value,'added_copy_bytes':traffic,'name':name})
                save()
        except Exception as exc:row.update(status='error',error=str(exc),traceback=traceback.format_exc())
        finally:row['wall_seconds']=time.monotonic()-t;row['end_seconds']=time.monotonic()-start;save()
        return row
    eval3(baseline_plan,'base_Q3',True,req.get('q3_result'))
    if not state['baseline']:raise RuntimeError('No verified old Q3 result; no replacement published')
    if req.get('old_makespan') is not None and state['baseline']['makespan']!=req['old_makespan']:
        raise ValueError('Saved baseline scalar differs from actual Q3 result; select the correct old final plan')
    original=state['baseline']['makespan'];state['old_q2_best']=req.get('old_q2_best')
    # Stored studies are candidate banks, not assumed winners against #38.
    for item in req.get('published',[]):
        if time.monotonic()>=search_deadline() or index>=req['max_calls']:break
        recorded=item.get('makespan')
        if recorded is not None and recorded>state['best']['makespan']*(1-req['min_gain']):
            state['notes'].append({'name':item['name'],'action':'skip_published_not_materially_better','reported_cycles':recorded});continue
        eval3(read(item['path']),item['name'])
    lower=core.bounds(g,cfg,n,3)['global_lower'];state['global_lower']=lower
    # V1 weak-unit policies were useful on strong starting plans. The poorly
    # performing topo4/shared/stagger and v2/v3 are deliberately not scheduled.
    if 1-lower/state['best']['makespan']>req['min_gain'] and req['search'] and index<req['max_calls']:
        mode='combined' if req.get('explore_portfolio') else 'weak'
        parent=context['plan']
        generation_start=time.monotonic()
        for name,p in generate(g,n,cfg,core,parent,search_deadline(),mode):
            if time.monotonic()>=search_deadline() or index>=req['max_calls']:break
            generation_elapsed=time.monotonic()-generation_start
            row=eval3(p,name)
            if row:row['generation_seconds']=generation_elapsed
            generation_start=time.monotonic()
            if index>=req['max_calls']:break
    best=state['best'];gain=1-best['makespan']/original
    # Do not replace a near-identical plan and then spend another Q2 evaluation
    # for a tiny improvement below the explicit user's time-saving threshold.
    changed=plan_key(context['plan'])!=plan_key(baseline_plan) and gain>=req['min_gain']
    state['selected']=best if changed else state['baseline']
    state['changed']=changed;state['raw_improvement_fraction']=gain;state['published_improvement_fraction']=gain if changed else 0.
    chosen=read(out/state['selected']['plan']);write(out/'plan.json',chosen);save()
    # A changed Q3 plan needs one new no-L2 score; unchanged plans can carry their
    # verified existing pair. This is NOT a Q2 optimization run.
    oldpair=req.get('no_l2_result');pairplan=req.get('no_l2_plan')
    state['phase']='same_plan_no_L2';save()
    try:
        if not changed and oldpair and pairplan and plan_key(read(pairplan))==plan_key(chosen):
            pair=checked_saved(oldpair,chosen,2);state['pair_reused']=True;pair_time=0.
        elif (changed or req.get('repair_missing_pairs')) and time.monotonic()<deadline-1:
            pair_start=time.monotonic();pair=session.evaluate(chosen,2);pair_time=time.monotonic()-pair_start;state['pair_reused']=False
        else:pair=None
        if pair:
            if pair.get('status')!='ok' or pair.get('audit',{}).get('ok') is not True or pair['audit'].get('errors'):raise ValueError('Same-plan no-L2 validation failed')
            write(out/'same_plan_no_l2.json.gz',pair);write(out/'same_plan_no_l2_plan.json',chosen)
            state['pair']={'status':'ok','makespan':score(pair)[0],'added_copy_bytes':score(pair)[1],
                           'response':'same_plan_no_l2.json.gz','plan':'same_plan_no_l2_plan.json',
                           'new_evaluation_seconds':pair_time,'reused':state['pair_reused']}
            if time.monotonic()>=deadline:state['pair']['completed_after_call_limit']=True
        else:state['pair']={'status':'pending','reason':'old pair was not supplied/matched; new selected-plan no-L2 not run'}
    except Exception as exc:state['pair']={'status':'error','error':str(exc)}
    state['status']='ok';state['phase']='done';save()

def main():
    req=read(sys.argv[1]);out=Path(req['out'])
    try:run(req)
    except Exception as exc:
        p=out/'progress.json';s=read(p) if p.is_file() else {};s.update(status='error',error=str(exc),traceback=traceback.format_exc());write(p,s);return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
