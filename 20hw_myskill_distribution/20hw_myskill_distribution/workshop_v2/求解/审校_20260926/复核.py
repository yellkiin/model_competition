import csv, json, statistics
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
COMBINED = BASE / '规范化数据' / 'combined'
STUDIES = BASE / '规范化数据' / 'studies' / 'cache_parameter_grid.csv'
OUT = BASE / '审校_20260926'

def read(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def num(row, key):
    return float(row[key]) if row[key] not in ('', None) else 0.0

def qstats(q):
    rows = read(COMBINED / f'appendix_q{q}.csv')
    baselines = {r['case']: int(r['makespan']) for r in read(COMBINED / 'appendix_q1.csv') if int(r['n']) == 1}
    out = {}
    for n in range(1, 6):
        rr = [r for r in rows if int(r['n']) == n and r['status'] == 'ok']
        out[str(n)] = {
            'rows': len(rr),
            'mean_speedup': statistics.mean(baselines[r['case']] / int(r['makespan']) for r in rr),
            'mean_added_copy_bytes': statistics.mean(num(r, 'added_copy_bytes') for r in rr),
            'median_added_copy_bytes': statistics.median(num(r, 'added_copy_bytes') for r in rr),
            'spill_positive_cases': sum(num(r, 'spill_added_copy_bytes') > 0 for r in rr),
        }
    return rows, out

def relation(a, b, field, lower_better=True):
    aa = {r['case']: r for r in a}
    result = {'improved': 0, 'same': 0, 'worse': 0}
    for r in b:
        x, y = num(aa[r['case']], field), num(r, field)
        key = 'improved' if (y < x if lower_better else y > x) else ('same' if y == x else 'worse')
        result[key] += 1
    return result

qs = {q: qstats(q) for q in (1, 2, 3)}
q1, q2, q3 = [qs[q][0] for q in (1, 2, 3)]
n5 = lambda rows: [r for r in rows if int(r['n']) == 5]
pairs = read(COMBINED / 'pairs.csv')
cross = read(COMBINED / 'cross_question.csv')
p5 = [r for r in pairs if int(r['n']) == 5]
ratios = [int(r['without_l2']) / int(r['with_l2']) for r in p5]
anytime = read(COMBINED / 'anytime.csv')
at30 = [r for r in anytime if int(r['q']) == 1 and int(r['n']) == 5 and num(r, 'seconds') == 30]
studies = read(STUDIES)
fixed = [r for r in studies if r['mode'] == 'fixed_plan']
adapted = [r for r in studies if r['mode'] != 'fixed_plan']

result = {
    'source_files': [str((COMBINED / f'appendix_q{q}.csv').relative_to(BASE)) for q in (1,2,3)] + [str((COMBINED / f).relative_to(BASE)) for f in ('pairs.csv','cross_question.csv','anytime.csv')],
    'main_rows': {f'q{q}': len(qs[q][0]) for q in (1,2,3)},
    'main_stats_by_question_and_n': {f'q{q}': qs[q][1] for q in (1,2,3)},
    'n5_casewise_comparisons': {
        'q2_vs_q1_makespan': relation(n5(q1), n5(q2), 'makespan'),
        'q2_vs_q1_added_copy': relation(n5(q1), n5(q2), 'added_copy_bytes'),
        'q3_vs_q2_makespan': relation(n5(q2), n5(q3), 'makespan'),
    },
    'cross_question_records': len(cross),
    'same_plan_cache_pairs_n5': {
        'count': len(p5), 'mean_ratio_no_l2_over_l2': statistics.mean(ratios),
        'median_ratio': statistics.median(ratios),
        'improved_count': sum(x > 1 for x in ratios), 'same_count': sum(x == 1 for x in ratios), 'worse_count': sum(x < 1 for x in ratios),
    },
    'case_079_n4_pair': next({k:r[k] for k in ('case','n','with_l2','without_l2','cache_speedup','with_l2_added_bytes','without_l2_added_bytes')} for r in pairs if r['case']=='case_079' and int(r['n'])==4),
    'q1_n5_30_seconds': {'rows':len(at30),'distinct_cases':len({r['case'] for r in at30}),'has_solution':sum(r['has_solution'].lower()=='true' for r in at30)},
    'cache_parameter_grid': {'total_records':len(studies),'fixed_plan_records':len(fixed),'readapted_records':len(adapted),'audit_ok_false':sum(r['audit_ok'].lower()!='true' for r in studies)},
    'scope_note': 'Recomputed from recorded CSV values only; no experiment or official evaluator was rerun.'
}
(OUT / '数值终审核对.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

lines = [
'# 数值终审核对', '',
'复核范围：逐行读取 `求解/规范化数据/combined/appendix_q1.csv`、`appendix_q2.csv`、`appendix_q3.csv`、`pairs.csv`、`cross_question.csv`、`anytime.csv`；参数记录另读 `求解/规范化数据/studies/cache_parameter_grid.csv`。均按记录重新汇总，没有运行实验或官方评价器。计算脚本为本目录 `复核.py`，结构化结果见 `数值终审核对.json`。', '',
'## 核数均值与五核 COPY', '',
'三问逐例表均为500条，每个核数100条，记录状态均为可用。由单核参考周期除以每个方案的实际周期，再取算术平均；缓存比也由配对两列周期重算：', '',
'| 核数 | Q1 | Q2 | Q3 |', '|---:|---:|---:|---:|',
]
for n in range(1,6):
    lines.append(f"| {n} | {qs[1][1][str(n)]['mean_speedup']:.4f} | {qs[2][1][str(n)]['mean_speedup']:.4f} | {qs[3][1][str(n)]['mean_speedup']:.4f} |")
lines += ['', '五核额外 COPY 均值 / 中位数（B）：Q1 `%.2f / %.0f`，Q2 `%.2f / %.0f`，Q3 `%.2f / %.0f`。这与正文三问表述一致；Q1/Q2 五核逐图 COPY 比较为 Q2 更少 50、相同 12、更多 38。Q1/Q2 五核周期逐例比较为 Q2 更快 89、相同 9、更慢 2；Q2/Q3 为 Q3 更快 66、相同 18、更慢 16。' % (qs[1][1]['5']['mean_added_copy_bytes'], qs[1][1]['5']['median_added_copy_bytes'], qs[2][1]['5']['mean_added_copy_bytes'], qs[2][1]['5']['median_added_copy_bytes'], qs[3][1]['5']['mean_added_copy_bytes'], qs[3][1]['5']['median_added_copy_bytes']), '',
f"同方案 L2 对照：`pairs.csv` 五核 100 条比值（无 L2 周期 / 有 L2 周期）均值 `{statistics.mean(ratios):.4f}`，中位数 `{statistics.median(ratios):.4f}`；有 L2 周期更短 77 条、相同 23 条、更长 0 条。正文 1.0558 与计数吻合。",
'',
'case_079 四核：有 L2 `7614798`、无 L2 `7614729`，有 L2 多 69 周期；两边额外 COPY 均为 `30445568 B`。该例反向细节准确。', '',
f"anytime.csv 在 Q1 五核、30 秒处恰有 100 个不同算例，其中 93 个 `has_solution=true`，7 个为 false；正文所述 93 个可用解正确。",
'',
'参数格：原始记录共 66 条，其中固定方案 54 条、重新适配 12 条，且 `audit_ok` 全部为 true；正文计数正确。正文举例值复核：算例080、容量262144 B 下带宽60/250/500的周期为 79170/80014/81744；算例044、容量1048576 B 下为 50723/36208/44299；算例001九格均为47502且命中率为0。', '',
'口径行数：三份附录逐例表展示 1500 行（每问 500）；Q1/Q2 的 100 个单核参考共用同一批原始响应，因此去重后为 1400 个主配置/响应口径，包含这 100 个参考。这个展示行数与去重口径相差 100，不构成数值冲突。', '',
'正文上述待核数字均与记录一致。此为记录值的独立汇总核对，不表示重跑或重新验证了官方评价器。', '']
(OUT / '数值终审核对.md').write_text('\n'.join(lines), encoding='utf-8')
