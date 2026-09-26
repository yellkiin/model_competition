"""Bounded Q3 refinement comparison on real official cases, with exact Q2 pairs."""
from __future__ import annotations
import argparse, collections, json, os, shutil, subprocess, sys, time, traceback
from pathlib import Path
from research_a_orion_unified.io import read, write, plan_key
from research_a_orion_unified.vendor.orion.engine import OfficialSession
from research_a_orion_unified.fifo import proposed_moves
from research_a_orion_unified.resources import Admission, terminate

MODULE = 'research_a_orion_unified.l2_refine_20260926.experiment'


def metrics(response):
    x = response['official_result']
    return dict(makespan=x['makespan'], **x.get('data_movement_bytes', {}),
                cache_hit_rate=x.get('cache_stats', {}).get('hit_rate'),
                cache_hit_bytes=x.get('cache_stats', {}).get('hit_bytes'),
                cache_miss_bytes=x.get('cache_stats', {}).get('miss_bytes'),
                pipe_busy={str(c['core_id']): {p: sum(o['end']-o['start'] for o in c['ops'] if o['pipe']==p)
                    for p in ('PIPE_M','PIPE_V','PIPE_MTE2','PIPE_MTE3')} for c in x['per_core_timeline']})


def worker(req):
    out=Path(req['out']); start=time.monotonic(); deadline=start+req['seconds']
    search_end=deadline-max(15,req['seconds']*.2)
    state=dict(case=req['case'],arm=req['arm'],version=req['version'],status='running',
               attempts=[],errors=[],best=None,baseline=None,epoch=0,seconds=req['seconds'])
    def save():
        state['elapsed_seconds']=time.monotonic()-start;write(out/'progress.json',state)
    save();session=OfficialSession(req['official'],req['graph'],req['config'])
    seed=read(req['seed']);seed_response=None;best_plan=None;best_response=None
    seen=set();counter=0
    def evaluate(plan,q,name,family,evidence=None,generation_seconds=0):
        nonlocal counter
        counter+=1; stem=f'e{counter:04d}'
        write(out/'attempts'/f'{stem}_plan.json',plan)
        row=dict(index=counter,q=q,name=name,family=family,evidence=evidence,
                 generation_seconds=generation_seconds,status='running',started_seconds=time.monotonic()-start,
                 plan_file=f'attempts/{stem}_plan.json',result_file=f'attempts/{stem}_result.json.gz')
        state['attempts'].append(row);state['phase']='official_evaluation';state['evaluation_started_epoch']=time.time();save()
        t=time.monotonic()
        try:
            response=session.evaluate(plan,q)
            write(out/row['result_file'],response)
            row.update(status=response['status'],eval_seconds=response['eval_seconds'],
                       eval_and_save_seconds=time.monotonic()-t,completed_seconds=time.monotonic()-start)
            if response['status']=='ok':row.update(metrics(response))
            else:row['audit_errors']=response.get('audit',{}).get('errors')
            save();return response,row
        except Exception as exc:
            row.update(status='error',error=str(exc),traceback=traceback.format_exc(),completed_seconds=time.monotonic()-start)
            state['errors'].append(row['error']);save();return None,row
    response,row=evaluate(seed,3,'same_strong_seed','seed')
    if not response or response['status']!='ok':
        state.update(status='failed',reason='seed_not_legal');save();write(out/'result.json',state);return
    if row['makespan']!=req['prior_makespan']:
        state.update(status='failed',reason='seed_replay_mismatch',expected=req['prior_makespan']);save();write(out/'result.json',state);return
    seed_response=response;best_response=response;best_plan=seed
    state['baseline']=metrics(response);state['best']={**metrics(response),'name':'same_strong_seed','family':'seed','ready_seconds':time.monotonic()-start}
    write(out/'best_plan.json',seed);write(out/'best_response.json.gz',response);row['accepted']=True;save()
    base_q2,base_q2_row=evaluate(seed,2,'baseline_same_plan_no_l2','pair')
    if base_q2 and base_q2['status']=='ok':
        state['baseline_no_l2']=metrics(base_q2)
    seen.add(plan_key(seed));feedback=[]
    for epoch in range(8):
        if time.monotonic()>=search_end or counter>=req['calls']-1:break
        state['epoch']=epoch;parent_plan=best_plan;parent_raw=best_response['official_result'];changed=False
        if req['arm']=='existing_F':
            stream=proposed_moves(session.graph,5,session.cfg,3,dict(plan=parent_plan,official_result=parent_raw),feedback,search_end)
        else:
            if req['arm']=='L2_hybrid_v3':
                from .candidates_v3 import propose
            elif req['arm']=='L2_local_v2':
                from .candidates_v2 import propose
            else:
                from .candidates import propose
            stream=propose(session.graph,5,session.cfg,parent_plan,parent_raw,search_end)
        while time.monotonic()<search_end and counter<req['calls']-1:
            t=time.monotonic()
            try:c=next(stream)
            except StopIteration:break
            generation=time.monotonic()-t
            p=c['plan'];key=plan_key(p)
            if key in seen:continue
            seen.add(key)
            if time.monotonic()>=search_end:break
            response,row=evaluate(p,3,c['name'],c['family'],c.get('evidence'),generation)
            if response and response['status']=='ok':
                before=(state['best']['makespan'],state['best']['added_copy_bytes'])
                now=(row['makespan'],row['added_copy_bytes']);within=time.monotonic()<search_end
                row['within_search_budget']=within;row['accepted']=now<before and within
                raw=state.get('raw_candidate_best')
                if within and (raw is None or now<(raw['makespan'],raw['added_copy_bytes'])):state['raw_candidate_best']={**metrics(response),'name':c['name'],'family':c['family']}
                if now<before and within:
                    best_plan=p;best_response=response;changed=True
                    write(out/'best_plan.json',p);write(out/'best_response.json.gz',response)
                    state['best']={**metrics(response),'name':c['name'],'family':c['family'],'ready_seconds':time.monotonic()-start}
                    write(out/'checkpoints'/f'accepted_{counter:04d}.json',state['best'])
                save()
        if not changed:break
    state['feedback']=feedback;state['phase']='same_plan_no_l2';save()
    if plan_key(best_plan)==plan_key(seed) and base_q2 and base_q2['status']=='ok':
        paired=base_q2;state['pair_reused_current_baseline']=True
    elif time.monotonic()<deadline-1:
        paired,_=evaluate(best_plan,2,'final_same_plan_no_l2','pair')
    else:paired=None
    if paired and paired['status']=='ok' and time.monotonic()<deadline:
        write(out/'same_plan_no_l2_plan.json',best_plan);write(out/'same_plan_no_l2_response.json.gz',paired)
        state['pair']=metrics(paired);state['same_plan_cache_ratio']=paired['official_result']['makespan']/state['best']['makespan']
        state['pair_status']='ok'
    else:state['pair_status']='missing_or_over_cap'
    state.update(status='complete' if state['pair_status']=='ok' else 'partial',phase='done',official_calls=counter)
    save();write(out/'result.json',state)


