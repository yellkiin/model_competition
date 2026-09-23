"""Render actual common-quality transport candidates and solver-bound gaps.
Reads saved execution results only; never solves or imputes missing incumbents.
"""
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
os.environ['MPLCONFIGDIR'] = str(HERE/'pareto_mplconfig')
os.environ['TEMP'] = str(HERE/'tmp')
os.environ['TMP'] = str(HERE/'tmp')
(HERE/'tmp').mkdir(exist_ok=True)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

summary_path = OUT/'official_pareto_summary.json'
q2_path = OUT/'official_best_transport_export/validation.json'
summary = json.loads(summary_path.read_text(encoding='utf-8'))
q2 = json.loads(q2_path.read_text(encoding='utf-8'))
assert q2['transport_valid']
records = summary['records']
valid = [r for r in records if r['solver_feasible'] and r['transport_validated']]
failed = [r for r in records if not r['solver_feasible']]
assert len(records)==13 and len(valid)==5 and len(failed)==8
anchor = summary['baseline']
q2_metrics = q2['independently_recomputed_metrics']
primary = [r for r in valid if r['attempt']=='CP-SAT 30s/30s']
warm = next(r for r in valid if 'warm180' in r['attempt'])
best = min(valid, key=lambda r: (r['energy_kwh'], r['makespan_s']))
assert abs(warm['energy_kwh']-best['energy_kwh']) < 1e-8
assert abs(warm['makespan_s']-best['makespan_s']) < 1e-6
assert all(r['weighted_tardiness_s']==0 for r in valid)

source_paths = [summary_path, q2_path, OUT/'official_pareto/experiment_contract.json']
for r in valid:
    source_paths += [OUT/r['plan'], OUT/r['validation']]
