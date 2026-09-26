"""Recompute paper Q3 data from a portable snapshot and the copied PR60-62 CSVs.

No evaluator calls. Q1/Q2, original baselines, old timing traces and parameter
experiments are not overwritten. All statistics average per-instance ratios.
"""
from pathlib import Path
import csv, io, json, lzma, math, statistics

ROOT = Path(__file__).resolve().parent
MISSING_T0 = {'case_072', 'case_076', 'case_091'}


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def save(name, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with (ROOT / name).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        w.writerows(rows)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    content = lzma.decompress((ROOT / 'q3_latest_500.csv.xz').read_bytes()).decode('utf-8-sig')
    rows = list(csv.DictReader(io.StringIO(content)))
    indexed = {(r['case'], int(r['n'])): r for r in rows}
    wanted = {(f'case_{i:03d}', n) for i in range(1, 101) for n in range(1, 6)}
    require(len(rows) == 500 and set(indexed) == wanted, 'Incomplete/duplicate Q3 snapshot')
    baselines = {}
    for r in rows:
        value = int(r['reference_t1'])
        require(value > 0, 'Nonpositive original baseline')
        require(r['case'] not in baselines or baselines[r['case']] == value, 'Baseline varies by n')
        baselines[r['case']] = value
        require(int(r['makespan']) <= int(r['old_makespan']), 'Selected Q3 regressed')
        r['hit_precision'] = 'changed: original CSV; unchanged: prior paper six decimals'
    paths = [ROOT / 'sources' / f'shard_{i}' / 'q3_overlay.csv' for i in range(3)]
    present = [p.is_file() for p in paths]
    require(not any(present) or all(present), 'Partial source set: supply all three CSVs')
    have_raw = all(present)
    if have_raw:
        seen = set()
        for shard, path in enumerate(paths):
            original = read_csv(path)
            require(len(original) == (170 if shard == 0 else 165), 'Wrong shard count')
            for source in original:
                key = source['case'], int(source['n'])
                require(key not in seen and key in indexed, f'Duplicate/unexpected key: {key}')
                seen.add(key)
                row = indexed[key]
                require(int(source['q']) == 3 and int(row['shard']) == shard, 'Shard/question mismatch')
                for field in ('old_makespan', 'makespan', 'no_l2_makespan', 'added_copy_bytes', 'no_l2_added_copy_bytes'):
                    require(int(source[field]) == int(row[field]), f'Snapshot/source mismatch: {key} {field}')
                require(source['changed'].lower() == row['changed'].lower(), 'Change label mismatch')
                if source.get('reference_t1'):
                    require(int(source['reference_t1']) == baselines[key[0]], 'Original denominator differs')
                else:
                    require(key[0] in MISSING_T0, 'Unexpected missing patch denominator')
                require(source['pair_status'] in ('ok', 'inherited_exact_plan'), 'Unresolved same-plan pair')
                require(int(source['partition_added_copy_bytes']) + int(source['spill_added_copy_bytes']) == int(source['added_copy_bytes']), 'COPY decomposition differs')
                for field in ('cache_hit_rate', 'partition_added_copy_bytes', 'spill_added_copy_bytes', 'selected_name', 'pair_status'):
                    row[field] = source.get(field, '')
                row['hit_precision'] = 'original patch CSV'
        require(len(seen) == 500, 'Missing native rows')
    for r in rows:
        t0, t, old, no_l2 = (int(r[x]) for x in ('reference_t1', 'makespan', 'old_makespan', 'no_l2_makespan'))
        r.update(speedup=t0/t, old_speedup=t0/old, same_plan_cache_ratio=no_l2/t,
                 same_plan_no_l2_speedup=t0/no_l2, time_reduction=1-t/old,
                 denominator_missing_in_patch=r['case'] in MISSING_T0)
    stats = []
    for n in range(1, 6):
        rs = [r for r in rows if int(r['n']) == n]
        native = [r for r in rs if r['case'] not in MISSING_T0]
        ratios = [r['same_plan_cache_ratio'] for r in rs]
        stats.append({'n':n, 'count':len(rs), 'patch_denominator_count':len(native),
            'changed':sum(r['changed'].lower() == 'true' for r in rs),
            'old_mean_speedup':statistics.mean(r['old_speedup'] for r in rs),
            'new_mean_speedup':statistics.mean(r['speedup'] for r in rs),
            'patch97_mean_speedup':statistics.mean(r['speedup'] for r in native),
            'median_speedup':statistics.median(r['speedup'] for r in rs),
            'mean_same_plan_no_l2_speedup':statistics.mean(r['same_plan_no_l2_speedup'] for r in rs),
            'mean_cache_ratio':statistics.mean(ratios), 'median_cache_ratio':statistics.median(ratios),
            'cache_improved':sum(x>1 for x in ratios), 'cache_equal':sum(x==1 for x in ratios),
            'cache_regressed':sum(x<1 for x in ratios),
            'mean_hit_rate':statistics.mean(float(r['cache_hit_rate']) for r in rs),
            'mean_added_copy_bytes':statistics.mean(int(r['added_copy_bytes']) for r in rs)})
    require(sum(r['changed'].lower() == 'true' for r in rows) == 90, 'Expected 90 updates')
    require(math.isclose(stats[-1]['new_mean_speedup'], 4.633285839797243, rel_tol=1e-12), 'Five-core mean differs')
    save('q3_latest_500.regenerated.csv', rows)
    save('q3_core_summary.regenerated.csv', stats)
    output = {'rows':500, 'changed':90, 'native_csvs_read':have_raw,
              'paper_baselines':100, 'patch_nonempty_baselines':97,
              'five_core_mean':stats[-1]['new_mean_speedup'], 'simulation_calls':0,
              'precision':'full original patch hit rates' if have_raw else 'unchanged hit rates retain prior paper six-decimal display'}
    (ROOT/'REGENERATION.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    main()
