"""Derive additional paper tables only from current independently checked rows."""
from __future__ import annotations

import csv
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "求解/正式实验/逐例分析.csv"
PAIR = ROOT / "求解/正式实验/场景配对分析.csv"
TRANSFER = ROOT / "求解/图件数据/q2-F03.csv"
SENS = ROOT / "求解/正式实验/L2参数敏感性_非官方/逐配置最优.csv"
OUT = ROOT / "求解/正式实验/深度分析.json"
CHAPTERS = ROOT / "论文/章节内容"


def read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fmt(value: float, digits: int = 4) -> str:
    return f"{value:.{digits}f}"


def save(name: str, text: str) -> None:
    (CHAPTERS / name).write_text(text.strip() + "\n", encoding="utf-8")


def main() -> None:
    rows = read(CASE)
    pairs = read(PAIR)
    transfer = read(TRANSFER)
    sensitivity = read(SENS)
    assert len(rows) == 500 and len(pairs) == 400 and len(sensitivity) == 54
    by_case = defaultdict(dict)
    for row in rows:
        by_case[row["case"]][int(row["cores"])] = row
    assert len(by_case) == 100 and all(set(v) == set(range(1, 6)) for v in by_case.values())
    result: dict = {
        "input_sha256": {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p)
                         for p in (CASE, PAIR, TRANSFER, SENS)},
        "q1": {}, "q2": {}, "q3": {},
    }

    bands = [(r"$f\leq0.05$", 0, .05), (r"$0.05<f\leq0.20$", .05, .20),
             (r"$0.20<f\leq0.60$", .20, .60), (r"$f>0.60$", .60, 1.01)]
    q1_groups = []
    for label, low, high in bands:
        selected = [v[5] for v in by_case.values() if low < float(v[5]["largest_component_fraction"]) <= high]
        assert selected
        counts = Counter(r["q1_candidate"] for r in selected)
        row = {"label": label, "count": len(selected),
               "mean_speedup": statistics.mean(float(r["q1_speedup"]) for r in selected),
               "median_depth": statistics.median(int(r["dag_depth"]) for r in selected),
               "candidate_counts": {k: counts[k] for k in ("components", "bands8", "batches800")}}
        q1_groups.append(row)
    result["q1"]["structure_groups"] = q1_groups
    q1_steps = []
    for k in range(2, 6):
        declining = [(v[k-1], v[k]) for v in by_case.values()
                     if float(v[k]["q1_speedup"]) < float(v[k-1]["q1_speedup"]) - 1e-9]
        q1_steps.append({"transition": f"{k-1}→{k}", "declining_cases": len(declining),
                         "candidate_changed": sum(a["q1_candidate"] != b["q1_candidate"] for a,b in declining),
                         "added_copy_increased": sum(int(b["q1_added_copy_bytes"]) > int(a["q1_added_copy_bytes"])
                                                    for a,b in declining)})
    result["q1"]["declining_transitions"] = q1_steps
    result["q1"]["nonmonotonic_distinct_cases"] = sum(any(float(v[k]["q1_speedup"]) < float(v[k-1]["q1_speedup"]) - 1e-9
                                                                for k in range(2,6)) for v in by_case.values())
    assert result["q1"]["nonmonotonic_distinct_cases"] == 26

    transfer_by_core = defaultdict(list)
    for row in transfer:
        transfer_by_core[int(row["cores"])].append(row)
    q2_steps = []
    for k in range(2, 6):
        group = [r for r in pairs if int(r["cores"]) == k]
        tr = transfer_by_core[k]
        assert len(group) == len(tr) == 100
        gains = [float(r["scene_b_gain_same_plan"]) for r in group]
        policies = [float(r["q2_policy_gain"]) for r in group]
        q2_steps.append({
            "cores": k, "same_plan_mean": statistics.mean(gains),
            "same_plan_better": sum(x > 1 + 1e-9 for x in gains),
            "same_plan_worse": sum(x < 1 - 1e-9 for x in gains),
            "policy_mean": statistics.mean(policies),
            "policy_positive": sum(x > 1 + 1e-9 for x in policies),
            "candidate_switches": sum(v[k]["q1_candidate"] != v[k]["q2_candidate"] for v in by_case.values()),
            "spill_cases": sum(int(r["spill_added_copy_bytes"]) > 0 for r in tr),
            "spill_bytes_total": sum(int(r["spill_added_copy_bytes"]) for r in tr),
            "partition_bytes_total": sum(int(r["partition_added_copy_bytes"]) for r in tr),
        })
    result["q2"]["by_core"] = q2_steps

    q3_steps = []
    for k in range(1, 6):
        group = [v[k] for v in by_case.values()]
        gains = [float(r["q3_cache_gain"]) for r in group]
        q3_steps.append({
            "cores": k, "mean_cache_gain": statistics.mean(gains),
            "median_cache_gain": statistics.median(gains),
            "positive_cases": sum(x > 1 + 1e-9 for x in gains),
            "negative_cases": sum(x < 1 - 1e-9 for x in gains),
            "zero_hit_cases": sum(float(r["q3_cache_hit_rate"]) == 0 for r in group),
            "mean_hit_rate": statistics.mean(float(r["q3_cache_hit_rate"]) for r in group),
        })
    result["q3"]["by_core"] = q3_steps
    grid = defaultdict(dict)
    for row in sensitivity:
        grid[row["case"]][(int(row["capacity_bytes"]), int(row["bandwidth_bytes_per_cycle"]))] = row
    assert len(grid) == 6 and all(len(v) == 9 for v in grid.values())
    q3_grid = []
    for case, values in sorted(grid.items()):
        default = int(values[(1048576, 250)]["makespan_cycles"])
        big = int(values[(4194304, 250)]["makespan_cycles"])
        fast = int(values[(1048576, 500)]["makespan_cycles"])
        slow = int(values[(1048576, 60)]["makespan_cycles"])
        times = [int(v["makespan_cycles"]) for v in values.values()]
        q3_grid.append({"case": case, "default_cycles": default, "range_min": min(times),
                        "range_max": max(times), "capacity_gain_percent": (default-big)/default*100,
                        "bandwidth_gain_percent": (default-fast)/default*100,
                        "bandwidth_slow_penalty_percent": (slow-default)/default*100,
                        "default_hit_rate": float(values[(1048576,250)]["hit_rate"]),
                        "candidate_count": len({v["candidate"] for v in values.values()})})
    result["q3"]["nonofficial_grid"] = q3_grid
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    q1lines = [r"\begin{table}[htbp]\centering", r"\caption{五核最大弱连通块占比分层的方案与收益}\label{tab:q1-structure-deep}",
               r"\small\begin{tabular}{lrrrrr}\toprule", r"最大块占比 $f$ & 算例数 & 平均加速比 & DAG深度中位数 & 连通块 & 分段/分批 \\ \midrule"]
    for r in q1_groups:
        c = r["candidate_counts"]
        q1lines.append(f'{r["label"]} & {r["count"]} & {fmt(r["mean_speedup"])} & {fmt(r["median_depth"],1)} & {c["components"]} & {c["bands8"]}/{c["batches800"]} \\\\')
    q1lines += [r"\bottomrule\end{tabular}\end{table}",
                r"\begin{table}[htbp]\centering", r"\caption{问题一相邻核数下降的真实配置次数}\label{tab:q1-nonmonotone-deep}",
                r"\small\begin{tabular}{lrrr}\toprule", r"核数变化 & 加速比下降配置 & 同时换候选族 & 同时新增搬运增加 \\ \midrule"]
    for r in q1_steps:
        q1lines.append(f'{r["transition"]} & {r["declining_cases"]} & {r["candidate_changed"]} & {r["added_copy_increased"]} \\\\')
    q1lines += [r"\bottomrule\end{tabular}\end{table}"]
    save("q1_深度分析.generated.tex", "\n".join(q1lines))

    q2lines = [r"\begin{table}[htbp]\centering", r"\caption{场景B逐核成对比较与搬运来源}\label{tab:q2-paired-deep}",
               r"\small\begin{tabular}{rrrrrrr}\toprule", r"核数 & 同方案均值 & 改善/变差例数 & 重选均值 & 重选受益例数 & 候选切换 & Spill例数 \\ \midrule"]
    for r in q2_steps:
        q2lines.append(f'{r["cores"]} & {fmt(r["same_plan_mean"])} & {r["same_plan_better"]}/{r["same_plan_worse"]} & {fmt(r["policy_mean"])} & {r["policy_positive"]} & {r["candidate_switches"]} & {r["spill_cases"]} \\\\')
    q2lines += [r"\bottomrule\end{tabular}\end{table}"]
    save("q2_深度分析.generated.tex", "\n".join(q2lines))

    q3lines = [r"\begin{table}[htbp]\centering", r"\caption{固定同一方案时的逐核L2收益分布}\label{tab:q3-core-deep}",
               r"\small\begin{tabular}{rrrrrr}\toprule", r"核数 & Cache比均值 & 中位数 & 受益/逆向例数 & 零命中例数 & 平均命中率 \\ \midrule"]
    for r in q3_steps:
        q3lines.append(f'{r["cores"]} & {fmt(r["mean_cache_gain"])} & {fmt(r["median_cache_gain"])} & {r["positive_cases"]}/{r["negative_cases"]} & {r["zero_hit_cases"]} & {fmt(r["mean_hit_rate"]*100,2)}\\% \\\\')
    q3lines += [r"\bottomrule\end{tabular}\end{table}"]
    save("q3_逐核深度.generated.tex", "\n".join(q3lines))
    gridlines = [r"\begin{table}[htbp]\centering",
                 r"\caption{六例非官方L2网格在默认点附近的有限差分}\label{tab:q3-grid-deep}",
                 r"\small\begin{tabular}{lrrrr}\toprule", r"算例 & 默认周期 & 九格范围/千周期 & 容量增益 & 带宽增益 \\ \midrule"]
    for r in q3_grid:
        gridlines.append(f'{r["case"].split("_")[-1]} & {r["default_cycles"]} & {fmt(r["range_min"]/1000,1)}--{fmt(r["range_max"]/1000,1)} & {fmt(r["capacity_gain_percent"],2)}\\% & {fmt(r["bandwidth_gain_percent"],2)}\\% \\\\')
    gridlines += [r"\bottomrule\end{tabular}\end{table}"]
    save("q3_参数深度.generated.tex", "\n".join(gridlines))
    print(json.dumps({"status": "DERIVED", "q1_groups": q1_groups, "q1_steps": q1_steps,
                      "q2_steps": q2_steps, "q3_steps": q3_steps, "q3_grid": q3_grid}, ensure_ascii=False))


if __name__ == "__main__":
    main()
