"""Direct bounded A experiments. No smoke tests, hashes, or global audit.

The supervisor also bounds candidate construction, not only official calls.
Run from the repository root with python -m research_a_aster_rbc.run.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys
import time
from research_a.launch import ensure_inputs
from .worker import save
from .awake import keep_system_awake

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / 'research_a_aster_rbc' / 'runs'


def result_folder(out, job):
    """Resolve retained evidence without copying or rewriting the source run."""
    if not job.get('result_root'):
        return out / job['id']
    folder = Path(job['result_root'])
    folder = (folder if folder.is_absolute() else out / folder).resolve()
    if not folder.is_relative_to(RUNS.resolve()):
        raise ValueError(f'Retained result_root must stay under {RUNS}: {folder}')
    return folder


def kill_tree(process):
    if process.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def official_makespan(item):
    value = item.get('makespan') if isinstance(item, dict) and item.get('status') == 'ok' else None
    return value if isinstance(value, (int, float)) and math.isfinite(value) and value > 0 else None


def report(out, jobs, baseline_evidence=None):
    records = []
    baseline_evidence = baseline_evidence or {}
    baseline = {case: value['makespan'] for case, value in baseline_evidence.items()}
    baseline_paths = {case: value['result_path'] for case, value in baseline_evidence.items()}
    for job in jobs:
        path = result_folder(out, job) / 'result.json'
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            cycles = official_makespan(data.get('incumbent'))
            if job['question'] == 0 and cycles is not None:
                baseline[job['case']] = cycles
                baseline_paths[job['case']] = os.path.relpath(path, out)
    for job in jobs:
        path = result_folder(out, job) / 'result.json'
        data = {}
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                pass
        by_label = {x['label']: x for x in data.get('evaluations', [])}
        by_index = {x.get('index'): x for x in data.get('evaluations', [])}
        for label, index in data.get('aliases', {}).items():
            if index in by_index:
                by_label[label] = by_index[index]
        for label in (['original_singlecore'] if job['question'] == 0 else ['fast', 'components', 'best']):
            item = data.get('incumbent') if label == 'best' else by_label.get(label)
            item = item or {}
            cycles = item.get('makespan') if item.get('status') == 'ok' else None
            t1 = baseline.get(job['case'])
            pair = data.get('cache_pair') or {}
            records.append(dict(case=job['case'], question=job['question'], cores=job['cores'],
                variant=label, job_status=job['status'], result_status=data.get('status', 'not_started'),
                evaluation_status=item.get('status', 'not_evaluated'), makespan=cycles,
                original_singlecore=t1, speedup=t1 / cycles if t1 and cycles else None,
                baseline_result_path=baseline_paths.get(job['case']),
                partition_added_copy_bytes=item.get('partition_added_copy_bytes'),
                spill_added_copy_bytes=item.get('spill_added_copy_bytes'),
                cache_byte_hit_rate=item.get('cache_byte_hit_rate'),
                same_plan_cache_ratio=pair.get('ratio') if label == 'best' else None,
                solve_seconds=data.get('solve_seconds'), bound=data.get('bound'),
                conditional_ratio_bound=data.get('conditional_ratio_bound') if label == 'best' else None,
                machine=job['machine'], result_path=os.path.relpath(path, out),
                timing_affected_by_interruption=bool(job.get('timing_affected_by_interruption'))))
    if records:
        with (out / 'summary.csv').open('w', newline='', encoding='utf-8-sig') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    counts = {}
    for job in jobs:
        counts[job['status']] = counts.get(job['status'], 0) + 1
    save(out / 'coverage.json', dict(expected=len(jobs), supervisor_status_counts=counts,
        note='All jobs retained. A successful process is not proof of a successful official evaluation. See each result.json.'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', help='New output directory; default is timestamped under this package')
    parser.add_argument('--archive', help='Only when original A inputs are missing')
    parser.add_argument('--input-root', help='Existing repository root with A inputs, reused without copying')
    parser.add_argument('--cases', nargs='+', type=int, help='Optional explicit official case numbers')
    parser.add_argument('--cores', nargs='+', type=int, default=[2, 5])
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--wall-seconds', type=float, default=1800.)
    parser.add_argument('--job-seconds', type=float, default=120.)
    parser.add_argument('--eval-seconds', type=float, default=45.)
    parser.add_argument('--budget', type=int, default=6)
    parser.add_argument('--shards', type=int, default=1)
    parser.add_argument('--shard', type=int, default=0)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--continue-from', type=Path,
        help='Finished source run under this package runs/; retain every started job and run only not_started jobs in a new output directory')
    parser.add_argument('--only-job-ids', type=Path,
        help='JSON file containing unique job ID strings; execute only these jobs once in a new independent run')
    parser.add_argument('--baseline-from', type=Path,
        help='Finished run under this package runs/; reuse only its legal Q0 denominators, with legal Q0 from this run taking priority')
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        parser.error('Use Python 3.10+; existing Windows Python 3.12 is preferred')
    if args.workers < 1 or args.budget < 3 or args.job_seconds < 5 or args.eval_seconds <= 0 or args.wall_seconds <= 0:
        parser.error('Positive budgets required; job-seconds >=5 and budget >=3')
    if any(k < 1 or k > 5 for k in args.cores) or len(set(args.cores)) != len(args.cores):
        parser.error('Use distinct core counts in 1..5')
    if args.shards < 1 or not 0 <= args.shard < args.shards:
        parser.error('Require 0 <= shard < shards')
    if args.cases and (len(set(args.cases)) != len(args.cases) or any(not 1 <= n <= 100 for n in args.cases)):
        parser.error('Use distinct official case numbers in 1..100')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    out = Path(args.out) if args.out else ROOT / 'research_a_aster_rbc' / 'runs' / f'{stamp}_{platform.node()}_s{args.shard}'
    out = out.resolve()
    explicit_job_ids = None
    baseline_source = None
    baseline_manifest = {}
    baseline_jobs = []
    baseline_evidence = {}
    baseline_unavailable = {}
    if args.only_job_ids:
        if args.continue_from or args.resume or args.shards != 1 or args.shard != 0:
            parser.error('--only-job-ids requires a fresh unsharded run and cannot combine with --continue-from/--resume')
        try:
            explicit_job_ids = json.loads(args.only_job_ids.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError) as exc:
            parser.error(f'Cannot read --only-job-ids: {exc}')
        if (not isinstance(explicit_job_ids, list) or not explicit_job_ids
                or not all(isinstance(value, str) for value in explicit_job_ids)
                or len(explicit_job_ids) != len(set(explicit_job_ids))):
            parser.error('--only-job-ids must contain a nonempty JSON array of unique strings')
        explicit_cases = set()
        for identifier in explicit_job_ids:
            match = re.fullmatch(r'case_(\d{3})_q([0-3])_n([1-5])', identifier)
            if not match:
                parser.error(f'Invalid explicit job ID: {identifier}')
            case_number, question, cores = map(int, match.groups())
            if not 1 <= case_number <= 100 or (question == 0 and cores != 1) or (question != 0 and cores not in args.cores):
                parser.error(f'Explicit job ID conflicts with official case/core settings: {identifier}')
            explicit_cases.add(case_number)
        if args.cases and not explicit_cases.issubset(args.cases):
            parser.error('--cases omits cases required by --only-job-ids')
        args.cases = sorted(explicit_cases)
        if out.exists() or not out.is_relative_to(RUNS.resolve()):
            parser.error('Targeted retries require a new, nonexistent output directory under runs/')
    if args.baseline_from:
        if not explicit_job_ids:
            parser.error('--baseline-from is only available with --only-job-ids')
        baseline_source = args.baseline_from
        if not baseline_source.exists():
            baseline_source = ROOT / 'research_a_aster_rbc' / baseline_source
        baseline_source = baseline_source.resolve()
        if not baseline_source.is_dir() or not baseline_source.is_relative_to(RUNS.resolve()) or not (baseline_source / 'run_status.json').is_file():
            parser.error('--baseline-from must be a finished run under this package runs/')
        if out.is_relative_to(baseline_source):
            parser.error('Retry output must be outside its baseline source run')
        try:
            baseline_manifest = json.loads((baseline_source / 'manifest.json').read_text(encoding='utf-8-sig'))
            baseline_jobs = json.loads((baseline_source / 'jobs.json').read_text(encoding='utf-8-sig'))
        except (OSError, ValueError) as exc:
            parser.error(f'Cannot read baseline source: {exc}')
        if not isinstance(baseline_manifest, dict) or not isinstance(baseline_jobs, list):
            parser.error('Invalid baseline source manifest/jobs')
    source = None
    source_manifest = None
    source_jobs = None
    source_interruption = {}
    if args.continue_from:
        if args.resume:
            parser.error('--continue-from and --resume cannot be combined')
        source = args.continue_from
        if not source.exists():
            source = ROOT / 'research_a_aster_rbc' / source
        source = source.resolve()
        if not source.is_dir() or not source.is_relative_to(RUNS.resolve()):
            parser.error('--continue-from must name an existing directory under this package runs/')
        if not (source / 'run_status.json').is_file():
            parser.error('Source run has no final run_status.json; do not continue an active or unfinalized run')
        if out.exists() or not out.is_relative_to(RUNS.resolve()) or out.is_relative_to(source):
            parser.error('Continuation requires a new, nonexistent output directory under runs/, outside the source run')
        try:
            source_manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8-sig'))
            source_jobs = json.loads((source / 'jobs.json').read_text(encoding='utf-8-sig'))
            if (source / 'interruption.json').is_file():
                source_interruption = json.loads((source / 'interruption.json').read_text(encoding='utf-8-sig'))
        except (OSError, ValueError) as exc:
            parser.error(f'Cannot read continuation evidence: {exc}')
        if not isinstance(source_manifest, dict) or not isinstance(source_jobs, list) or not isinstance(source_interruption, dict):
            parser.error('Source manifest/jobs/interruption has an invalid structure')
    if (out / 'manifest.json').exists() and not args.resume:
        parser.error('Output already has a manifest; use a new directory or explicit --resume')
    # Start total budget before input preparation. No experiment starts after it.
    start = time.perf_counter()
    deadline = start + args.wall_seconds
    if source is None:
        out.mkdir(parents=True, exist_ok=True)
    attachment = ensure_inputs(Path(args.input_root).resolve() if args.input_root else ROOT, args.archive)
    data = attachment / 'data'
    if args.cases:
        selected = [data / f'case_{n:03d}.json' for n in args.cases]
    elif source is not None:
        # The source's preselected population is retained, never reselected by scores.
        selected = [data / name for name in source_manifest.get('cases', [])]
    else:
        available = sorted(data.glob('case_*.json'), key=lambda p: (p.stat().st_size, p.name))
        if len(available) < 6:
            parser.error('Need six real A inputs or specify --cases')
        # File-size strata, fixed before evaluation; not selected for observed wins.
        selected = [available[round(i * (len(available) - 1) / 5)] for i in range(6)]
    for path in selected:
        if not path.is_file():
            parser.error(f'Missing case: {path}')
    manifest = dict(cases=[p.name for p in selected], cores=args.cores, questions=[1, 2, 3],
        budget=args.budget, job_seconds=args.job_seconds, eval_seconds=args.eval_seconds,
        shard=args.shard, shards=args.shards, python=sys.version, machine=platform.node(),
        python_executable=sys.executable, workers=args.workers, wall_seconds=args.wall_seconds,
        input_root=str(Path(args.input_root).resolve()) if args.input_root else str(ROOT),
        code_root=str(ROOT),
        input_selection=source_manifest.get('input_selection') if source is not None else ('explicit' if args.cases else 'six_file_size_quantiles'),
        implementation='ASTER-RBC revision 2: bounded independent component moves; same construction and budgets')
    if explicit_job_ids is not None:
        manifest.update(explicit_job_ids=explicit_job_ids, only_job_ids_file=str(args.only_job_ids.resolve()),
            input_selection='explicit_job_ids', run_kind='targeted_retry',
            retry_policy='One attempt per listed job in this independent output. Scores from other multicore runs are not imported. Different budgets do not form a fixed-budget complete 100-case result.')
    if baseline_source is not None:
        for key in ('input_root', 'code_root'):
            if not baseline_manifest.get(key) or Path(baseline_manifest[key]).resolve() != Path(manifest[key]).resolve():
                parser.error(f'Baseline source differs in {key}')
        wanted_cases = {path.stem for path in selected}
        baseline_seen = set()
        for job in baseline_jobs:
            if not isinstance(job, dict) or job.get('question') != 0 or job.get('case') not in wanted_cases:
                continue
            case = job['case']
            if case in baseline_seen or job.get('cores') != 1:
                parser.error(f'Invalid or duplicate source Q0 denominator: {case}')
            baseline_seen.add(case)
            expected_paths = {'graph': data / f'{case}.json', 'config': data / 'config.txt', 'code': attachment / 'code'}
            for key, expected_path in expected_paths.items():
                if not job.get(key) or Path(job[key]).resolve() != expected_path.resolve():
                    parser.error(f'Baseline source {case} differs in {key}')
            try:
                baseline_path = result_folder(baseline_source, job) / 'result.json'
                if not baseline_path.is_file():
                    continue
                baseline_data = json.loads(baseline_path.read_text(encoding='utf-8-sig'))
            except (OSError, ValueError) as exc:
                parser.error(f'Cannot read baseline {case}: {exc}')
            cycles = official_makespan(baseline_data.get('incumbent'))
            if cycles is not None:
                try:
                    raw_baseline = json.loads((baseline_path.parent / 'best_official.json').read_text(encoding='utf-8-sig'))
                    raw_cycles = raw_baseline.get('makespan')
                except (OSError, ValueError):
                    raw_cycles = None
                if (not isinstance(raw_cycles, (int, float)) or not math.isfinite(raw_cycles)
                        or raw_cycles <= 0 or not math.isclose(cycles, raw_cycles, rel_tol=1e-10, abs_tol=1e-6)):
                    baseline_unavailable[case] = 'Missing or inconsistent saved official Q0 Makespan; denominator left blank'
                    continue
                baseline_evidence[case] = dict(makespan=cycles, result_path=os.path.relpath(baseline_path, out),
                    timing_affected_by_interruption=bool(job.get('timing_affected_by_interruption')))
        manifest.update(baseline_from=str(baseline_source), baseline_source_manifest=baseline_manifest,
            baseline_evidence=baseline_evidence, baseline_unavailable=baseline_unavailable,
            baseline_policy='Reuse only saved legal original whole-graph Q0. A legal Q0 from this retry takes priority; missing/failed denominators remain blank.')
    if source is not None:
        immutable = ('cases', 'cores', 'questions', 'budget', 'job_seconds', 'eval_seconds',
                     'shard', 'shards', 'python', 'machine', 'input_selection', 'implementation')
        changed = [key for key in immutable if source_manifest.get(key) != manifest[key]]
        for key in ('python_executable', 'input_root', 'code_root'):
            if not source_manifest.get(key) or Path(source_manifest[key]).resolve() != Path(manifest[key]).resolve():
                changed.append(key)
        if changed:
            parser.error('Continuation immutable parameters differ: ' + ', '.join(changed))
        manifest.update(continued_from=str(source), continuation_source_manifest=source_manifest,
            continuation_policy='Retain all previously started logical jobs by result_root; execute only source not_started jobs. No per-case best-of-version selection.')
        if source_interruption:
            manifest['continued_from_interruption'] = os.path.relpath(source / 'interruption.json', out)
            manifest['continuation_source_interruption'] = source_interruption
    prior = out / 'manifest.json'
    if prior.exists():
        old = json.loads(prior.read_text(encoding='utf-8'))
        if old != manifest:
            parser.error('Resume parameters/environment differ; use a new directory, no fingerprint audit needed')
    elif source is None:
        save(prior, manifest)
    jobs = []
    for i, path in enumerate(selected):
        if i % args.shards != args.shard:
            continue
        specs = [(0, 1)] + [(q, k) for k in args.cores for q in (1, 2, 3)]
        for q, k in specs:
            identifier = f'{path.stem}_q{q}_n{k}'
            item = dict(id=identifier, case=path.stem, graph=str(path.resolve()), question=q,
                cores=k, config=str((data / 'config.txt').resolve()),
                code=str((attachment / 'code').resolve()), budget=args.budget,
                eval_seconds=args.eval_seconds, job_seconds=args.job_seconds,
                machine=platform.node(), status='not_started')
            result_path = out / identifier / 'result.json'
            if args.resume and result_path.is_file():
                previous = json.loads(result_path.read_text(encoding='utf-8'))
                # Never overwrite partial/failed trajectories during a resume.
                # Reruns for those cases belong in a new output directory.
                item['status'] = 'retained_' + previous.get('status', 'partial')
            elif args.resume and any((out / item['id'] / name).exists()
                    for name in ('request.json', 'job.log', 'worker_error.json')):
                # A worker may fail before its first result checkpoint. Retrying
                # here would overwrite the request and truncate the failure log.
                parser.error(f"Resume job {item['id']} has prior attempt evidence but no result.json; use a new directory with --only-job-ids")
            jobs.append(item)
    if explicit_job_ids is not None:
        requested_ids = set(explicit_job_ids)
        jobs = [job for job in jobs if job['id'] in requested_ids]
        if {job['id'] for job in jobs} != requested_ids:
            parser.error('Some explicit job IDs do not match the requested case/question/core population')
    if source is not None:
        previous_by_id = {}
        for previous in source_jobs:
            if not isinstance(previous, dict) or not previous.get('id') or previous['id'] in previous_by_id:
                parser.error('Source jobs.json contains an invalid or duplicate job id')
            previous_by_id[previous['id']] = previous
        if set(previous_by_id) != {job['id'] for job in jobs}:
            parser.error('Source logical job population differs from the requested case/question/core population')
        retained = 0
        timing_affected = set(source_interruption.get('timing_affected_jobs', []))
        for position, job in enumerate(jobs):
            previous = previous_by_id[job['id']]
            for key in ('case', 'question', 'cores', 'budget', 'eval_seconds', 'job_seconds', 'machine'):
                if previous.get(key) != job[key]:
                    parser.error(f'Source job {job["id"]} differs in immutable parameter {key}')
            for key in ('graph', 'config', 'code'):
                if not previous.get(key) or Path(previous[key]).resolve() != Path(job[key]).resolve():
                    parser.error(f'Source job {job["id"]} differs in input/config/evaluator path {key}')
            if not isinstance(previous.get('status'), str):
                parser.error(f'Source job {job["id"]} has no valid status')
            try:
                previous_folder = result_folder(source, previous).resolve()
            except ValueError as exc:
                parser.error(str(exc))
            if previous['status'] == 'not_started':
                # An inconsistent status must not cause a hidden rerun/overwrite.
                for evidence_folder in {previous_folder, source / job['id']}:
                    if (evidence_folder / 'request.json').exists() or (evidence_folder / 'result.json').exists():
                        parser.error(f'Source not_started job already has request/result evidence: {job["id"]}')
                continue
            carried = dict(previous)
            carried['result_root'] = os.path.relpath(previous_folder, out)
            carried['retained_from'] = str(source)
            carried['timing_affected_by_interruption'] = bool(previous.get('timing_affected_by_interruption') or job['id'] in timing_affected)
            jobs[position] = carried
            retained += 1
        manifest['retained_job_count'] = retained
        manifest['pending_job_count'] = len(jobs) - retained
        out.mkdir(parents=True, exist_ok=False)
        save(prior, manifest)
    # Breadth-first across cases and questions; don't leave Q3 until the end.
    jobs.sort(key=lambda j: (j['question'] != 0, j['cores'], j['case'], j['question']))
    pending = [j for j in jobs if j['status'] == 'not_started']
    if source is not None or explicit_job_ids is not None:
        save(out / 'jobs.json', jobs)
        report(out, jobs, baseline_evidence)
    running = []
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
    try:
        while (pending or running) and time.perf_counter() < deadline:
            while pending and len(running) < args.workers and time.perf_counter() < deadline - 2.:
                job = pending.pop(0)
                folder = out / job['id']
                if (source is not None or explicit_job_ids is not None) and ((folder / 'request.json').exists() or (folder / 'result.json').exists()):
                    raise FileExistsError(f'Refusing to overwrite continuation job evidence: {folder}')
                save(folder / 'request.json', job)
                stream = (folder / 'job.log').open('w', encoding='utf-8')
                command = [sys.executable, '-X', 'utf8', '-u', '-m', 'research_a_aster_rbc.worker', str(folder / 'request.json')]
                options = dict(cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
                if os.name == 'nt':
                    options['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
                else:
                    options['start_new_session'] = True
                process = subprocess.Popen(command, **options)
                job['status'] = 'running'
                running.append((process, stream, job, time.perf_counter()))
                print(f'START {job["id"]}', flush=True)
            for entry in list(running):
                process, stream, job, began = entry
                expired = time.perf_counter() - began >= args.job_seconds
                if process.poll() is not None or expired:
                    if expired and process.poll() is None:
                        kill_tree(process)
                        job['status'] = 'job_timeout'
                    else:
                        job['status'] = 'process_ok' if process.returncode == 0 else 'process_error'
                    stream.close()
                    running.remove(entry)
                    print(f'END {job["id"]}: {job["status"]}', flush=True)
                    save(out / 'jobs.json', jobs)
                    report(out, jobs, baseline_evidence)
            time.sleep(.1)
    except KeyboardInterrupt:
        print('Interrupted; retaining all completed official results.', flush=True)
    finally:
        for process, stream, job, _ in running:
            kill_tree(process)
            stream.close()
            job['status'] = 'stopped_at_limit_or_interrupt'
        save(out / 'jobs.json', jobs)
        report(out, jobs, baseline_evidence)
        save(out / 'run_status.json', dict(elapsed_seconds=time.perf_counter() - start,
            wall_seconds=args.wall_seconds, note='Shutdown/reporting may add several seconds. No automatic budget extension.'))
        print(f'Results: {out}', flush=True)


if __name__ == '__main__':
    with keep_system_awake():
        main()
