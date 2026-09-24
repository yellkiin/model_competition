"""Run and checkpoint official A-problem evaluators on registered cases.

All numerical scores come from the unchanged official evaluator functions and
fixed config.  Full evaluator returns are retained as compressed JSON; compact
receipts make long runs resumable and identify the exact inputs and code.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "数据/原始/A题官方附件/data"
CODE = ROOT / "数据/原始/A题官方附件/code"
OUT = ROOT / "求解/正式实验"
AUDIT = ROOT / "求解/数据审计.json"
sys.path.insert(0, str(CODE))
sys.path.insert(0, str(ROOT / "求解"))
from evaluation_validation import read_evaluation_config  # noqa: E402
from multicore_cut_evaluate_problem_1 import evaluate_scene_a, read_scene_a_config  # noqa: E402
from multicore_cut_evaluate_problem_2 import evaluate_scene_b, read_scene_b_config  # noqa: E402
from multicore_cut_evaluate_problem_3 import evaluate_problem_3, read_cache_config  # noqa: E402
from singlecore_evaluate import evaluate_singlecore  # noqa: E402
from solve_components import build_plan as component_plan  # noqa: E402
from solve_bands import build_plan as band_plan  # noqa: E402
from solve_batches import build_plan as batch_plan  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evaluate(problem: int, graph: dict, plan: dict, settings: dict, scene_a: dict, scene_b: dict, cache: dict) -> dict:
    common = {"bandwidth": settings["bandwidth"], "capacity": settings["capacity"]}
    if problem == 0:
        return evaluate_singlecore(graph, **common)
    if problem == 1:
        return evaluate_scene_a(
            graph, plan, **common,
            cross_core_wait=scene_a["task_cross_core_wait_cycles"],
            same_core_wait=scene_a["task_same_core_wait_cycles"],
        )
    if problem == 2:
        return evaluate_scene_b(
            graph, plan, **common,
            cross_core_copy_delay=scene_b["cross_core_copy_delay_cycles"],
        )
    if problem == 3:
        return evaluate_problem_3(
            graph, plan, **common,
            cross_core_copy_delay=scene_b["cross_core_copy_delay_cycles"],
            **cache,
        )
    raise ValueError(problem)


def run_one(case: str, graph: dict, graph_path: Path, n: int, candidate: str,
            plan: dict | None, metadata: dict | None, settings: dict,
            scene_a: dict, scene_b: dict, cache: dict, source_hashes: dict) -> None:
    folder = OUT / "候选评估" / case / f"n{n}" / candidate
    folder.mkdir(parents=True, exist_ok=True)
    plan_path = folder / "plan.json"
    if plan is not None:
        plan_bytes = (json.dumps(plan, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        if not plan_path.exists() or plan_path.read_bytes() != plan_bytes:
            plan_path.write_bytes(plan_bytes)
    plan_hash = sha256(plan_path) if plan is not None else None
    if metadata:
        (folder / "plan_meta.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    # The official singlecore entrypoint calls evaluate_scene_a on exactly
    # this one-subgraph plan.  For n=1, that is the problem-1 baseline itself;
    # a second scene-A run is numerically redundant and very costly on large
    # graphs.  Problems 2/3 still get their own official evaluation.
    problems = [0] if candidate == "singlecore" else ([2, 3] if n == 1 else [1, 2, 3])
    for problem in problems:
        result_path = folder / f"q{problem}.json.gz"
        receipt_path = folder / f"q{problem}.receipt.json"
        fingerprint = {
            "graph_sha256": sha256(graph_path),
            "plan_sha256": plan_hash,
            "source_sha256": source_hashes,
        }
        if receipt_path.exists() and result_path.exists():
            old = json.loads(receipt_path.read_text(encoding="utf-8"))
            old_fp = old.get("fingerprint", {})
            old_sources = dict(old_fp.get("source_sha256", {}))
            new_sources = dict(source_hashes)
            runner_key = Path(__file__).relative_to(ROOT).as_posix()
            old_sources.pop(runner_key, None)
            new_sources.pop(runner_key, None)
            if candidate != "batches800":
                old_sources.pop("求解/solve_batches.py", None)
                new_sources.pop("求解/solve_batches.py", None)
            if (old_fp.get("graph_sha256") == fingerprint["graph_sha256"]
                    and old_fp.get("plan_sha256") == plan_hash
                    and old_sources == new_sources
                    and old.get("status") == "PASS"):
                continue
        started = time.perf_counter()
        try:
            result = evaluate(problem, graph, plan, settings, scene_a, scene_b, cache)
            result["input_graph"] = graph_path.relative_to(ROOT).as_posix()
            result["input_plan"] = plan_path.relative_to(ROOT).as_posix() if plan is not None else None
            result_bytes = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            with gzip.open(result_path, "wb", compresslevel=6) as stream:
                stream.write(result_bytes)
            movement = result.get("data_movement_bytes", {})
            receipt = {
                "status": "PASS",
                "case": case,
                "num_cores": n,
                "candidate": candidate,
                "problem": problem,
                "makespan": result["makespan"],
                "data_movement_bytes": movement,
                "cache_stats": result.get("cache_stats", {}),
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "result_path": result_path.relative_to(ROOT).as_posix(),
                "result_sha256": sha256(result_path),
                "fingerprint": fingerprint,
            }
        except Exception as exc:
            receipt = {
                "status": "FAIL",
                "case": case,
                "num_cores": n,
                "candidate": candidate,
                "problem": problem,
                "error": f"{type(exc).__name__}: {exc}",
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "fingerprint": fingerprint,
            }
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: receipt.get(k) for k in ("case", "num_cores", "candidate", "problem", "status", "makespan", "elapsed_seconds", "error") if k in receipt}, ensure_ascii=False), flush=True)


def parse_cases(spec: str) -> list[int]:
    result = set()
    for part in spec.split(","):
        if "-" in part:
            first, last = map(int, part.split("-", 1))
            result.update(range(first, last + 1))
        else:
            result.add(int(part))
    if not result or min(result) < 1 or max(result) > 100:
        raise ValueError("cases must be in 1..100")
    return sorted(result)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="1-100")
    parser.add_argument("--min-cores", type=int, default=1)
    parser.add_argument("--max-cores", type=int, default=5)
    args = parser.parse_args()
    config_path = DATA / "config.txt"
    settings = read_evaluation_config(str(config_path))
    scene_a = read_scene_a_config(str(config_path))
    scene_b = read_scene_b_config(str(config_path))
    cache = read_cache_config(str(config_path))
    audit = {x["case"]: x for x in json.loads(AUDIT.read_text(encoding="utf-8"))["cases"]}
    source_paths = sorted(CODE.glob("*.py")) + [config_path, Path(__file__), ROOT / "求解/solve_components.py", ROOT / "求解/solve_bands.py", ROOT / "求解/solve_batches.py"]
    source_hashes = {path.relative_to(ROOT).as_posix(): sha256(path) for path in source_paths}
    for index in parse_cases(args.cases):
        case = f"case_{index:03d}"
        graph_path = DATA / f"{case}.json"
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        if args.min_cores <= 1:
            run_one(case, graph, graph_path, 1, "singlecore", None, None, settings, scene_a, scene_b, cache, source_hashes)
        row = audit[case]
        try_bands = (
            row["largest_component"] / row["internal_ops"] >= 0.2
            and row["max_level_width"] >= 20
        )
        for n in range(args.min_cores, args.max_cores + 1):
            try_batches = (
                n > 1 and row["internal_ops"] / n > 2500
                and row["largest_component"] <= 600
            )
            # A giant single-core subgraph can make the official Task
            # scheduler prohibitively expensive.  The bounded candidate is
            # the prespecified path for wide independent-component graphs.
            if not try_batches:
                component, component_meta = component_plan(graph, n)
                run_one(case, graph, graph_path, n, "components", component, component_meta, settings, scene_a, scene_b, cache, source_hashes)
            else:
                batches, batches_meta = batch_plan(graph, n, target_ops=800)
                run_one(case, graph, graph_path, n, "batches800", batches, batches_meta, settings, scene_a, scene_b, cache, source_hashes)
            if n > 1 and try_bands:
                bands, bands_meta = band_plan(graph, n, target_bands=8)
                run_one(case, graph, graph_path, n, "bands8", bands, bands_meta, settings, scene_a, scene_b, cache, source_hashes)


if __name__ == "__main__":
    main()
