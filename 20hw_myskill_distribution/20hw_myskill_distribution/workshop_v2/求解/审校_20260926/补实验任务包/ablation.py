"""Two-case, four-arm diagnostic wrapper around the frozen Trident solver."""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import platform
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARMS = ("smf", "sm", "sf", "mf")
EXPECTED = {
    "case_080": {"seed": 63518, "revision_claim": "854d8775ee378e14089fade6e30fd83b0a832842"},
    "case_046": {"seed": 52952, "revision_claim": "489ec93a4c74683679e6a87a0175e4b8a3e3bbe1"},
}


def read(path: Path):
    with (gzip.open(path, "rt", encoding="utf-8-sig") if path.suffix == ".gz"
          else path.open(encoding="utf-8-sig")) as stream:
        return json.load(stream)


def write(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file(path):
    require(path.is_file(), f"缺少文件: {path}")
    return path


def prepare(args):
    case = args.case
    asset = HERE / "assets" / case
    out = Path(args.out).resolve()
    require(not out.exists(), f"输出目录已存在，另选全新目录: {out}")
    old = read(file(asset / "request.json"))
    progress = read(file(asset / "progress.json"))
    baseline = progress.get("baseline") or {}
    require(old["case"] == case and old["q"] == 3 and old["n"] == 5, "原请求身份不符")
    require(baseline.get("plan_file") == "attempts/e0001_plan.json", "原进度共同方案不是 e0001")
    require(baseline.get("result_file") == "attempts/e0001_result.json.gz", "原进度共同响应不是 e0001")
    require(baseline.get("makespan") == EXPECTED[case]["seed"], "原进度种子周期不符")
    seed_plan = read(file(asset / "e0001_plan.json"))
    seed_result = read(file(asset / "e0001_result.json.gz"))
    require(len(seed_plan["core_schedules"]) == 5, "种子核数不符")
    require(seed_result.get("status") == "ok" and seed_result.get("audit", {}).get("ok") is True,
            "原官方种子响应无效")
    require(seed_result["official_result"]["makespan"] == EXPECTED[case]["seed"], "种子响应周期不符")

    source_pkg = asset / "source_snapshot"
    file(source_pkg / "solve.py")
    version_text = file(source_pkg / "__init__.py").read_text(encoding="utf-8-sig")
    require(old["version"] in version_text, "源码版本与原请求不符")
    official_code = asset / "official_code"
    config = asset / "config.txt"
    graph = asset / f"{case}.json"
    for p in (official_code / "evaluation_validation.py", config, graph):
        file(p)

    out.mkdir(parents=True)
    shutil.copytree(source_pkg, out / "source" / "research_a_orion_trident")
    shutil.copytree(official_code, out / "official" / "code")
    (out / "official" / "data").mkdir()
    shutil.copy2(config, out / "official" / "data" / "config.txt")
    shutil.copy2(graph, out / "official" / "data" / f"{case}.json")
    (out / "seed").mkdir()
    shutil.copy2(asset / "e0001_plan.json", out / "seed" / "e0001_plan.json")
    shutil.copy2(asset / "e0001_result.json.gz", out / "seed" / "e0001_result.json.gz")
    shutil.copy2(asset / "request.json", out / "origin_request.json")
    shutil.copy2(asset / "progress.json", out / "origin_progress.json")
    requests = []
    for arm in ARMS:
        req = dict(old)
        req.update(out=str(out / "arms" / arm), official=str(out / "official"),
                   config=str(out / "official" / "data" / "config.txt"),
                   graph=str(out / "official" / "data" / f"{case}.json"),
                   components=arm, seconds=120.0, job_seconds=120.0,
                   max_evaluations=512, stop_gap=0.0,
                   seed_plan=str(out / "seed" / "e0001_plan.json"),
                   seed_response=str(out / "seed" / "e0001_result.json.gz"),
                   reuse_verified_response=True, campaign_jobs_root=None,
                   alternatives=[], baseline_alternatives=[], pair_inline=False,
                   keep_all_responses=True)
        require(req["source_policy"] == "work_adaptive" and req["mode"] == "warm", "原请求策略不符")
        write(out / "requests" / f"{arm}.json", req)
        requests.append(f"requests/{arm}.json")
    write(out / "manifest.json", {
        "schema": 1, "state": "prepared_not_run", "case": case, "q": 3, "n": 5,
        "arms": list(ARMS), "request_files": requests,
        "source_identity": "original_executed_source_snapshot",
        "source_revision_claim_from_delivery": EXPECTED[case]["revision_claim"],
        "revision_claim_verified_by_snapshot": False,
        "original_version": old["version"], "seed_makespan": EXPECTED[case]["seed"],
        "historical_source_seed_seconds": old["source_seed_seconds"],
        "budget_seconds_each": 120, "max_evaluations": 512, "stop_gap": 0,
        "concurrency": 1, "comparability": "within_case_same_host_only",
    })
    print(f"已准备 {case} 的四份请求: {out}")


def run(args):
    root = Path(args.prepared).resolve()
    manifest = read(file(root / "manifest.json"))
    require(manifest["state"] == "prepared_not_run", "该任务包已有运行记录；须新建任务包")
    require(tuple(manifest["arms"]) == ARMS and manifest["concurrency"] == 1, "运行协议不符")
    require(not (root / "arms").exists(), "运行目录已存在；禁止覆盖或混合续跑")
    source = root / "source"
    sys.path.insert(0, str(source))
    from research_a_orion_trident.pool import run_jobs
    from research_a_orion_trident.resources import memory

    host = {"node": platform.node(), "platform": platform.platform(), "python": sys.version,
            "processor": platform.processor(), "logical_cpus": os.cpu_count(),
            "memory_total_bytes": memory()[0], "pid": os.getpid(), "start_epoch": time.time(),
            "concurrency": 1, "thread_environment": {
                k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")}}
    write(root / "host_execution.json", host)
    for arm in ARMS:
        req = read(file(root / "requests" / f"{arm}.json"))
        require(req["out"] == str(root / "arms" / arm), "请求输出目录不符")
        require(req["components"] == arm and req["job_seconds"] == 120.0, "请求臂或预算不符")
        # One job per call, one active worker, same host and environment for all arms.
        run_jobs([req], root / "queue" / arm, time.time() + 150, max_workers=1)
    host["end_epoch"] = time.time()
    write(root / "host_execution.json", host)
    manifest["state"] = "run_completed_collect_pending"
    write(root / "manifest.json", manifest)
    print("四臂运行结束；请执行 collect 并检查原始记录。")


def candidate(root, row, cutoff=120.0):
    if row.get("status") != "ok" or row.get("completed_seconds", float("inf")) > cutoff:
        return None
    if not row.get("result_retained"):
        return None
    pp = root / row["plan_file"]
    rp = root / row["result_file"]
    if not (pp.is_file() and rp.is_file()):
        return None
    result = read(rp)
    if result.get("status") != "ok" or result.get("audit", {}).get("ok") is not True:
        return None
    raw = result["official_result"]
    return {"makespan_cycles": raw["makespan"],
            "added_copy_bytes": raw["data_movement_bytes"]["added_copy_bytes"],
            "ready_seconds": row["completed_seconds"], "source": row.get("source"),
            "plan_path": str(pp), "response_path": str(rp)}


def collect(args):
    root = Path(args.prepared).resolve()
    manifest = read(file(root / "manifest.json"))
    rows = []
    for arm in ARMS:
        folder = root / "arms" / arm
        req = read(file(root / "requests" / f"{arm}.json"))
        summary = read(folder / "summary.json") if (folder / "summary.json").is_file() else {}
        progress = read(folder / "progress.json") if (folder / "progress.json").is_file() else {}
        attempts = progress.get("attempts", [])
        base = progress.get("baseline") or {}
        choices = []
        if base and base.get("ready_seconds", float("inf")) <= 120:
            seed_path = folder / base.get("result_file", "")
            plan_path = folder / base.get("plan_file", "")
            if seed_path.is_file() and plan_path.is_file():
                response = read(seed_path)
                if response.get("status") == "ok" and response.get("audit", {}).get("ok") is True:
                    choices.append({"makespan_cycles": response["official_result"]["makespan"],
                                    "added_copy_bytes": response["official_result"]["data_movement_bytes"]["added_copy_bytes"],
                                    "ready_seconds": base["ready_seconds"], "source": "seed",
                                    "plan_path": str(plan_path), "response_path": str(seed_path)})
        source_attempts = {s: 0 for s in "bsmf"}
        source_acceptances = {s: 0 for s in "bsmf"}
        source_makespan_improvements = {s: 0 for s in "bsmf"}
        for attempt in attempts:
            source = attempt.get("source")
            if source in source_attempts:
                source_attempts[source] += 1
                if attempt.get("accepted"):
                    source_acceptances[source] += 1
                if attempt.get("improved_makespan"):
                    source_makespan_improvements[source] += 1
            item = candidate(folder, attempt)
            if item:
                choices.append(item)
        best = min(choices, key=lambda x: (x["makespan_cycles"], x["added_copy_bytes"])) if choices else None
        final = None
        if summary.get("status") == "ok" and (folder / "result.json.gz").is_file():
            response = read(folder / "result.json.gz")
            if response.get("status") == "ok" and response.get("audit", {}).get("ok") is True:
                final = {"makespan_cycles": response["official_result"]["makespan"],
                         "added_copy_bytes": response["official_result"]["data_movement_bytes"]["added_copy_bytes"],
                         "selected_ready_seconds": summary.get("selected_plan_ready_seconds"),
                         "plan_path": str(folder / "plan.json"), "response_path": str(folder / "result.json.gz")}
        execution = summary.get("execution", {})
        row = {"case": manifest["case"], "q": 3, "n": 5, "components": arm,
               "version": progress.get("version"), "status": summary.get("status"),
               "response_status": "ok" if final else None,
               "audit_ok": True if final else None,
               "initial_seed_makespan_cycles": base.get("makespan"),
               "final": final, "at_120_seconds": best,
               "relative_reduction_at_120":
                   (1 - best["makespan_cycles"] / base["makespan"]) if best and base.get("makespan") else None,
               "attempt_count": len(attempts), "source_attempts": source_attempts,
               "source_acceptances": source_acceptances,
               "source_makespan_improvements": source_makespan_improvements,
               "stop_reason": progress.get("stop_reason"),
               "wall_seconds": execution.get("wall_seconds"),
               "official_eval_seconds": progress.get("official_eval_seconds"),
               "execution_reason": execution.get("reason"),
               "observation": "zero_attempts_unidentified" if not attempts else
                              "incomplete_run" if summary.get("status") != "ok" else "observed"}
        row["minimum_interpretable"] = bool(summary.get("status") == "ok" and any(
            a.get("status") in ("ok", "audit_failed") and a.get("completed_seconds", float("inf")) <= 120
            for a in attempts))
        if not row["minimum_interpretable"]:
            row["observation"] = "zero_attempts_unidentified" if not attempts else "no_completed_candidate_by_120"
        # A result completed after the wall limit is never used as a 120 s observation.
        rows.append(row)
    write(root / "collected.json", {"state": "collected_from_saved_records", "rows": rows,
                                    "scope": "two targeted graphs; each case compared only within one host"})
    with (root / "collected.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        names = ["case", "components", "status", "initial_seed_makespan_cycles",
                 "at_120_makespan_cycles", "at_120_added_copy_bytes", "at_120_ready_seconds",
                 "final_makespan_cycles", "attempt_count", "stop_reason", "wall_seconds",
                 "official_eval_seconds", "minimum_interpretable", "observation"]
        writer = csv.DictWriter(stream, fieldnames=names)
        writer.writeheader()
        for row in rows:
            best = row["at_120_seconds"] or {}
            final = row["final"] or {}
            writer.writerow({"case": row["case"], "components": row["components"],
                             "status": row["status"], "initial_seed_makespan_cycles": row["initial_seed_makespan_cycles"],
                             "at_120_makespan_cycles": best.get("makespan_cycles"),
                             "at_120_added_copy_bytes": best.get("added_copy_bytes"),
                             "at_120_ready_seconds": best.get("ready_seconds"),
                             "final_makespan_cycles": final.get("makespan_cycles"),
                             "attempt_count": row["attempt_count"], "stop_reason": row["stop_reason"],
                             "wall_seconds": row["wall_seconds"], "official_eval_seconds": row["official_eval_seconds"],
                             "minimum_interpretable": row["minimum_interpretable"], "observation": row["observation"]})
    print(f"已汇总保存记录: {root / 'collected.json'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare", help="复制原分片小型原件，产生四份可审请求")
    p.add_argument("--case", required=True, choices=tuple(EXPECTED))
    p.add_argument("--out", required=True, help="全新输出目录")
    p.set_defaults(func=prepare)
    p = sub.add_parser("run", help="同一主机依次运行四臂，严格单并发")
    p.add_argument("--prepared", required=True)
    p.set_defaults(func=run)
    p = sub.add_parser("collect", help="只读取实际保存的结果")
    p.add_argument("--prepared", required=True)
    p.set_defaults(func=collect)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
