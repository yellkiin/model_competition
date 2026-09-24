"""Read completed real jobs once and report progress; no evaluator calls."""
from __future__ import annotations
import json
import math
import os
from pathlib import Path
import sys
from collections import Counter


RUNS = Path(__file__).resolve().parent / 'runs'


def result_folder(run, job):
    folder = Path(job.get('result_root') or job['id'])
    folder = (folder if folder.is_absolute() else run / folder).resolve()
    if not folder.is_relative_to(RUNS.resolve()):
        raise ValueError(f'result_root must remain under this package runs/: {folder}')
    return folder


def main(folder):
    path = Path(folder).resolve()
    jobs = json.loads((path / 'jobs.json').read_text(encoding='utf-8'))
    cache_path = path / 'progress_cache.json'
    cache = json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
    interruption_path = path / 'interruption.json'
    interruption = json.loads(interruption_path.read_text(encoding='utf-8')) if interruption_path.exists() else {}
    timing_affected_jobs = set(interruption.get('timing_affected_jobs', []))
    job_ids = {job['id'] for job in jobs}
    cache = {key: value for key, value in cache.items() if key in job_ids}
    for job in jobs:
        if job['status'] == 'not_started' or (job['status'] == 'running' and not job.get('result_root')):
            continue
        evidence_folder = result_folder(path, job)
        evidence_relative = os.path.relpath(evidence_folder, path)
        timing_affected = bool(job.get('timing_affected_by_interruption') or job['id'] in timing_affected_jobs)
        cached = cache.get(job['id'], {})
        if (cached.get('evidence_version') == 2 and cached.get('result_root') == evidence_relative
                and cached.get('timing_affected_by_interruption') == timing_affected
                and cached.get('supervisor_status') == job['status']):
            continue
        result_path = evidence_folder / 'result.json'
        result = json.loads(result_path.read_text(encoding='utf-8')) if result_path.exists() else {}
        item = result.get('incumbent') or {}
        makespan = item.get('makespan')
        legal = item.get('status') == 'ok' and isinstance(makespan, (int, float)) and math.isfinite(makespan) and makespan > 0
        timeout = job['status'] in ('job_timeout', 'stopped_at_limit_or_interrupt') or any(e.get('status') == 'timeout' for e in result.get('evaluations', []))
        complete = (result.get('status') == 'complete' and not timing_affected
            and job['status'] not in ('running', 'job_timeout', 'process_error', 'stopped_at_limit_or_interrupt')
            and (job['question'] != 3 or bool(result.get('cache_pair'))))
        state = ('complete' if complete else 'partial') if legal else ('timeout' if timeout else 'failed')
        cache[job['id']] = dict(question=job['question'], state=state,
            evidence_version=2, result_root=evidence_relative, supervisor_status=job['status'],
            timing_affected_by_interruption=timing_affected,
            bound_violation=bool(result.get('bound_violation')), cache_pair=bool(result.get('cache_pair')),
            evaluations=len(result.get('evaluations', [])), solve_seconds=result.get('solve_seconds'))
    summary = {}
    for question in range(4):
        selected = [x for x in cache.values() if x['question'] == question]
        summary['Q' + str(question)] = dict(planned=sum(j['question'] == question for j in jobs),
            finished=len(selected), **dict(Counter(x['state'] for x in selected)))
    output = dict(finished=len(cache), total=len(jobs), by_question=summary,
        bound_violations=[key for key, item in cache.items() if item['bound_violation']],
        recorded_cache_pairs=sum(x['question'] == 3 and x['cache_pair'] for x in cache.values()),
        evaluations=sum(x['evaluations'] for x in cache.values()),
        timing_affected_jobs=[key for key, item in cache.items() if item.get('timing_affected_by_interruption')],
        supervisor_complete=(path / 'run_status.json').exists())
    cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding='utf-8')
    (path / 'progress.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    main(sys.argv[1])
