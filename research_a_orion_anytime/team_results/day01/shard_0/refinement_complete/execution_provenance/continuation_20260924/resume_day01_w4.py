"""User-authorized day01 continuation. Original solver/evaluator stay unchanged."""
import argparse
import copy
import ctypes
import json
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(r'D:\桌面\model_competition_orion_anytime')
sys.path.insert(0, str(REPO))
from research_a_orion_anytime.campaign import make_job, list_bound, index_write, required
from research_a_orion_anytime.supervisor import run_job, locate_official
from research_a_orion_anytime.solver import read
from research_a_orion_anytime.worker import atomic_json
from research_a_orion_anytime.transfer import rewrite
from research_a_orion_anytime.reporting import collect


def memory():
    class Memory(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [(n, ctypes.c_ulonglong) for n in
            ['total', 'avail', 'total_page', 'avail_page', 'total_virtual', 'avail_virtual', 'avail_extended']]
    m = Memory(); m.length = ctypes.sizeof(m)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        raise ctypes.WinError()
    return dict(available_physical_gib=m.avail/2**30, available_commit_gib=m.avail_page/2**30)


def summaries(root):
    return [read(p) for p in sorted(root.glob('*/summary.json'))] if root.exists() else []


def carry_summary(folder, req, state, elapsed):
    """Finalize only an exhausted interrupted allowance; never invent evaluation results."""
    meta = state.get('incumbent')
    s = dict(case=req['case'], q=req['q'], n=req['n'], job=str(folder),
             job_identity=req['job_identity'], signature=req['identity'],
             status='ok' if meta else 'interrupted_without_incumbent',
             policy=dict(seconds=req['seconds'], max_evaluations=req['max_evaluations']),
             process_seconds=elapsed, total_job_seconds=elapsed, hard_timeout=False,
             stopped='user_switch_allowance_exhausted', evaluations=state.get('evaluations', 0),
             features=state.get('graph_features'), construction_seconds=state.get('construction_seconds'),
             switch_interrupted=True)
    if meta:
        result=read(folder/meta['result_file'])
        if result['status']!='ok' or not result['audit']['ok']:
            raise ValueError('Interrupted checkpoint is not officially valid')
        raw=result['official_result']
        s.update(makespan=meta['makespan'], plan_hash=meta['plan_hash'],
                 plan=str(folder/meta['plan_file']), result=str(folder/meta['result_file']),
                 certificate=result['audit']['certificate'],
                 cache_hit_rate=raw.get('cache_stats',{}).get('hit_rate'), **raw['data_movement_bytes'])
    atomic_json(folder/'summary.json', s)
    return s


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',required=True); p.add_argument('--out',required=True)
    p.add_argument('--switch-record',required=True); p.add_argument('--workers',type=int,choices=[4],default=4)
    a=p.parse_args(); source=Path(a.source).resolve(); out=Path(a.out).resolve()
    if out.exists(): raise ValueError('Continuation needs a new, unused output root')
    switch=read(a.switch_record); stop=float(switch['stop_epoch'])
    original=read(source/'campaign.json'); args=original['identity']['args']
    deadline=original['deadline_epoch']; reserve=args['verify_reserve_seconds']
    if time.time()>=deadline-reserve: raise TimeoutError('Original computation deadline passed')
    if (source/'pairs').exists() or (source/'final_index.json').exists():
        raise ValueError('This handoff is only for an unfinished refinement phase')
    mem=memory()
    if mem['available_physical_gib']<4 or mem['available_commit_gib']<1:
        raise MemoryError(f'Insufficient launch headroom: {mem}')
    shutil.copytree(source,out,ignore=shutil.ignore_patterns('*.tmp'))
    for f in out.rglob('*.json'):
        if f.name.endswith('_plan.json') or f.name=='current_plan.json': continue
        val=json.loads(f.read_text(encoding='utf-8-sig'))
        changed=rewrite(val,str(source),out.as_posix())
        if changed!=val: atomic_json(f,changed)
    manifest=read(out/'campaign.json')
    manifest['prior_execution_overrides']=manifest.get('prior_execution_overrides',[])+([manifest['execution_override']] if 'execution_override' in manifest else [])
    manifest['execution_override']=dict(workers=4, source_root=str(source), switch_epoch=stop,
        user_authorized_mixed_worker_results=True, solver_source_changed=False,
        note='identity.args records original campaign; execution_override records continuation')
    atomic_json(out/'campaign.json',manifest)
    atomic_json(out/'continuation_receipt.json',dict(**manifest['execution_override'], memory_at_launch=mem,
        deadline_epoch=deadline, interruption_policy='Debit elapsed wall allowance and attempted evaluations; keep both segments'))
    official,config=locate_official(args['official'])
    gate=read(args['gate'])
    if not gate['accepted']: raise ValueError('Original pilot was not accepted')
    admission=read(out/'capacity_admission.json'); policy=read(out/'refinement_policy.json')
    sizes=admission['sizes']; pair_caps={tuple(r['key']):r['seconds'] for r in admission['pair_caps']}
    expected=required([f'case_{i:03d}' for i in range(1,101) if (i-1)%args['shards']==args['shard_index']])
    selected={}
    for stage in ['coverage','coverage_retry']:
        for r in summaries(out/stage):
            key=(r['case'],r['q'],r['n'])
            if stage=='coverage' or r['status']=='ok': selected[key]=r
    if set(selected)!=set(expected) or any(r['status']!='ok' for r in selected.values()):
        raise ValueError('Expected complete, valid coverage before this continuation')
    good=[r for r in selected.values() if r['q']>0]
    good.sort(key=lambda r:(-(r['makespan']/max(1,r['certificate']['global_lower'])-1),r['case'],r['q'],r['n']))
    planned=[r for r in good if r['certificate']['approximation_ratio_upper']>1+args['gap_tolerance']]
    if len(planned)!=policy['jobs']: raise ValueError('Original refinement job list cannot be reconstructed exactly')
    # Keep the original serial reserve and refinement cutoff, even after adding a worker.
    refinement_deadline=deadline-reserve-list_bound(pair_caps.values(),args['workers'])
    jobs=[]; split={}; completed_before=0
    for base in planned:
        c,q,n=base['case'],base['q'],base['n']; folder=out/'refinement'/f'{c}_q{q}_n{n}'
        cap=policy['uniform_base_seconds']*(2 if sizes[c]>8000 else 1)
        if (folder/'summary.json').exists(): completed_before+=1; continue
        seed=base['job']; allowance=cap; calls=256
        if (folder/'request.json').exists():
            req=read(folder/'request.json')
            elapsed=max(0,stop-(source/'refinement'/folder.name/'request.json').stat().st_mtime)
            state=read(folder/'progress.json') if (folder/'progress.json').exists() else dict(attempts=[],incumbent=None)
            used_calls=max([state.get('evaluations',0)]+[x.get('index',0) for x in state['attempts']])
            allowance=max(0,cap-elapsed); calls=max(0,256-used_calls)
            for attempt in state['attempts']:
                if attempt['status']=='running':
                    attempt.update(status='interrupted_by_user_switch',completed_seconds=elapsed)
            state['stopped']='user_authorized_worker_switch'
            atomic_json(folder/'progress.json',state)
            if allowance<=0 or calls<=0:
                carry_summary(folder,req,state,elapsed)
                completed_before+=1
                continue
            prior=out/'refinement_interrupted'/folder.name
            prior.parent.mkdir(parents=True,exist_ok=True); folder.rename(prior)
            if state.get('incumbent'): seed=str(prior)
            split[str(folder)]=dict(prior=str(prior),elapsed=elapsed,used_calls=used_calls,
                original_seconds=cap,remaining_seconds=allowance,remaining_calls=calls)
        jobs.append(make_job(official,config,out/'refinement',c,q,n,allowance,calls,
            refinement_deadline,seed_job=seed,gap_tolerance=args['gap_tolerance']))
    bound=list_bound([j['seconds'] for j in jobs],a.workers)+list_bound(pair_caps.values(),a.workers)+reserve
    capacity=dict(accepted=bound<=deadline-time.time(), workers=a.workers, remaining_jobs=len(jobs),
        preserved_refinement=completed_before, remaining_capped_wall_bound=bound,
        available_seconds=deadline-time.time(), original_refinement_deadline_epoch=refinement_deadline,
        deadline_epoch=deadline, original_budgets_preserved=True)
    atomic_json(out/'continuation_capacity_admission.json',capacity)
    if not capacity['accepted']: raise RuntimeError(f'Remaining capacity refused: {capacity}')
    atomic_json(out/'continuation_plan.json',dict(capacity=capacity, interrupted_segments=split,
        remaining=[dict(case=Path(j['graph']).stem,q=j['q'],n=j['n'],seconds=j['seconds'],calls=j['max_evaluations']) for j in jobs]))
    print(json.dumps(capacity),flush=True)

    def execute(j):
        s=run_job(**j); part=split.get(str(j['folder']))
        if part and 'job' in s:
            folder=Path(s['job']); old=read(Path(part['prior'])/'progress.json'); new=read(folder/'progress.json')
            tail=copy.deepcopy(new['attempts'])
            for item in tail:
                if 'index' in item:item['index']+=part['used_calls']
                for field in ('started_seconds','completed_seconds'):
                    if field in item:item[field]+=part['elapsed']
            new['attempts']=old['attempts']+tail
            new['evaluations']=part['used_calls']+new.get('evaluations',0)
            new['continuation_segments']=part
            atomic_json(folder/'progress.json',new)
            s['continuation_segments']=part; s['evaluations']=new['evaluations']
            s['process_seconds']+=part['elapsed']; s['total_job_seconds']+=part['elapsed']
            s['official_eval_seconds']=sum(x.get('eval_seconds',0) for x in new['attempts'])
            valid=[x for x in new['attempts'] if x['status']=='ok']
            s['completed_evaluations']=len(valid)
            s['first_valid_seconds']=min((x['completed_seconds'] for x in valid),default=None)
            s['prefix3_makespan']=min((x['makespan'] for x in valid if x.get('index',999)<=3),default=None)
            atomic_json(folder/'summary.json',s)
        return s

    def dispatch(batch_jobs,stage):
        atomic_json(out/'continuation_status.json',dict(stage=stage,status='running',workers=a.workers,total=len(batch_jobs),completed=0))
        rows=[]
        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            futures={pool.submit(execute,j):j for j in batch_jobs}
            for future in as_completed(futures):
                s=future.result(); rows.append(s)
                print(f"{stage} {s['case']} q{s['q']} n{s['n']} {s['status']} T={s.get('makespan')} wall={s.get('process_seconds')}",flush=True)
                atomic_json(out/'continuation_status.json',dict(stage=stage,status='running',workers=a.workers,total=len(batch_jobs),completed=len(rows)))
        return rows

    dispatch(jobs,'refinement')
    for r in summaries(out/'refinement'):
        key=(r['case'],r['q'],r['n'])
        if r['status']=='ok':
            old=selected[key]
            if (r['makespan'],r['added_copy_bytes'])>(old['makespan'],old['added_copy_bytes']):
                raise ValueError('Refinement regressed from the original coverage seed')
            r['coverage_seconds']=old.get('total_job_seconds',old['process_seconds'])
            r['end_to_end_solve_seconds']=r.get('total_job_seconds',r['process_seconds'])+r['coverage_seconds']
            atomic_json(Path(r['job'])/'summary.json',r); selected[key]=r
    run_policy=dict(algorithm='ORION-A',shards=args['shards'],shard_index=args['shard_index'],
        deadline_epoch=deadline,refinement_seconds=policy['uniform_base_seconds'],execution_override=manifest['execution_override'])
    index_write(out/'phase_index.json',selected,{},expected,{**run_policy,'stage':'refinement_complete','pairs_pending':True})
    atomic_json(out/'refinement_complete.json',dict(completed_epoch=time.time(),records=len(summaries(out/'refinement')),workers_after_switch=4))
    pair_jobs=[make_job(official,config,out/'pairs',c,2,n,pair_caps[c,q,n],1,deadline-reserve,fixed_plan=r['plan'])
        for (c,q,n),r in selected.items() if q==3 and r['status']=='ok']
    pairs={(r['case'],3,r['n']):r for r in dispatch(pair_jobs,'pairs')}
    index_write(out/'final_index.json',selected,pairs,expected,run_policy)
    atomic_json(out/'continuation_status.json',dict(stage='verification',status='running',workers=4))
    report=collect(out/'final_index.json',out/'final_report',official,verify=True,require_complete=False)
    atomic_json(out/'formal_status.json',dict(status='shard_or_incomplete',report=report))
    atomic_json(out/'continuation_status.json',dict(stage='finished',status='complete' if not report['failures_or_missing'] else 'incomplete',workers=4))


if __name__=='__main__':
    main()
