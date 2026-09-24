"""Extract selected FINAL raw records and reconcile them with published CSVs.

Use upstream transfer unpack first to relocate Windows paths. This reads only
requested cases; it is not a repository audit. No graph or official file changes.
"""
from __future__ import annotations
import argparse
import csv
from pathlib import Path
from .storage import read, write, incumbent_from_job
from .diagnose import csv_write
from .trace import read_requests


def records(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def key(row):
    return row['case'], int(row['q']), int(row['n'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--publication-root', required=True)
    p.add_argument('--raw-roots', nargs='+', required=True)
    p.add_argument('--cases', nargs='+', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    pub, out = Path(a.publication_root), Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    cases = {f'case_{int(c.removeprefix("case_")):03d}' for c in a.cases}
    tables = {}
    for name in ('per_case', 'lower_tail', 'improvements', 'budget_prefixes', 'cache_pairs'):
        tables[name] = [r for r in records(pub/(name+'.csv')) if r['case'] in cases]
        csv_write(out/(name+'_published.csv'), tables[name])
    published = {key(r): r for r in tables['per_case']}
    improvement = {key(r): r for r in tables['improvements']}
    selected, conflicts = {}, []
    for root in map(Path, a.raw_roots):
        # Never silently use pilot or an intermediate stage when final is missing.
        index = read(root/'final_index.json')
        for entry in index['chosen']:
            case, q, n = entry['key']
            if case not in cases or q == 0:
                continue
            summary_file = Path(entry['summary'])
            if not summary_file.is_absolute():
                summary_file = root/summary_file
            if not summary_file.is_file():
                raise FileNotFoundError(f'Unrelocated final summary: {summary_file}; unpack with the original transfer utility')
            k = (case, q, n)
            if k in selected:
                raise ValueError(f'Duplicate final key across supplied shards: {k}')
            selected[k] = summary_file
    seeds = []
    for k, summary_file in selected.items():
        summary = read(summary_file)
        incumbent, progress = incumbent_from_job(summary_file.parent)
        folder = out/f'{k[0]}_q{k[1]}_n{k[2]}'
        write(folder/'original_summary.json', summary)
        write(folder/'original_progress.json', progress)
        if not incumbent:
            conflicts.append(dict(key=k, reason='final record has no audited incumbent'))
            continue
        actual = incumbent['official_result']['makespan']
        reported = float(published[k]['makespan']) if k in published else None
        write(folder/'selected_plan.json', incumbent['plan'])
        write(folder/'official_response.json.gz', incumbent['response'])
        discrepancy = actual != reported or summary.get('makespan') != actual
        if discrepancy:
            conflicts.append(dict(key=k, original_response=actual, published=reported, summary=summary.get('makespan')))
        if k[1] == 3:
            reads, fills = read_requests(incumbent['official_result'])
            csv_write(folder/'original_cache_reads.csv', reads)
            csv_write(folder/'original_cache_fills.csv', fills)
        cost = improvement.get(k, {}).get('end_to_end_solve_seconds')
        if not discrepancy and cost not in (None, ''):
            seeds.append(dict(case=k[0], q=k[1], n=k[2], seed_job=str(summary_file.parent),
                              seed_solve_seconds=float(cost),
                              cost_source=str(pub/'improvements.csv')+':end_to_end_solve_seconds',
                              original_response_makespan=actual))
    missing = [k for k in published if k[1] != 0 and k not in selected]
    write(out/'seed_index.json', seeds)
    write(out/'reconciliation.json', dict(conflicts=conflicts, missing_raw_keys=missing,
         requested_cases=sorted(cases), selected_raw_keys=len(selected),
         passed=not conflicts and not missing, new_algorithm_experiments=False))


if __name__ == '__main__':
    main()
