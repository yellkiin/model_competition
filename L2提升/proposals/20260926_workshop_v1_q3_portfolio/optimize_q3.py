"""Isolated Q3 portfolio search against the unchanged official evaluator.

Original Q1/Q2/Q3 files are read-only. Every selected row starts from the old
Q3 winner and accepts only lexicographic (makespan, added-copy-bytes) improvement.
All rejected/failed/timed-out evaluations remain recorded. Uses stdlib only.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
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

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "数据/原始/A题官方附件/data"
CODE = ROOT / "数据/原始/A题官方附件/code"
OLD = ROOT / "求解/正式实验"
for p in (HERE, ROOT / "求解", CODE):
    sys.path.insert(0, str(p))
sys.dont_write_bytecode = True


def read(path):
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def plan_key(plan):
    positions = {sg: (core, order) for core, seq in enumerate(plan["core_schedules"])
                 for order, sg in enumerate(seq)}
    representation = sorted((int(op), *positions[sg])
                            for op, sg in plan["node_to_subgraph"].items())
    return hashlib.sha256(json.dumps(representation).encode()).hexdigest()


def old_rows():
    with (OLD / "逐例分析.csv").open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def baseline_folder(row):
    return OLD / "候选评估" / row["case"] / f"n{row['cores']}" / row["q3_candidate"]


def initialize():
    target = HERE / "baseline_snapshot.json"
    if target.exists():
        return read(target)
    rows = old_rows()
    paths = set(CODE.glob("*.py")) | set(DATA.glob("*.json")) | {DATA / "config.txt", OLD / "逐例分析.csv"}
    paths.update((ROOT / "求解").glob("solve_*.py"))
    paths.add(ROOT / "求解/run_official_experiments.py")
    for row in rows:
        for q in (1, 2, 3):
            folder = OLD / "候选评估" / row["case"] / f"n{row['cores']}" / row[f"q{q}_candidate"]
            for name in ("plan.json", f"q{q}.json.gz", f"q{q}.receipt.json"):
                path = folder / name
                if path.exists():
                    paths.add(path)
        if row["cores"] == "1":
            paths.update((OLD / "候选评估" / row["case"] / "n1/singlecore").glob("*"))
    snapshot = {"created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "rows": rows, "protected_sha256": {str(p.relative_to(ROOT)): digest(p)
                                                      for p in sorted(paths) if p.is_file()},
                "selection_rule": "min(makespan, added_copy_bytes); retain incumbent on ties",
                "official_config": read_settings()}
    write(target, snapshot)
    print(json.dumps({"snapshot_rows": len(rows), "protected_files": len(snapshot["protected_sha256"])}), flush=True)
    return snapshot


def read_settings():
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_3 import read_scene_b_config, read_cache_config
    path = str(DATA / "config.txt")
    return {**read_evaluation_config(path), **read_scene_b_config(path), **read_cache_config(path)}


def worker(args):
    from multicore_cut_evaluate_problem_3 import evaluate_problem_3
    from multicore_cut_evaluate_problem_2 import evaluate_scene_b
    from stub_multicore_cut_and_schedule import validate_multicore_plan
    from verify_official_results import verify
    start = time.perf_counter()
    folder = Path(args.folder)
    plan = read(folder / "plan.json")
    graph_path = DATA / f"{args.case}.json"
    graph = read(graph_path)
    settings = read_settings()
    report = {"case": args.case, "cores": len(plan["core_schedules"]), "problem": args.problem,
              "plan_sha256": digest(folder / "plan.json"), "graph_sha256": digest(graph_path),
              "config_sha256": digest(DATA / "config.txt"),
              "official_code_sha256": {p.name: digest(p) for p in sorted(CODE.glob("*.py"))}}
    try:
        validate_multicore_plan(graph, plan)
        kwargs = {k: settings[k] for k in ("bandwidth", "capacity")}
        kwargs["cross_core_copy_delay"] = settings["cross_core_copy_delay_cycles"]
        if args.problem == 3:
            kwargs.update({k: settings[k] for k in ("cache_capacity_bytes", "cache_bandwidth_bytes_per_cycle")})
            result = evaluate_problem_3(graph, plan, **kwargs)
        else:
            result = evaluate_scene_b(graph, plan, **kwargs)
        validation = verify(graph, plan, result)
        report.update(status="PASS", makespan=result["makespan"],
                      movement=result["data_movement_bytes"], cache_stats=result.get("cache_stats", {}),
                      independent_validation=validation)
        if result["makespan"] <= args.retain_threshold:
            result["input_graph"] = str(graph_path.relative_to(ROOT))
            result["input_plan"] = str((folder / "plan.json").relative_to(ROOT))
            result_path = folder / f"q{args.problem}.json.gz"
            with gzip.open(result_path, "wt", encoding="utf-8", compresslevel=3) as f:
                json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
            report["result_path"] = str(result_path.relative_to(ROOT))
            report["result_sha256"] = digest(result_path)
    except Exception as exc:
        report.update(status="FAIL", error=f"{type(exc).__name__}: {exc}", traceback=traceback.format_exc())
    report["elapsed_seconds"] = time.perf_counter() - start
    write(folder / f"q{args.problem}.receipt.json", report)
    return 0 if report["status"] == "PASS" else 1


def run_eval(case, folder, problem, timeout, threshold):
    receipt = folder / f"q{problem}.receipt.json"
    if receipt.exists():
        old = read(receipt)
        if old.get("status") == "PASS" and old.get("plan_sha256") == digest(folder / "plan.json"):
            return old
        if old.get("status") == "TIMEOUT" and old.get("timeout_seconds", 0) >= timeout:
            return old
    command = [sys.executable, "-X", "utf8", "-B", str(__file__), "worker", "--case", case,
               "--folder", str(folder), "--problem", str(problem), "--retain-threshold", str(threshold)]
    try:
        proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                              timeout=timeout, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        if receipt.exists():
            report = read(receipt)
        else:
            report = {"status": "FAIL", "returncode": proc.returncode,
                      "error": (proc.stderr + proc.stdout)[-4000:]}
            write(receipt, report)
    except subprocess.TimeoutExpired:
        report = {"status": "TIMEOUT", "timeout_seconds": timeout,
                  "case": case, "problem": problem, "plan_sha256": digest(folder / "plan.json")}
        write(receipt, report)
    return report


def search_row(row, args):
    folder = HERE / "evaluations" / row["case"] / f"n{row['cores']}"
    folder.mkdir(parents=True, exist_ok=True)
    lock = folder / ".search.lock"
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            break
        except FileExistsError:
            time.sleep(.25)
    try:
        return _search_row(row, args)
    finally:
        lock.unlink(missing_ok=True)


def _search_row(row, args):
    case, n = row["case"], int(row["cores"])
    output = HERE / "evaluations" / case / f"n{n}"
    output.mkdir(parents=True, exist_ok=True)
    base_folder = baseline_folder(row)
    baseline_plan = read(base_folder / "plan.json")
    baseline_receipt = read(base_folder / "q3.receipt.json")
    baseline_time = int(row["q3_makespan_cycles"])
    assert baseline_receipt["makespan"] == baseline_time
    selected = {"case": case, "cores": n, "candidate": "baseline_" + row["q3_candidate"],
                "baseline_makespan": baseline_time, "makespan": baseline_time,
                "plan_path": str((base_folder / "plan.json").relative_to(ROOT)),
                "q3_result_path": str((base_folder / "q3.json.gz").relative_to(ROOT)),
                "q3_receipt_path": str((base_folder / "q3.receipt.json").relative_to(ROOT)),
                "added_copy_bytes": baseline_receipt["data_movement_bytes"]["added_copy_bytes"],
                "no_l2_makespan": int(row["q3_matched_no_l2_cycles"]),
                "cache_hit_rate": float(row["q3_cache_hit_rate"]),
                "baseline_cache_gain": float(row["q3_cache_gain"]), "baseline_speedup": float(row["q3_speedup"])}
    selected_path = output / "selected.json"
    if selected_path.exists():
        incumbent = read(selected_path)
        if (incumbent["makespan"], incumbent["added_copy_bytes"]) < (selected["makespan"], selected["added_copy_bytes"]):
            selected = incumbent
    graph = read(DATA / f"{case}.json")
    # Globally valid compute-work bound: no assignment can beat total work/n
    # on any one exclusive pipe. Near-bound incumbents still remain selectable.
    pipe_work = {}
    for op in graph["ops"]:
        if op["op"] not in {"COPY_IN", "COPY_OUT"}:
            pipe_work[op["pipe"]] = pipe_work.get(op["pipe"], 0) + op["cycles"]
    bound = max(pipe_work.values(), default=0) / n
    if args.skip_near_bound and bound and baseline_time / bound <= 1 + args.skip_near_bound:
        selected["search_status"] = "SKIPPED_GLOBAL_COMPUTE_BOUND"
        selected["compute_lower_bound"] = bound
        write(selected_path, selected)
        return {"case": case, "cores": n, "old": baseline_time, "new": selected["makespan"], "evaluated": 0, "status": selected["search_status"]}
    settings = read_settings()
    seen = {plan_key(baseline_plan)}
    attempts, failures = [], []
    for family in args.families.split(","):
        if family in {"band", "refine"} and n == 1:
            continue
        module = importlib.import_module(f"{family}_candidates")
        try:
            for name, plan, metadata in module.generate_candidates(graph, n, baseline_plan, settings):
                key = plan_key(plan)
                if key in seen:
                    continue
                seen.add(key)
                if args.names and not any(fragment in name for fragment in args.names.split(",")):
                    continue
                folder = output / (name + "_" + key[:10])
                folder.mkdir(parents=True, exist_ok=True)
                write(folder / "plan.json", plan)
                write(folder / "metadata.json", metadata)
                report = run_eval(case, folder, 3, args.timeout, baseline_time)
                attempt = {"candidate": name, "status": report["status"], "makespan": report.get("makespan"),
                           "receipt": str((folder / "q3.receipt.json").relative_to(ROOT))}
                attempts.append(attempt)
                if report["status"] == "PASS":
                    score = (report["makespan"], report["movement"]["added_copy_bytes"])
                    if score < (selected["makespan"], selected["added_copy_bytes"]):
                        selected.update(candidate=name, makespan=score[0], added_copy_bytes=score[1],
                                        plan_path=str((folder / "plan.json").relative_to(ROOT)),
                                        q3_result_path=report["result_path"],
                                        q3_receipt_path=str((folder / "q3.receipt.json").relative_to(ROOT)),
                                        no_l2_makespan=None, cache_hit_rate=report["cache_stats"]["hit_rate"])
                        write(selected_path, selected)
                if args.max_candidates and len(attempts) >= args.max_candidates:
                    break
        except Exception as exc:
            failures.append({"family": family, "error": repr(exc), "traceback": traceback.format_exc()})
        if args.max_candidates and len(attempts) >= args.max_candidates:
            break
    assert selected["makespan"] <= baseline_time
    selected["search_status"] = "SEARCHED"
    write(output / "search.json", {"attempts": attempts, "generation_failures": failures,
                                  "timeout_seconds": args.timeout, "families": args.families})
    write(selected_path, selected)
    return {"case": case, "cores": n, "old": baseline_time, "new": selected["makespan"],
            "gain": round(baseline_time / selected["makespan"], 6), "candidate": selected["candidate"],
            "evaluated": len(attempts), "generation_failures": failures}


def cases(spec):
    result = set()
    for part in spec.split(","):
        if "-" in part:
            start, end = map(int, part.split("-"))
            result.update(range(start, end + 1))
        else:
            result.add(int(part))
    return {f"case_{i:03d}" for i in result}


def search(args):
    snapshot = initialize()
    selected_cases = cases(args.cases)
    ns = {int(n) for n in args.cores.split(",")}
    rows = [r for r in snapshot["rows"] if r["case"] in selected_cases and int(r["cores"]) in ns]
    started = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(search_row, row, args): (row["case"], row["cores"]) for row in rows}
        for future in concurrent.futures.as_completed(futures):
            try:
                report = future.result()
            except Exception as exc:
                report = {"row": futures[future], "status": "ERROR", "error": repr(exc), "traceback": traceback.format_exc()}
            report["wall_seconds"] = round(time.time() - started, 2)
            print(json.dumps(report, ensure_ascii=False), flush=True)


def finalize(args):
    snapshot = initialize()
    changes = [rel for rel, checksum in snapshot["protected_sha256"].items()
               if not (ROOT / rel).is_file() or digest(ROOT / rel) != checksum]
    if changes:
        raise RuntimeError(f"Protected input/results changed: {changes}")
    def finalize_row(row):
        path = HERE / "evaluations" / row["case"] / f"n{row['cores']}" / "selected.json"
        if not path.exists():
            # Materialize the unchanged incumbent, without generating candidates.
            options = argparse.Namespace(families="", names="", timeout=args.timeout, max_candidates=0, skip_near_bound=0)
            search_row(row, options)
        entry = read(path)
        if entry["no_l2_makespan"] is None:
            folder = (ROOT / entry["plan_path"]).parent
            report = run_eval(row["case"], folder, 2, args.timeout, 10**30)
            if report["status"] != "PASS":
                raise RuntimeError(f"Matched no-L2 evaluation failed: {row['case']}/{row['cores']}: {report}")
            entry["no_l2_makespan"] = report["makespan"]
            entry["q2_counterfactual_result_path"] = report["result_path"]
            write(path, entry)
        entry["optimization_gain"] = entry["baseline_makespan"] / entry["makespan"]
        entry["time_reduction_pct"] = (1 - entry["makespan"] / entry["baseline_makespan"]) * 100
        entry["cache_gain"] = entry["no_l2_makespan"] / entry["makespan"]
        entry["speedup"] = entry["baseline_speedup"] * entry["optimization_gain"]
        assert entry["makespan"] <= entry["baseline_makespan"]
        return entry
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        selected = list(pool.map(finalize_row, snapshot["rows"]))
    summary = {"protected_files_checked": len(snapshot["protected_sha256"]), "protected_changes": changes,
               "rows": len(selected), "cores": {}, "official_config": snapshot["official_config"]}
    for n in range(1, 6):
        group = [e for e in selected if e["cores"] == n]
        summary["cores"][str(n)] = {"count": len(group), "improved": sum(e["makespan"] < e["baseline_makespan"] for e in group),
                                   "worse": sum(e["makespan"] > e["baseline_makespan"] for e in group),
                                   **{key: sum(e[key] for e in group) / len(group) for key in
                                      ("baseline_speedup", "speedup", "optimization_gain", "time_reduction_pct", "baseline_cache_gain", "cache_gain")}}
    write(HERE / "selected_results.json", selected)
    write(HERE / "summary.json", summary)
    fields = sorted(set().union(*(set(row) for row in selected)))
    with (HERE / "selected_results.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(selected)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    p = sub.add_parser("search")
    p.add_argument("--cases", default="1-100")
    p.add_argument("--cores", default="5")
    p.add_argument("--families", default="cache,band")
    p.add_argument("--names", default="")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--timeout", type=float, default=60)
    p.add_argument("--max-candidates", type=int, default=0)
    p.add_argument("--skip-near-bound", type=float, default=0)
    p = sub.add_parser("worker")
    p.add_argument("--case", required=True)
    p.add_argument("--folder", required=True)
    p.add_argument("--problem", type=int, choices=(2, 3), default=3)
    p.add_argument("--retain-threshold", type=int, default=10**30)
    p = sub.add_parser("finalize")
    p.add_argument("--timeout", type=float, default=180)
    p.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.command != "worker":
        with (HERE / "run_history.jsonl").open("a", encoding="utf-8") as history:
            history.write(json.dumps({"started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                      "argv": sys.argv, "python": sys.version,
                                      "sources": {p.name: digest(p) for p in sorted(HERE.glob("*.py"))}},
                                     ensure_ascii=False) + "\n")
    if args.command == "init": initialize()
    elif args.command == "search": search(args)
    elif args.command == "worker": return worker(args)
    elif args.command == "finalize": finalize(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
