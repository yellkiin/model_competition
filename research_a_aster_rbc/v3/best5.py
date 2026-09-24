"""Run the fixed strongest measured V3 policy directly on five cores, all questions.

No separate fast-mode/ablation/budget grid. No smoke tests or fingerprints.
The first-plan metric is taken from the same full solve, not an extra experiment.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
import os
from pathlib import Path
import platform
import sys
import time
from .job import run_job
from .model import read_json
from .policy import VERSION
from .reporting import aggregate
from .session import dump

ROOT = Path(__file__).resolve().parents[2]
HOLDOUT_CASES = [3, 7, 12, 20, 28, 35, 47, 56, 65, 76, 88, 94]


def main(argv=None):
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--official-dir')
    parser.add_argument('--cases', type=int, nargs='+', default=HOLDOUT_CASES)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--wall-seconds', type=float, default=900.)
    parser.add_argument('--out')
    parser.add_argument('--shards', type=int, default=1)
    parser.add_argument('--shard', type=int, default=0)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args(argv)
    if args.workers < 1 or args.wall_seconds <= 0 or args.shards < 1 or not 0 <= args.shard < args.shards:
        parser.error('invalid workers, wall cap or shard')
    cases = sorted(set(args.cases))
    if any(c < 1 or c > 100 for c in cases): parser.error('cases must be 1..100')
    cases = [c for i, c in enumerate(cases) if i % args.shards == args.shard]
    if not cases: parser.error('empty shard')
    if args.resume and not args.out: parser.error('--resume requires --out')
    if args.official_dir:
        official = Path(args.official_dir).expanduser().resolve()
    else:
        found = sorted((ROOT / '题目' / 'A题').glob('*附件'))
        if len(found) != 1: parser.error('pass --official-dir pointing to code/ and data/')
        official = found[0]
    config, code = official / 'data/config.txt', official / 'code'
    required = [config] + [official / f'data/case_{c:03d}.json' for c in cases]
    required += [code / name for name in ('contest_io.py', 'evaluation_validation.py', 'schedule_step1.py',
        'schedule_step2.py', 'schedule_step3.py', 'singlecore_evaluate.py',
        'multicore_cut_evaluate_problem_1.py', 'multicore_cut_evaluate_problem_2.py', 'multicore_cut_evaluate_problem_3.py')]
    for path in required:
        if not path.is_file(): parser.error(f'Missing A input; restore only A inputs: {path}')
        with path.open('rb') as f: head = f.read(128)
        if not head or head.startswith(b'version https://git-lfs.github.com/spec/v1'):
            parser.error(f'Empty input/LFS pointer; restore only A inputs: {path}')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%f')
    out = Path(args.out).resolve() if args.out else ROOT / 'research_a_aster_rbc/v3/runs' / f'best5_{stamp}_{os.getpid()}'
    protocol = dict(version=VERSION, preset='best5-8eval-90s', cases=cases, cores=[5], questions=[1,2,3],
                    mode='full', budget=8, job_seconds=90., eval_seconds=45., baseline_seconds=120.,
                    gap_tolerance=.03, shards=args.shards, shard=args.shard, official_dir=str(official),
                    config_text=config.read_text(encoding='utf-8-sig'))
    jobs = []
    for c in cases:
        # All three questions appear near the start; the large baseline is not a serial precondition.
        jobs.extend(dict(id=f'case_{c:03d}_q{q}_n{1 if q == 0 else 5}', case=c, q=q, n=1 if q == 0 else 5)
                    for q in (1, 2, 3, 0))
    manifest = dict(settings=protocol, jobs=jobs, machine=platform.node(), python=sys.version, created_utc=stamp)
    if args.resume:
        previous = read_json(out / 'manifest.json')
        if previous['settings'] != protocol: parser.error('different protocol; use a new output directory')
        manifest = previous
    else:
        out.mkdir(parents=True, exist_ok=False); dump(out / 'manifest.json', manifest)
    pending = [j for j in jobs if not (out / j['id']).exists()]
    deadline = started + args.wall_seconds
    active, cursor = {}, 0
    print(f'Output: {out}; jobs not yet started: {len(pending)}', flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        while active or cursor < len(pending) and time.monotonic() < deadline:
            while len(active) < args.workers and cursor < len(pending) and time.monotonic() < deadline:
                job = pending[cursor]; cursor += 1
                request = dict(job, graph=str(official / f'data/case_{job["case"]:03d}.json'),
                    config=str(config), code=str(code), job_seconds=122. if job['q']==0 else 90.,
                    eval_seconds=120. if job['q']==0 else 45., budget=8, gap_tolerance=.03, mode='full')
                active[pool.submit(run_job, request, out / job['id'], deadline)] = job
            if not active: break
            done, _ = wait(active, timeout=.25, return_when=FIRST_COMPLETED)
            for future in done:
                job = active.pop(future)
                try:
                    result = future.result()
                    print(job['id'], result['status'], (result.get('incumbent') or {}).get('makespan'), flush=True)
                except Exception as error:
                    path = out / job['id'] / 'result.json'
                    result = read_json(path) if path.exists() else dict(case=job['case'], q=job['q'], n=job['n'], attempts=[], incumbent=None)
                    result.update(status='partial' if result.get('incumbent') else 'failed', controller_error=str(error))
                    dump(path, result)
                    print(job['id'], 'controller_error', error, flush=True)
    aggregate(out, manifest)
    dump(out / 'run_receipt.json', dict(version=VERSION, elapsed_wall_seconds=time.monotonic()-started,
         requested_wall_seconds=args.wall_seconds, workers=args.workers, resume=args.resume))
    print(f'Report: {out / "REPORT.md"}', flush=True)
    return out


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError, KeyError) as exc: raise SystemExit(str(exc))