sources = dict(
    figure='pareto_actual_results.png / pareto_actual_results.pdf',
    scope='Actual transport-only Q2 results, no relay. Not a proven global or continuous Pareto frontier.',
    all_13_execution_records=records, plotted_valid_records=valid,
    excluded_no_incumbent_records=failed,
    excluded_policy='Do not plot empty-plan zero energy/makespan from the eight failed HiGHS attempts.',
    baseline_anchor=anchor, q2_fixed_route_cpsat_reference=q2_metrics,
    unique_nondominated_coordinates=summary['unique_nondominated_objective_points'],
    bound_meaning='Solver lower bound of the corresponding finite candidate/grid model; not a statistical confidence interval.',
    energy_stage_budgets_s=[30,30,30,30,180], secondary_makespan_budget_s=30,
    source_files=[dict(path=p.relative_to(OUT).as_posix(), sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in source_paths],
)
(HERE/'pareto_actual_results_sources.json').write_text(json.dumps(sources, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

font_path = Path('C:/Windows/Fonts/msyh.ttc')
if font_path.is_file():
    font_manager.fontManager.addfont(str(font_path))
    family = font_manager.FontProperties(fname=str(font_path)).get_name()
else:
    family = 'DejaVu Sans'
plt.rcParams.update({'font.family': family, 'axes.unicode_minus': False, 'font.size': 11,
                     'pdf.fonttype': 42, 'ps.fonttype': 42, 'axes.spines.top': False,
                     'axes.spines.right': False, 'axes.labelcolor': '#24344A',
                     'xtick.color': '#46586F', 'ytick.color': '#46586F'})
blue, orange, grey, ink = '#1268B3', '#DB7D1C', '#7B8B9C', '#23354D'
fig, axes = plt.subplots(1, 2, figsize=(17, 8.2))
fig.subplots_adjust(left=.065, right=.985, top=.835, bottom=.225, wspace=.24)
fig.suptitle('共同质量约束下的实际能耗与工期结果', fontsize=20, x=.5, y=.975, color=ink)
fig.text(.5, .925, '只画真实可行候选；保留较差结果与求解下界，未绘制假定的平滑前沿',
         ha='center', fontsize=12, color='#536579')

ax = axes[0]
ax.set_title('A  实际返仓工期与运输能耗', loc='left', fontsize=14, pad=16, color=ink)
ax.set_xlim(8070, 10070)
ax.set_ylim(70.8, 75.8)
ax.set_xlabel('实际全部运输返仓时间 / s', labelpad=10)
ax.set_ylabel('运输能耗 / kWh', labelpad=9)
ax.grid(color='#E5EAF0', linewidth=.7)
ax.set_axisbelow(True)
for r in primary:
    if r is best or abs(r['energy_kwh']-best['energy_kwh']) < 1e-9:
        ax.scatter(r['makespan_s'], r['energy_kwh'], s=100, color=blue, zorder=7,
                   edgecolors='white', linewidth=.9, label='已观察到的非支配坐标')
    else:
        ax.scatter(r['makespan_s'], r['energy_kwh'], s=72, marker='o', color=grey, zorder=5,
                   edgecolors='white', linewidth=.8)
ax.scatter(warm['makespan_s'], warm['energy_kwh'], s=205, marker='s', facecolors='none',
           edgecolors=orange, linewidth=2.0, zorder=6, label='warm180：与 cap1 重合')
ax.scatter(anchor['makespan_s'], anchor['energy_kwh'], s=95, marker='D', facecolors='white',
           edgecolors=ink, linewidth=1.3, zorder=5)
ax.scatter(q2_metrics['makespan_s'], q2_metrics['energy_kwh'], s=125, marker='*', color=ink, zorder=5)
ann = dict(arrowprops=dict(arrowstyle='-', color='#A0AAB6', linewidth=.8), fontsize=10.3,
           color=ink, ha='left', va='center', annotation_clip=False)
ax.annotate('60 s 网格锚点\n8310.169 s / 75.069 kWh', (anchor['makespan_s'], anchor['energy_kwh']), xytext=(8660,75.46), **ann)
ax.annotate('固定路线 CP-SAT（Q2参考）\n8258.191 s / 75.069 kWh', (q2_metrics['makespan_s'], q2_metrics['energy_kwh']), xytext=(8660,74.55), **ann)
for ratio, label_y in [(1.1,73.22), (1.25,72.52)]:
    r = next(x for x in primary if x['ratio']==ratio)
    ax.annotate(f'cap {ratio:g}：{r["energy_kwh"]:.3f} kWh', (r['makespan_s'],r['energy_kwh']), xytext=(8600,label_y), **ann)
r = next(x for x in primary if x['ratio']==1.5)
ax.annotate(f'cap 1.5 初跑\n{r["makespan_s"]:.3f} s / {r["energy_kwh"]:.3f} kWh',
            (r['makespan_s'],r['energy_kwh']), xytext=(9300,73.15), **ann)
ax.annotate('cap 1 与 warm cap 1.5 同坐标\n8237.191 s / 71.245 kWh',
            (best['makespan_s'],best['energy_kwh']), xytext=(8560,71.32),
            arrowprops=dict(arrowstyle='-', color=blue, linewidth=1.0), fontsize=10.3,
            color=blue, ha='left', va='center')

ax = axes[1]
ax.set_title('B  各上限下的当前能耗与下界差距', loc='left', fontsize=14, pad=16, color=ink)
ax.set_ylim(60.25,76.4)
ax.set_xlim(-.5,4.55)
ax.set_ylabel('运输能耗 / kWh', labelpad=9)
ax.set_xlabel('工期上限倍率 / 能耗阶段预算', labelpad=10)
ax.grid(axis='y', color='#E5EAF0', linewidth=.7)
ax.set_axisbelow(True)
ax.axhline(anchor['energy_kwh'], color='#B1BAC6', linewidth=1, linestyle='--')
ax.text(4.4, anchor['energy_kwh']+.23, '锚点 75.069', color='#647489', fontsize=9.5, ha='right')
for x, r in enumerate(primary+[warm]):
    color = orange if r is warm else blue
    low, high = r['energy_bound_kwh'], r['energy_kwh']
    assert low is not None and low <= high+1e-6
    ax.vlines(x, low, high, color=color, linewidth=2.0, alpha=.65)
    ax.hlines([low,high], x-.10, x+.10, color=color, linewidth=1.5)
    ax.scatter(x, high, s=62, color=color, zorder=5)
    ax.scatter(x, low, s=36, marker='v', color=color, zorder=5)
    ax.text(x, high+.3, f'{high:.3f}', ha='center', va='bottom', color=ink, fontsize=10.3)
    ax.text(x, low-.4, f'{low:.3f}', ha='center', va='top', color='#536579', fontsize=9.8)
    ax.text(x+.12, (low+high)/2, f'{100*r["energy_gap_from_bound"]:.2f}%', ha='left', va='center', color=color, fontsize=9.5)
ax.set_xticks(range(5), ['cap 1\n30 s','cap 1.1\n30 s','cap 1.25\n30 s','cap 1.5\n30 s','cap 1.5\nwarm 180 s'])

fig.text(.065,.13,'● 当前可行能量   ▼ 求解下界   竖线：尚未闭合的优化差距（非统计置信区间）', fontsize=10.5, color=ink)
fig.text(.065,.085,'范围：Transport only / Q2，无中继。共同要求为零软/硬迟到；固定 600 条路线、60 s 启动网格。8 次 HiGHS 无 incumbent，未画其空计划零值。', fontsize=10.1, color='#536579')
fig.text(.065,.05,'仅观察到一个不同的非支配目标坐标；CP-SAT 均为限时 FEASIBLE，不能据此声称全局连续前沿。warm 使用 cap1 提示，次级工期预算仍为 30 s。', fontsize=10.1, color='#536579')
for ext in ('png','pdf'):
    fig.savefig(HERE/f'pareto_actual_results.{ext}', dpi=180, facecolor='white')
plt.close(fig)
(HERE/'pareto_actual_results_README.md').write_text('''# 正式运输能耗取舍图

`pareto_actual_results.png/.pdf` 是一张两面板图，读取本次13次真实运行总表。A面板仅画5个独立运输校验通过的结果和两个背景参考；cap1与warm180结果共用同一目标坐标。B面板画各工期上限下的求解下界和实际候选能耗，两者之间不是统计置信区间。

8次HiGHS无incumbent保留在来源JSON中，不绘制空计划的零值。所有数据只代表运输/Q2、不含中继。仅观察到一个不同的非支配坐标，因此没有拟合或连接任何平滑Pareto前沿。

来源路径、SHA256、全部13次状态、排除记录和作图数值保存在 `pareto_actual_results_sources.json`。脚本为 `pareto_actual_results.py`，运行结果只写本目录。未修改 `plot_official.py` 或既有图件。
''', encoding='utf-8')
print(json.dumps(dict(png=str(HERE/'pareto_actual_results.png'), pdf=str(HERE/'pareto_actual_results.pdf'), plotted=5, excluded_no_incumbent=8, unique_nondominated_coordinates=1), ensure_ascii=False))
