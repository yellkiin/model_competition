"""Bounded real-graph experiments with persisted observation-time trajectories."""
from __future__ import annotations
import argparse
from collections import Counter, deque
import csv
import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
from research_a_orion_anytime.worker import atomic_json
from .worker import read


def numbers(text):
    return sorted(set(int(x.strip()) for x in text.split(',') if x.strip()))


def available_memory():
    try:
        if os.name == 'nt':
            class Memory(ctypes.Structure):
                _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
                    (x, ctypes.c_ulonglong) for x in ('total', 'available', 'page', 'available_page',
                                                       'virtual', 'available_virtual', 'extended')]
            m = Memory()
            m.length = ctypes.sizeof(m)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return int(m.available)
        values = {line.split(':')[0]: int(line.split()[1])*1024
                  for line in Path('/proc/meminfo').read_text().splitlines()}
        available = values['MemAvailable']
        limit, current = Path('/sys/fs/cgroup/memory.max'), Path('/sys/fs/cgroup/memory.current')
        if limit.exists() and limit.read_text().strip() != 'max':
            available = min(available, int(limit.read_text())-int(current.read_text()))
        return max(0, available)
    except (OSError, KeyError, ValueError):
        return None


def csv_write(path, rows):
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


class Campaign:
    def __init__(self, args, out):
        self.a, self.out = args, out
        self.start = time.monotonic()
        self.deadline = self.start + args.wall_seconds
        self.records, self.policy = [], []
        self.peak_rss = 0
        self.timeouts = 0
        self.repo = Path(__file__).resolve().parents[1]

    def request(self, case, q, n, method, phase, **extra):
        return dict(case='case_'+case, q=q, n=n, method=method, phase=phase,
            job=str(self.out/'jobs'/f'{phase}_{case}_q{q}_n{n}_{method}'),
            official=str(self.a.official), config=str(self.a.config),
            graph=str(self.a.data_root/f'case_{case}.json'), seconds=self.a.seconds,
            max_evaluations=self.a.max_evaluations, strategy='anytime',
            identity=dict(run_id=self.out.name, case=case, q=q, n=n, method=method, phase=phase), **extra)

    def cap(self):
        if self.a.workers != 'auto':
            return int(self.a.workers)
        cpu = len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else (os.cpu_count() or 1)
        available = available_memory()
        if available is None:
            return 1
        per_worker = max(768*1024**2, int(2.5*self.peak_rss))
        memory_cap = max(1, (available-512*1024**2)//per_worker)
        cap = max(1, min(4, max(1, cpu//2), memory_cap))
        return min(cap, 2) if self.timeouts else cap

    def batch(self, requests):
        queue, active, finished = deque(requests), [], []
        while queue or active:
            cap = self.cap()
            while queue and len(active) < cap:
                r = queue.popleft()
                if self.deadline-time.monotonic() < r['seconds']:
                    row = {**r, 'status':'not_started', 'makespan':None, 'solve_seconds':0.0,
                           'observations':[], 'reason':'insufficient_remaining_full_job_budget'}
                    self.records.append(row)
                    finished.append(row)
                    continue
                job = Path(r['job'])
                job.mkdir(parents=True, exist_ok=False)
                started = time.monotonic()
                atomic_json(job/'request.json', r)
                log = (job/'stdout.log').open('wb')
                kwargs = dict(cwd=str(self.repo), stdout=log, stderr=subprocess.STDOUT)
                if os.name == 'nt':
                    kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
                else:
                    kwargs['start_new_session'] = True
                proc = subprocess.Popen([sys.executable, '-u', '-m', 'research_a_orion_track_structure.worker',
                                         str(job/'request.json')], **kwargs)
                active.append(dict(r=r, proc=proc, log=log, start=started, events=[], last=None,
                                   peak=0, timeout=False))
                self.policy.append(dict(elapsed_seconds=started-self.start, job=job.name,
                                        active=len(active), cap=cap, available_bytes=available_memory()))
                print('START', job.name, 'workers', cap, flush=True)
            for task in active[:]:
                r, proc = task['r'], task['proc']
                job = Path(r['job'])
                elapsed = time.monotonic()-task['start']
                try:
                    import psutil
                    rss = psutil.Process(proc.pid).memory_info().rss
                    task['peak'] = max(task['peak'], rss)
                    self.peak_rss = max(self.peak_rss, rss)
                except Exception:
                    pass
                try:
                    state = read(job/'progress.json')
                    incumbent = state.get('incumbent')
                    if incumbent:
                        key = (incumbent['plan_file'], incumbent['makespan'], incumbent.get('added_copy_bytes'))
                        if key != task['last']:
                            task['last'] = key
                            event = dict(elapsed_seconds=time.monotonic()-task['start'],
                                makespan=incumbent['makespan'], added_copy_bytes=incumbent.get('added_copy_bytes'),
                                plan_file=incumbent['plan_file'], result_file=incumbent['result_file'],
                                evaluations=incumbent.get('evaluation'))
                            task['events'].append(event)
                            with (job/'observations.jsonl').open('a', encoding='utf8') as f:
                                f.write(json.dumps(event)+'\n')
                except (OSError, ValueError, KeyError):
                    pass
                if proc.poll() is None and (elapsed >= r['seconds'] or time.monotonic() >= self.deadline):
                    task['timeout'] = True
                    self.timeouts += 1
                    try:
                        if os.name == 'nt':
                            proc.terminate()
                        else:
                            os.killpg(proc.pid, signal.SIGTERM)
                        proc.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        if os.name == 'nt':
                            proc.kill()
                        else:
                            os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                if proc.poll() is not None:
                    task['log'].close()
                    row = self.finish(task)
                    self.records.append(row)
                    finished.append(row)
                    active.remove(task)
                    atomic_json(self.out/'run_status.json', dict(elapsed_seconds=time.monotonic()-self.start,
                                finished=len(self.records), active=len(active), queued=len(queue)))
                    print('END', job.name, row['status'], row.get('makespan'),
                          round(row['solve_seconds'], 3), flush=True)
            if active:
                time.sleep(.10)
        return finished

    def finish(self, task):
        r, job = task['r'], Path(task['r']['job'])
        events = [e for e in task['events'] if e['elapsed_seconds'] <= r['seconds']]
        best = min(events, key=lambda e:(e['makespan'], e.get('added_copy_bytes', 0))) if events else None
        try:
            state = read(job/'progress.json')
        except (OSError, ValueError):
            state = {}
        result = read(job/best['result_file']) if best else None
        raw = result['official_result'] if result else {}
        row = {**r, 'status':('ok_with_timeout' if task['timeout'] else 'ok') if best else
               ('timeout' if task['timeout'] else 'failed'), 'solve_seconds':time.monotonic()-task['start'],
               'timed_out':task['timeout'], 'observations':events, 'peak_rss_bytes':task['peak'],
               'makespan':best['makespan'] if best else None,
               'added_copy_bytes':best.get('added_copy_bytes') if best else None,
               'plan_file':str(job/best['plan_file']) if best else None,
               'result_file':str(job/best['result_file']) if best else None,
               'construction_seconds':state.get('construction_seconds'),
               'candidate_generation_seconds':state.get('candidate_generation_seconds', state.get('expanded_construction_seconds')),
               'evaluations':sum(a.get('status') in ('ok','error','audit_failed') for a in state.get('attempts', [])),
               'lower':result['audit']['certificate']['global_lower'] if result else None,
               'cache_hit_rate':raw.get('cache_stats', {}).get('hit_rate'), 'stopped':state.get('stopped')}
        if task['timeout']:
            atomic_json(job/'timeout.json', dict(elapsed_seconds=row['solve_seconds'],
                unfinished=[a for a in state.get('attempts', []) if a.get('status')=='running'],
                preserved_incumbent=bool(best)))
        atomic_json(job/'summary.json', row)
        return row


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cases', required=True)
    p.add_argument('--questions', default='1,2,3')
    p.add_argument('--cores', default='2,5')
    p.add_argument('--seconds', type=float, default=300)
    p.add_argument('--wall-seconds', type=float, default=1200)
    p.add_argument('--max-evaluations', type=int, default=8)
    p.add_argument('--workers', default='auto')
    p.add_argument('--shards', type=int, default=1)
    p.add_argument('--shard-index', type=int, default=0)
    for name in ('official','config','data-root','out','warm-spec','seed-index'):
        p.add_argument('--'+name, type=Path)
    p.add_argument('--skip-paired', action='store_true')
    a = p.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    a.official = (a.official or repo/'题目/A题/通用神经网络处理器下的多核调度问题  附件').resolve()
    a.data_root = (a.data_root or a.official/'data').resolve()
    a.config = (a.config or (a.data_root/'config.txt' if (a.data_root/'config.txt').exists() else a.official/'config.txt')).resolve()
    if a.shards<1 or not 0<=a.shard_index<a.shards:
        p.error('invalid shard parameters')
    if a.workers!='auto' and (not a.workers.isdigit() or int(a.workers)<1):
        p.error('workers must be auto or a positive integer')
    if a.seconds<=0 or a.wall_seconds<=0 or a.max_evaluations<1:
        p.error('budgets must be positive')
    qs, ns = numbers(a.questions), numbers(a.cores)
    if not qs or not ns or any(q not in (1,2,3) for q in qs) or any(n<1 for n in ns):
        p.error('invalid questions or cores')
    full_cases = [f'{x:03d}' for x in numbers(a.cases)]
    cases = full_cases[a.shard_index::a.shards]
    out = (a.out or Path(__file__).resolve().parent/'results'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')).resolve()
    if out.exists():
        p.error('output exists; choose a new run ID')
    if not a.config.is_file() or not (a.official/'code/multicore_cut_evaluate_problem_3.py').is_file():
        p.error('official code or configuration missing')
    out.mkdir(parents=True)
    available, missing = [], []
    for c in cases:
        path = a.data_root/f'case_{c}.json'
        if not path.is_file():
            missing.append(dict(case=c, status='missing_input'))
            continue
        with path.open('rb') as f:
            header = f.read(120)
        if header.startswith(b'version https://git-lfs'):
            missing.append(dict(case=c, status='lfs_pointer_not_input'))
        else:
            available.append(c)
    atomic_json(out/'manifest.json', dict(run_id=out.name, platform=platform.platform(),
        python=sys.version, executable=sys.executable, requested_cases=full_cases, shard_cases=cases,
        available_cases=available, missing=missing, questions=qs, cores=ns, seconds=a.seconds,
        wall_seconds=a.wall_seconds, max_evaluations=a.max_evaluations, workers=a.workers,
        shards=a.shards, shard_index=a.shard_index, argv=sys.argv, formal_complete=False))
    campaign = Campaign(a, out)
    baseline_jobs = campaign.batch([campaign.request(c,0,1,'new','baseline') for c in available])
    baselines = {r['case']:r['makespan'] for r in baseline_jobs if r.get('makespan') is not None}
    warm = []
    if a.warm_spec:
        for i, spec in enumerate(read(a.warm_spec)):
            c = f'{int(spec["case"]):03d}'
            if c not in available:
                continue
            seed = campaign.batch([campaign.request(c,int(spec['q']),int(spec['source_n']),'old',f'seed{i}')])[0]
            if seed.get('plan_file'):
                warm += campaign.batch([campaign.request(c,int(spec['q']),int(spec['target_n']),'new',f'warm{i}',
                    seed_plan=seed['plan_file'], seed_solve_seconds=seed['solve_seconds'], seed_job=seed['job'],
                    seed_origin='fresh_old_solver_seed_not_day01_archive')])
    if a.seed_index:
        for i, spec in enumerate(read(a.seed_index)):
            c = f'{int(str(spec["case"]).replace("case_", "")):03d}'
            if c in available:
                warm += campaign.batch([campaign.request(c,int(spec['q']),int(spec['target_n']),'new',f'external_warm{i}',
                    seed_plan=str(Path(spec['plan_file']).resolve()), seed_solve_seconds=spec.get('seed_solve_seconds'),
                    seed_origin=spec.get('source','external_seed_cost_unknown'))])
    paired = []
    if not a.skip_paired:
        requests = []
        for i,c in enumerate(available):
            for q in qs:
                for n in ns:
                    for method in (('old','new') if (i+q+n)%2==0 else ('new','old')):
                        requests.append(campaign.request(c,q,n,method,'paired'))
        paired = campaign.batch(requests)
    requests = [campaign.request(r['case'].replace('case_',''),2,r['n'],'new',f'no_l2_{i}',
                    fixed_plan=r['plan_file'], pair_source_job=r['job'])
                for i,r in enumerate(warm+paired) if r['q']==3 and r.get('plan_file')]
    pairs = campaign.batch(requests)
    pair_map = {r['pair_source_job']:r for r in pairs}
    old_map = {(r['case'],r['q'],r['n']):r for r in paired if r['method']=='old'}
    rows, trajectory = [], []
    for r in warm+paired:
        old, pair = old_map.get((r['case'],r['q'],r['n']), {}), pair_map.get(r['job'], {})
        is_warm = 'warm' in r['phase']
        seed_cost = r.get('seed_solve_seconds') if is_warm else 0.0
        total = None if seed_cost is None else seed_cost+r['solve_seconds']
        rows.append(dict(case=r['case'],q=r['q'],n=r['n'],method=r['method'],run_id=out.name,
            mode='warm_start' if is_warm else 'cold_start',status=r['status'],baseline=baselines.get(r['case']),
            old_makespan=old.get('makespan'),new_makespan=r.get('makespan'),
            old_added_copy_bytes=old.get('added_copy_bytes'),new_added_copy_bytes=r.get('added_copy_bytes'),
            seed_solve_seconds=seed_cost,added_solve_seconds=r['solve_seconds'],total_solve_seconds=total,
            construction_seconds=r.get('construction_seconds'),candidate_generation_seconds=r.get('candidate_generation_seconds'),
            evaluations=r.get('evaluations'),lower=r.get('lower'),no_l2_makespan=pair.get('makespan'),
            no_l2_replay_seconds=pair.get('solve_seconds'),cache_hit_rate=r.get('cache_hit_rate'),
            plan_file=str(Path(r['plan_file']).relative_to(out)) if r.get('plan_file') else None,
            result_file=str(Path(r['result_file']).relative_to(out)) if r.get('result_file') else None,
            job=str(Path(r['job']).relative_to(out)),seed_origin=r.get('seed_origin'),
            pair_status=pair.get('status','missing' if r['q']==3 else 'not_applicable')))
        for t in (30,60,120,300) + ((600,) if a.seconds>300 else ()):
            observed = [e for e in r.get('observations',[]) if e['elapsed_seconds']<=t]
            best = min(observed,key=lambda e:(e['makespan'],e.get('added_copy_bytes',0))) if observed else None
            actual, b = min(t,r['solve_seconds']), baselines.get(r['case'])
            trajectory.append(dict(case=r['case'],q=r['q'],n=r['n'],method=r['method'],run_id=out.name,
                mode='warm_start' if is_warm else 'cold_start',
                phase='stopped_carry_forward' if t>r['solve_seconds'] else 'running_prefix',
                budget_seconds=t,elapsed_seconds=actual,total_elapsed_seconds=None if seed_cost is None else seed_cost+actual,
                best_makespan=best['makespan'] if best else None,baseline=b,
                speedup=b/best['makespan'] if best and b else None,
                added_copy_bytes=best.get('added_copy_bytes') if best else None,
                evaluations=best.get('evaluations') if best else 0,has_valid_incumbent=bool(best),
                job=str(Path(r['job']).relative_to(out))))
    csv_write(out/'per_case.csv',rows)
    csv_write(out/'trajectory.csv',trajectory)
    atomic_json(out/'all_jobs.json',campaign.records)
    atomic_json(out/'worker_policy.json',campaign.policy)
    atomic_json(out/'run_summary.json',dict(elapsed_seconds=time.monotonic()-campaign.start,
        jobs=len(campaign.records),status_counts=dict(Counter(r['status'] for r in campaign.records)),
        q3_pairs=len(pairs),missing_inputs=missing,formal_complete=False))
    print('RESULTS',out,flush=True)

if __name__ == '__main__':
    main()
