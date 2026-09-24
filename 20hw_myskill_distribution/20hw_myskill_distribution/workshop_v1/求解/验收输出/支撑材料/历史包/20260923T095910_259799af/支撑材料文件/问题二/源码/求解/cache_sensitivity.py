"""Non-official controlled L2 capacity/bandwidth study on six real graphs.

The contest's fixed config is never edited.  Every altered config is stored
under the workspace, and every score still comes from the unchanged official
problem-3 evaluator.  The same candidate plan is compared across settings;
best-of-candidates is reported separately as the adapted selection policy.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
from pathlib import Path

from run_official_experiments import CODE, DATA, ROOT, evaluate
from verify_official_results import verify
from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_1 import read_scene_a_config
from multicore_cut_evaluate_problem_2 import read_scene_b_config
from multicore_cut_evaluate_problem_3 import read_cache_config


BASE = ROOT / "求解/正式实验/候选评估"
OUT = ROOT / "求解/正式实验/L2参数敏感性_非官方"
CAPACITIES = (262144, 1048576, 4194304)
BANDWIDTHS = (60, 250, 500)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def representative_cases(rows: list[dict]) -> list[str]:
    five = sorted((row for row in rows if int(row["cores"]) == 5),
                  key=lambda row: (float(row["cache_gain"]), row["case"]))
    # Fixed rank rule, with ties broken by case ID.  This is a purposive
    # mechanism sample, not an estimator for all 100 benchmark instances.
    ranks = (0, 1, 48, 50, 98, 99)
    cases = sorted({five[index]["case"] for index in ranks})
    assert len(cases) == 6
    return cases


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = table(ROOT / "求解/问题三/结果/逐例官方评估.csv")
    assert len(rows) == 500
    cases = representative_cases(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    original_config = DATA / "config.txt"
    original_text = original_config.read_text(encoding="utf-8")
    results = []
    for cap in CAPACITIES:
        for bandwidth in BANDWIDTHS:
            config = OUT / f"config_C{cap}_B{bandwidth}.txt"
            adjusted = re.sub(r"(?m)^cache_capacity_bytes \d+$",
                              f"cache_capacity_bytes {cap}", original_text)
            adjusted = re.sub(r"(?m)^cache_bandwidth_bytes_per_cycle \d+$",
                              f"cache_bandwidth_bytes_per_cycle {bandwidth}", adjusted)
            assert adjusted != original_text or (cap, bandwidth) == (1048576, 250)
            config.write_text("# 非官方参数敏感性实验；正式成绩仅使用原始 data/config.txt。\n" + adjusted,
                              encoding="utf-8")
            settings = read_evaluation_config(str(config))
            scene_a = read_scene_a_config(str(config))
            scene_b = read_scene_b_config(str(config))
            cache = read_cache_config(str(config))
            assert cache["cache_capacity_bytes"] == cap
            assert cache["cache_bandwidth_bytes_per_cycle"] == bandwidth
            for case in cases:
                graph_path = DATA / f"{case}.json"
                graph = json.loads(graph_path.read_text(encoding="utf-8"))
                for candidate in ("components", "bands8", "batches800"):
                    plan_path = BASE / case / "n5" / candidate / "plan.json"
                    if not plan_path.is_file():
                        continue
                    plan = json.loads(plan_path.read_text(encoding="utf-8"))
                    folder = OUT / case / f"C{cap}_B{bandwidth}" / candidate
                    folder.mkdir(parents=True, exist_ok=True)
                    result_path = folder / "official_q3.json.gz"
                    receipt_path = folder / "receipt.json"
                    fingerprint = {
                        "graph_sha256": sha(graph_path), "plan_sha256": sha(plan_path),
                        "config_sha256": sha(config),
                        "official_evaluator_sha256": sha(CODE / "multicore_cut_evaluate_problem_3.py"),
                    }
                    if receipt_path.is_file() and result_path.is_file():
                        old = json.loads(receipt_path.read_text(encoding="utf-8"))
                        if old.get("fingerprint") == fingerprint and old.get("status") == "PASS":
                            result = json.loads(gzip.open(result_path, "rt", encoding="utf-8").read())
                        else:
                            result = None
                    else:
                        result = None
                    if result is None:
                        result = evaluate(3, graph, plan, settings, scene_a, scene_b, cache)
                        with gzip.open(result_path, "wt", encoding="utf-8") as stream:
                            json.dump(result, stream, ensure_ascii=False, separators=(",", ":"))
                        independent = verify(graph, plan, result)
                        receipt_path.write_text(json.dumps({
                            "status": "PASS", "fingerprint": fingerprint,
                            "result_sha256": sha(result_path),
                            "independent_validation": independent,
                        }, ensure_ascii=False, indent=2), encoding="utf-8")
                    stats = result["cache_stats"]
                    results.append({
                        "case": case, "cores": 5, "capacity_bytes": cap,
                        "bandwidth_bytes_per_cycle": bandwidth,
                        "candidate": candidate, "makespan_cycles": result["makespan"],
                        "added_copy_bytes": result["data_movement_bytes"]["added_copy_bytes"],
                        "hit_rate": stats["hit_rate"], "hit_bytes": stats["hit_bytes"],
                        "miss_bytes": stats["miss_bytes"],
                        "config": config.relative_to(ROOT).as_posix(),
                        "result": result_path.relative_to(ROOT).as_posix(),
                        "receipt": receipt_path.relative_to(ROOT).as_posix(),
                    })
                    print(json.dumps({"case": case, "capacity": cap, "bandwidth": bandwidth,
                                      "candidate": candidate, "makespan": result["makespan"]}), flush=True)
    write_csv(OUT / "全部候选.csv", results)
    best = {}
    for row in results:
        key = (row["case"], row["capacity_bytes"], row["bandwidth_bytes_per_cycle"])
        if key not in best or (row["makespan_cycles"], row["candidate"]) < (
                best[key]["makespan_cycles"], best[key]["candidate"]):
            best[key] = row
    write_csv(OUT / "逐配置最优.csv", list(best.values()))
    (OUT / "实验说明.json").write_text(json.dumps({
        "status": "non_official_sensitivity_only", "main_config": original_config.relative_to(ROOT).as_posix(),
        "cases": cases, "selection": "5核官方Cache收益升序第1、2、49、51、99、100位，按案例名打破并列",
        "capacity_bytes": CAPACITIES, "bandwidth_bytes_per_cycle": BANDWIDTHS,
        "scope": "用途是条件响应和候选方案切换；六个目的抽样案例不代表100例均值。",
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
