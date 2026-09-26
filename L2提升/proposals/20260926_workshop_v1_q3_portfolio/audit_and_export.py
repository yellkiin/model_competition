"""Read back selected official traces; export Q3 plans without changing Q1/Q2."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import statistics
import sys

from optimize_q3 import HERE, ROOT, DATA, CODE, OLD, read, write, digest, initialize, run_eval, baseline_folder
from stub_multicore_cut_and_schedule import validate_multicore_plan
from verify_official_results import verify


def verify_receipt_identity(receipt, graph_path, plan_path, result_path, problem):
    assert receipt["problem"] == problem
    assert receipt["status"] == "PASS"
    assert digest(result_path) == receipt["result_sha256"]
    fingerprint = receipt.get("fingerprint", receipt)
    assert fingerprint["graph_sha256"] == digest(graph_path)
    assert fingerprint["plan_sha256"] == digest(plan_path)
    if "source_sha256" in fingerprint:
        for path in list(CODE.glob("*.py")) + [DATA / "config.txt"]:
            assert fingerprint["source_sha256"][path.relative_to(ROOT).as_posix()] == digest(path)
    else:
        assert receipt["config_sha256"] == digest(DATA / "config.txt")
        for path in CODE.glob("*.py"):
            assert receipt["official_code_sha256"][path.name] == digest(path)


def replay_baselines():
    snapshot = initialize()
    records = []
    for row in snapshot["rows"]:
        if row["cores"] != "5" or row["case"] not in {"case_002", "case_006", "case_044", "case_056", "case_083"}:
            continue
        source = baseline_folder(row)
        folder = HERE / "baseline_replay" / row["case"] / "n5"
        write(folder / "plan.json", read(source / "plan.json"))
        result = run_eval(row["case"], folder, 3, 180, 10**30)
        assert result["status"] == "PASS", result
        expected = read(source / "q3.receipt.json")
        assert result["makespan"] == expected["makespan"], (row["case"], result["makespan"], expected["makespan"])
        assert result["cache_stats"] == expected["cache_stats"]
        assert result["movement"] == expected["data_movement_bytes"]
        records.append({"case": row["case"], "status": "PASS", "makespan": result["makespan"],
                        "receipt": str((folder / "q3.receipt.json").relative_to(ROOT))})
    write(HERE / "baseline_replay_audit.json", {"status": "PASS", "count": len(records), "records": records})
    print(json.dumps({"baseline_replays": records}, ensure_ascii=False), flush=True)


def audit():
    snapshot = initialize()
    rows = read(HERE / "selected_results.json")
    assert len(rows) == 500
    old_rows = {(r["case"], int(r["cores"])): r for r in snapshot["rows"]}
    assert len(old_rows) == 500
    assert {(r["case"], r["cores"]) for r in rows} == set(old_rows)
    coverage = {"cache_single_core_rows": 0, "full_multicore_rows": 0, "generation_failures": []}
    for row in rows:
        search = read(HERE / "evaluations" / row["case"] / f"n{row['cores']}" / "search.json")
        families = set(search["families"].split(","))
        if row["cores"] == 1 and "cache" in families:
            coverage["cache_single_core_rows"] += 1
        if row["cores"] > 1 and {"band", "refine"} <= families:
            coverage["full_multicore_rows"] += 1
        coverage["generation_failures"].extend(search.get("generation_failures", []))
    assert coverage["cache_single_core_rows"] == 100
    assert coverage["full_multicore_rows"] == 400
    assert not coverage["generation_failures"], coverage
    failures = []
    checks = []
    merged = []
    for row in rows:
        graph = read(DATA / (row["case"] + ".json"))
        plan = read(ROOT / row["plan_path"])
        result = read(ROOT / row["q3_result_path"])
        validate_multicore_plan(graph, plan)
        record = verify(graph, plan, result)
        assert result["makespan"] == row["makespan"] <= row["baseline_makespan"]
        assert abs(result["cache_stats"]["hit_rate"] - row["cache_hit_rate"]) < 1e-12
        receipt = read(ROOT / row["q3_receipt_path"])
        graph_path = DATA / (row["case"] + ".json")
        plan_path = ROOT / row["plan_path"]
        verify_receipt_identity(receipt, graph_path, plan_path, ROOT / row["q3_result_path"], 3)
        original_row = old_rows[row["case"], row["cores"]]
        assert row["baseline_makespan"] == int(original_row["q3_makespan_cycles"])
        if row.get("q2_counterfactual_result_path"):
            q2_path = ROOT / row["q2_counterfactual_result_path"]
        else:
            q2_path = baseline_folder(original_row) / "q2.json.gz"
        no_l2 = read(q2_path)
        q2_receipt = read(q2_path.with_name("q2.receipt.json"))
        verify_receipt_identity(q2_receipt, graph_path, plan_path, q2_path, 2)
        verify(graph, plan, no_l2)
        assert no_l2["makespan"] == row["no_l2_makespan"]
        assert "cache_stats" not in no_l2 and "cache_stats" in result
        record.update(case=row["case"], candidate=row["candidate"], no_regression=True)
        checks.append(record)
        plan_out = HERE / "final_plans" / f"n{row['cores']}" / (row["case"] + "_multicore_res.json")
        write(plan_out, plan)
        # Keep all original metrics under their original names; explicit new
        # columns prevent accidentally treating new Q3 as old Q1/Q2 results.
        original = dict(old_rows[row["case"], row["cores"]])
        original.update({"optimized_q3_" + key: row[key] for key in
                         ("candidate", "makespan", "no_l2_makespan", "cache_hit_rate", "cache_gain",
                          "speedup", "time_reduction_pct", "added_copy_bytes")})
        original["optimized_q3_plan"] = str(plan_out.relative_to(ROOT))
        merged.append(original)
    for rel, checksum in snapshot["protected_sha256"].items():
        if not (ROOT / rel).is_file() or digest(ROOT / rel) != checksum:
            failures.append(rel)
    assert not failures, failures
    report = {"status": "PASS", "selected_configurations": len(rows), "protected_files": len(snapshot["protected_sha256"]),
              "protected_changes": failures, "q1_q2_selected_plans_results_and_solver_sources_unchanged": True,
              "protection_scope": "Files explicitly listed in baseline_snapshot.json; no claim of a full repository hash audit",
              "q3_worse_rows": 0, "official_evaluator_modified": False,
              "search_coverage": coverage,
              "checks": checks,
              "new_source_sha256": {p.name: digest(p) for p in sorted(HERE.glob("*.py"))}}
    write(HERE / "final_audit.json", report)
    fields = list(merged[0])
    with (HERE / "all_questions_comparison.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(merged)
    gains = []
    for n in range(1, 6):
        group = [r for r in rows if r["cores"] == n]
        gains.append({"cores": n, "improved": sum(r["time_reduction_pct"] > 0 for r in group),
                      "time_reduction_mean_pct": statistics.mean(r["time_reduction_pct"] for r in group),
                      "time_reduction_median_pct": statistics.median(r["time_reduction_pct"] for r in group),
                      "time_reduction_over_1pct": sum(r["time_reduction_pct"] > 1 for r in group),
                      "time_reduction_over_5pct": sum(r["time_reduction_pct"] > 5 for r in group),
                      "time_reduction_over_10pct": sum(r["time_reduction_pct"] > 10 for r in group)})
    write(HERE / "gain_distribution.json", gains)
    print(json.dumps({"status": "PASS", "configurations": len(rows), "protected_files": len(snapshot["protected_sha256"]),
                      "gains": gains}, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("replay", "export"))
    args = parser.parse_args()
    (replay_baselines if args.action == "replay" else audit)()
