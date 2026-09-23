"""Summarize only the newly executed synthetic output folders; no solver runs."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
OUTPUTS = HERE.parent
REPO = OUTPUTS.parent.parent
HERE.mkdir(exist_ok=True)
for name in ("mplconfig", "tmp"):
    (HERE / name).mkdir(exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(HERE / "mplconfig")
os.environ["TEMP"] = os.environ["TMP"] = str(HERE / "tmp")
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

SOURCES = {}


def read(relative):
    path = OUTPUTS / relative
    SOURCES[path.relative_to(REPO).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return json.loads(path.read_text(encoding="utf-8"))


benchmark = read("benchmark80/summary.json")
records = benchmark["records"]
seeds = [7, 17, 42, 73, 101]
methods = ["greedy", "route_milp", "dual_route_milp", "resource_dispatch", "alns"]
by_key = {(row["seed"], row["method"]): row for row in records}
assert len(records) == len(by_key) == 25
assert set(by_key) == {(s, m) for s in seeds for m in methods}
for seed in seeds:
    source = read(f"benchmark80/seed_{seed}/comparison.json")
    assert source["methods"] == [{k: v for k, v in by_key[seed, m].items() if k != "seed"} for m in methods]
    inp = read(f"benchmark80/seed_{seed}/instance.json")
    assert len(inp["boxes"]) == 80

metrics = ["weighted_tardiness_s", "makespan_s", "energy_kwh"]
paired = []
for seed in seeds:
    dispatch = by_key[seed, "resource_dispatch"]
    alns = by_key[seed, "alns"]
    paired.append({
        "seed": seed,
        "dispatch": {k: dispatch[k] for k in metrics + ["trips", "feasible"]},
        "alns": {k: alns[k] for k in metrics + ["trips", "feasible"]},
        "reduction_pct": {k: 100 * (dispatch[k] - alns[k]) / dispatch[k] for k in metrics},
    })

means = {
    "dispatch": {k: statistics.mean(p["dispatch"][k] for p in paired) for k in metrics},
    "alns": {k: statistics.mean(p["alns"][k] for p in paired) for k in metrics},
    "mean_paired_reduction_pct": {k: statistics.mean(p["reduction_pct"][k] for p in paired) for k in metrics},
}
means["reduction_of_mean_pct"] = {k: 100 * (means["dispatch"][k] - means["alns"][k]) / means["dispatch"][k] for k in metrics}
small = read("small_s7/transport/comparison.json")
small_input = read("small_s7/instance.json")
assert len(small_input["boxes"]) == 12
radio = read("small_s7/radio/radio_result.json")
partitions = {f"{p}_{k}": read(f"small_s7/partition_{p}_{k}.json") for p in ["strict", "duplicate"] for k in [2, 3]}
validation = read("small_s7/export/validation.json")
relay_path = OUTPUTS / "small_s7/export/relay_tasks.csv"
SOURCES[relay_path.relative_to(REPO).as_posix()] = hashlib.sha256(relay_path.read_bytes()).hexdigest()
with relay_path.open(encoding="utf-8-sig", newline="") as f:
    relay_tasks = list(csv.DictReader(f))
logs = {"small": read("logs/small_end_to_end.json"), "benchmark80": read("logs/benchmark80.json")}
assert all(v["returncode"] == 0 and v["status"] == "completed" for v in logs.values())
exact = read("benchmark80/small_exact.json")
status_counts = {m: {"feasible": sum(by_key[s, m]["feasible"] for s in seeds), "infeasible": sum(not by_key[s, m]["feasible"] for s in seeds)} for m in methods}
dual_equal = all(all(by_key[s, "route_milp"][k] == by_key[s, "dual_route_milp"][k] for k in metrics + ["trips", "hard_violations"]) for s in seeds)

summary = {
    "scope": "Only outputs/small_s7 and outputs/benchmark80; all synthetic; not official attachment results.",
    "seeds": seeds,
    "environment": benchmark["environment"],
    "budgets": {
        "milp_stage_limit_s": 10,
        "alns_iteration_limit": 70,
        "alns_total_limit_s": 30,
        "benchmark_route_trials": 500,
        "small_route_trials": 200,
        "max_stops": 3,
        "max_boxes_per_route": 8,
        "dual_rounds": 2,
        "benchmark_full_backend": "none",
        "small_full_backend": "HiGHS",
        "small_time_step_s": 60,
        "small_radio_sample_step_s": 40,
        "small_radio_evaluation_step_s": 10,
        "radio_ray_step_m": validation["radio_ray_step_m"],
    },
    "benchmark_records": records,
    "method_feasibility": status_counts,
    "dispatch_alns_pairs": paired,
    "means": means,
    "dual_vs_static_no_objective_improvement_on_all_seeds": dual_equal,
    "small_transport": small,
    "small_radio": radio,
    "small_partitions": partitions,
    "small_relay_tasks": relay_tasks,
    "small_validation": validation,
    "small_exact_bin_packing": exact,
    "execution_logs": logs,
    "not_run_in_these_experiments": ["CP-SAT", "80-box full time-indexed model", "80-box fixed-route retiming", "synthetic Pareto sweep", "radio 60/20/5 s reconstruction", "radio ray 30/15/7.5 m sweep"],
    "limits": [
        "Synthetic geometry, physical parameters and deadlines cannot be treated as official values.",
        "Only a finite route pool is searched; the same box group retains one visit order.",
        "MILP optimality applies to the finite candidate pool and time grid, not the continuous original problem.",
        "A solved static route selection can still violate delivery hard deadlines after list scheduling.",
        "No unexecuted backend is assigned a score; no formal population confidence claim from five synthetic seeds.",
        "Fine radio evaluation is numerical sampling, not a continuous-time proof.",
        "Elapsed method time excludes route-pool construction except method-specific expansion; end-to-end logs report whole-process time.",
    ],
    "source_sha256": SOURCES,
}
(HERE / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")

lines = [
    "# 本次合成实验实跑摘要",
    "",
    "仅读取 `outputs/small_s7/` 与 `outputs/benchmark80/` 的本次输出及对应执行日志；不引用旧 `research_fd/results/` 数字。全部是合成实验，几何、需求、能耗、充电和通信参数不能当作正式题给值。",
    "",
    "## 执行范围与预算",
    "",
    f"小规模：4 服务点、12 箱、种子 7；7 种运输方法、固定运输中继、严格/复制解释的两/三分组。整条命令耗时 {logs['small']['elapsed_s']:.3f} s。",
    f"80 箱：15 服务点，5 种子、每实例 5 种方法，共 25 组；整条命令耗时 {logs['benchmark80']['elapsed_s']:.3f} s。MILP 每目标阶段上限 10 s，ALNS 70 次迭代且总限时 30 s；路线试验分别 200/500 次，扩列 2 轮，每路线最多 3 服务点/8 箱。500 是候选生成次数，不是 ALNS 迭代数。",
    "",
    "80 箱本次 `--backend none`，未运行完整时间索引模型、固定路线重排及 CP-SAT；集合划分与 ALNS 内部确实调用 HiGHS。小规模完整/重排使用 60 s 启动网格。所有最优状态限于已生成候选与离散时间；不等于原问题全局最优。方法耗时不包含初始路线池生成，整条命令耗时包含生成与写盘。",
    "",
    "## 80 箱可行性与负结果",
    "",
    "每个单元格是硬截止违约箱数；0 的方法同时通过覆盖、重复箱和资源冲突检查，因而可行。非零结果全部保留。",
    "",
    "| 种子 | greedy | route_milp | dual_route_milp | resource_dispatch | alns |",
    "|---|---:|---:|---:|---:|---:|",
]
for seed in seeds:
    lines.append("| " + str(seed) + " | " + " | ".join(str(by_key[seed, m]["hard_violations"]) for m in methods) + " |")
lines += [
    "",
    "派单和 ALNS 各 5/5 可行，另三方法各 0/5 可行。对偶扩列后路线数、硬违约、迟到、工期和能耗与静态集合划分全部相同，未获改进。静态集合划分虽比贪心少飞，但每个种子的硬违约都更多；这些无效方案不能因能耗较低而列为可行优胜者。",
    "",
    "## 同实例派单 → ALNS",
    "",
    "每单元格为派单 → ALNS，括号为相对下降 `(派单−ALNS)/派单`。",
    "",
    "| 种子 | 趟数 | 加权软迟到 / s | 工期 / s | 能耗 / kWh |",
    "|---|---|---|---|---|",
]
for p in paired:
    cells = [str(p["seed"]), f"{p['dispatch']['trips']} → {p['alns']['trips']}"]
    for m in metrics:
        decimals = 3 if m == "energy_kwh" else 2
        cells.append(f"{p['dispatch'][m]:.{decimals}f} → {p['alns'][m]:.{decimals}f}（{p['reduction_pct'][m]:.2f}%）")
    lines.append("| " + " | ".join(cells) + " |")
lines += [
    "",
    "| 统计口径 | 加权软迟到 | 工期 | 能耗 |",
    "|---|---:|---:|---:|",
    "| 派单均值 | " + " | ".join(f"{means['dispatch'][m]:.5f}" for m in metrics) + " |",
    "| ALNS 均值 | " + " | ".join(f"{means['alns'][m]:.5f}" for m in metrics) + " |",
    "| 5 个实例下降百分比的算术平均 | " + " | ".join(f"{means['mean_paired_reduction_pct'][m]:.2f}%" for m in metrics) + " |",
    "| 两方法均值之差 / 派单均值 | " + " | ".join(f"{means['reduction_of_mean_pct'][m]:.2f}%" for m in metrics) + " |",
    "",
    "上述两个百分比口径分别列出，不能混用。未对 5 个合成种子作总体显著性声明。",
    "",
    "## 12 箱完整模型、重排与中继",
    "",
    "| 方法 | 可行 | 趟数 | 加权软迟到 / s | 工期 / s | 运输能耗 / kWh | 方法耗时 / s |",
    "|---|---|---:|---:|---:|---:|---:|",
]
for row in small["methods"]:
    lines.append(f"| {row['method']} | {'是' if row['feasible'] else '否'} | {row['trips']} | {row['weighted_tardiness_s']:.2f} | {row['makespan_s']:.5f} | {row['energy_kwh']:.5f} | {row['elapsed_s']:.4f} |")
lines += [
    "",
    "固定重排 4 路线/32 启动选项，未改善 ALNS；完整模型 362 路线/1186 选项，两目标阶段均 status=0、gap=0。完整模型工期更短但运输能耗高于 ALNS，不能声称所有目标同时更好；本次完整模型没有能耗最小化阶段。",
    f"固定运输中继使用 {radio['sites']} 个位置、{radio['sessions']} 个会话候选，{radio['requirements']} 个条件通信需求，无不可达需求；时序候选未截断。三阶段均 status=0、gap=0，得到 {radio['relay_trips']} 趟中继任务，联合返回 {radio['joint_makespan_s']:.5f} s，中继能耗 {radio['relay_energy_kwh']:.8f} kWh，总能耗 {radio['stages'][-1]['value']:.8f} kWh。",
    "",
    "| 中继机身/能源编号 | 起飞 / s | 到位 / s | 建链完成 / s | 服务结束 / s | 返仓 / s | 再可用 / s | 能源恢复 / s | 能耗 / kWh |",
    "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
]
for r in relay_tasks:
    vals = [r["aircraft_id"] + "/" + r["pack_label"]]
    for k in ["departure_s", "arrived_s", "ready_s", "service_stop_s", "returned_s", "aircraft_available_s", "pack_full_s", "energy_kwh"]:
        vals.append(f"{float(r[k]):.5f}")
    lines.append("| " + " | ".join(vals) + " |")
fine = radio["fine_evaluation"]
lines += [
    "",
    f"通信求解采样 40 s、启动网格 60 s；复核采样 10 s 并包含阶段边界，共 {fine['samples']} 点、断联 {fine['misses']} 点、最小裕量 {fine['minimum_margin_db']:.8f} dB。射线步长 {validation['radio_ray_step_m']:.0f} m。此处只执行了该精度，未执行 60/20/5 s 重建或 30/15/7.5 m 射线对照；零断联是有限采样结论。导出独立算术检查状态为 `{validation['status']}`，物理/无线仍复用声明的模型引擎。",
    "",
    "## 冻结计划两/三分组",
    "",
    "严格共享口径下 4 服务点连成 1 个不可分分量，两组、三组均不可行；未改路线或任务时刻凑组。复制中继口径允许增加资源：",
    "",
    "| 分组数 | 分组 | A/B/C 机身总量（电池同量） | 中继机身/能源总量 | 比原计划新增 |",
    "|---|---|---|---|---|",
]
for k in [2, 3]:
    p = partitions[f"duplicate_{k}"]
    totals = {key: sum(r[key] for r in p["resources"]) for key in p["global_resources"]}
    groups = "；".join("+".join(g) for g in p["groups"])
    lines.append(f"| {k} | {groups} | {totals['A_aircraft']}/{totals['B_aircraft']}/{totals['C_aircraft']} | {totals['relay']}/{totals['relay_pack']} | {p['extra']['relay']} 架中继、{p['extra']['relay_pack']} 组能源 |")
lines += [
    "",
    "两分枚举 7 个、三分枚举 6 个固定分量划分，当前枚举完整。分组不会降低原运输时序需求；复制解释的资源增加必须保留。每组逐型资源完整值见 `summary.json.small_partitions`。",
    "",
    "另有本次小箱组反例：重量 `[6,5,3,2,2,2]`、载荷 10，降序首次适配 3 趟，完整可行子集集合划分 2 趟，均装载 10。不是正式 80 箱最优架次。",
    "",
    "本子任务不跑正式附件实验，也未补填 CP-SAT、80 箱完整模型或能耗—工期扫描的成绩。上述时限中没有产生超时无 incumbent 的结果；保留的负结果是 80 箱硬违约、对偶无改进、小规模固定重排无改进，以及严格分组不可行。",
    "",
    "## 可复核文件",
    "",
    "- `summary.json`：全部 25 组记录、配对改善、小规模求解阶段、分组、执行命令、来源 SHA256。",
    "- `method_comparison.png` / `.pdf`：80 箱硬违约矩阵与可行两方法的逐种子对照，无误差条或未运行后端。",
    "- `build_summary.py`：从本次原始输出重建此摘要与图；不会调用优化后端或修改原输出。",
    "- 逐箱交付、机身/电池时间表及中继任务原表保存在 `../small_s7/export/`。",
    "",
]
(HERE / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})
fig, axs = plt.subplots(2, 2, figsize=(11.9, 8.2))
fig.subplots_adjust(left=0.145, right=0.98, top=0.86, bottom=0.17, hspace=0.46, wspace=0.30)
fig.suptitle("Synthetic 80-box experiments | five seeds", fontsize=17, x=0.54, y=0.97)
fig.text(0.54, 0.925, "Actual runs only: 3 static methods fail hard deadlines; dispatch and ALNS are feasible", ha="center", fontsize=10)
mat = np.array([[by_key[s, m]["hard_violations"] for s in seeds] for m in methods])
ax = axs[0, 0]
ax.imshow(mat, cmap="YlOrRd", vmin=0, vmax=10, aspect="auto")
ax.set_xticks(range(5), [str(s) for s in seeds])
ax.set_yticks(range(5), ["Greedy", "Route MILP", "Dual route MILP", "Dispatch", "ALNS"])
ax.set_xlabel("Instance seed")
ax.set_title("(a) Hard-deadline violations [boxes]", loc="left", pad=9)
for i in range(5):
    for j in range(5):
        ax.text(j, i, str(mat[i, j]), ha="center", va="center", color="white" if mat[i, j] >= 7 else "#222222", fontweight="bold")
for ax, metric, title, scale, unit in zip(axs.flat[1:], metrics, ["Weighted tardiness", "Return makespan", "Transport energy"], [1/60, 1/60, 1], ["weighted min", "min", "kWh"]):
    x = np.arange(5)
    d = np.array([by_key[s, "resource_dispatch"][metric] * scale for s in seeds])
    a = np.array([by_key[s, "alns"][metric] * scale for s in seeds])
    ax.bar(x - .19, d, width=.36, label="Dispatch", color="#8B9AAA")
    ax.bar(x + .19, a, width=.36, label="ALNS", color="#087F8C")
    ax.set_xticks(x, [str(s) for s in seeds])
    ax.set_xlabel("Instance seed")
    ax.set_ylabel(unit)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#dddddd", linewidth=.65)
    letter = {"weighted_tardiness_s": "b", "makespan_s": "c", "energy_kwh": "d"}[metric]
    ax.set_title(f"({letter}) {title}", loc="left", pad=9)
    ax.text(.98, .96, f"Mean paired reduction: {means['mean_paired_reduction_pct'][metric]:.2f}%", transform=ax.transAxes, ha="right", va="top", fontsize=9)
    ax.set_ylim(0, max(d) * 1.20)
axs[0, 1].legend(loc="upper left", frameon=False, fontsize=9)
fig.text(.145, .04, "Source: outputs/benchmark80/summary.json. Each bar is one synthetic instance; no population inference.\nMILP stage cap 10 s; ALNS 70 iterations / 30 s cap; finite route pools. Full time-indexed and CP-SAT backends not run here.", fontsize=8.5, color="#444444", va="bottom")
fig.savefig(HERE / "method_comparison.png", dpi=180)
fig.savefig(HERE / "method_comparison.pdf")
plt.close(fig)
(HERE / "figure_spec.json").write_text(json.dumps({
    "source": "research_fd/outputs/benchmark80/summary.json",
    "source_sha256": SOURCES["research_fd/outputs/benchmark80/summary.json"],
    "script": "build_summary.py",
    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "panels": ["Hard violations (5 methods, 5 seeds)", "Weighted tardiness in weighted minutes", "Return makespan in minutes", "Transport energy in kWh"],
    "uncertainty": "None displayed; observations are five individual synthetic seeds.",
    "paired_reduction": "Arithmetic mean of per-seed (dispatch - ALNS) / dispatch percentages.",
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(means, ensure_ascii=False, indent=2))
