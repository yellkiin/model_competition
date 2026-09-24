"""Independent measured adapter. Run as python -m research_a_orion_track_memory.run.

The old arm calls the existing solver unchanged. Memory cold starts use
up to three old evaluations (10 s soft startup admission) then finite repair.
Warm starts reuse a separately costed, officially rechecked seed. No test suite.
"""
from __future__ import annotations
import argparse
from collections import deque
import csv
import gzip
import json
import math
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
import traceback
from research_a_orion_anytime.core import Config, one_core, plan_view
from research_a_orion_anytime.engine import OfficialSession
from research_a_orion_anytime.solver import solve as old_solve
from research_a_orion_anytime.worker import atomic_json
from .plugin import propose, _key, VERSION

ADAPTER_VERSION = 'memory-adapter-1.4'
RUN_MODULE = __spec__.name if __spec__ else 'research_a_orion_track_memory.run'


def read(path):
    p=Path(path)
    if p.suffix=='.gz':
        with gzip.open(p,'rt',encoding='utf-8') as f:return json.load(f)
    return json.loads(p.read_text(encoding='utf-8-sig'))


def save_gz(path, value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp')
    with gzip.open(tmp,'wt',encoding='utf-8',compresslevel=6) as f:
        json.dump(value,f,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    tmp.replace(p)


def csv_write(path, rows):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)


def seed_payload(req, session):
    """Check seed metadata/config; score equality is checked after official replay."""
    sd=Path(req['seed_job']);sp=read(sd/'progress.json');sr=read(sd/'request.json')
    if (sp.get('case'),sp.get('q'),sp.get('n')) != (req['case'],req['q'],req['n']):
        raise ValueError('seed case/q/n mismatch')
    if sp.get('cache_overrides') or sr.get('cache_overrides'):
        raise ValueError('non-default cache seed is not a formal default seed')
    config_path=req.get('seed_config') or sr['config']
    if Config.read(config_path)!=session.cfg:raise ValueError('seed hardware mismatch')
    meta=sp.get('incumbent')
    if not meta:raise ValueError('seed has no feasible incumbent')
    plan=read(sd/meta['plan_file']);plan_view(session.graph,plan)
    original=read(sd/meta['result_file'])
    if original.get('status')!='ok':raise ValueError('seed response was not officially accepted')
    return sp,plan,original


def check_seed_replay(original, replay):
    if replay.get('status')!='ok':raise ValueError('seed official replay failed')
    a,b=original['official_result'],replay['official_result']
    if a['makespan']!=b['makespan'] or a['data_movement_bytes']!=b['data_movement_bytes']:
        raise ValueError('seed score/traffic changed under the current official graph and config')


def fixed_singlecore(req, out, started):
    """Q1/Q2 N=1 uses the original reference, never an optimized Task order."""
    session=OfficialSession(req['official'],req['graph'],req['config'])
    plan=one_core(session.graph,1);r=session.evaluate(plan,0)
    if r['status']!='ok':raise ValueError('official original single-core reference failed')
    save_gz(out/'fixed_result.json.gz',r);atomic_json(out/'fixed_plan.json',plan)
    tm=time.monotonic()-started;raw=r['official_result']
    meta=dict(plan_file='fixed_plan.json',result_file='fixed_result.json.gz',name='fixed_original_singlecore',
        makespan=raw['makespan'],added_copy_bytes=raw['data_movement_bytes']['added_copy_bytes'],
        elapsed_seconds=tm,certificate=r['audit']['certificate'])
    row=dict(name=meta['name'],status='ok',makespan=meta['makespan'],added_copy_bytes=meta['added_copy_bytes'],
        eval_seconds=r['eval_seconds'],available_seconds=tm,completed_seconds=tm)
    atomic_json(out/'progress.json',dict(case=req['case'],q=req['q'],n=1,status='ok',incumbent=meta,
        evaluations=1,attempts=[row],elapsed_seconds=tm,official_eval_seconds=r['eval_seconds'],
        stopped='fixed_original_singlecore',benchmark_role='original_singlecore_reference'))


def memory_worker(req):
    out=Path(req['job']);started=time.monotonic();deadline=started+req['seconds']
    out.mkdir(parents=True,exist_ok=True)
    state=dict(status='initializing',case=req['case'],q=req['q'],n=req['n'],identity=req['identity'],
               method='memory',version=VERSION,attempts=[],rejections=[],incumbent=None,
               construction_seconds=0.0,generation_seconds=0.0,official_eval_seconds=0.0,
               output_seconds=0.0,evaluations=0,stopped=None)
    atomic_json(out/'progress.json',state)
    st=time.monotonic();session=OfficialSession(req['official'],req['graph'],req['config'])
    g,cfg=session.graph,session.cfg;q=req['q'];n=req['n']
    state['construction_seconds']+=time.monotonic()-st
    def checkpoint():
        state['elapsed_seconds']=time.monotonic()-started
        t=time.monotonic();atomic_json(out/'progress.json',state)
        state['output_seconds']+=time.monotonic()-t
    best=None;seen=set()
    def accept(plan, response, name, row):
        nonlocal best
        raw=response['official_result'];score=(raw['makespan'],raw['data_movement_bytes']['added_copy_bytes'])
        row.update(makespan=score[0],added_copy_bytes=score[1])
        previous=(best['official_result']['makespan'],best['official_result']['data_movement_bytes']['added_copy_bytes']) if best else (math.inf,math.inf)
        if score<previous:
            best=dict(plan=plan,official_result=raw)
            state['incumbent']=dict(plan_file=row['plan_file'],result_file=row['result_file'],name=name,
                makespan=score[0],added_copy_bytes=score[1],elapsed_seconds=time.monotonic()-started,
                certificate=response['audit']['certificate'])
            row['improved']=True
        else:row['improved']=False
        row['best_makespan']=state['incumbent']['makespan']
        row['available_seconds']=time.monotonic()-started
    if req.get('seed_job'):
        sp,plan,original=seed_payload(req,session)
        r=session.evaluate(plan,q);check_seed_replay(original,r)
        state['official_eval_seconds']+=r['eval_seconds']
        row=dict(name='seed_official_recheck',status=r['status'],eval_seconds=r['eval_seconds'],
                 completed_seconds=time.monotonic()-started,plan_file='seed_plan.json',result_file='seed_result.json.gz')
        t=time.monotonic();atomic_json(out/row['plan_file'],plan);save_gz(out/row['result_file'],r)
        state['output_seconds']+=time.monotonic()-t
        state['attempts'].append(row)
        if r['status']!='ok':raise ValueError('seed official validation failed')
        accept(plan,r,row['name'],row);seen.add(_key(plan));checkpoint()
    else:
        t=time.monotonic();prefix={**req,'job':str(out/'startup'),'seconds':max(.001,min(10.0,deadline-time.monotonic())),
                                'max_evaluations':min(3,req['max_evaluations'])}
        atomic_json(Path(prefix['job'])/'request.json',prefix)
        state['startup_offset_seconds']=t-started;checkpoint()
        ps=old_solve(prefix);offset=t-started
        state['startup_seconds']=time.monotonic()-t
        state['construction_seconds']+=ps.get('construction_seconds',0)
        for item in ps['attempts']:
            row={**item,'phase':'old_startup'}
            for k in ('started_seconds','completed_seconds','available_seconds'):
                if k in row:row[k]+=offset
            state['attempts'].append(row)
        state['evaluations']=ps.get('evaluations',0)
        state['official_eval_seconds']+=sum(a.get('eval_seconds',0) for a in ps['attempts'])
        if ps.get('incumbent'):
            meta=ps['incumbent'];plan=read(Path(prefix['job'])/meta['plan_file']);r=read(Path(prefix['job'])/meta['result_file'])
            best=dict(plan=plan,official_result=r['official_result']);seen.add(_key(plan))
            state['incumbent']={**meta,'plan_file':'startup/'+meta['plan_file'],
                                'result_file':'startup/'+meta['result_file'],'elapsed_seconds':offset+meta['elapsed_seconds']}
        checkpoint()
    if best is None:
        state.update(status='no_valid_solution',stopped='startup_no_valid_solution');checkpoint();return state
    for round_no in range(4):
        if time.monotonic()>=deadline:state['stopped']='time_budget';break
        if state['evaluations']>=req['max_evaluations']:state['stopped']='evaluation_cap';break
        stream=propose(g,n,cfg,q,best,state['attempts'],deadline);improved_round=False
        while time.monotonic()<deadline and state['evaluations']<req['max_evaluations']:
            st=time.monotonic()
            try:c=next(stream)
            except StopIteration as done:
                state['generation_seconds']+=time.monotonic()-st
                if isinstance(done.value,dict):state['rejections'].extend(done.value.get('diagnostics',[]))
                break
            state['generation_seconds']+=time.monotonic()-st
            state['rejections'].extend(c.get('generation_diagnostics',[]))
            key=_key(c['plan'])
            if key in seen:continue
            seen.add(key);state['evaluations']+=1;i=state['evaluations']
            row=dict(index=i,name=c['name'],family=c['family'],round=round_no,status='running',
                     mechanism=c.get('mechanism'),proxy=c['proxy'],bounds=c['bounds'],
                     started_seconds=time.monotonic()-started,
                     plan_file=f'raw/e{i:04d}_plan.json',result_file=f'raw/e{i:04d}_result.json.gz')
            state['attempts'].append(row)
            st=time.monotonic();atomic_json(out/row['plan_file'],c['plan'])
            state['output_seconds']+=time.monotonic()-st
            checkpoint()
            try:
                r=session.evaluate(c['plan'],q)
                row.update(status=r['status'],eval_seconds=r['eval_seconds'],completed_seconds=time.monotonic()-started)
                state['official_eval_seconds']+=r['eval_seconds']
                st=time.monotonic();save_gz(out/row['result_file'],r);state['output_seconds']+=time.monotonic()-st
                if r['status']=='ok':
                    accept(c['plan'],r,c['name'],row);improved_round |= row['improved']
                else:row['validation_errors']=r['audit']['errors']
            except Exception as exc:
                row.update(status='error',error=str(exc),traceback=traceback.format_exc(),completed_seconds=time.monotonic()-started)
            checkpoint()
        if not improved_round:
            state['stopped']='finite_neighbourhood_exhausted';break
    state.update(status='ok' if best else 'no_valid_solution',stopped=state['stopped'] or (
        'evaluation_cap' if state['evaluations']>=req['max_evaluations'] else 'time_budget' if time.monotonic()>=deadline else 'round_cap'))
    checkpoint();return state


def execute_worker(req):
    out=Path(req['job']);out.mkdir(parents=True,exist_ok=True);started=time.monotonic()
    if req.get('fixed_original_baseline'):
        fixed_singlecore(req,out,started);return
    if req['method'] in ('baseline','pair'):
        s=OfficialSession(req['official'],req['graph'],req['config'])
        p=one_core(s.graph,1) if req['method']=='baseline' else read(req['plan'])
        r=s.evaluate(p,0 if req['method']=='baseline' else 3,
                     None if req['method']=='baseline' else {'cache_capacity_bytes':0})
        save_gz(out/'result.json.gz',r);atomic_json(out/'plan.json',p)
        atomic_json(out/'progress.json',dict(status=r['status'],elapsed_seconds=time.monotonic()-started,
            official_eval_seconds=r['eval_seconds'],makespan=r['official_result']['makespan']))
    elif req['method']=='old':
        pre=0.0
        if req.get('seed_job'):
            s=OfficialSession(req['official'],req['graph'],req['config'])
            sp,plan,original=seed_payload(req,s)
            r=s.evaluate(plan,req['q']);check_seed_replay(original,r)
            save_gz(out/'seed_recheck.json.gz',r)
            pre=time.monotonic()-started
        atomic_json(out/'adapter_timing.json',{'prefix_seconds':pre})
        state=old_solve({**req,'seconds':max(.001,req['seconds']-pre)})
        state['adapter_prefix_seconds']=pre
        state['adapter_total_seconds']=time.monotonic()-started
        atomic_json(out/'progress.json',state)
    else:memory_worker(req)


def resources():
    cpu=os.cpu_count() or 1
    try:
        quota,period=Path('/sys/fs/cgroup/cpu.max').read_text().split()
        if quota!='max':cpu=min(cpu,max(1,math.ceil(int(quota)/int(period))))
    except (OSError,ValueError):pass
    free=0;limit=0
    try:
        vals={x.split(':')[0]:int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines()}
        free=vals['MemAvailable'];limit=vals['MemTotal']
        ml=Path('/sys/fs/cgroup/memory.max').read_text().strip()
        if ml!='max':
            limit=min(limit,int(ml));free=min(free,max(0,int(ml)-int(Path('/sys/fs/cgroup/memory.current').read_text())))
    except (OSError,ValueError,KeyError):
        if os.name=='nt':
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_ulonglong) for n in ('total','avail','page','availpage','virt','availvirt','extended')]
            m=MEMORYSTATUSEX();m.length=ctypes.sizeof(m)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):free,limit=m.avail,m.total
    return dict(cpu_quota=cpu,available_memory=free,memory_limit=limit)


