"""Performance tables, graph-level paired analysis, diagnoses and runnable repairs."""
from __future__ import annotations
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import csv
import itertools
import math
from pathlib import Path
import random
import statistics
from .model import Graph, Plan, read_json, settings, write_json
from .solver import search
from .evaluator import Official


def csv_file(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text('', encoding='utf-8')
        return
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: v for k, v in row.items() if not isinstance(v, (dict, list))})


def bootstrap_mean(values, seed=0, repeats=1000):
    """Graph resampling sensitivity interval, NOT a population confidence claim."""
    if not values:
        return None, None
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(repeats))
    return means[int(.025 * repeats)], means[min(repeats - 1, int(.975 * repeats))]


def records(source: Path):
    spec = read_json(source / 'run.json')
    rows = []
    for case, q, n, v, s in itertools.product(spec['cases'], spec['questions'], spec['cores'], spec['variants'], spec['seeds']):
        if (v == 'no_cache' and q != 3) or (v == 'rr' and s != spec['seeds'][0]):
            continue
        directory = source / case / f'q{q}_n{n}_{v}_s{s}'
        row = dict(case=case, question=q, cores=n, variant=v, seed=s, status='missing',
                   speedup=None, directory=str(directory.resolve()), split=spec.get('case_splits', {}).get(case),
                   graph_path=spec.get('case_paths', {}).get(case))
        if (directory / 'search.json').exists():
            row.update(read_json(directory / 'search.json'))
        if row['status'] == 'ok' and (directory / 'best_metrics.json').exists():
            row.update(read_json(directory / 'best_metrics.json'))
        proxy_file = directory / 'best_proxy.json'
        if proxy_file.exists():
            proxy = read_json(proxy_file)
            row.update(pre_spill_bytes_predicted=proxy['pre_spill_bytes'],
                       cache_hit_bytes_predicted=proxy['cache_hit_bytes_proxy'],
                       excess_residency_bytes_predicted=proxy.get('excess_bytes'))
            if row.get('scheduled_copy_bytes') is not None:
                row['pre_spill_formula_error'] = proxy['pre_spill_bytes'] - (row['scheduled_copy_bytes'] - row.get('spill_added_copy_bytes', 0))
        rows.append(row)
    return spec, rows


def summaries(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['question'], row['cores'], row['variant']].append(row)
    output = []
    for (q, n, variant), group in sorted(grouped.items()):
        valid = [r for r in group if r['status'] == 'ok' and r.get('speedup') is not None]
        complete = len(valid) == len(group)
        graphs = defaultdict(list)
        for row in valid:
            graphs[row['case']].append(row['speedup'])
        values = [statistics.mean(v) for v in graphs.values()]
        interval = bootstrap_mean(values) if complete else (None, None)
        output.append(dict(question=q, cores=n, variant=variant, complete=complete,
                           expected_jobs=len(group), scored_jobs=len(valid), graphs=len(graphs),
                           mean_speedup=statistics.mean(values) if complete else None,
                           geometric_mean_speedup=math.exp(statistics.mean(map(math.log, values))) if complete else None,
                           worst_graph_mean_speedup=min(values) if complete else None,
                           resampling_low=interval[0], resampling_high=interval[1],
                           mean_search_seconds=statistics.mean(r.get('search_seconds', 0.) for r in valid) if valid else None))
    return output


def paired(rows, left='full', right='common'):
    """One value per graph, averaging matched seeds before graph resampling."""
    lookup = {(r['case'], r['question'], r['cores'], r['variant'], r['seed']): r for r in rows}
    grouped, expected = defaultdict(lambda: defaultdict(list)), defaultdict(set)
    round_robin = {(r['case'], r['question'], r['cores']): r for r in rows if r['variant'] == 'rr'}
    for row in rows:
        if row['variant'] != left:
            continue
        q, n, case = row['question'], row['cores'], row['case']
        expected[q, n].add((case, row['seed']))
        base = round_robin.get((case, q, n)) if right == 'rr' else lookup.get((case, q, n, right, row['seed']))
        if base and row.get('speedup') is not None and base.get('speedup') is not None:
            grouped[q, n][case].append(row['speedup'] - base['speedup'])
    output = []
    for qn, jobs in sorted(expected.items()):
        differences = grouped[qn]
        count = sum(len(v) for v in differences.values())
        complete = count == len(jobs)
        values = [statistics.mean(v) for v in differences.values()]
        lo, hi = bootstrap_mean(values) if complete else (None, None)
        output.append(dict(question=qn[0], cores=qn[1], candidate=left, reference=right,
                           complete=complete, matched_jobs=count, expected_jobs=len(jobs),
                           paired_speedup_difference=statistics.mean(values) if complete else None,
                           resampling_low=lo, resampling_high=hi))
    return output