def launch(args):
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False)
    official=Path(args.official).resolve(); seeds=Path(args.seed_root).resolve()
    start=time.time();deadline=min(start+args.wall_seconds,args.deadline_epoch or float('inf'))
    jobs=[]
    for pos,case in enumerate(args.cases):
        case='case_'+case.removeprefix('case_').zfill(3)
        old=seeds/'jobs'/f'{case}_q3_n5';s=read(old/'summary.json')
        if s.get('status')!='ok':raise ValueError(f'No legal source plan for {case}')
        seed_dir=out/'seeds'/case;seed_dir.mkdir(parents=True)
        shutil.copyfile(old/'plan.json',seed_dir/'plan.json')
        shutil.copyfile(old/'summary.json',seed_dir/'source_summary.json')
        arms=list(args.arms)
        if pos%2:arms.reverse()
        for arm in arms:
            job=out/'jobs'/f'{case}_{arm}';job.mkdir(parents=True)
            req=dict(case=case,arm=arm,version=args.version,out=str(job),official=str(official),
                graph=str(official/'data'/f'{case}.json'),config=str(official/'data/config.txt'),
                seed=str(seed_dir/'plan.json'),prior_makespan=s['makespan'],seconds=args.seconds,calls=args.calls)
            write(job/'request.json',req);jobs.append(req)
    write(out/'PROTOCOL.json',dict(cases=args.cases,cores=5,question=3,seconds=args.seconds,calls=args.calls,
        workers=args.workers,arms=args.arms,version=args.version,started_epoch=start,deadline_epoch=deadline,baseline='same fixed previously validated Trident plan, fresh Q3 and Q2 replay per arm',
        scope='local Q3 refinement comparison; neither arm is a full SMFB search',
        objective='lexicographic (official makespan, added COPY); hit rate is diagnostic only',
        official_config_unchanged=True,original_baselines_reused=True,full_run_resumed=False))
    snapshot=out/'source_snapshot';snapshot.mkdir()
    for p in Path(__file__).parent.glob('*.py'):shutil.copyfile(p,snapshot/p.name)
    waiting=collections.deque(jobs);active=[];policy=Admission(args.workers,.25);last=0;last_tick={}
    with (out/'resources.jsonl').open('a',encoding='utf8') as resources:
        try:
            while waiting or active:
                now=time.time()
                if now-last>=1:
                    sample=policy.update(active);last=now
                    resources.write(json.dumps(dict(epoch=now,active=len(active),**sample))+'\n');resources.flush()
                while waiting and len(active)<sample['target_workers'] and now<deadline:
                    req=waiting.popleft();folder=Path(req['out']);log=(folder/'worker.log').open('w',encoding='utf8')
                    p=subprocess.Popen([sys.executable,'-X','utf8','-u','-m',MODULE,'--job',str(folder/'request.json')],stdout=log,stderr=subprocess.STDOUT,
                        cwd=Path(__file__).resolve().parents[2],start_new_session=(os.name!='nt'),env={**os.environ,'PYTHONUTF8':'1'})
                    active.append(dict(proc=p,req=req,log=log,start=time.time(),peak_rss=0));last_tick[p.pid]=-1
                for item in active[:]:
                    p=item['proc'];folder=Path(item['req']['out']);elapsed=time.time()-item['start'];reason=None
                    tick=int(elapsed//30)
                    if tick>last_tick[p.pid]:
                        progress=read(folder/'progress.json') if (folder/'progress.json').exists() else {}
                        with (folder/'anytime.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(dict(observed_seconds=elapsed,best=progress.get('best'),completed_calls=sum(a.get('status')!='running' for a in progress.get('attempts',[]))))+'\n')
                        last_tick[p.pid]=tick
                    if time.time()>=deadline:reason='experiment_deadline'
                    elif elapsed>=item['req']['seconds']:reason='job_wall_limit'
                    if reason:terminate(p)
                    if p.poll() is not None:
                        item['log'].close();active.remove(item)
                        write(folder/'execution.json',dict(reason=reason or ('completed' if p.returncode==0 else 'worker_error'),returncode=p.returncode,wall_seconds=elapsed,peak_rss=item['peak_rss']))
                        print(folder.name,reason or p.returncode,round(elapsed,3),flush=True)
                if waiting and time.time()>=deadline:
                    for req in waiting:write(Path(req['out'])/'execution.json',dict(reason='not_started_deadline'))
                    waiting.clear()
                if waiting or active:time.sleep(.25)
        finally:
            for item in active:terminate(item['proc']);item['log'].close()
    write(out/'RUN_EXIT.json',dict(started_epoch=start,ended_epoch=time.time(),wall_seconds=time.time()-start))


def main():
    p=argparse.ArgumentParser();p.add_argument('--job');p.add_argument('--out');p.add_argument('--official');p.add_argument('--seed-root')
    p.add_argument('--cases',nargs='+');p.add_argument('--seconds',type=float,default=120);p.add_argument('--calls',type=int,default=64)
    p.add_argument('--workers',type=int,default=2);p.add_argument('--wall-seconds',type=float,default=1500);p.add_argument('--deadline-epoch',type=float)
    p.add_argument('--arms',nargs='+',choices=['existing_F','L2_window_v1','L2_local_v2','L2_hybrid_v3'],default=['existing_F','L2_window_v1'])
    p.add_argument('--version',default='q3-l2-window-1')
    a=p.parse_args()
    if a.job:
        req=read(a.job)
        try:worker(req)
        except Exception:
            write(Path(req['out'])/'worker_error.json',dict(traceback=traceback.format_exc()));raise
    else:launch(a)
if __name__=='__main__':main()