def rss(pid):
    if os.name=='nt':
        import ctypes
        class Counters(ctypes.Structure):
            _fields_=[('cb',ctypes.c_ulong),('faults',ctypes.c_ulong)]+[(x,ctypes.c_size_t) for x in
                ('peak_working','working','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile','private')]
        kernel=ctypes.windll.kernel32;kernel.OpenProcess.restype=ctypes.c_void_p
        kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        handle=kernel.OpenProcess(0x1000|0x0010,False,pid)
        if not handle:return None
        try:
            counter=Counters();counter.cb=ctypes.sizeof(counter)
            get=ctypes.windll.psapi.GetProcessMemoryInfo
            get.argtypes=[ctypes.c_void_p,ctypes.POINTER(Counters),ctypes.c_ulong]
            return counter.working if get(handle,ctypes.byref(counter),counter.cb) else None
        finally:kernel.CloseHandle(handle)
    try:
        lines=Path(f'/proc/{pid}/status').read_text().splitlines()
        return next(int(l.split()[1])*1024 for l in lines if l.startswith('VmRSS:'))
    except (OSError,StopIteration):return None


def terminate(p):
    if p.poll() is not None:return
    if os.name=='nt':
        subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
    else:
        try:os.killpg(p.pid,signal.SIGTERM)
        except ProcessLookupError:pass
    try:p.wait(timeout=2)
    except subprocess.TimeoutExpired:p.kill();p.wait()


