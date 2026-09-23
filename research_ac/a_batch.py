"""A full-data runner: fixed single-core denominators, all failures retained.

Problem 3 additionally evaluates its selected plan with cache disabled (P2),
so cache-only improvement is not confounded with a different partition.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import math
from pathlib import Path
import statistics
from a_search import load_json, save_json, search, run_cli


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path, help="Only the restored A raw-graph directory")
    parser.add_argument("--code", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-count", type=int, default=100)
    parser.add_argument("--cores", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    parser.add_argument("--problems", type=int, nargs="+", choices=[1, 2, 3], default=[1, 2, 3])
    parser.add_argument("--budget", type=int, default=24)
    parser.add_argument("--timeout", type=float, default=120.)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    if args.expected_count < 1 or len(set(args.cores)) != len(args.cores) or len(set(args.problems)) != len(args.problems):
        raise ValueError("Positive case count and unique cores/problems are required")
    if any(not 1 <= c <= 5 for c in args.cores) or args.budget < 1 or args.timeout <= 0:
        raise ValueError("Invalid core count, budget or timeout")
    paths = sorted(args.data.rglob("*.json"))
    if len(paths) != args.expected_count:
        raise ValueError(f"Expected {args.expected_count} graph JSONs, found {len(paths)}; no files silently skipped")
    for path in paths:
        graph = load_json(path)
        if not all(k in graph for k in ("ops", "tensors", "edges")):
            raise ValueError(f"Not a raw graph: {path}")
    args.out.mkdir(parents=True, exist_ok=False)
    code_hash = {p.name: sha(p) for p in sorted(args.code.glob("*.py"))}
    config_hash = sha(args.config)
    rows = []
    for path in paths:
        case = path.stem + "_" + sha(path)[:10]
        case_dir = args.out / case
        case_dir.mkdir()
        baseline = run_cli(args.code / "singlecore_evaluate.py", path, args.config,
                           case_dir / "baseline", args.timeout)
        cache = dict(graph_sha256=sha(path), config_sha256=config_hash,
                     evaluator_sha256=code_hash, record=baseline)
        save_json(case_dir / "baseline_cache.json", cache)
        for problem in args.problems:
            for cores in args.cores:
                output = case_dir / f"p{problem}_c{cores}"
                row = dict(case=str(path.relative_to(args.data)), problem=problem, cores=cores,
                           status="error", makespan=None, singlecore_makespan=None, speedup=None,
                           same_plan_no_cache_makespan=None, same_plan_cache_speedup=None,
                           cache_comparison_status=None, error=None)
                try:
                    result = search(path, args.code, args.config, output, cores, problem,
                                    args.budget, args.timeout, args.seed, baseline_cache=cache)
                    row.update(status=result["status"], makespan=result.get("best_makespan"),
                               speedup=result.get("speedup"),
                               singlecore_makespan=baseline.get("result", {}).get("makespan"))
                    if problem == 3 and result["status"] == "ok":
                        paired = run_cli(args.code / "multicore_cut_evaluate_problem_2.py",
                                         path, args.config, output / "same_plan_no_cache",
                                         args.timeout, output / "best_plan.json")
                        row["cache_comparison_status"] = paired["status"]
                        save_json(output / "same_plan_no_cache.json", paired)
                        if paired["status"] == "ok":
                            row["same_plan_no_cache_makespan"] = paired["result"]["makespan"]
                            row["same_plan_cache_speedup"] = paired["result"]["makespan"] / row["makespan"]
                except (ValueError, OSError, RuntimeError) as exc:
                    row["error"] = str(exc)
                rows.append(row)
                save_json(args.out / "case_results.json", rows)
    summaries = []
    for problem in args.problems:
        for cores in args.cores:
            selected = [r for r in rows if r["problem"] == problem and r["cores"] == cores]
            valid = [r["speedup"] for r in selected if r["status"] == "ok" and r["speedup"] is not None]
            matched = [r["same_plan_cache_speedup"] for r in selected if r["same_plan_cache_speedup"] is not None]
            complete = len(valid) == args.expected_count and (problem != 3 or len(matched) == args.expected_count)
            summaries.append(dict(problem=problem, cores=cores, complete=complete,
                                  expected=args.expected_count, scored=len(valid), failures_or_missing=len(selected) - len(valid),
                                  arithmetic_mean_speedup=statistics.mean(valid) if complete else None,
                                  geometric_mean_speedup=math.exp(statistics.mean(map(math.log, valid))) if complete else None,
                                  worst_speedup=min(valid) if complete else None,
                                  mean_same_plan_cache_speedup=statistics.mean(matched) if len(matched) == args.expected_count else None))
    save_json(args.out / "summary.json", summaries)
    with (args.out / "case_results.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(args.out / "summary.json")
    if not all(r["complete"] for r in summaries):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
