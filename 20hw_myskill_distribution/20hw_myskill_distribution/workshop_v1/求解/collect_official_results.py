"""Select evaluated plans, independently verify, and publish per-case tables."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import statistics
from collections import defaultdict
from pathlib import Path

from verify_official_results import read_json, verify


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "求解/正式实验/候选评估"
DATA = ROOT / "数据/原始/A题官方附件/data"
PROBLEM = {1: "问题一", 2: "问题二", 3: "问题三"}


def receipt(case: str, n: int, candidate: str, q: int) -> dict | None:
    path = RUNS / case / f"n{n}" / candidate / f"q{q}.receipt.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def select(case: str, n: int, q: int) -> tuple[str, dict]:
    choices = []
    for candidate in ("components", "bands8", "batches800"):
        r = receipt(case, n, candidate, q)
        if r is not None and r.get("status") == "PASS":
            choices.append((r["makespan"], r["data_movement_bytes"]["added_copy_bytes"], candidate, r))
    if not choices:
        raise RuntimeError(f"missing successful official evaluation: {case} n{n} q{q}")
    _, _, candidate, r = min(choices)
    return candidate, r


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=100)
    parser.add_argument("--max-cores", type=int, default=5)
    args = parser.parse_args()
    selected = {q: [] for q in PROBLEM}
    summaries = []
    for index in range(1, args.cases + 1):
        case = f"case_{index:03d}"
        graph_path = DATA / f"{case}.json"
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        base = receipt(case, 1, "singlecore", 0)
        if base is None or base.get("status") != "PASS":
            raise RuntimeError(f"missing singlecore baseline for {case}")
        baseline = base["makespan"]
        for n in range(1, args.max_cores + 1):
            q3_candidate, q3_receipt = select(case, n, 3)
            for q in PROBLEM:
                candidate, r = (("components", base) if q == 1 and n == 1
                                else (q3_candidate, q3_receipt) if q == 3
                                else select(case, n, q))
                folder = RUNS / case / f"n{n}" / candidate
                plan_path = folder / "plan.json"
                result_path = (RUNS / case / "n1/singlecore/q0.json.gz"
                               if q == 1 and n == 1 else folder / f"q{q}.json.gz")
                plan, result = read_json(plan_path), read_json(result_path)
                independent = verify(graph, plan, result)
                output = ROOT / f"求解/{PROBLEM[q]}/结果/验证/{case}_n{n}.json"
                output.parent.mkdir(parents=True, exist_ok=True)
                independent.update({"candidate": candidate, "official_result": result_path.relative_to(ROOT).as_posix()})
                output.write_text(json.dumps(independent, ensure_ascii=False, indent=2), encoding="utf-8")
                plan_output = ROOT / f"求解/{PROBLEM[q]}/方案/{n}核/{case}_multicore_res.json"
                plan_output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(plan_path, plan_output)
                row = {
                    "case": case,
                    "cores": n,
                    "candidate": candidate,
                    "makespan_cycles": r["makespan"],
                    "singlecore_cycles": baseline,
                    "speedup": baseline / r["makespan"],
                    "original_copy_bytes": r["data_movement_bytes"]["original_graph_copy_bytes"],
                    "scheduled_copy_bytes": r["data_movement_bytes"]["scheduled_copy_bytes"],
                    "added_copy_bytes": r["data_movement_bytes"]["added_copy_bytes"],
                    "partition_added_copy_bytes": r["data_movement_bytes"]["partition_added_copy_bytes"],
                    "spill_added_copy_bytes": r["data_movement_bytes"]["spill_added_copy_bytes"],
                    "official_result": result_path.relative_to(ROOT).as_posix(),
                    "plan": plan_output.relative_to(ROOT).as_posix(),
                    "verification": output.relative_to(ROOT).as_posix(),
                }
                if q == 3:
                    no_l2 = receipt(case, n, candidate, 2)
                    if no_l2 is None or no_l2.get("status") != "PASS":
                        raise RuntimeError(f"missing matched no-L2 result for {case} n{n}")
                    no_l2_result = read_json(folder / "q2.json.gz")
                    verify(graph, plan, no_l2_result)
                    row.update({
                        "no_l2_makespan_cycles": no_l2["makespan"],
                        "cache_gain": no_l2["makespan"] / r["makespan"],
                        "cache_hits": r["cache_stats"]["hits"],
                        "cache_accesses": r["cache_stats"]["accesses"],
                        "cache_hit_bytes": r["cache_stats"]["hit_bytes"],
                        "cache_miss_bytes": r["cache_stats"]["miss_bytes"],
                        "cache_hit_rate": r["cache_stats"]["hit_rate"],
                        "matched_no_l2_result": (folder / "q2.json.gz").relative_to(ROOT).as_posix(),
                    })
                selected[q].append(row)
        print(f"verified {case}", flush=True)
    for q, rows in selected.items():
        write_csv(ROOT / f"求解/{PROBLEM[q]}/结果/逐例官方评估.csv", rows)
        by_n = defaultdict(list)
        for row in rows:
            by_n[row["cores"]].append(row)
        for n, group in sorted(by_n.items()):
            item = {
                "question": q,
                "cores": n,
                "cases": len(group),
                "mean_speedup": statistics.mean(x["speedup"] for x in group),
                "median_speedup": statistics.median(x["speedup"] for x in group),
                "mean_makespan_cycles": statistics.mean(x["makespan_cycles"] for x in group),
                "median_makespan_cycles": statistics.median(x["makespan_cycles"] for x in group),
                "mean_added_copy_bytes": statistics.mean(x["added_copy_bytes"] for x in group),
                "band_selected": sum(x["candidate"] == "bands8" for x in group),
            }
            if q == 3:
                item.update({
                    "mean_cache_gain": statistics.mean(x["cache_gain"] for x in group),
                    "mean_cache_hit_rate": statistics.mean(x["cache_hit_rate"] for x in group),
                })
            summaries.append(item)
    write_csv(ROOT / "求解/正式实验/总体摘要.csv", summaries)
    (ROOT / "求解/正式实验/总体摘要.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