def recover_startup(req):
    if req.get('method')!='memory':return
    out=Path(req['job']);fp=out/'progress.json';sp=out/'startup/progress.json'
    if not fp.exists() or not sp.exists():return
    state=read(fp);startup=read(sp);meta=startup.get('incumbent')
    if state.get('incumbent') or not meta or 'startup_offset_seconds' not in state:return
    response=read(out/'startup'/meta['result_file'])
    if response.get('status')!='ok':return
    offset=state['startup_offset_seconds'];tm=offset+meta['elapsed_seconds']
    if tm>req['seconds']:return
    state['incumbent']={**meta,'plan_file':'startup/'+meta['plan_file'],
        'result_file':'startup/'+meta['result_file'],'elapsed_seconds':tm}
    state['attempts']=[{**a,**{k:a[k]+offset for k in ('started_seconds','completed_seconds','available_seconds') if k in a}}
        for a in startup.get('attempts',[])]
    state.update(status='ok',evaluations=startup.get('evaluations',0),stopped='saved_startup_recovered_after_stop',
        elapsed_seconds=offset+startup.get('elapsed_seconds',0),startup_recovery=True)
    atomic_json(fp,state)


def run_queue(requests, workers, global_deadline, log):
    pending=deque(requests);active=[];completed=[];peak_observed=256*1024**2
    while pending or active:
        now=time.monotonic();res=resources()
        auto=max(1,min(4,res['cpu_quota'],int(max(0,res['available_memory']-384*1024**2)/max(512*1024**2,peak_observed*1.5))))
        cap=auto if workers=='auto' else int(workers)
        while pending and len(active)<cap and now<global_deadline:
            req=pending.popleft();out=Path(req['job']);out.mkdir(parents=True,exist_ok=True)
            req={**req,'launch_wall_seconds':time.time()}
            atomic_json(out/'request.json',req)
            f=(out/'stderr.txt').open('w',encoding='utf-8')
            p=subprocess.Popen([sys.executable,'-m',RUN_MODULE,'--request',str(out/'request.json')],
                               stdout=f,stderr=f,start_new_session=os.name!='nt')
            active.append(dict(p=p,f=f,req=req,start=time.monotonic(),rss=0,workers_at_start=cap))
            log.append(dict(event='start',job=req['job'],method=req['method'],workers=cap,resources=res))
        if pending and now>=global_deadline:
            while pending:
                req=pending.popleft();Path(req['job']).mkdir(parents=True,exist_ok=True)
                atomic_json(Path(req['job'])/'request.json',req)
                atomic_json(Path(req['job'])/'execution.json',{'status':'not_started_global_deadline','wall_seconds':0})
        for a in active[:]:
            a['rss']=max(a['rss'],rss(a['p'].pid) or 0);peak_observed=max(peak_observed,a['rss'])
            elapsed=time.monotonic()-a['start'];reason=None
            if time.monotonic()>=global_deadline:reason='global_deadline'
            elif elapsed>=a['req']['seconds']:reason='hard_time_budget'
            if reason:terminate(a['p'])
            if a['p'].poll() is not None:
                a['f'].close();active.remove(a);out=Path(a['req']['job'])
                info=dict(status=reason or ('completed' if a['p'].returncode==0 else 'worker_error'),
                          returncode=a['p'].returncode,wall_seconds=elapsed,peak_rss_bytes=a['rss'],
                          workers_at_start=a['workers_at_start'])
                atomic_json(out/'execution.json',info);recover_startup(a['req']);completed.append(a['req']);log.append(dict(event='finish',job=str(out),**info))
        time.sleep(.05)
    return completed


