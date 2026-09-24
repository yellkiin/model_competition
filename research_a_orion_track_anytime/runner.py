"""Real-graph controller: same-host pairs, hard deadlines and conservative prefixes.

No benchmark success is inferred from starting this program. Only completed,
audited original responses establish feasible solutions. Input preparation is
read-only; missing LFS payloads produce blocked.json rather than substitute data.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback
from .storage import read, write, incumbent_from_job
from .diagnose import csv_write

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parent
PREFIXES = (30, 60, 120, 300, 600)


def memory_available():
    try:
        import psutil
        return psutil.virtual_memory().available, psutil.cpu_percent(interval=None)
    except ImportError:
        pass
    if os.name == 'nt':
        import ctypes
        class Memory(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
                (x, ctypes.c_ulonglong) for x in ('total', 'available', 'page_total', 'page_available',
                                                'virtual_total', 'virtual_available', 'extended')]
        data = Memory()
        data.length = ctypes.sizeof(data)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(data)):
            return data.available, None
    try:
        values = {line.split(':')[0]: int(line.split()[1])*1024
                  for line in Path('/proc/meminfo').read_text().splitlines()}
        return values['MemAvailable'], None
    except (OSError, ValueError, KeyError):
        return None, None


def worker_limit(requested, maximum, history):
    available, load = memory_available()
    cpus = max(1, (os.cpu_count() or 1)//2)
    # Start with one paired work unit; increase only between completed waves.
    peak = max((r.get('peak_rss_bytes') or 0 for r in history), default=0)
    per_worker = max(1024**3, int(1.5*peak))
    ram = max(1, int(max(0, (available or per_worker)-512*1024**2)//per_worker))
    target = min(maximum, cpus, ram)
    if requested != 'auto':
        target = min(target, int(requested))
    elif not history:
        target = 1
    elif any(r.get('status') not in ('ok', 'not_started_deadline') for r in history[-4:]):
        target = max(1, target//2)
    if load is not None and load > 90:
        target = 1
    return max(1, target), dict(available_bytes=available, cpu_percent=load,
                                predicted_worker_bytes=per_worker, cpu_count=os.cpu_count())


def startup(official, cases):
    if official:
        root = Path(official).resolve()
    else:
        roots = list((ROOT/'题目'/'A题').glob('*附件'))
        if len(roots) != 1:
            raise FileNotFoundError('Original A attachment missing; supply --official. No substitute graph will run.')
        root = roots[0]
    config = next((p for p in (root/'data/config.txt', root/'config.txt') if p.is_file()), None)
    if config is None or not (root/'code/evaluation_validation.py').is_file():
        raise FileNotFoundError('Original config/evaluation_validation.py missing')
    if not (ROOT/'research_a_orion_anytime/solver.py').is_file():
        raise FileNotFoundError('Place this independent directory next to the existing research_a_orion_anytime package')
    for case in cases:
        path = root/'data'/f'{case}.json'
        with path.open('rb') as f:
            first = f.read(160)
        if first.startswith(b'version https://git-lfs.github.com/spec/'):
            raise FileNotFoundError(f'{case}: only a Git LFS pointer is present; original payload is required')
    return root, config


def run_job(request, cap, baseline=None, seed_cost=0.0):
    started = time.monotonic()
    folder = Path(request['job'])
    folder.mkdir(parents=True, exist_ok=False)
    write(folder/'request.json', request)
    observations, peak = [], 0
    seed = request.get('seed_job')
    inherited, _ = incumbent_from_job(seed) if seed else (None, {})
    def observe(meta, phase, evaluations, stopped=False):
        value = meta.get('makespan') if meta else None
        elapsed = time.monotonic()-started
        observations.append(dict(elapsed_seconds=elapsed, total_elapsed_seconds=seed_cost+elapsed,
            best_makespan=value, baseline=baseline, speedup=baseline/value if baseline and value else None,
            added_copy_bytes=meta.get('added_copy_bytes') if meta else None,
            evaluations=evaluations, has_valid_incumbent=meta is not None, phase=phase, stopped=stopped))
    if inherited:
        observe(inherited['meta'], 'seed_available', 0)
        observations[-1].update(elapsed_seconds=0.0, total_elapsed_seconds=seed_cost)
    proc, state, timed_out = None, {}, False
    try:
        with (folder/'stdout.txt').open('w', encoding='utf-8') as stdout, (folder/'stderr.txt').open('w', encoding='utf-8') as stderr:
            proc = subprocess.Popen([sys.executable, '-m', 'research_a_orion_track_anytime.adapter', str(folder/'request.json')],
                cwd=ROOT, stdout=stdout, stderr=stderr,
                env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONHASHSEED': '0', 'OMP_NUM_THREADS': '1',
                     'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'})
            old_observation = None
            while True:
                if (folder/'progress.json').is_file():
                    state = read(folder/'progress.json')
                    meta = state.get('incumbent')
                    observation = (meta.get('plan_file') if meta else None, state.get('phase'), state.get('evaluations'))
                    if observation != old_observation:
                        observe(meta, state.get('phase', 'original_solver'), state.get('evaluations', 0))
                        write(folder/'observations.json', observations)
                        old_observation = observation
                try:
                    import psutil
                    peak = max(peak, psutil.Process(proc.pid).memory_info().rss)
                except (ImportError, OSError):
                    pass
                except Exception:
                    pass  # Resource observation cannot invalidate an original score.
                if proc.poll() is not None:
                    break
                if time.monotonic()-started >= cap:
                    timed_out = True
                    proc.kill()
                    proc.wait()
                    break
                time.sleep(min(.2, max(.001, cap-(time.monotonic()-started))))
    except BaseException:
        if proc and proc.poll() is None:
            proc.kill()
            proc.wait()
        raise
    if (folder/'progress.json').exists():
        state = read(folder/'progress.json')
    for row in state.get('attempts', []):
        if row.get('status') == 'running':
            row.update(status='interrupted_by_budget' if timed_out else 'worker_interrupted')
    meta = state.get('incumbent')
    observe(meta, 'stopped', state.get('evaluations', 0), True)
    write(folder/'observations.json', observations)
    elapsed = time.monotonic()-started
    result = dict(job=str(folder), status='ok' if meta else 'no_valid_solution',
                  hard_timeout=timed_out, process_seconds=elapsed, peak_rss_bytes=peak or None,
                  exit_code=proc.returncode, stopped=state.get('stopped') or ('hard_deadline' if timed_out else 'worker_exit'),
                  first_valid_parent_seconds=next((o['elapsed_seconds'] for o in observations if o['has_valid_incumbent']), None),
                  first_valid_child_seconds=state.get('first_valid_seconds'), evaluations=state.get('evaluations', 0),
                  construction_seconds=state.get('construction_seconds'), costs=state.get('costs', {}),
                  prefix_clock='parent-observed availability (conservative); no final-value backfill',
                  seed_solve_seconds=seed_cost, total_solve_seconds=seed_cost+elapsed)
    if meta:
        incumbent, _ = incumbent_from_job(folder)
        raw = incumbent['official_result']
        result.update(makespan=raw['makespan'], plan_file=incumbent['plan_file'], result_file=incumbent['result_file'],
                      added_copy_bytes=raw['data_movement_bytes']['added_copy_bytes'],
                      cache_hit_rate=raw.get('cache_stats', {}).get('hit_rate'),
                      lower=incumbent['response']['audit'].get('certificate', {}).get('global_lower'))
    if timed_out:
        state.update(stopped='hard_deadline', status=result['status'])
        write(folder/'progress.json', state)
    csv_write(folder/'improvement_events.csv', [dict(
        index=r.get('index'), name=r.get('name'), family=r.get('family'), makespan=r.get('makespan'),
        added_copy_bytes=r.get('added_copy_bytes'), child_completed_seconds=r.get('completed_seconds'),
        plan_file=r.get('plan_file'), result_file=r.get('result_file'),
        clock='child completion; availability prefixes remain parent-observed')
        for r in state.get('attempts', []) if r.get('status') == 'ok' and r.get('improved')])
    write(folder/'summary.json', result)
    return result


def prefixes(job, budget, seed_cost):
    observations = read(Path(job)/'observations.json')
    rows = []
    for clock, key in [('added', 'elapsed_seconds'), ('end_to_end', 'total_elapsed_seconds')]:
        for cutoff in PREFIXES:
            if cutoff > budget + (seed_cost if clock == 'end_to_end' else 0):
                continue
            seen = [r for r in observations if r[key] <= cutoff]
            selected = seen[-1] if seen else {}
            rows.append(dict(clock=clock, cutoff_seconds=cutoff,
                best_makespan=selected.get('best_makespan'), has_valid_incumbent=selected.get('has_valid_incumbent', False),
                status='stopped_incumbent_held' if selected.get('stopped') else 'observed_prefix' if seen else 'seed_prefix_unavailable',
                observed_seconds=selected.get(key)))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--official')
    parser.add_argument('--cases', nargs='+')
    parser.add_argument('--case-list', default=str(PACKAGE/'small_batch.json'))
    parser.add_argument('--questions', type=int, nargs='+', default=[1, 2, 3])
    parser.add_argument('--cores', type=int, nargs='+', default=[2, 5])
    parser.add_argument('--methods', nargs='+', choices=['old', 'budget', 'combined'], default=['old', 'budget', 'combined'])
    parser.add_argument('--modes', nargs='+', choices=['warm', 'cold'], default=['warm'])
    parser.add_argument('--seconds', type=float, default=300)
    parser.add_argument('--seed-seconds', type=float, default=30)
    parser.add_argument('--pair-seconds', type=float, default=120)
    parser.add_argument('--wall-seconds', type=float, default=7200)
    parser.add_argument('--max-evaluations', type=int, default=256)
    parser.add_argument('--workers', default='auto')
    parser.add_argument('--max-workers', type=int, default=1)
    parser.add_argument('--shards', type=int, default=1)
    parser.add_argument('--shard-index', type=int, default=0)
    parser.add_argument('--seed-index', help='JSON list: case,q,n,seed_job,seed_solve_seconds; prior costs must be known')
    parser.add_argument('--gap-tolerance', type=float, default=.005)
    parser.add_argument('--diagnostics', action='store_true')
    parser.add_argument('--run-id', default=time.strftime('%Y%m%d_%H%M%S'))
    parser.add_argument('--out')
    args = parser.parse_args(argv)
    if min(args.seconds, args.seed_seconds, args.pair_seconds, args.wall_seconds) <= 0:
        parser.error('All budgets must be positive')
    if args.max_evaluations < 1 or args.max_workers < 1 or args.gap_tolerance < 0:
        parser.error('Invalid counts or tolerance')
    if args.workers != 'auto' and (not args.workers.isdigit() or int(args.workers) < 1):
        parser.error('--workers must be auto or a positive integer')
    if args.shards < 1 or not 0 <= args.shard_index < args.shards:
        parser.error('Invalid shard')
    if not set(args.questions) <= {1, 2, 3} or not set(args.cores) <= {1, 2, 3, 4, 5}:
        parser.error('Questions are 1..3 and NPU cores are 1..5')
    cases = args.cases or read(args.case_list)['cases']
    cases = sorted(set(f'case_{int(str(c).removeprefix("case_")):03d}' for c in cases))
    assigned = cases[args.shard_index::args.shards]
    out = Path(args.out).resolve() if args.out else PACKAGE/'results'/args.run_id
    out.mkdir(parents=True, exist_ok=False)
    clock = time.monotonic()
    deadline = clock + args.wall_seconds
    manifest = dict(vars(args), assigned_cases=assigned, all_cases=cases, platform=platform.platform(),
                    python=sys.version, executable=sys.executable, experiment_status='not_started',
                    semantic_config_overrides=None, npu_cores_are_not_workers=True)
    write(out/'manifest.json', manifest)
    try:
        official, config = startup(args.official, assigned)
    except Exception as exc:
        write(out/'blocked.json', dict(status='startup_blocked', error=str(exc), real_graph_evaluations=0,
                                      measured_algorithm_comparison=False))
        print(str(exc), file=sys.stderr)
        return 2
    identity = dict(run_id=args.run_id, official=str(official), config=str(config),
                    python=sys.version, context='same immutable original files in this process session')
    external = {(r['case'], r['q'], r['n']): r for r in read(args.seed_index)} if args.seed_index else {}
    measurements, histories, curves, trajectories = [], [], [], []
    baselines = {}

    def request(case, q, n, name, seconds, method='old', seed_job=None, fixed_plan=None, calls=None):
        req = dict(identity={**identity, 'case': case}, official=str(official), config=str(config),
                   graph=str(official/'data'/f'{case}.json'), job=str(out/name), case=case, q=q, n=n,
                   seconds=seconds, max_evaluations=calls or args.max_evaluations,
                   method=method, strategy='anytime', gap_tolerance=args.gap_tolerance)
        if seed_job:
            req['seed_job'] = str(seed_job)
        if fixed_plan:
            req['fixed_plan'] = str(fixed_plan)
        return req

    # This is real official baseline evaluation, not a preflight or unit test.
    for case in assigned:
        cap = min(args.pair_seconds, deadline-time.monotonic())
        if cap <= .1:
            break
        req = request(case, 0, 1, f'baseline/{case}', cap, calls=1)
        baselines[case] = run_job(req, cap)
        histories.append(baselines[case])

    units = [(case, q, n, mode) for mode in args.modes for case in assigned
             for n in args.cores for q in args.questions]

    def unit(spec):
        case, q, n, mode = spec
        base = baselines.get(case, {}).get('makespan')
        if q in (1, 2) and n == 1:
            original = baselines.get(case, {})
            return [dict(original, case=case, q=q, n=n, mode=mode, method=m, baseline=base, run_id=args.run_id,
                         convention='original single-core baseline; no independent Q1/Q2 n1 optimization',
                         process_seconds=0.0, seed_solve_seconds=0.0, total_solve_seconds=0.0) for m in args.methods]
        prefix = f'{mode}/{case}_q{q}_n{n}'
        results, seed, seed_cost = [], None, 0.0
        if mode == 'warm':
            prior = external.get((case, q, n))
            if prior and prior.get('seed_solve_seconds') is None:
                raise ValueError('External seed cost missing: recover its original acquisition cost before comparison')
            seed_cost = float(prior['seed_solve_seconds']) if prior else 0.0
            if not math.isfinite(seed_cost) or seed_cost < 0:
                raise ValueError('Unknown seed cost must remain missing, not zero')
            original, prior_state = incumbent_from_job(prior['seed_job']) if prior else (None, {})
            if prior:
                if (prior_state.get('case'), prior_state.get('q'), prior_state.get('n')) != (case, q, n):
                    raise ValueError('External seed case/question/core mismatch')
                if original is None or len(original['plan']['core_schedules']) != n:
                    raise ValueError('External seed lacks a feasible plan with the requested core count')
            cap = min(args.seed_seconds if not prior else args.pair_seconds, deadline-time.monotonic())
            if cap <= .1:
                return []
            req = request(case, q, n, prefix+'/seed', cap, fixed_plan=original['plan_file'] if original else None,
                          calls=1 if original else 3)
            seed = run_job(req, cap, base, seed_cost)
            seed_cost += seed['process_seconds']
            if seed['status'] != 'ok':
                return [dict(case=case, q=q, n=n, mode=mode, method='seed', **seed)]
            if prior and original and seed['makespan'] == original['official_result']['makespan']:
                # Quality-only history. Historical machine timing is NEVER imported.
                old_state = read(Path(prior['seed_job'])/'progress.json')
                new_state = read(Path(seed['job'])/'progress.json')
                new_state['attempts'] = [dict(r, time_source='historical') for r in old_state.get('attempts', [])] + new_state.get('attempts', [])
                new_state['historical_quality_guard'] = 'same case/q/n and re-evaluated incumbent score; heuristic prior, not a source-identity certificate'
                write(Path(seed['job'])/'progress.json', new_state)
        order = list(args.methods)
        if (int(case[-3:]) + q + n) % 2:
            order.reverse()  # Counterbalance run order; no case-specific search policy.
        pairs_reserved = args.pair_seconds*len(order) if q == 3 else 0
        for method in order:
            cap = min(args.seconds, deadline-time.monotonic()-pairs_reserved)
            if cap <= .1:
                results.append(dict(case=case, q=q, n=n, mode=mode, method=method, status='not_started_deadline'))
                continue
            req = request(case, q, n, prefix+'/'+method, cap, method,
                          seed_job=seed['job'] if seed else None)
            result = run_job(req, cap, base, seed_cost)
            result.update(case=case, q=q, n=n, mode=mode, method=method, baseline=base,
                          run_id=args.run_id, requested_budget=args.seconds, admitted_budget=cap,
                          seed_cost_source=prior.get('cost_source') if mode == 'warm' and prior else 'same-host seed run' if mode == 'warm' else None)
            results.append(result)
        # Pair exactly each selected Q3 plan, after selection; no L2 result affects search.
        for result in results:
            if q != 3 or result['status'] != 'ok':
                continue
            cap = min(args.pair_seconds, deadline-time.monotonic())
            if cap <= .1:
                result['pair_status'] = 'not_started_deadline'
                continue
            req = request(case, 2, n, prefix+'/'+result['method']+'_no_l2', cap,
                          fixed_plan=result['plan_file'], calls=1)
            paired = run_job(req, cap, base)
            result.update(pair_status=paired['status'], pair_seconds=paired['process_seconds'],
                          no_l2_makespan=paired.get('makespan'), no_l2_result_file=paired.get('result_file'),
                          total_seconds_including_pair=result['total_solve_seconds']+paired['process_seconds'])
        return results

    waves = []
    position = 0
    while position < len(units) and time.monotonic() < deadline:
        workers, probe = worker_limit(args.workers, args.max_workers, histories)
        subset = units[position:position+workers]
        position += len(subset)
        waves.append(dict(workers=workers, probe=probe, units=subset, elapsed=time.monotonic()-clock))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(unit, spec) for spec in subset]
            for spec, future in zip(subset, futures):
                try:
                    rows = future.result()
                except Exception as exc:
                    rows = [dict(case=spec[0], q=spec[1], n=spec[2], mode=spec[3], method='unit',
                                 status='error', error=str(exc), traceback=traceback.format_exc())]
                measurements.extend(rows)
                histories.extend(rows)
        write(out/'worker_waves.json', waves)
        write(out/'measurements.json', measurements)
    for case, q, n, mode in units[position:]:
        for method in args.methods:
            measurements.append(dict(case=case, q=q, n=n, mode=mode, method=method, status='not_started_deadline'))
    old = {(r['case'], r['q'], r['n'], r['mode']): r for r in measurements if r['method'] == 'old'}
    per_case = []
    for r in measurements:
        control = old.get((r['case'], r['q'], r['n'], r['mode']), {})
        row = dict(case=r['case'], q=r['q'], n=r['n'], method=r['method'], run_id=args.run_id, mode={'warm': 'warm_start', 'cold': 'cold_start'}[r['mode']],
            status=r['status'], baseline=r.get('baseline'), old_makespan=control.get('makespan'), new_makespan=r.get('makespan'),
            old_added_copy_bytes=control.get('added_copy_bytes'), new_added_copy_bytes=r.get('added_copy_bytes'),
            seed_solve_seconds=r.get('seed_solve_seconds'), added_solve_seconds=r.get('process_seconds'),
            total_solve_seconds=r.get('total_solve_seconds'), construction_seconds=r.get('construction_seconds'),
            evaluations=r.get('evaluations'), lower=r.get('lower'), no_l2_makespan=r.get('no_l2_makespan'),
            cache_hit_rate=r.get('cache_hit_rate'), plan_file=r.get('plan_file'), result_file=r.get('result_file'),
            admitted_budget=r.get('admitted_budget'),
            matched_budget=(r.get('admitted_budget') is not None and control.get('admitted_budget') == r.get('admitted_budget')),
            pair_status=r.get('pair_status'), pair_seconds=r.get('pair_seconds'),
            first_valid_parent_seconds=r.get('first_valid_parent_seconds'), stopped=r.get('stopped'),
            **{k: r.get('costs', {}).get(k) for k in ('initialization_seconds', 'candidate_generation_seconds',
                 'official_eval_seconds', 'io_seconds', 'selection_other_seconds')})
        per_case.append(row)
        if r.get('job') and (Path(r['job'])/'observations.json').is_file():
            tag = {k: row[k] for k in ('case', 'q', 'n', 'method', 'run_id', 'mode')}
            trajectories.extend({**tag, **o} for o in read(Path(r['job'])/'observations.json'))
            curves.extend({**tag, **o} for o in prefixes(r['job'], r.get('admitted_budget', 0), r.get('seed_solve_seconds', 0)))
    csv_write(out/'per_case.csv', per_case)
    csv_write(out/'trajectory.csv', trajectories)
    csv_write(out/'budget_prefixes.csv', curves)
    write(out/'measurements.json', measurements)
    requested = len(units)*len(args.methods)
    completed = sum(r.get('status') == 'ok' and r['method'] in args.methods for r in measurements)
    complete_pairs = all(r.get('pair_status') == 'ok' for r in measurements if r['q'] == 3 and r['status'] == 'ok' and r['method'] in args.methods)
    baselines_complete = len(baselines) == len(assigned) and all(r['status'] == 'ok' for r in baselines.values())
    report = dict(baselines_complete=baselines_complete, requested_jobs=requested, valid_search_jobs=completed, pairs_complete=complete_pairs,
                  all_requested_complete=completed == requested and complete_pairs and baselines_complete,
                  formal_100_graph_claim=False, elapsed_seconds=time.monotonic()-clock,
                  acceptance='NOT AUTOMATIC: inspect same-host matched-budget rows, traces, and prefixes before expansion')
    write(out/'run_status.json', report)
    if args.diagnostics:
        from .diagnose import diagnose
        for r in measurements:
            if time.monotonic() >= deadline:
                break
            if r.get('q') == 3 and r.get('status') == 'ok' and r.get('result_file'):
                # Diagnostics gets a hard-capped separate process, never run unbounded here.
                command = [sys.executable, '-m', 'research_a_orion_track_anytime.diagnose', '--official', str(official),
                    '--config', str(config), '--graph', str(official/'data'/f"{r['case']}.json"), '--plan', r['plan_file'],
                    '--response', r['result_file'], '--out', str(Path(r['job'])/'diagnostics')]
                if r.get('no_l2_result_file'):
                    command += ['--no-l2', r['no_l2_result_file']]
                try:
                    subprocess.run(command, cwd=ROOT, timeout=min(args.pair_seconds, deadline-time.monotonic()), check=True)
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
                    write(Path(r['job'])/'diagnostic_error.json', dict(error=str(exc)))
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['all_requested_complete'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
