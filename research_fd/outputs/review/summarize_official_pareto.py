"""Build a traceable summary only from actually saved solver/validation results."""
import csv
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]
attempts = [('HiGHS 60s', 'official_pareto'), ('HiGHS 精确预删120s', 'official_pareto_repair_exact'),
            ('CP-SAT 30s/30s', 'official_pareto_cpsat'), ('CP-SAT warm180s/30s', 'official_pareto_cpsat_warm180')]
baseline = json.loads((OUT/'official_transport_s7/best_plan.json').read_text(encoding='utf-8'))['metrics']
allrows, observed = [], []
for name, directory in attempts:
    path = OUT/directory/'pareto.json'
    if not path.is_file():
        continue
    data = json.loads(path.read_text(encoding='utf-8'))
    for row in data['records']:
        ratio = f"{row['ratio']:g}"
        detail = json.loads((OUT/directory/f'energy_cap_{ratio}_solver.json').read_text(encoding='utf-8'))
        validation_path = OUT/directory/('export_cap'+ratio.replace('.', 'p'))/'validation.json'
        validation = json.loads(validation_path.read_text(encoding='utf-8')) if validation_path.is_file() else None
        stage = detail['stages'][0] if detail['stages'] else {}
        bound = stage.get('bound')
        record = dict(attempt=name, ratio=row['ratio'], cap_s=row['cap_s'], solver_feasible=row['feasible'],
                      transport_validated=bool(validation and validation['transport_valid']),
                      radio_checked=False, energy_stage_status=stage.get('status'),
                      energy_bound_kwh=bound, energy_kwh=row['energy_kwh'], makespan_s=row['makespan_s'],
                      weighted_tardiness_s=row['weighted_tardiness_s'], trips=row['trips'], elapsed_s=row['elapsed_s'],
                      plan=f'{directory}/energy_cap_{ratio}.json', validation=str(validation_path.relative_to(OUT)))
        record['energy_gap_from_bound'] = (record['energy_kwh']-bound)/record['energy_kwh'] if row['feasible'] and bound is not None and record['energy_kwh'] else None
        allrows.append(record)
        if row['feasible'] and record['transport_validated']:
            observed.append(record)
for record in observed:
    record['observed_nondominated'] = not any(
        other is not record and other['energy_kwh'] <= record['energy_kwh']+1e-8 and other['makespan_s'] <= record['makespan_s']+1e-6
        and (other['energy_kwh'] < record['energy_kwh']-1e-8 or other['makespan_s'] < record['makespan_s']-1e-6)
        for other in observed)
best = min(observed, key=lambda r: (r['energy_kwh'], r['makespan_s'])) if observed else None
unique_frontier = {}
for r in observed:
    if r['observed_nondominated']:
        key = (round(r['makespan_s'], 6), round(r['energy_kwh'], 9))
        unique_frontier.setdefault(key, []).append(r)
result = dict(baseline=baseline, records=allrows, best_observed_energy_plan=None if best is None else best['plan'],
              observed_nondominated=[r['plan'] for r in observed if r['observed_nondominated']],
              unique_nondominated_objective_points=[dict(makespan_s=key[0], energy_kwh=key[1], plans=[r['plan'] for r in group]) for key, group in unique_frontier.items()],
              radio_scope='No point in this report is declared jointly feasible; radio assessment is a separate follow-up.')