def summarize(out, requests, run_id, baseline_by_case):
    rows=[];trajectory=[];prefixes=[]
    for req in requests:
        job=Path(req['job']);seed_cost=req.get('seed_solve_seconds',0);baseline=baseline_by_case.get(req['case'])
        state=read(job/'progress.json') if (job/'progress.json').exists() else {}
        execution=read(job/'execution.json') if (job/'execution.json').exists() else {}
        meta=state.get('incumbent');elapsed=execution.get('wall_seconds',state.get('elapsed_seconds',0))
        result=read(job/meta['result_file'])['official_result'] if meta else None
        seedmeta=None
        if req.get('seed_job') and (Path(req['seed_job'])/'progress.json').exists():
            seedmeta=read(Path(req['seed_job'])/'progress.json').get('incumbent')
        old_ms=seedmeta['makespan'] if seedmeta else None;old_bytes=seedmeta['added_copy_bytes'] if seedmeta else None
        events=[]
        if seedmeta and result:events.append(dict(elapsed_seconds=0.0,makespan=old_ms,added_copy_bytes=old_bytes,phase='imported_seed_pre_recheck'))
        pre=state.get('adapter_prefix_seconds',0)
        if not pre and (job/'adapter_timing.json').exists():pre=read(job/'adapter_timing.json').get('prefix_seconds',0)
        clock=read(job/'worker_clock.json') if (job/'worker_clock.json').exists() else {}
        launch_offset=clock.get('launch_offset_seconds',0)
        legacy_clock_uncertainty=max(0,elapsed-state.get('elapsed_seconds',elapsed)-pre) if not clock else 0
        for a in state.get('attempts',[]):
            if a.get('status')=='ok' and a.get('makespan') is not None:
                t=a.get('available_seconds',a.get('completed_seconds',0))+(pre if req['method']=='old' else 0)+launch_offset
                if t<=req['seconds']:
                    events.append(dict(elapsed_seconds=t,makespan=a['makespan'],added_copy_bytes=a['added_copy_bytes'],phase=a.get('phase',a['name'])))
        events.sort(key=lambda e:e['elapsed_seconds']);best=None;ev=0
        common={k:req[k] for k in ('case','q','n','method','mode')};common['run_id']=run_id
        for e in events:
            ev+=e['phase']!='imported_seed_pre_recheck'
            score=(e['makespan'],e['added_copy_bytes'])
            if best is None or score<best:best=score
            trajectory.append({**common,'phase':e['phase'],'elapsed_seconds':e['elapsed_seconds'],
                'total_elapsed_seconds':seed_cost+e['elapsed_seconds'],'best_makespan':best[0],
                'baseline':baseline,'speedup':baseline/best[0] if baseline else None,'added_copy_bytes':best[1],
                'evaluations':ev,'has_valid_incumbent':True})
        for budget in (30,60,120,300,600):
            eligible=[e for e in events if e['elapsed_seconds']<=budget]
            winner=min(eligible,key=lambda e:(e['makespan'],e['added_copy_bytes'])) if eligible else None
            prefixes.append({**common,'budget_seconds':budget,'total_budget_seconds':seed_cost+budget,
                'process_startup_uncertainty_seconds':legacy_clock_uncertainty,
                'conservative_best_makespan':min((e['makespan'] for e in events if e['elapsed_seconds']+(0 if e['phase']=='imported_seed_pre_recheck' else legacy_clock_uncertainty)<=budget),default=None),
                'best_makespan':winner['makespan'] if winner else None,'baseline':baseline,
                'speedup':baseline/winner['makespan'] if winner and baseline else None,
                'added_copy_bytes':winner['added_copy_bytes'] if winner else None,
                'stopped_before_prefix':elapsed<budget,'actual_stop_seconds':elapsed,
                'prefix_kind':'stopped_carry_forward' if elapsed<budget else 'completed_events_only'})
        pair_dir=job/'no_l2';pair=read(pair_dir/'progress.json') if (pair_dir/'progress.json').exists() else {}
        pair_exec=read(pair_dir/'execution.json') if (pair_dir/'execution.json').exists() else {}
        cache=result.get('cache_stats',{}) if result else {}
        eval_seconds=sum(a.get('eval_seconds',0) for a in state.get('attempts',[]))
        recheck=read(job/'seed_recheck.json.gz').get('eval_seconds',0) if (job/'seed_recheck.json.gz').exists() else 0
        eval_seconds+=recheck
        rows.append({**common,'status':'ok' if result else execution.get('status','no_valid_solution'),
            'baseline':baseline,'old_makespan':old_ms,'new_makespan':result['makespan'] if result else None,
            'old_added_copy_bytes':old_bytes,'new_added_copy_bytes':result['data_movement_bytes']['added_copy_bytes'] if result else None,
            'partition_added_copy_bytes':result['data_movement_bytes'].get('partition_added_copy_bytes') if result else None,
            'spill_added_copy_bytes':result['data_movement_bytes'].get('spill_added_copy_bytes') if result else None,
            'seed_solve_seconds':seed_cost,'added_solve_seconds':elapsed,'total_solve_seconds':seed_cost+elapsed,
            'construction_seconds':state.get('construction_seconds',0),'generation_seconds':state.get('generation_seconds'),
            'expanded_construction_seconds':state.get('expanded_construction_seconds',0),
            'official_eval_seconds':state.get('official_eval_seconds',eval_seconds),
            'legacy_generation_and_io_seconds':sum(a.get('generation_and_io_seconds',0) for a in state.get('attempts',[])),
            'output_seconds':state.get('output_seconds'),'evaluations':state.get('evaluations',0)+(1 if seedmeta and not req.get('fixed_original_baseline') else 0),
            'candidate_evaluations':state.get('evaluations',0),'seed_recheck_seconds':recheck or next((a.get('eval_seconds',0) for a in state.get('attempts',[]) if a.get('name')=='seed_official_recheck'),0),
            'launch_offset_seconds':launch_offset,'legacy_clock_uncertainty_seconds':legacy_clock_uncertainty,
            'clock_basis':'parent_launch_wall_offset_plus_worker_monotonic' if clock else 'legacy_worker_monotonic_excludes_process_startup',
            'lower':meta.get('certificate',{}).get('global_lower') if meta else None,
            'no_l2_makespan':pair.get('makespan'),'pair_status':pair.get('status',pair_exec.get('status')),
            'pair_seconds':pair_exec.get('wall_seconds',0),
            'experiment_total_seconds':seed_cost+elapsed+pair_exec.get('wall_seconds',0),
            'cache_hit_rate':cache.get('byte_hit_rate',cache.get('hit_rate')),
            'plan_file':str((job/meta['plan_file']).relative_to(out)) if meta else None,
            'result_file':str((job/meta['result_file']).relative_to(out)) if meta else None,
            'stop_reason':state.get('stopped',execution.get('status')),'execution_status':execution.get('status'),
            'workers_at_start':execution.get('workers_at_start'),'peak_rss_bytes':execution.get('peak_rss_bytes'),
            'seed_provenance':req.get('seed_provenance','fresh_local_upstream' if seedmeta else 'none'),
            'benchmark_role':state.get('benchmark_role','optimized_multicore'),
            'adapter_version':clock.get('adapter_version','adapter-1.3-frozen'),'summary_version':ADAPTER_VERSION,
            'requested_seconds':req['seconds']})
    csv_write(out/'per_case.csv',rows);csv_write(out/'trajectory.csv',trajectory);csv_write(out/'budget_prefixes.csv',prefixes)
    paired=[]
    index={(r['case'],r['q'],r['n'],r['mode'],r['method']):r for r in rows}
    for key,old in index.items():
        if key[-1]!='old':continue
        new=index.get((*key[:-1],'memory'))
        if not new:continue
        a,b=old['new_makespan'],new['new_makespan']
        paired.append(dict(case=key[0],q=key[1],n=key[2],mode=key[3],old_makespan=a,new_makespan=b,
            makespan_reduction_pct=(a-b)/a*100 if a and b else None,
            old_added_copy_bytes=old['new_added_copy_bytes'],new_added_copy_bytes=new['new_added_copy_bytes'],
            old_solve_seconds=old['added_solve_seconds'],new_solve_seconds=new['added_solve_seconds'],
            old_status=old['status'],new_status=new['status'],
            same_budget=(old['requested_seconds']==new['requested_seconds'] and old['execution_status']!='global_deadline' and new['execution_status']!='global_deadline'),
            comparison='same_cpu_only_host_same_requested_worker_policy'))
    csv_write(out/'comparison.csv',paired)
    return rows


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request');p.add_argument('--official');p.add_argument('--data');p.add_argument('--config')
    p.add_argument('--cases',nargs='+',type=int,default=[2,16,44,71,59,83]);p.add_argument('--questions',nargs='+',type=int,default=[1,2,3])
    p.add_argument('--cores',nargs='+',type=int,default=[2,5]);p.add_argument('--seconds',type=float,default=300)
    p.add_argument('--seed-seconds',type=float,default=60);p.add_argument('--seed-evaluations',type=int,default=8)
    p.add_argument('--max-evaluations',type=int,default=24);p.add_argument('--total-seconds',type=float,default=1800)
    p.add_argument('--pair-seconds',type=float,default=120);p.add_argument('--workers',default='auto')
    p.add_argument('--modes',nargs='+',choices=['warm_start','cold_start'],default=['warm_start','cold_start'])
    p.add_argument('--shards',type=int,default=1);p.add_argument('--shard-index',type=int,default=0)
    p.add_argument('--out');p.add_argument('--resume',action='store_true');p.add_argument('--seed-index')
    args=p.parse_args(argv)
    if args.request:
        req=read(args.request)
        offset=max(0,time.time()-req['launch_wall_seconds']) if 'launch_wall_seconds' in req else 0
        atomic_json(Path(req['job'])/'worker_clock.json',dict(launch_offset_seconds=offset,worker_entry_wall_seconds=time.time(),adapter_version=ADAPTER_VERSION))
        try:execute_worker(req);return 0
        except Exception as exc:
            atomic_json(Path(req['job'])/'worker_error.json',dict(status='error',error=str(exc),traceback=traceback.format_exc()));return 1
    if args.shards<1 or not 0<=args.shard_index<args.shards:p.error('invalid shard assignment')
    if any(q not in (1,2,3) for q in args.questions) or any(n not in range(1,6) for n in args.cores):p.error('q=1..3, cores=1..5')
    if min(args.seconds,args.seed_seconds,args.total_seconds,args.pair_seconds)<=0:p.error('budgets must be positive')
    if args.workers!='auto' and (not args.workers.isdigit() or int(args.workers)<1):p.error('workers must be auto or positive integer')
    root=Path(__file__).resolve().parents[1]
    official=Path(args.official).resolve() if args.official else next((root/'题目/A题').glob('*附件'),None)
    if official is None:p.error('official attachment directory absent; pass --official')
    data=Path(args.data).resolve() if args.data else official/'data';config=Path(args.config).resolve() if args.config else data/'config.txt'
    out=Path(args.out).resolve() if args.out else root/'research_a_orion_track_memory/results'/time.strftime('%Y%m%d_%H%M%S')
    if out.exists() and any(out.iterdir()) and not args.resume:p.error('output is nonempty; use a new run id (resume is explicit)')
    out.mkdir(parents=True,exist_ok=True);run_id=out.name
    all_cases=sorted(set(args.cases));cases=all_cases[args.shard_index::args.shards]
    if not (official/'code/evaluation_validation.py').is_file() or not config.is_file():p.error('official source/config absent')
    deadline=time.monotonic()+args.total_seconds;log=[];missing=[];usable=[]
    for c in cases:
        gp=data/f'case_{c:03d}.json'
        if not gp.is_file():missing.append({'case':c,'status':'missing_original_input'});continue
        with gp.open('rb') as f:begin=f.read(100)
        if begin.startswith(b'version https://git-lfs'):missing.append({'case':c,'status':'lfs_pointer_not_graph'});continue
        usable.append(c)
    manifest=dict(run_id=run_id,version=VERSION,adapter_version=ADAPTER_VERSION,argv=vars(args),python=sys.version,
        platform=platform.platform(),resources=resources(),all_cases=all_cases,assigned_cases=cases,
        usable_cases=usable,missing=missing,source_provenance='original full JSON, official evaluator unchanged',
        formal_100_graph_complete=False,requested_target_gate_passed=False)
    if (out/'manifest.json').exists():
        previous=read(out/'manifest.json')
        for key in ('cases','questions','cores','seconds','seed_seconds','seed_evaluations','max_evaluations','workers','modes'):
            if previous['argv'].get(key)!=vars(args).get(key):p.error('resume changes the fixed experiment: '+key)
        atomic_json(out/'resume_history'/f'manifest_{time.time_ns()}.json',manifest)
    else:atomic_json(out/'manifest.json',manifest)
    external={}
    if args.seed_index:
        entries=read(args.seed_index)
        for entry in entries:
            c=int(str(entry['case']).removeprefix('case_'));key=(c,int(entry['q']),int(entry['n']))
            if key in external:raise ValueError('duplicate external seed: '+str(key))
            cost=entry.get('seed_solve_seconds')
            if not isinstance(cost,(int,float)) or not math.isfinite(cost) or cost<0 or entry.get('cost_status')!='complete':
                raise ValueError('seed requires complete finite acquisition cost, including coverage/retries/refinement')
            external[key]=entry
    def base(c,q,n,method,mode,job,seconds):
        return dict(case=f'case_{c:03d}',q=q,n=n,method=method,mode=mode,job=str(job),seconds=seconds,
            graph=str(data/f'case_{c:03d}.json'),official=str(official),config=str(config),identity=run_id,
            max_evaluations=args.max_evaluations,strategy='anytime',gap_tolerance=0,
            fixed_original_baseline=(q in (1,2) and n==1))
    baseline_reqs=[base(c,0,1,'baseline','baseline',out/'baselines'/f'case_{c:03d}',args.pair_seconds) for c in usable]
    def pending(reqs):
        chosen=[]
        for r in reqs:
            ep=Path(r['job'])/'execution.json'
            if args.resume and ep.exists():
                previous=read(ep)
                if previous.get('status')!='not_started_global_deadline':continue
                atomic_json(ep.parent/'resume_history'/f'execution_{time.time_ns()}.json',previous)
            chosen.append(r)
        return chosen
    run_queue(pending(baseline_reqs),args.workers,deadline,log)
    baseline_values={r['case']:read(Path(r['job'])/'progress.json')['makespan'] for r in baseline_reqs if (Path(r['job'])/'progress.json').exists()}
    seed_reqs=[];reqs=[]
    for c in usable:
        for n in args.cores:
            for q in args.questions:
                tag=f'case_{c:03d}_q{q}_n{n}'
                sd=out/'seeds'/tag
                seed=base(c,q,n,'old','cold_start',sd,args.seed_seconds);seed['max_evaluations']=args.seed_evaluations
                if args.seed_index and (c,q,n) in external:
                    entry=external[c,q,n];seed.update(job=str(Path(entry['job']).resolve()),external=True,
                        seed_solve_seconds=entry['seed_solve_seconds'],seed_provenance=entry.get('provenance','explicit_external_index'),seed_config=entry.get('config'))
                elif args.seed_index:seed['external_missing']=True
                seed_reqs.append(seed)
    if 'warm_start' in args.modes:run_queue(pending([s for s in seed_reqs if not s.get('external') and not s.get('external_missing')]),args.workers,deadline,log)
    for mode in args.modes:
        batch=[]
        for seed in seed_reqs:
            sd=Path(seed['job']);c=int(seed['case'].split('_')[1]);q=seed['q'];n=seed['n'];tag=f'case_{c:03d}_q{q}_n{n}'
            methods=('old','memory') if (c+q+n)%2 else ('memory','old')
            for method in methods:
                req=base(c,q,n,method,mode,out/mode/tag/method,args.seconds)
                if mode=='warm_start':
                    req['seed_job']=str(sd)
                    req['seed_solve_seconds']=seed.get('seed_solve_seconds',read(sd/'execution.json').get('wall_seconds',0) if (sd/'execution.json').exists() else 0)
                    req['seed_provenance']=seed.get('seed_provenance','fresh_local_upstream')
                    if seed.get('seed_config'):req['seed_config']=seed['seed_config']
                    if req.get('fixed_original_baseline'):
                        req.pop('seed_job');req['seed_solve_seconds']=0;req['seed_provenance']='fixed_original_singlecore'
                batch.append(req)
        reqs.extend(batch);run_queue(pending(batch),args.workers,deadline,log)
        pairs=[]
        for req in batch:
            job=Path(req['job'])
            if req['q']!=3 or not (job/'progress.json').exists():continue
            meta=read(job/'progress.json').get('incumbent')
            if meta:pairs.append({**req,'method':'pair','job':str(job/'no_l2'),'plan':str(job/meta['plan_file']),'seconds':args.pair_seconds})
        run_queue(pending(pairs),args.workers,deadline,log)
        summarize(out,reqs,run_id,baseline_values)
        atomic_json(out/('worker_policy.json' if not args.resume else f'resume_history/worker_policy_{time.time_ns()}.json'),log)
    all_reqs=[read(f) for mode in ('warm_start','cold_start') for f in (out/mode).glob('*/*/request.json')]
    rows=summarize(out,all_reqs,run_id,baseline_values)
    atomic_json(out/'campaign_status.json',dict(requested_configs=len(cases)*len(args.cores)*len(args.questions),
        requested_rows=len(usable)*len(args.cores)*len(args.questions)*len(args.modes)*2,
        recorded_rows=len(rows),ok_rows=sum(r['status']=='ok' for r in rows),missing=missing,
        global_deadline_reached=time.monotonic()>=deadline))
    print(json.dumps(read(out/'campaign_status.json'),ensure_ascii=False))
    return 0 if rows and all(r['status']=='ok' for r in rows) and not missing else 2

if __name__=='__main__':raise SystemExit(main())
