"""Compare saved official results from two fixed algorithm versions; never solve."""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path
from collections import Counter


def load_rows(folder):
    with (folder / 'summary.csv').open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    groups = {}
    duplicates = []
    for row in rows:
        key = (row['case'], row['question'], row['cores'], row['variant'])
        if key in groups:
            duplicates.append(key)
        groups[key] = row
    return groups, duplicates


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('first', type=Path)
    parser.add_argument('second', type=Path)
    args = parser.parse_args()
    first, second = args.first.resolve(), args.second.resolve()
    a, da = load_rows(first)
    b, db = load_rows(second)
    ma = json.loads((first / 'manifest.json').read_text(encoding='utf-8'))
    mb = json.loads((second / 'manifest.json').read_text(encoding='utf-8'))
    fields = ['cases', 'cores', 'questions', 'budget', 'job_seconds', 'eval_seconds',
              'shards', 'shard', 'machine', 'input_root', 'workers', 'wall_seconds']
    differences = {f: [ma.get(f), mb.get(f)] for f in fields if ma.get(f) != mb.get(f)}
    rows = []
    for key in sorted(a.keys() | b.keys()):
        x, y = a.get(key, {}), b.get(key, {})
        av, bv = number(x.get('makespan')), number(y.get('makespan'))
        paired = av is not None and av > 0 and bv is not None and bv > 0
        change = ('improved' if bv < av else 'worse' if bv > av else 'equal') if paired else 'unpaired'
        rows.append(dict(case=key[0], question=key[1], cores=key[2], variant=key[3],
            first_makespan=av, second_makespan=bv, outcome=change,
            first_over_second=av / bv if paired else None,
            cycle_reduction_pct=100 * (av - bv) / av if paired else None,
            first_speedup=number(x.get('speedup')), second_speedup=number(y.get('speedup')),
            first_solve_seconds=number(x.get('solve_seconds')),
            second_solve_seconds=number(y.get('solve_seconds')),
            first_copy=number(x.get('partition_added_copy_bytes')),
            second_copy=number(y.get('partition_added_copy_bytes')),
            first_spill=number(x.get('spill_added_copy_bytes')),
            second_spill=number(y.get('spill_added_copy_bytes')),
            first_cache_hit_rate=number(x.get('cache_byte_hit_rate')),
            second_cache_hit_rate=number(y.get('cache_byte_hit_rate')),
            first_same_plan_cache_ratio=number(x.get('same_plan_cache_ratio')),
            second_same_plan_cache_ratio=number(y.get('same_plan_cache_ratio'))))
    with (second / 'cross_round.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    details = dict(first=str(first), second=str(second), parameter_differences=differences,
                   duplicates_first=da, duplicates_second=db,
                   missing_first=sorted(b.keys() - a.keys()), missing_second=sorted(a.keys() - b.keys()),
                   baseline_differences=[], groups=[])
    for row in rows:
        if row['question'] == '0' and row['outcome'] not in ('equal', 'unpaired'):
            details['baseline_differences'].append(row['case'])
    text = ['# 两轮固定版本配对比较', '',
            f'第一轮：`{first.name}`。第二轮：`{second.name}`。', '',
            '第一轮与第二轮独立报告；未拼接每图跨版本最好值。周期仅取官方合法记录。',
            'solve_seconds 是整次求解时间，CSV 在不同 variant 行重复它只是便于定位，不能解释为变体独立耗时。', '',
            '两轮每个图分别使用该轮原始单核分母；分母缺失时速度比留空。不同小问优化出来的最好周期不用于计算 Cache 收益。', '',
            f'参数差异：{differences or "无"}；重复键：{len(da)}/{len(db)}；行缺项：{len(details["missing_first"])}/{len(details["missing_second"])}。', '',
            '|小问|核数|variant|有效配对|改善|相同|变差|第一轮/第二轮周期比几何均值|',
            '|---|---:|---|---:|---:|---:|---:|---:|']
    for q in ['1', '2', '3']:
        for cores in ['2', '5']:
            for variant in ['fast', 'components', 'best']:
                group = [r for r in rows if r['question'] == q and r['cores'] == cores and r['variant'] == variant]
                counts = Counter(r['outcome'] for r in group)
                ratios = [r['first_over_second'] for r in group if r['first_over_second'] is not None]
                gm = math.exp(sum(math.log(v) for v in ratios) / len(ratios)) if ratios else None
                details['groups'].append(dict(question=int(q), cores=int(cores), variant=variant,
                    paired=len(ratios), counts=dict(counts), geometric_cycle_ratio=gm))
                text.append(f'|Q{q}|{cores}|{variant}|{len(ratios)}|{counts["improved"]}|{counts["equal"]}|{counts["worse"]}|{gm:.6f}|' if gm is not None else f'|Q{q}|{cores}|{variant}|0|0|0|0|未完成|')
    text += ['', '## best 逐例配对', '',
             '|案例|小问|核数|第一轮周期|第二轮周期|周期下降%|',
             '|---|---|---:|---:|---:|---:|']
    for r in rows:
        if r['variant'] != 'best':
            continue
        av = str(int(r['first_makespan'])) if r['first_makespan'] is not None else '未完成'
        bv = str(int(r['second_makespan'])) if r['second_makespan'] is not None else '未完成'
        delta = f'{r["cycle_reduction_pct"]:.4f}' if r['cycle_reduction_pct'] is not None else ''
        text.append(f'|{r["case"]}|Q{r["question"]}|{r["cores"]}|{av}|{bv}|{delta}|')
    text += ['', '## 解释边界', '',
             '- 上表是相同六图、相同核数/小问、固定版本之间的逐例比较，不能当成旧论文对照。',
             '- 本轮尚不能判断是否超过论文：没有旧论文同配置、同分母逐例数据。',
             '- 负载代理仅用于挑候选；不是正式周期、严格下界或最优性证书。',
             '- 固定同一 best_plan 的 Cache 比、Spill、搬运和所有评估耗时分别见两轮 REPORT.md、summary.csv 和 evaluation_times.csv。', '']
    (second / 'comparison.json').write_text(json.dumps(details, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (second / 'COMPARISON.md').write_text('\n'.join(text), encoding='utf-8')
    print(json.dumps(details, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