def diagnosis(row):
    if row['status'] != 'ok':
        return 'coarse', '没有有效方案：减少切分、降低实际使用核数，保留官方错误信息；不改原图/硬件。'
    if abs(row.get('pre_spill_formula_error', 0)) > 1e-6:
        return 'unranked', '边界流量公式与当前评估器不一致：暂时停用代理筛选，以原评估器排序，并核对版本和构图规则。'
    scheduled = row.get('scheduled_copy_bytes') or 0.
    spill = row.get('spill_added_copy_bytes') or 0.
    partition = row.get('partition_added_copy_bytes') or 0.
    if scheduled and spill / scheduled > .15:
        return 'spill', 'Spill 占比超过 15%：加强生命周期惩罚，优先最后使用者，配合迁移/拆分。'
    if row['question'] == 3 and row.get('overlapping_miss_bytes', 0) > 0:
        return 'cache', '同键读取重叠且再次未命中：重排独立子图，尝试让复用发生在前次 COPY_IN 完成之后。'
    if scheduled and partition / scheduled > .35:
        return 'locality', '划分附加 COPY 占比超过 35%：加强张量亲和，合并重通信块，允许少用核心。'
    bound = row.get('compute_lower_bound', 0)
    if bound and row['best_makespan'] / bound < 1.15:
        return 'critical', '已靠近计算下界：收益空间有限，扫描更少实际核心而非强求线性加速。'
    work = row.get('compute_work_by_core', {})
    values = [work.get(k, work.get(str(k), 0.)) for k in range(row['cores'])]
    if sum(values) and max(values) / (sum(values) / len(values)) > 1.4:
        return 'fine', '计算负载偏斜：细化高工作量块并迁移，检查通信增长是否抵消收益。'
    if row.get('speedup') is None or row['speedup'] < 1.05:
        return 'coarse', '相对单核收益小：先减少等待和边界通信，允许原核数下只使用部分核心。'
    return 'explore', '没有单一强瓶颈：扩大拓扑/划分多样性，在相同追加预算下检验局部最优假设。'


def analyze(args):
    source, out = Path(args.source), Path(args.out)
    spec, rows = records(source)
    table = summaries(rows)
    csv_file(out / 'per_job.csv', rows)
    csv_file(out / 'proxy_calibration.csv', [{k: r.get(k) for k in ['case', 'question', 'cores', 'variant', 'seed', 'pre_spill_bytes_predicted', 'scheduled_copy_bytes', 'spill_added_copy_bytes', 'pre_spill_formula_error', 'cache_hit_bytes_predicted', 'cache_hit_bytes', 'excess_residency_bytes_predicted']} for r in rows])
    csv_file(out / 'summary.csv', table)
    split_table = [dict(split=split, **r) for split in ['dev', 'eval']
                   for r in summaries([row for row in rows if row.get('split') == split])]
    csv_file(out / 'summary_by_split.csv', split_table)
    comparisons = []
    for right in ['rr', 'common', 'no_memory', 'no_cache', 'portfolio']:
        if 'full' in spec['variants'] and right in spec['variants']:
            comparisons.extend(paired(rows, right=right))
    csv_file(out / 'paired.csv', comparisons)
    diagnoses = []
    for row in rows:
        if row['variant'] == 'rr':
            continue
        profile, reason = diagnosis(row)
        diagnoses.append({**row, 'repair_profile': profile, 'reason': reason})
    write_json(out / 'diagnosis.json', diagnoses)
    csv_file(out / 'diagnosis.csv', diagnoses)
    convergence = []
    for row in rows:
        path = Path(row['directory']) / 'trajectory.json'
        if path.exists():
            for item in read_json(path):
                convergence.append({k: row[k] for k in ['case', 'question', 'cores', 'variant', 'seed']} | item)
    csv_file(out / 'convergence.csv', convergence)
    text = ['# A 三问性能实验', '',
            '主指标：每图先求单核时间/方案时间，再按图平均；多种子先在图内平均。',
            '重采样区间只表示该图集的重采样敏感性，不代表新图总体置信区间。缺例不输出完整均值。', '',
            '|问题|核数|方法|完整|平均加速比|最差图|', '|---|---:|---|---|---:|---:|']
    for r in table:
        mean = f"{r['mean_speedup']:.4f}" if r['complete'] else '不完整'
        worst = f"{r['worst_graph_mean_speedup']:.4f}" if r['complete'] else '—'
        text.append(f"|{r['question']}|{r['cores']}|{r['variant']}|{r['scored_jobs']}/{r['expected_jobs']}|{mean}|{worst}|")
    text += ['', '## 修正操作', '', '依据 diagnosis.csv 选择诊断，或运行（默认只处理 dev）：', '',
             f'```sh\npython -m research_a.report repair --source "{source}" --out "{out.parent / "repairs"}" --budget 96 --limit 12 --workers 2\n```',
             '', '修正结果不并入主实验。先在开发集选择统一配置，再对全部正式图重跑，避免逐图事后择优。']
    out.mkdir(parents=True, exist_ok=True)
    (out / 'REPORT.md').write_text('\n'.join(text) + '\n', encoding='utf-8')
    print(out / 'REPORT.md')


