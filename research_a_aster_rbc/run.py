"""Direct bounded A experiments. No smoke tests, hashes, or global audit.

The supervisor also bounds candidate construction, not only official calls.
Run from the repository root with python -m research_a_aster_rbc.run.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
from research_a.launch import ensure_inputs
from .worker import save

ROOT = Path(__file__).resolve().parents[1]


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


def report(out, jobs):
    records = []
    baseline = {}
    for job in jobs:
        path = out / job['id'] / 'result.json'
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            if job['question'] == 0 and data.get('incumbent'):
                baseline[job['case']] = data['incumbent']['makespan']
    for job in jobs:
        path = out / job['id'] / 'result.json'
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
                partition_added_copy_bytes=item.get('partition_added_copy_bytes'),
                spill_added_copy_bytes=item.get('spill_added_copy_bytes'),
                cache_byte_hit_rate=item.get('cache_byte_hit_rate'),
                same_plan_cache_ratio=pair.get('ratio') if label == 'best' else None,
                solve_seconds=data.get('solve_seconds'), bound=data.get('bound'),
                conditional_ratio_bound=data.get('conditional_ratio_bound') if label == 'best' else None,
                machine=job['machine'], result_path=str(path.relative_to(out))))
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
    if (out / 'manifest.json').exists() and not args.resume:
        parser.error('Output already has a manifest; use a new directory or explicit --resume')
    # Start total budget before input preparation. No experiment starts after it.
    start = time.perf_counter()
    deadline = start + args.wall_seconds
    out.mkdir(parents=True, exist_ok=True)
    attachment = ensure_inputs(ROOT, args.archive)
    data = attachment / 'data'
    if args.cases:
        selected = [data / f'case_{n:03d}.json' for n in args.cases]
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
        input_selection='explicit' if args.cases else 'six_file_size_quantiles',
        implementation='ASTER-RBC initial implementation; performance unverified')
    prior = out / 'manifest.json'
    if prior.exists():
        old = json.loads(prior.read_text(encoding='utf-8'))
        if old != manifest:
            parser.error('Resume parameters/environment differ; use a new directory, no fingerprint audit needed')
    else:
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
            jobs.append(item)
    # Breadth-first across cases and questions; don't leave Q3 until the end.
    jobs.sort(key=lambda j: (j['question'] != 0, j['cores'], j['case'], j['question']))
    pending = [j for j in jobs if j['status'] == 'not_started']
    running = []
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
    try:
        while (pending or running) and time.perf_counter() < deadline:
            while pending and len(running) < args.workers and time.perf_counter() < deadline - 2.:
                job = pending.pop(0)
                folder = out / job['id']
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
                    report(out, jobs)
            time.sleep(.1)
    except KeyboardInterrupt:
        print('Interrupted; retaining all completed official results.', flush=True)
    finally:
        for process, stream, job, _ in running:
            kill_tree(process)
            stream.close()
            job['status'] = 'stopped_at_limit_or_interrupt'
        save(out / 'jobs.json', jobs)
        report(out, jobs)
        save(out / 'run_status.json', dict(elapsed_seconds=time.perf_counter() - start,
            wall_seconds=args.wall_seconds, note='Shutdown/reporting may add several seconds. No automatic budget extension.'))
        print(f'Results: {out}', flush=True)


if __name__ == '__main__':
    main()
