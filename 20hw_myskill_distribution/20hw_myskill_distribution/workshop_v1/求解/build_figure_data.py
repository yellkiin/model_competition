"""Create auditable, plot-ready rows from all 100 formal benchmark cases."""

import csv
import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOLVE = ROOT / "求解"
OUT = SOLVE / "图件数据"


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write(name, rows):
    assert rows
    path = OUT / f"{name}.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pick(rows, *fields):
    return [{name: row[name] for name in fields} for row in rows]


def main():
    OUT.mkdir(exist_ok=True)
    audit_path = SOLVE / "数据审计.csv"
    detail_path = SOLVE / "正式实验/逐例分析.csv"
    paired_path = SOLVE / "正式实验/场景配对分析.csv"
    q_paths = {q: SOLVE / f"问题{q}/结果/逐例官方评估.csv" for q in "一二三"}
    grid_path = SOLVE / "正式实验/L2参数敏感性_非官方/逐配置最优.csv"
    audit = read(audit_path)
    detail = read(detail_path)
    paired = read(paired_path)
    q = {name: read(path) for name, path in q_paths.items()}
    grid = read(grid_path)
    assert len(audit) == 100 and len(detail) == 500 and len(paired) == 400
    assert all(len(rows) == 500 for rows in q.values()) and len(grid) == 54
    graph = {row["case"]: row for row in audit}
    q2_n5 = {(row["case"], row["cores"]): row for row in q["二"]}
    result = {}
    result["q1-F01"] = [{"case": r["case"], "internal_ops": r["internal_ops"],
                          "components": r["components"],
                          "largest_component_fraction": int(r["largest_component"]) / int(r["internal_ops"])} for r in audit]
    result["q1-F02"] = pick(detail, "case", "cores", "q1_speedup")
    result["q1-F03"] = pick((r for r in detail if r["cores"] == "5"),
                           "case", "internal_ops", "largest_component_fraction", "q1_speedup")
    result["q1-F04"] = [{"case": r["case"], "internal_ops": r["internal_ops"],
                          "added_copy_mb": int(r["q1_added_copy_bytes"]) / 1048576,
                          "speedup": r["q1_speedup"]} for r in detail if r["cores"] == "5"]
    result["q1-F05"] = [{"case": r["case"], "cores": r["cores"], "candidate": r["q1_candidate"],
                          "largest_component_fraction": r["largest_component_fraction"],
                          "max_level_width": r["max_level_width"], "internal_ops": r["internal_ops"]}
                         for r in detail if r["cores"] != "1"]
    candidate = []
    for path in (SOLVE / "正式实验/候选评估").glob("case_*/n*/*/q1.receipt.json"):
        row = json.loads(path.read_text(encoding="utf-8"))
        assert row["status"] == "PASS"
        candidate.append({"case": path.parts[-4], "cores": int(path.parts[-3][1:]),
                          "candidate": path.parts[-2], "makespan_cycles": row["makespan"],
                          "evaluation_seconds": row["elapsed_seconds"]})
    assert len(candidate) >= 400
    result["q1-F06"] = sorted(candidate, key=lambda r: (r["case"], r["cores"], r["candidate"]))
    result["q2-F01"] = pick(paired, "case", "cores", "candidate", "scene_b_gain_same_plan")
    result["q2-F02"] = pick(paired, "case", "cores", "q2_policy_gain")
    result["q2-F03"] = pick((r for r in q["二"] if r["cores"] != "1"),
                           "case", "cores", "candidate", "partition_added_copy_bytes", "spill_added_copy_bytes", "added_copy_bytes")
    memory = []
    for row in q["二"]:
        if row["cores"] != "5":
            continue
        with gzip.open(ROOT / row["official_result"], "rt", encoding="utf-8") as stream:
            official = json.load(stream)
        capacity = official["capacity_bytes"]
        fraction = max(peak[key] / capacity[key] for peak in official["memory_peak_by_core"].values()
                       for key in ("L1", "UB"))
        memory.append({"case": row["case"], "memory_peak_fraction": fraction,
                       "q2_speedup": row["speedup"],
                       "internal_ops": int(graph[row["case"]]["internal_ops"]),
                       "largest_component_fraction": int(graph[row["case"]]["largest_component"]) /
                       int(graph[row["case"]]["internal_ops"])})
    result["q2-F04"] = memory
    result["q2-F05"] = [{"case": r["case"], "q1_speedup": r["q1_speedup"],
                          "q2_speedup": r["q2_speedup"], "q1_added_copy_bytes": r["q1_added_copy_bytes"],
                          "q2_added_copy_bytes": r["q2_added_copy_bytes"]}
                         for r in detail if r["cores"] == "5"]
    result["q2-F06"] = pick(detail, "case", "cores", "q2_speedup")
    result["q3-F01"] = pick(q["三"], "case", "cores", "cache_gain")
    result["q3-F02"] = pick((r for r in detail if r["cores"] == "5"),
                           "case", "internal_ops", "q3_cache_hit_rate", "q3_cache_gain")
    result["q3-F03"] = pick(grid, "case", "capacity_bytes", "bandwidth_bytes_per_cycle",
                           "candidate", "makespan_cycles")
    result["q3-F04"] = pick(grid, "case", "capacity_bytes", "bandwidth_bytes_per_cycle", "hit_rate")
    result["q3-F05"] = pick(q["三"], "case", "cores", "cache_hit_bytes", "cache_miss_bytes", "cache_hit_rate")
    baseline = {r["case"]: int(r["q1_makespan_cycles"]) for r in detail if r["cores"] == "1"}
    assert len(baseline) == 100
    result["q3-F06"] = [{"case": r["case"], "cores": r["cores"],
                          "no_l2_speedup": baseline[r["case"]] / int(r["q3_matched_no_l2_cycles"]),
                          "with_l2_speedup": r["q3_speedup"]} for r in detail]
    index = {"status": "data_ready", "cases": 100,
             "inputs": {p.relative_to(ROOT).as_posix(): digest(p) for p in
                        [audit_path, detail_path, paired_path, *q_paths.values(), grid_path]},
             "figures": {}}
    for name, rows in result.items():
        path = write(name, rows)
        index["figures"][name] = {"path": path.relative_to(ROOT).as_posix(),
                                   "rows": len(rows), "sha256": digest(path)}
    (OUT / "索引.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: item["rows"] for name, item in index["figures"].items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