def repair_one(job):
    row, spec, options = job
    directory = Path(options['out']) / row['case'] / f"q{row['question']}_n{row['cores']}_{row['repair_profile']}_s{row['seed']}"
    graph_path = Path(row['graph_path']) if row.get('graph_path') else None
    if graph_path is None:
        return dict(case=row['case'], status='missing_graph_path')
    graph = Graph(read_json(graph_path))
    parent = Path(row['directory']) / 'best_plan.json'
    initial = Plan.load(read_json(parent), graph) if parent.exists() else None
    evaluator = Official(spec['code'], spec['config'], graph_path, directory, options['timeout'])
    result = search(graph, settings(Path(spec['config'])), lambda p: evaluator.evaluate(p, row['question']),
                    directory, row['question'], row['cores'], row['repair_profile'], options['budget'],
                    row['seed'], options['pool'], initial=initial)
    old, new = row.get('best_makespan'), result['best_makespan']
    result.update(case=row['case'], split=row.get('split'), parent_directory=row['directory'],
                  previous_makespan=old, repair_gain=(old / new if old and new else None), reason=row['reason'],
                  note='Adaptive, additional-budget experiment; never overwrite the primary result')
    write_json(directory / 'repair.json', result)
    return result


def repair(args):
    source, out = Path(args.source), Path(args.out)
    if out.exists():
        raise FileExistsError(out)
    spec, rows = records(source)
    chosen = [r for r in rows if r['variant'] == args.variant and (args.split == 'all' or r.get('split') == args.split)]
    chosen.sort(key=lambda r: (r.get('speedup') is not None, r.get('speedup') or 0., r['case']))
    chosen = chosen[:args.limit]
    for row in chosen:
        row['repair_profile'], row['reason'] = diagnosis(row)
        if args.profile:
            row['repair_profile'] = args.profile
    options = {k: v for k, v in vars(args).items() if k != 'func'}
    out.mkdir(parents=True)
    write_json(out / 'repair_spec.json', dict(source=str(source.resolve()), selected=chosen, options=options))
    jobs = [(row, spec, options) for row in chosen]
    if args.workers == 1:
        result = [repair_one(job) for job in jobs]
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            result = list(executor.map(repair_one, jobs))
    csv_file(out / 'repair_summary.csv', result)
    write_json(out / 'repair_summary.json', result)
    print(out / 'repair_summary.csv')


def cross_report(args):
    rows = read_json(Path(args.source) / 'cross.json')
    out = Path(args.out)
    csv_file(out / 'cross_matrix.csv', rows)
    groups = defaultdict(dict)
    for row in rows:
        groups[row['case'], row['cores'], row['seed']][row['origin'], row['target']] = row
    table = []
    for (case, cores, seed), group in sorted(groups.items()):
        needed = [(2, 2), (2, 3), (3, 2), (3, 3)]
        complete = all(group.get(k, {}).get('status') == 'ok' for k in needed)
        record = dict(case=case, cores=cores, seed=seed, complete=complete)
        if complete:
            a, b, c, d = [group[k]['makespan'] for k in needed]
            record.update(T2_P2=a, T3_P2=b, T2_P3=c, T3_P3=d,
                          cache_gain_fixed_P2=a / b, cache_gain_fixed_P3=c / d,
                          retuning_gain_under_Q3=b / d, joint_gain=a / d,
                          factorization_error=abs(a / d - (a / b) * (b / d)))
        table.append(record)
    csv_file(out / 'cache_decomposition.csv', table)
    print(out / 'cache_decomposition.csv')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    a = sub.add_parser('analyze'); a.set_defaults(func=analyze)
    c = sub.add_parser('cross'); c.set_defaults(func=cross_report)
    r = sub.add_parser('repair'); r.set_defaults(func=repair)
    for command in [a, c, r]:
        command.add_argument('--source', required=True); command.add_argument('--out', required=True)
    r.add_argument('--variant', default='full'); r.add_argument('--split', choices=['all', 'dev', 'eval'], default='dev')
    r.add_argument('--profile', choices=['coarse', 'fine', 'locality', 'spill', 'cache', 'critical', 'explore', 'unranked'])
    r.add_argument('--budget', type=int, default=96); r.add_argument('--limit', type=int, default=12)
    r.add_argument('--workers', type=int, default=2); r.add_argument('--pool', type=int, default=4)
    r.add_argument('--timeout', type=float, default=300.)
    args = p.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