(OUT/'official_pareto_summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
columns = list(allrows[0]) if allrows else []
if 'observed_nondominated' not in columns:
    columns.append('observed_nondominated')
with (OUT/'official_pareto_comparison.csv').open('w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=columns)
    writer.writeheader()
    writer.writerows(allrows)
lines = ['# 正式附件：共同质量约束下的运输能耗与工期双目标', '',
         f'锚点来自实际执行的 official_transport_s7/best_plan.json：{baseline["trips"]} 趟、工期 {baseline["makespan_s"]:.6f} 秒、能耗 {baseline["energy_kwh"]:.9f} kWh，软/硬迟到均为 0。', '',
         '所有试验固定同一 600 条路线池、60 秒启动网格、共同加权软迟到上限 0（数值容差 1e-5）和原硬截止，保留全部箱覆盖、共享机身/电池容量。cap=锚点工期×倍率。此锚点特意使用同网格方案；没有用稍快的连续/整秒方案改写实验上限。', '',
         '|实际后端与预算|cap倍率|能量阶段状态|独立运输检查|实际工期/s|能耗/kWh|能量界/kWh|界差距|',
         '|---|---:|---|---|---:|---:|---:|---:|']
for r in allrows:
    good = r['solver_feasible'] and r['transport_validated']
    bound = '—' if r['energy_bound_kwh'] is None else f'{r["energy_bound_kwh"]:.6f}'
    gap = '—' if r['energy_gap_from_bound'] is None else f'{100*r["energy_gap_from_bound"]:.3f}%'
    duration = f'{r["makespan_s"]:.6f}' if good else '无 incumbent'
    energy = f'{r["energy_kwh"]:.9f}' if good else '无 incumbent'
    lines.append(f'|{r["attempt"]}|{r["ratio"]:g}|{r["energy_stage_status"]}|{"通过" if good else "invalid/80箱未交付"}|{duration}|{energy}|{bound}|{gap}|')
lines += ['', '## 失败与修复的实际结论', '',
          '首次 HiGHS 四点均在能量阶段限时退出、没有 incumbent；共同质量精确预删后加到 120 秒的四点也没有 incumbent，均完整保留原空计划、求解状态和 80 箱未交付的独立导出。原 CSV 中空计划的能耗/工期为 0，是空集合求和，不参与成绩排序。', '',
          'baseline_witness.json 逐项直接核验了同网格基线满足覆盖、迟到、资源与工期约束，且原池与预删修复池的所有路线一致，因此这些无 incumbent 结果是搜索失败，不是正式物理问题不可行。', '',
          'CP-SAT 使用同一个池和同一网格的可选占用区间，并提供真实可行方案提示；这些点只有后端实际返回 FEASIBLE/OPTIMAL 才写为求解候选。已核验基线另存 known_baseline_plan.json，未冒充 CP-SAT incumbent。能量目标量化至 1e-9 kWh，次级工期至 1 微秒；本例所有有效启动的迟到均为 0，没有正迟到近似表。', '',
          '初轮更宽 cap 的能耗反而略差，已保留全部负结果。更宽 cap 包含更窄 cap 的可行域，但限时 incumbent 不必单调，不能把这些点连线称为全局连续 Pareto 前沿。warm180 仅改变提示和能量阶段预算，原锚点、候选池与共同质量保持不变。', '', '## 已观察到的取舍', '']
if best is not None:
    lines.append(f'当前最低能耗的已验证候选为 [{best["plan"]}]({best["plan"]})：{best["energy_kwh"]:.9f} kWh、{best["makespan_s"]:.6f} 秒，较锚点节能 {(1-best["energy_kwh"]/baseline["energy_kwh"])*100:.3f}%。')
    lines.append('')
    frontier = [group[0] for group in unique_frontier.values()]
    lines.append(f'本次实际候选中有 {len(frontier)} 个不同的未被其他已验证候选支配的目标坐标（相同坐标去重，但不删除原候选）：')
    lines.append('')
    for r in frontier:
        lines.append(f'- [{r["plan"]}]({r["plan"]})：{r["makespan_s"]:.6f} 秒，{r["energy_kwh"]:.9f} kWh。')
    lines.append('')
    if len(frontier)==1:
        lines.append('目前仅发现一个非支配点，不能据此画出“工期越长能耗越低”的趋势，也未证明更长工期不可能节能。')
    warm = [r for r in observed if 'warm180' in r['attempt']]
    if warm:
        r = warm[-1]
        lines.append(f'最大 cap 的180秒能耗修复仍返回 {r["energy_kwh"]:.9f} kWh；该受限模型的能量界为 {r["energy_bound_kwh"]:.9f} kWh，剩余相对差距 {100*r["energy_gap_from_bound"]:.3f}%。这量化了搜索尚未完成，不能据此宣布不存在更好的能耗—工期取舍。')
lines += ['', '全部可行点均已逐箱、机身/电池库存、释放与硬截止、载荷、路线能量及充电周转独立复核；各 export_cap*/ 中保留 CSV 与 validation.json。所有这些点仅完成运输检查，通信需另行联验；本报告没有把运输能耗或工期冒称运输—中继联合值。', '',
          '原始日志在 logs/official_pareto*.log/json；各 cap 的阶段状态、bound、gap 和候选本体在对应目录，失败与较差方案均未覆盖或删除。']
(OUT/'PARETO_OFFICIAL_RESULTS.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
print(json.dumps(dict(records=len(allrows), validated_transport_points=len(observed), best_plan=None if best is None else best['plan']), ensure_ascii=False))
