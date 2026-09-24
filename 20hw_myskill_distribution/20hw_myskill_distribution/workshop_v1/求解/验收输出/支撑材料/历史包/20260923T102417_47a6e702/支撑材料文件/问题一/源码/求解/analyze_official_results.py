"""Derive paper statistics solely from published, independently checked cases."""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOLVE = ROOT / "求解"
OUT = SOLVE / "正式实验"


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def quantile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    at = (len(ordered) - 1) * fraction
    low = int(at)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] * (1 - (at - low)) + ordered[high] * (at - low)


def describe(values: list[float]) -> dict:
    return {
        "count": len(values), "mean": statistics.mean(values),
        "median": statistics.median(values), "p10": quantile(values, .1),
        "p90": quantile(values, .9), "minimum": min(values),
        "maximum": max(values),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    base = {row["case"]: row for row in read_csv(SOLVE / "数据审计.csv")}
    q = {
        number: {(row["case"], int(row["cores"])): row for row in read_csv(
            SOLVE / f"问题{['一', '二', '三'][number-1]}/结果/逐例官方评估.csv")}
        for number in (1, 2, 3)
    }
    expected = {(f"case_{index:03d}", cores) for index in range(1, 101) for cores in range(1, 6)}
    assert all(set(table) == expected for table in q.values()), "all 100 cases × 5 cores required"
    for question in q:
        assert all((SOLVE / "../" / row["verification"]).is_file() for row in q[question].values())
    cases = []
    by_question_core = defaultdict(list)
    q2_vs_q1_fixed = []
    for case, cores in sorted(expected):
        r1, r2, r3 = (q[i][(case, cores)] for i in (1, 2, 3))
        a = base[case]
        nops = int(a["internal_ops"])
        components = int(a["components"])
        width = int(a["max_level_width"])
        ratio = int(a["largest_component"]) / nops
        q1t = int(r1["makespan_cycles"])
        q2t = int(r2["makespan_cycles"])
        q3t = int(r3["makespan_cycles"])
        no_l2 = int(r3["no_l2_makespan_cycles"])
        speedups = [float(row["speedup"]) for row in (r1, r2, r3)]
        row = {
            "case": case, "cores": cores, "internal_ops": nops,
            "components": components, "dag_depth": int(a["dag_depth"]),
            "max_level_width": width, "largest_component_fraction": ratio,
            "q1_candidate": r1["candidate"], "q2_candidate": r2["candidate"],
            "q3_candidate": r3["candidate"],
            "q1_makespan_cycles": q1t, "q2_makespan_cycles": q2t,
            "q3_makespan_cycles": q3t, "q3_matched_no_l2_cycles": no_l2,
            "q1_speedup": speedups[0], "q2_speedup": speedups[1],
            "q3_speedup": speedups[2],
            "q1_added_copy_bytes": int(r1["added_copy_bytes"]),
            "q2_added_copy_bytes": int(r2["added_copy_bytes"]),
            "q3_added_copy_bytes": int(r3["added_copy_bytes"]),
            "q2_over_q1_selected_gain": q1t / q2t,
            "q3_cache_gain": float(r3["cache_gain"]),
            "q3_cache_hit_rate": float(r3["cache_hit_rate"]),
            "q3_cache_hits": int(r3["cache_hits"]),
            "q3_cache_accesses": int(r3["cache_accesses"]),
            "q3_cache_hit_bytes": int(r3["cache_hit_bytes"]),
            "q3_cache_miss_bytes": int(r3["cache_miss_bytes"]),
        }
        cases.append(row)
        for question in (1, 2, 3):
            by_question_core[(question, cores)].append(float(q[question][(case, cores)]["speedup"]))
        if cores > 1:
            path = OUT / "候选评估" / case / f"n{cores}" / r1["candidate"] / "q2.receipt.json"
            receipt = json.loads(path.read_text(encoding="utf-8"))
            assert receipt["status"] == "PASS"
            q2_fixed = int(receipt["makespan"])
            q2_vs_q1_fixed.append({
                "case": case, "cores": cores, "candidate": r1["candidate"],
                "q1_cycles": q1t, "q2_same_plan_cycles": q2_fixed,
                "scene_b_gain_same_plan": q1t / q2_fixed,
                "q2_best_cycles": q2t,
                "q2_policy_gain": q2_fixed / q2t,
            })

    overall = {}
    for question in (1, 2, 3):
        overall[f"q{question}"] = {
            str(cores): describe(by_question_core[(question, cores)])
            for cores in range(1, 6)
        }
    for cores in range(2, 6):
        rows = [row for row in cases if row["cores"] == cores]
        fixed = [row for row in q2_vs_q1_fixed if row["cores"] == cores]
        overall[f"paired_{cores}"] = {
            "scene_b_vs_a_same_plan": describe([r["scene_b_gain_same_plan"] for r in fixed]),
            "scene_b_policy_gain": describe([r["q2_policy_gain"] for r in fixed]),
            "cache_gain_same_plan": describe([r["q3_cache_gain"] for r in rows]),
            "cache_hit_rate": describe([r["q3_cache_hit_rate"] for r in rows]),
            "cache_benefit_cases": sum(r["q3_cache_gain"] > 1 for r in rows),
            "q1_worse_than_singlecore": sum(r["q1_speedup"] < 1 for r in rows),
            "q2_worse_than_singlecore": sum(r["q2_speedup"] < 1 for r in rows),
            "q3_worse_than_singlecore": sum(r["q3_speedup"] < 1 for r in rows),
            "candidate_counts": {
                f"q{question}": dict(Counter(r[f"q{question}_candidate"] for r in rows))
                for question in (1, 2, 3)
            },
        }
    overall["nonmonotonic_cases"] = {
        f"q{question}": sum(
            any(float(q[question][(f"case_{index:03d}", n+1)]["speedup"]) <
                float(q[question][(f"case_{index:03d}", n)]["speedup"]) for n in range(1, 5))
            for index in range(1, 101)
        ) for question in (1, 2, 3)
    }
    write_csv(OUT / "逐例分析.csv", cases)
    write_csv(OUT / "场景配对分析.csv", q2_vs_q1_fixed)
    (OUT / "统计分析.json").write_text(json.dumps(overall, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: overall[key]["5"] if key.startswith("q") else overall[key]
                      for key in ("q1", "q2", "q3", "nonmonotonic_cases")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
