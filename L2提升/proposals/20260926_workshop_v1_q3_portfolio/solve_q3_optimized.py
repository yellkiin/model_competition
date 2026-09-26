"""Improve any supplied Q3 baseline with a bounded official-evaluator search.

This CLI reads arbitrary graph JSON files. It never changes Q1/Q2 solvers,
official evaluation code or settings, and only publishes a verified incumbent.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CODE = ROOT / "数据/原始/A题官方附件/code"
CONFIG = ROOT / "数据/原始/A题官方附件/data/config.txt"
for directory in (HERE, ROOT / "求解", CODE):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
sys.dont_write_bytecode = True


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def signature(plan):
    positions = {sg: (core, rank) for core, order in enumerate(plan["core_schedules"])
                 for rank, sg in enumerate(order)}
    return tuple(sorted((int(op), *positions[sg])
                        for op, sg in plan["node_to_subgraph"].items()))


def official_settings():
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_3 import read_cache_config, read_scene_b_config
    return {**read_evaluation_config(str(CONFIG)), **read_cache_config(str(CONFIG)),
            **read_scene_b_config(str(CONFIG))}


def old_candidates(graph, cores):
    from solve_components import build_plan as components
    from solve_bands import build_plan as bands
    from solve_batches import build_plan as batches
    plan, meta = components(graph, cores)
    yield "original_components", plan, meta
    if cores > 1:
        plan, meta = bands(graph, cores, target_bands=8)
        yield "original_bands8", plan, meta
    if len(graph["ops"]) > 2500:
        plan, meta = batches(graph, cores, target_ops=800)
        yield "original_batches800", plan, meta


def worker(request_path):
    request = read(request_path)
    report_path = Path(request["report"])
    began = time.perf_counter()
    report = {"status": "FAIL", "action": request["action"]}
    try:
        from stub_multicore_cut_and_schedule import validate_multicore_plan
        graph = read(request["graph"])
        plan = read(request["plan"])
        if len(plan["core_schedules"]) != request["cores"]:
            raise ValueError("Baseline/core count mismatch")
        validate_multicore_plan(graph, plan)
        if request["action"] == "generate":
            family = request["family"]
            candidates = old_candidates(graph, request["cores"]) if family == "original" else (
                importlib.import_module(f"{family}_candidates").generate_candidates(
                    graph, request["cores"], plan, request["settings"]))
            manifest = []
            for index, (name, candidate, meta) in enumerate(candidates):
                validate_multicore_plan(graph, candidate)
                folder = report_path.parent / f"candidate_{index:03d}"
                candidate_path = folder / "plan.json"
                write(candidate_path, candidate)
                write(folder / "metadata.json", meta)
                manifest.append({"name": name, "plan": str(candidate_path)})
            report.update(status="PASS", candidates=manifest)
        else:
            from multicore_cut_evaluate_problem_3 import evaluate_problem_3
            from verify_official_results import verify
            settings = request["settings"]
            result = evaluate_problem_3(
                graph, plan, bandwidth=settings["bandwidth"], capacity=settings["capacity"],
                cross_core_copy_delay=settings["cross_core_copy_delay_cycles"],
                cache_capacity_bytes=settings["cache_capacity_bytes"],
                cache_bandwidth_bytes_per_cycle=settings["cache_bandwidth_bytes_per_cycle"])
            verification = verify(graph, plan, result)
            report.update(status="PASS", makespan=result["makespan"],
                          added_copy_bytes=result["data_movement_bytes"]["added_copy_bytes"],
                          cache_stats=result["cache_stats"],
                          data_movement_bytes=result["data_movement_bytes"],
                          independent_validation=verification,
                          graph_sha256=digest(request["graph"]),
                          plan_sha256=digest(request["plan"]))
            threshold = request.get("retain_threshold")
            if threshold is None or result["makespan"] <= threshold:
                trace = report_path.parent / "q3_result.json.gz"
                with gzip.open(trace, "wt", encoding="utf-8", compresslevel=3) as stream:
                    json.dump(result, stream, ensure_ascii=False, separators=(",", ":"))
                report.update(result_path=str(trace), result_sha256=digest(trace))
    except Exception as exc:
        report.update(error=f"{type(exc).__name__}: {exc}", traceback=traceback.format_exc())
    report["elapsed_seconds"] = round(time.perf_counter() - began, 6)
    write(report_path, report)
    return 0 if report["status"] == "PASS" else 1


def run_worker(request, timeout):
    report_path = Path(request["report"])
    request_path = report_path.with_name("request.json")
    write(request_path, request)
    began = time.perf_counter()
    try:
        process = subprocess.run(
            [sys.executable, "-X", "utf8", "-B", str(Path(__file__).resolve()),
             "--worker", str(request_path)], cwd=ROOT, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=timeout)
        if report_path.exists():
            return read(report_path)
        report = {"status": "FAIL", "error": "Worker exited without a receipt",
                  "returncode": process.returncode, "stderr": process.stderr[-4000:]}
    except subprocess.TimeoutExpired:
        report = {"status": "TIMEOUT", "timeout_seconds": timeout}
    report["elapsed_seconds"] = round(time.perf_counter() - began, 6)
    write(report_path, report)
    return report


def solve(args):
    graph_path = args.graph.resolve()
    baseline_path = args.baseline_plan.resolve()
    output_path = args.output.resolve()
    receipt_path = (args.receipt or output_path.with_suffix(".receipt.json")).resolve()
    if output_path in {graph_path, baseline_path} or receipt_path in {graph_path, baseline_path, output_path}:
        raise ValueError("Output and receipt must be separate from input graph and baseline")
    # Input reads establish existence before any output or subprocess is created.
    read(graph_path)
    read(baseline_path)
    run_parent = (args.work_dir or output_path.parent / (output_path.stem + "_runs")).resolve()
    run_dir = run_parent / (time.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8])
    run_dir.mkdir(parents=True, exist_ok=False)
    settings = official_settings()
    source_paths = [Path(__file__), CONFIG, ROOT / "求解/verify_official_results.py"]
    source_paths += list(CODE.glob("*.py")) + list((ROOT / "求解").glob("solve_*.py"))
    source_paths += list(HERE.glob("*_candidates.py"))
    evidence = {"graph": str(graph_path), "baseline_plan": str(baseline_path),
                "graph_sha256": digest(graph_path), "baseline_sha256": digest(baseline_path),
                "official_settings": settings, "num_cores": args.cores,
                "source_sha256": {str(p): digest(p) for p in sorted(set(source_paths))},
                "run_directory": str(run_dir), "attempts": [], "generation": [],
                "budget_seconds": args.budget_seconds, "candidate_timeout_seconds": args.timeout_seconds,
                "max_candidates": args.max_candidates,
                "selection_rule": "min(makespan, added_copy_bytes); retain incumbent on ties"}
    common = {"graph": str(graph_path), "cores": args.cores, "settings": settings}
    initial_report_path = run_dir / "baseline" / "q3.receipt.json"
    baseline = run_worker({**common, "action": "evaluate", "plan": str(baseline_path),
                           "report": str(initial_report_path)}, args.baseline_timeout_seconds)
    evidence["baseline_evaluation"] = baseline
    if baseline["status"] != "PASS":
        evidence.update(status="BASELINE_UNVERIFIED", output_written=False,
                        reason="A successful official baseline evaluation is required for a non-regression guarantee.")
        write(receipt_path, evidence)
        print(json.dumps({"status": evidence["status"], "receipt": str(receipt_path)}, ensure_ascii=False))
        return 2
    selected = {"name": "supplied_baseline", "plan": str(baseline_path),
                "receipt": str(initial_report_path), **baseline}
    seen = {signature(read(baseline_path))}
    deadline = time.perf_counter() + args.budget_seconds
    stop_reason = "CANDIDATES_EXHAUSTED"
    for family in args.families.split(","):
        remaining = deadline - time.perf_counter()
        if remaining <= 0 or len(evidence["attempts"]) >= args.max_candidates:
            stop_reason = "BUDGET_EXHAUSTED" if remaining <= 0 else "CANDIDATE_LIMIT"
            break
        generation_report = run_dir / ("generation_" + family) / "generation.receipt.json"
        generated = run_worker({**common, "action": "generate", "family": family,
                                "plan": str(baseline_path), "report": str(generation_report)},
                               min(args.timeout_seconds, remaining))
        evidence["generation"].append({"family": family, "receipt": str(generation_report),
                                       "status": generated["status"]})
        if generated["status"] != "PASS":
            continue
        for item in generated["candidates"]:
            remaining = deadline - time.perf_counter()
            if remaining <= 0 or len(evidence["attempts"]) >= args.max_candidates:
                stop_reason = "BUDGET_EXHAUSTED" if remaining <= 0 else "CANDIDATE_LIMIT"
                break
            key = signature(read(item["plan"]))
            if key in seen:
                continue
            seen.add(key)
            candidate_report = Path(item["plan"]).parent / "q3.receipt.json"
            report = run_worker({**common, "action": "evaluate", "plan": item["plan"],
                                 "report": str(candidate_report), "retain_threshold": selected["makespan"]},
                                min(args.timeout_seconds, remaining))
            evidence["attempts"].append({"name": item["name"], "plan": item["plan"],
                                         "receipt": str(candidate_report), "status": report["status"],
                                         "makespan": report.get("makespan")})
            if report["status"] == "PASS" and (report["makespan"], report["added_copy_bytes"]) < (
                    selected["makespan"], selected["added_copy_bytes"]):
                selected = {"name": item["name"], "plan": item["plan"],
                            "receipt": str(candidate_report), **report}
    if digest(graph_path) != evidence["graph_sha256"] or digest(baseline_path) != evidence["baseline_sha256"]:
        raise RuntimeError("Input graph or baseline changed during search; output not published")
    chosen_plan = read(selected["plan"])
    if digest(selected["plan"]) != selected["plan_sha256"]:
        raise RuntimeError("Selected plan changed after evaluation; output not published")
    if stop_reason == "CANDIDATES_EXHAUSTED" and any(
            item["status"] != "PASS" for item in evidence["generation"]):
        stop_reason = "CANDIDATE_FAMILY_FAILURES"
    assert selected["makespan"] <= baseline["makespan"]
    write(output_path, chosen_plan)
    evidence.update(status="PASS", output_written=True, output=str(output_path),
                    output_sha256=digest(output_path), selected=selected, stop_reason=stop_reason,
                    non_regression_verified=True, baseline_makespan=baseline["makespan"],
                    selected_makespan=selected["makespan"],
                    time_reduction_fraction=(baseline["makespan"] - selected["makespan"]) / max(1, baseline["makespan"]))
    write(receipt_path, evidence)
    print(json.dumps({k: evidence[k] for k in ("status", "baseline_makespan", "selected_makespan",
                                               "time_reduction_fraction", "stop_reason", "output")}, ensure_ascii=False))
    return 0


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        return worker(sys.argv[2])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("-n", "--cores", type=int, choices=range(1, 6), required=True)
    parser.add_argument("--baseline-plan", type=Path, required=True)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--families", default="original,band,cache,refine")
    parser.add_argument("--budget-seconds", type=float, default=300)
    parser.add_argument("--timeout-seconds", type=float, default=30)
    parser.add_argument("--baseline-timeout-seconds", type=float, default=120)
    parser.add_argument("--max-candidates", type=int, default=24)
    args = parser.parse_args()
    if any(f not in {"original", "band", "cache", "refine"} for f in args.families.split(",")):
        parser.error("--families must contain only original,band,cache,refine")
    if len(set(args.families.split(","))) != len(args.families.split(",")):
        parser.error("--families must not contain duplicate families")
    if args.budget_seconds < 0 or args.timeout_seconds <= 0 or args.baseline_timeout_seconds <= 0 or args.max_candidates < 0:
        parser.error("Budget and candidate count must be nonnegative; timeouts must be positive")
    try:
        return solve(args)
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
