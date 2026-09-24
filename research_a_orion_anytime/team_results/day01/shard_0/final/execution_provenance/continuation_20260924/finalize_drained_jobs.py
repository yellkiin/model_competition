"""Finalize drained solver checkpoints without re-evaluation or extra search."""
import sys
from pathlib import Path
sys.path.insert(0,r'D:\桌面\model_competition_orion_anytime')
from research_a_orion_anytime.solver import read
from research_a_orion_anytime.worker import atomic_json

record=read(sys.argv[1])
for item in record['jobs']:
    folder=Path(item['folder']); req=read(folder/'request.json')
    if (folder/'summary.json').exists():raise ValueError('Drain job already finalized; do not overwrite')
    state=read(folder/'progress.json') if (folder/'progress.json').exists() else dict(attempts=[],incumbent=None)
    duration=item['process_seconds']; timed_out=item['hard_timeout']
    if timed_out:
        for attempt in state['attempts']:
            if attempt['status']=='running':attempt.update(status='interrupted_by_budget',completed_seconds=duration)
        state.update(stopped='hard_job_deadline',status='ok' if state.get('incumbent') else 'deadline_without_incumbent')
        atomic_json(folder/'progress.json',state)
    meta=state.get('incumbent')
    policy={k:req[k] for k in ['q','n','seconds','max_evaluations','strategy','gap_tolerance']}
    policy.update(flags={},cache_overrides=req.get('cache_overrides'))
    s=dict(case=req['case'],q=req['q'],n=req['n'],job=str(folder),job_identity=req['job_identity'],
        signature=req['identity'],policy=policy,status='ok' if meta else state.get('status','worker_failed'),
        hard_timeout=timed_out,process_seconds=duration,total_job_seconds=duration,
        construction_seconds=state.get('construction_seconds'),evaluations=state.get('evaluations',0),
        exit_code=item.get('exit_code'),stopped=state.get('stopped'),features=state.get('graph_features'),
        graceful_worker_handoff=True,timing_note='Process start-to-observed-exit measured by drain supervisor; original parent paused')
    if meta:
        result=read(folder/meta['result_file']);raw=result['official_result']
        if result['status']!='ok' or not result['audit']['ok']:raise ValueError('Invalid drained incumbent checkpoint')
        s.update(makespan=meta['makespan'],plan_hash=meta['plan_hash'],plan=str(folder/meta['plan_file']),
            result=str(folder/meta['result_file']),certificate=result['audit']['certificate'],
            cache_hit_rate=raw.get('cache_stats',{}).get('hit_rate'),**raw['data_movement_bytes'])
        completed=[x for x in state['attempts'] if x['status']=='ok']
        s['prefix3_makespan']=min((x['makespan'] for x in completed if x.get('index',999)<=3),default=None)
        s['completed_evaluations']=len(completed)
        s['official_eval_seconds']=sum(x.get('eval_seconds',0) for x in state['attempts'])
        s['first_valid_seconds']=min((x['completed_seconds'] for x in completed),default=None)
        s['expanded_construction_seconds']=state.get('expanded_construction_seconds',0)
    if (folder/'worker_error.json').exists():s['worker_error']=read(folder/'worker_error.json')
    atomic_json(folder/'summary.json',s)
    print(req['case'],req['q'],req['n'],s['status'],s.get('makespan'),'drained at original time cap',timed_out,flush=True)
