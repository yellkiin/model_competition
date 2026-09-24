"""Read saved real-run evidence and write reports; never run a solver/evaluator.

Usage: python -X utf8 -m research_a_aster_rbc.analyze_results runs/<directory>
The path may also be absolute or repository relative. Existing experiment files
are read only. Only analysis.json, evaluation_times.csv, coverage_detailed.json,
and REPORT.md are written. This is snapshot reporting, not an experiment check.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys


PACKAGE = Path(__file__).resolve().parent
STATES = ("complete", "failed", "timeout", "partial", "not_started", "running")
METRICS = (
    "partition_added_copy_bytes", "spill_added_copy_bytes", "scheduled_copy_bytes",
    "cache_byte_hit_rate", "cache_hit_bytes", "cache_accesses", "overlapping_miss_bytes",
    "memory_peak", "pipe_occupancy", "compute_work_by_core", "memory_dependency_count",
    "ddr_accounted_bytes", "ddr_service_lower_bound_cycles",
)


def number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def positive(value):
    result = number(value)
    return result if result is not None and result > 0 else None


def legal(item):
    return isinstance(item, dict) and item.get("status") == "ok" and positive(item.get("makespan")) is not None


def close(left, right):
    left, right = number(left), number(right)
    return left is not None and right is not None and math.isclose(left, right, rel_tol=1e-10, abs_tol=1e-6)


def read_json(path, warnings, default=None, required=False):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        if required:
            warnings.append({"path": str(path), "error": "missing"})
    except (OSError, ValueError) as exc:
        warnings.append({"path": str(path), "error": str(exc)})
    return default


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def geometric_mean(values):
    values = [v for value in values if (v := positive(value)) is not None]
    return math.exp(math.fsum(math.log(value) for value in values) / len(values)) if values else None


def display(value, decimals=4):
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.{decimals}f}".rstrip("0").rstrip(".")
    return str(value).replace("|", "\\|").replace("\n", " ")


def table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(display(cell) for cell in row) + " |" for row in rows)
    return "\n".join(lines)


def result_folder(run, job):
    folder = Path(job.get("result_root") or job["id"])
    folder = (folder if folder.is_absolute() else run / folder).resolve()
    if not folder.is_relative_to((PACKAGE / "runs").resolve()):
        raise ValueError(f"result_root must remain under this package runs/: {folder}")
    return folder


def raw_evidence(path, item, warnings, run):
    """Keep compact observations; do not retain huge official timelines in RAM."""
    if not path.is_file():
        return {"path": os.path.relpath(path, run), "present": False, "matches_recorded_makespan": None}
    raw = read_json(path, warnings, default={})
    if not isinstance(raw, dict):
        return {"path": os.path.relpath(path, run), "present": True, "readable": False}
    result = {
        "path": os.path.relpath(path, run), "present": True, "readable": bool(raw),
        "makespan": raw.get("makespan"), "problem": raw.get("problem"),
        "scene": raw.get("scene"), "num_cores": raw.get("num_cores"),
        "matches_recorded_makespan": close(raw.get("makespan"), item.get("makespan")) if legal(item) else None,
        "data_movement_bytes": raw.get("data_movement_bytes"),
        "cache_stats": raw.get("cache_stats"),
        "cross_core_copy_delay_cycles": raw.get("cross_core_copy_delay_cycles"),
        "task_cross_core_wait_cycles": raw.get("task_cross_core_wait_cycles"),
        "task_same_core_wait_cycles": raw.get("task_same_core_wait_cycles"),
        "task_dependency_count": len(raw.get("task_dependencies") or []),
        "cross_core_transfer_count": len(raw.get("cross_core_transfers") or []),
    }
    # These are official event counts, not a claim about critical-path waiting.
    cache_events = raw.get("cache_events") or []
    result["cache_event_counts"] = dict(Counter(event.get("event", "unknown") for event in cache_events if isinstance(event, dict)))
    result["cache_event_first_time"] = min((t for event in cache_events if isinstance(event, dict) and (t := number(event.get("time"))) is not None), default=None)
    result["cache_event_last_time"] = max((t for event in cache_events if isinstance(event, dict) and (t := number(event.get("time"))) is not None), default=None)
    stats = raw.get("cache_stats") or {}
    hit, miss = number(stats.get("hit_bytes")), number(stats.get("miss_bytes"))
    result["official_cache_byte_hit_rate"] = hit / (hit + miss) if hit is not None and miss is not None and hit + miss > 0 else None
    timelines = raw.get("per_core_timeline") or []
    compute, occupied = {}, {}
    for timeline in timelines:
        if not isinstance(timeline, dict):
            continue
        core = str(timeline.get("core_id"))
        compute[core] = 0.0
        for op in timeline.get("ops") or []:
            if not isinstance(op, dict):
                continue
            duration = number(op.get("duration"))
            if duration is None:
                begin, end = number(op.get("start")), number(op.get("end"))
                duration = end - begin if begin is not None and end is not None else None
            if duration is None or duration < 0:
                continue
            pipe = str(op.get("pipe"))
            key = core + ":" + pipe
            occupied[key] = occupied.get(key, 0.0) + duration
            if pipe in ("PIPE_M", "PIPE_V"):
                compute[core] += duration
    result["compute_duration_by_core_from_timeline"] = compute
    result["pipe_duration_sum_from_timeline"] = occupied
    cores = raw.get("num_cores")
    if isinstance(cores, int) and cores > 0 and compute:
        work = [compute.get(str(k), 0.0) for k in range(cores)]
        average = math.fsum(work) / cores
        result["compute_load_max_over_mean"] = max(work) / average if average > 0 else None
    else:
        result["compute_load_max_over_mean"] = None
    return result


def expected_jobs(manifest):
    output = []
    shards, shard = int(manifest.get("shards", 1)), int(manifest.get("shard", 0))
    for index, name in enumerate(manifest.get("cases", [])):
        if index % shards != shard:
            continue
        case = Path(name).stem
        specs = [(0, 1)] + [(question, cores) for cores in manifest.get("cores", []) for question in manifest.get("questions", [1, 2, 3])]
        for question, cores in specs:
            output.append({"id": f"{case}_q{question}_n{cores}", "case": case, "question": int(question), "cores": int(cores), "status": "not_started", "machine": manifest.get("machine")})
    if manifest.get("explicit_job_ids") is not None:
        explicit_ids = set(manifest["explicit_job_ids"])
        output = [job for job in output if job["id"] in explicit_ids]
    return output


def pair_evidence(folder, data, verified_best, evaluations, raw_by_index, warnings):
    if data.get("question") != 3:
        return None
    pair = data.get("cache_pair") or {}
    no_cache = next((item for item in reversed(evaluations) if item.get("label") == "same_plan_no_cache" and item.get("question") == 2 and legal(item)), None)
    result = {"complete": False, "reported_pair": pair or None, "reason": "缺少合法 Q3 incumbent 或同方案 Q2 回放"}
    if not verified_best or no_cache is None:
        return result
    index = no_cache.get("index")
    if not isinstance(index, int):
        result["reason"] = "回放缺少评估序号"
        return result
    replay_raw = raw_by_index.get(index) or {}
    if replay_raw.get("matches_recorded_makespan") is not True:
        result["reason"] = "Q2 回放缺少一致的官方原始响应"
        return result
    best_plan = read_json(folder / "best_plan.json", warnings)
    replay_plan = read_json(folder / f"candidate_{index:02d}.json", warnings)
    if best_plan is None or replay_plan is None or best_plan != replay_plan:
        result["reason"] = "best_plan.json 与 Q2 回放方案缺失或不相同"
        return result
    incumbent = data.get("incumbent") or {}
    best_index = incumbent.get("index")
    if not isinstance(best_index, int):
        result["reason"] = "Q3 incumbent 缺少评估序号"
        return result
    selected_plan = read_json(folder / f"candidate_{best_index:02d}.json", warnings)
    if selected_plan is None or selected_plan != best_plan:
        result["reason"] = "Q3 已评估方案与 best_plan.json 缺失或不相同"
        return result
    q3_raw = raw_by_index.get(best_index) or {}
    if q3_raw.get("matches_recorded_makespan") is not True:
        result["reason"] = "Q3 incumbent 缺少一致的官方原始响应"
        return result
    q2_time, q3_time = positive(no_cache.get("makespan")), positive(incumbent.get("makespan"))
    result.update(complete=True, reason=None, no_cache_makespan=q2_time, with_cache_makespan=q3_time,
                  ratio=q2_time / q3_time, replay_evaluation_index=index, selected_evaluation_index=best_index,
                  same_plan_comparison="parsed JSON equality; no fingerprints", plan_file="best_plan.json")
    if pair and (not close(pair.get("no_cache_makespan"), q2_time) or not close(pair.get("with_cache_makespan"), q3_time) or not close(pair.get("ratio"), q2_time / q3_time)):
        result["reported_pair_mismatch"] = True
    return result


def summarize_pairs(rows):
    grouped = defaultdict(dict)
    for row in rows:
        if row["question"] != 0:
            grouped[(row["case"], row["question"], row["cores"])][row["variant"]] = row
    output = []
    for question, cores in sorted({(key[1], key[2]) for key in grouped}):
        selected = [values for key, values in grouped.items() if key[1:] == (question, cores)]
        for reference in ("fast", "components"):
            ratios, wins, ties, losses, copy_wins = [], 0, 0, 0, 0
            for variants in selected:
                first, best = variants.get(reference, {}), variants.get("best", {})
                left, right = positive(first.get("makespan")), positive(best.get("makespan"))
                if left is None or right is None:
                    continue
                ratios.append(left / right)
                if close(left, right):
                    ties += 1
                    copy_left, copy_right = first.get("extra_copy_total_bytes"), best.get("extra_copy_total_bytes")
                    if number(copy_left) is not None and number(copy_right) is not None and copy_right < copy_left:
                        copy_wins += 1
                elif right < left:
                    wins += 1
                else:
                    losses += 1
            output.append({"question": question, "cores": cores, "reference": reference,
                           "planned_pairs": len(selected), "legal_pairs": len(ratios), "best_faster": wins,
                           "equal_makespan": ties, "best_slower": losses, "equal_time_lower_copy": copy_wins,
                           "geomean_reference_over_best": geometric_mean(ratios)})
    return output


def analyze(run, command=None, interpreter=None, note=None):
    warnings = []
    manifest = read_json(run / "manifest.json", warnings, default={}, required=True)
    manifest = manifest if isinstance(manifest, dict) else {}
    source_jobs = read_json(run / "jobs.json", warnings, default=[], required=True)
    source_jobs = source_jobs if isinstance(source_jobs, list) else []
    run_status = read_json(run / "run_status.json", warnings, default={}) or {}
    interruption = read_json(run / "interruption.json", warnings, default={}) or {}
    timing_affected_jobs = set(interruption.get("timing_affected_jobs", []))
    expected = expected_jobs(manifest)
    by_id = defaultdict(list)
    for job in source_jobs:
        if isinstance(job, dict) and job.get("id"):
            by_id[job["id"]].append(job)
    jobs = []
    for job in expected:
        saved = by_id.get(job["id"], [])
        # Duplicate source records are disclosed, never counted as extra evidence.
        jobs.append({**job, **(saved[-1] if saved else {})})
    if not expected:
        jobs = [items[-1] for items in by_id.values()]
    expected_ids = {job["id"] for job in jobs}
    records, eval_rows, job_rows, bounds, raw_issues = [], [], [], [], []
    for job in jobs:
        folder = result_folder(run, job)
        timing_affected = bool(job.get("timing_affected_by_interruption") or job["id"] in timing_affected_jobs)
        data = read_json(folder / "result.json", warnings, default={}) or {}
        if not isinstance(data, dict):
            data = {}
        evaluations = [item for item in data.get("evaluations", []) if isinstance(item, dict)]
        question = int(job["question"])
        data.setdefault("question", question)
        labels, indices, raw_by_index = {}, {}, {}
        for position, item in enumerate(evaluations):
            index = item.get("index", position)
            item_question = int(item.get("question", 1 if question == 0 else question))
            raw_path = folder / ("best_official.json" if question == 0 else f"official_{index:02d}.json")
            raw = raw_evidence(raw_path, item, warnings, run)
            raw_by_index[index] = raw
            if legal(item) and raw.get("matches_recorded_makespan") is False:
                raw_issues.append({"job_id": job["id"], "index": index, "error": "official/recorded Makespan mismatch"})
            if legal(item) and not raw.get("present"):
                raw_issues.append({"job_id": job["id"], "index": index, "error": "official raw response missing"})
            labels[item.get("label")] = item
            indices[index] = item
            eval_rows.append({"job_id": job["id"], "case": job["case"], "job_question": question,
                "evaluation_question": item_question, "cores": job["cores"], "evaluation_index": index,
                "label": item.get("label"), "status": item.get("status"), "official_seconds": number(item.get("seconds")),
                "makespan": positive(item.get("makespan")) if legal(item) else None,
                "raw_present": raw.get("present"), "raw_makespan_matches": raw.get("matches_recorded_makespan"),
                "raw_path": os.path.relpath(raw_path, run), "error": item.get("error"), "machine": job.get("machine", manifest.get("machine")),
                "timing_affected_by_interruption": timing_affected})
        for label, index in (data.get("aliases") or {}).items():
            if index in indices:
                labels[label] = indices[index]
            else:
                warnings.append({"job_id": job["id"], "error": f"alias {label} references missing evaluation {index}"})
        incumbent = data.get("incumbent") or {}
        best_raw = raw_evidence(folder / "best_official.json", incumbent, warnings, run) if legal(incumbent) else {}
        verified_best = legal(incumbent) and best_raw.get("matches_recorded_makespan") is not False
        cache = pair_evidence(folder, data, verified_best, evaluations, raw_by_index, warnings)
        supervisor = job.get("status", "not_started")
        eval_timeouts = sum(item.get("status") == "timeout" for item in evaluations)
        parent_timeout = supervisor in ("job_timeout", "stopped_at_limit_or_interrupt")
        has_timeout = bool(eval_timeouts or parent_timeout)
        if verified_best:
            complete = data.get("status") == "complete" and not timing_affected and supervisor not in ("running", "job_timeout", "process_error", "stopped_at_limit_or_interrupt") and (question != 3 or (cache and cache["complete"]))
            state = "complete" if complete else "partial"
        elif has_timeout:
            state = "timeout"
        elif supervisor == "not_started" and not (folder / "result.json").exists() and not (folder / "request.json").exists():
            state = "not_started"
        elif supervisor == "running" or (not run_status and data.get("status") == "running" and supervisor == "not_started"):
            state = "running"
        else:
            state = "failed"
        worker_error = read_json(folder / "worker_error.json", warnings)
        row = {"job_id": job["id"], "case": job["case"], "question": question, "cores": job["cores"],
               "classification": state, "supervisor_status": supervisor, "result_status": data.get("status", "absent"),
               "legal_incumbent": bool(verified_best), "no_legal": not verified_best and state != "not_started",
               "evaluation_timeout_events": eval_timeouts, "supervisor_timeout_or_limit_events": int(parent_timeout),
               "has_timeout_event": has_timeout, "solve_seconds": number(data.get("solve_seconds")),
               "timing_affected_by_interruption": timing_affected,
               "solve_seconds_is_checkpoint": data.get("status") == "running", "cache_pair": cache,
               "construction_errors": data.get("construction_errors", []), "neighbor_errors": data.get("neighbor_errors", []),
               "worker_error": worker_error, "best_diagnostics": best_raw,
               "result_root": os.path.relpath(folder, run), "retained_from": job.get("retained_from"),
               "result_path": os.path.relpath(folder / "result.json", run), "job_log": os.path.relpath(folder / "job.log", run)}
        job_rows.append(row)
        bound, upper = number(data.get("bound")), positive(incumbent.get("makespan")) if verified_best else None
        violation = data.get("bound_violation") is True or (bound is not None and upper is not None and bound > upper + 1e-6)
        if violation:
            bounds.append({"job_id": job["id"], "bound": bound, "official_makespan": upper, "status": data.get("bound_status")})
        for variant in (["original_singlecore"] if question == 0 else ["fast", "components", "best"]):
            item = incumbent if variant == "best" else labels.get(variant, {})
            item_index = item.get("index", 0 if question == 0 else None)
            raw = best_raw if variant == "best" else raw_by_index.get(item_index, {})
            valid = legal(item) and raw.get("matches_recorded_makespan") is not False
            values = {metric: item.get(metric) if valid else None for metric in METRICS}
            added, spilled = number(values["partition_added_copy_bytes"]), number(values["spill_added_copy_bytes"])
            records.append({"job_id": job["id"], "case": job["case"], "question": question, "cores": job["cores"],
                "variant": variant, "classification": state, "evaluation_status": item.get("status", "not_evaluated"),
                "legal": valid, "makespan": positive(item.get("makespan")) if valid else None,
                "original_singlecore": None, "speedup": None, **values,
                "extra_copy_total_bytes": added + spilled if added is not None and spilled is not None else None,
                "same_plan_cache_ratio": cache.get("ratio") if cache and cache["complete"] and variant == "best" else None,
                "solve_seconds": number(data.get("solve_seconds")), "variant_solve_seconds": None,
                "timing_affected_by_interruption": timing_affected,
                "result_root": os.path.relpath(folder, run), "retained_from": job.get("retained_from"),
                "source_official_seconds": number(item.get("seconds")), "source_evaluation_index": item_index,
                "source_label": item.get("label"), "alias_evaluation_index": (data.get("aliases") or {}).get(variant),
                "bound": bound, "bound_status": data.get("bound_status"), "bound_violation": violation,
                "raw_evidence": raw, "machine": job.get("machine", manifest.get("machine"))})
    baseline, baseline_paths = {}, {}
    for case, evidence in (manifest.get("baseline_evidence") or {}).items():
        baseline_path = (run / evidence["result_path"]).resolve()
        if not baseline_path.is_relative_to((PACKAGE / "runs").resolve()):
            warnings.append({"path": str(baseline_path), "error": "baseline result outside package runs/"})
            continue
        source_data = read_json(baseline_path, warnings, default={}, required=True) or {}
        item = source_data.get("incumbent") or {}
        raw_baseline = read_json(baseline_path.parent / "best_official.json", warnings, default={}, required=True) or {}
        corroborated = close(raw_baseline.get("makespan"), item.get("makespan"))
        if source_data.get("question") == 0 and source_data.get("cores") == 1 and source_data.get("case") == case and legal(item) and corroborated:
            baseline[case] = positive(item.get("makespan"))
            baseline_paths[case] = os.path.relpath(baseline_path, run)
        else:
            warnings.append({"path": str(baseline_path), "error": "specified baseline has no corroborated legal original Q0 incumbent"})
    # This run's legal Q0 always wins, independent of whether it is faster/slower.
    for row in records:
        if row["question"] == 0 and row["legal"]:
            baseline[row["case"]] = row["makespan"]
            baseline_paths[row["case"]] = str(Path(row["result_root"]) / "result.json")
    for row in records:
        row["original_singlecore"] = baseline.get(row["case"])
        row["baseline_result_path"] = baseline_paths.get(row["case"])
        if row["makespan"] and row["original_singlecore"]:
            row["speedup"] = row["original_singlecore"] / row["makespan"]
    counts = {}
    for question in (0, 1, 2, 3):
        selected = [row for row in job_rows if row["question"] == question]
        categories = Counter(row["classification"] for row in selected)
        counts[f"Q{question}"] = {"planned": len(selected), **{state: categories[state] for state in STATES},
            "no_legal": sum(row["no_legal"] for row in selected), "jobs_with_timeout_events": sum(row["has_timeout_event"] for row in selected),
            "evaluation_timeout_events": sum(row["evaluation_timeout_events"] for row in selected),
            "supervisor_timeout_or_limit_events": sum(row["supervisor_timeout_or_limit_events"] for row in selected)}
    expected_keys = [(row["case"], row["question"], row["cores"], variant) for row in jobs for variant in (["original_singlecore"] if row["question"] == 0 else ["fast", "components", "best"])]
    summary_rows = []
    try:
        with (run / "summary.csv").open(encoding="utf-8-sig", newline="") as stream:
            summary_rows = list(csv.DictReader(stream))
    except (OSError, csv.Error) as exc:
        warnings.append({"path": str(run / "summary.csv"), "error": str(exc)})
    summary_keys = []
    for row in summary_rows:
        try:
            summary_keys.append((row["case"], int(row["question"]), int(row["cores"]), row["variant"]))
        except (KeyError, TypeError, ValueError):
            warnings.append({"error": "invalid summary key", "row": row})
    summary_counter, expected_counter = Counter(summary_keys), Counter(expected_keys)
    key_list = lambda keys: [dict(case=key[0], question=key[1], cores=key[2], variant=key[3]) for key in sorted(keys)]
    structural = {
        "duplicate_job_ids": {key: len(value) for key, value in by_id.items() if len(value) > 1},
        "jobs_missing_from_jobs_json": [job["id"] for job in jobs if job["id"] not in by_id],
        "unexpected_jobs": sorted(set(by_id) - expected_ids),
        "duplicate_expected_variant_keys": [{**key_list([key])[0], "count": count} for key, count in expected_counter.items() if count > 1],
        "duplicate_summary_variant_keys": [{**key_list([key])[0], "count": count} for key, count in summary_counter.items() if count > 1],
        "missing_summary_variant_keys": key_list(set(expected_counter) - set(summary_counter)),
        "unexpected_summary_variant_keys": key_list(set(summary_counter) - set(expected_counter)),
        "missing_legal_variant_keys": key_list((row["case"], row["question"], row["cores"], row["variant"]) for row in records if not row["legal"]),
    }
    variant_coverage = []
    for question, cores, variant in sorted({(row["question"], row["cores"], row["variant"]) for row in records}):
        selected = [row for row in records if (row["question"], row["cores"], row["variant"]) == (question, cores, variant)]
        variant_coverage.append({"question": question, "cores": cores, "variant": variant,
            "planned": len(selected), "legal": sum(row["legal"] for row in selected),
            "speedup_denominator_available": sum(row["speedup"] is not None for row in selected),
            "geomean_speedup": geometric_mean(row["speedup"] for row in selected),
            "evaluation_status_counts": dict(Counter(row["evaluation_status"] for row in selected))})
    paired = summarize_pairs(records)
    coverage = {"generated_utc": datetime.now(timezone.utc).isoformat(), "run_directory": str(run), "by_question": counts,
        "definitions": {
            "complete": "合法 incumbent，worker 正常完成；Q3 还要求相同 best_plan 的合法 Q2/Q3 原始响应与方案 JSON 一致证据。",
            "partial": "有合法 incumbent，但未完整结束、进程异常、作业停止、受休眠中断计时影响，或 Q3 缺少同方案回放证据。",
            "timeout": "无合法 incumbent，且至少一次官方评估超时或被父进程按作业/总窗口停止。",
            "failed": "已启动且无合法 incumbent；不归入 timeout。process_ok 本身不是官方成功。",
            "not_started": "尚无启动/结果证据。", "running": "仅用于运行中的快照：已启动、尚无合法 incumbent 且未结束。",
            "no_legal": "已启动且没有合法 incumbent，包含 failed/timeout/running；不是互斥主分类。",
            "timeout_events": "逐次官方 timeout 与父进程 timeout/limit 事件分别计数，可与 complete/partial 等主分类重叠；总窗口/中断无法从原字段区分。",
        }, "variant_coverage": variant_coverage, "structure": structural, "jobs": job_rows}
    analysis = {"generated_utc": coverage["generated_utc"], "run_directory": str(run), "manifest": manifest,
        "run_status": run_status, "interruption": interruption,
        "continued_from": manifest.get("continued_from"),
        "run_kind": manifest.get("run_kind"), "baseline_from": manifest.get("baseline_from"),
        "baseline_result_paths": baseline_paths,
        "continuation_source_interruption": manifest.get("continuation_source_interruption"),
        "actual_command": command, "actual_interpreter_path": interpreter,
        "operator_note": note, "coverage_by_question": counts, "variant_coverage": variant_coverage,
        "paired_best_improvement": paired, "records": records, "bound_violations": bounds,
        "raw_evidence_issues": raw_issues, "read_warnings": warnings, "structure": structural,
        "claims": {"old_paper_comparison": "本轮尚不能判断是否超过论文：缺少相同案例、核数、小问、配置、单核分母的旧论文逐例证据。",
                   "bound": "条件性计算松弛；未经实际评估语义确认，不是已认证最优性缺口。",
                   "timing": "solve_seconds 是整个作业用时；未记录各 variant 独立求解时间。official_seconds 仅为相应官方调用用时。",
                   "scores": "正式分数来自已保存的官方评估结果；代理估计不填充周期、加速比、Spill 或 Cache 成绩。"}}
    return analysis, coverage, eval_rows


def report_markdown(analysis, coverage):
    rows = analysis["records"]
    counts, manifest = analysis["coverage_by_question"], analysis["manifest"]
    paired = analysis["paired_best_improvement"]
    lines = ["# ASTER 实际实验结果报告", "", f"生成时间：{analysis['generated_utc']}。输出目录：`{analysis['run_directory']}`。",
        "", "本报告只汇总本目录已有真实实验记录；统计过程不启动求解或官方评估。运行中生成的报告是快照，缺少结果与缺少回放均保留。",
        "", "## 执行记录", "", f"解释器路径：`{analysis.get('actual_interpreter_path') or 'manifest 未保存可执行文件路径；待执行者补充'}`。",
        f"Python：`{manifest.get('python', '未记录')}`；机器：`{manifest.get('machine', '未记录')}`。",
        "", "实际命令：", "", "```powershell", analysis.get("actual_command") or "未提供实际命令；不能从 manifest 推断 workers、wall-seconds、input-root 等未保存参数。", "```", "",
        f"案例：{', '.join(manifest.get('cases', []))}。选择规则：`{manifest.get('input_selection')}`。",
        f"题目模拟核数：{manifest.get('cores')}；每次求解官方调用预算：{manifest.get('budget')}；每作业 {manifest.get('job_seconds')} 秒；每次评估 {manifest.get('eval_seconds')} 秒。",
        f"本次运行保存的总耗时：{display(analysis['run_status'].get('elapsed_seconds'))} 秒；窗口：{display(analysis['run_status'].get('wall_seconds'))} 秒。"]
    if analysis.get("operator_note"):
        lines += ["", analysis["operator_note"]]
    if manifest.get("continued_from"):
        lines += ["", f"本目录续接 `{manifest['continued_from']}`：保留 {manifest.get('retained_job_count')} 个已启动作业的原始状态与证据引用，仅执行旧目录的 {manifest.get('pending_job_count')} 个未开始作业。没有选择不同版本逐图最好值，原目录未被覆盖。"]
    if manifest.get("explicit_job_ids") is not None:
        lines += ["", f"这是仅含 {len(manifest['explicit_job_ids'])} 个指定作业的独立定向补跑；本次每作业 {manifest.get('job_seconds')} 秒、每次评估 {manifest.get('eval_seconds')} 秒、官方调用预算 {manifest.get('budget')}。旧失败/超时/部分完成轨迹保留在原目录，本报告没有导入旧多核成绩。不同预算的补跑不能拼成固定预算的完整 100 图成绩。"]
    if manifest.get("baseline_from"):
        lines += ["", f"单核分母只读来源：`{manifest['baseline_from']}`。仅复用该来源已保存的合法原始整图 Q0；本次补跑若得到合法 Q0，则无条件优先使用本次 Q0，不择优拼接分母。没有合法分母仍留空；逐例来源路径保存在 analysis.json 和 summary.csv。"]
    affected_ids = [job["job_id"] for job in coverage["jobs"] if job.get("timing_affected_by_interruption")]
    if affected_ids:
        lines += ["", "受机器休眠/中断影响的计时作业：" + ", ".join(affected_ids) + "。合法方案仍保留；有合法方案者计部分完成，无合法者按超时/失败；solve_s 标 *，其秒数含暂停，不解释为 CPU 执行耗时。"]
    lines += ["", "## 完成覆盖", "", table(["小问", "计划", "完成", "失败", "超时", "部分完成", "未开始", "运行中", "无合法结果", "发生超时的作业", "评估超时次数"],
        [(question, *(value[key] for key in ("planned", "complete", "failed", "timeout", "partial", "not_started", "running", "no_legal", "jobs_with_timeout_events", "evaluation_timeout_events"))) for question, value in counts.items()]),
        "", "完成、失败、超时、部分完成、未开始、运行中是互斥主分类。超时主分类要求没有合法 incumbent；已有合法结果但未完整结束或 Q3 回放不全计部分完成。无合法结果和超时事件是补充统计，可与主分类重叠。process_ok 不等于官方成功。Q0 是原始整图单核基准，没有可用的合法 Q0 分母时对应图的加速比留空。",
        "", "## 构造器、参照与增强结果", "", "fast 是独立快速构造方案；components 是连通块参照；best 是本作业小预算内已通过官方评估的最好方案。同方案 alias 复用一次真实评估，不计为额外调用。", "",
        table(["小问", "核数", "variant", "计划", "合法", "加速比分母齐全", "加速比几何均值"],
              [(f"Q{row['question']}", row["cores"], row["variant"], row["planned"], row["legal"], row["speedup_denominator_available"], row["geomean_speedup"]) for row in analysis["variant_coverage"]]),
        "", "上述几何均值仅覆盖合法且单核分母齐全的样本，不能作为缺失案例的替代成绩。", "",
        table(["小问", "核数", "参照", "合法配对/计划", "best 更快", "同周期", "best 更慢", "同周期搬运减少", "参照/best 几何均值"],
              [(f"Q{row['question']}", row["cores"], row["reference"], f"{row['legal_pairs']}/{row['planned_pairs']}", row["best_faster"], row["equal_makespan"], row["best_slower"], row["equal_time_lower_copy"], row["geomean_reference_over_best"]) for row in paired]),
        "", "配对几何均值大于 1 表示小预算结果相对该参照的实测周期更短。best 可能来自 fast、components、单核参照或定向候选，不能把 best 当作不搜索构造器。"]
    fast_pairs = [row for row in paired if row["reference"] == "fast"]
    legal_pairs, wins = sum(row["legal_pairs"] for row in fast_pairs), sum(row["best_faster"] for row in fast_pairs)
    lines += ["", f"实测：best 对 fast 的合法配对共有 {legal_pairs} 个，其中 {wins} 个周期改善。" + ("当前记录未显示周期改善收益。" if legal_pairs and not wins else "收益只适用于已完成的对应配对。"),
              "", "## 同方案 Cache 收益", "", "逐个读取 Q3 的 best_plan.json、选中候选方案与 Q2 回放候选方案作普通 JSON 相等比较，并核对两次官方原始 Makespan。周期比固定为同一方案 Q2/Q3；不使用分别优化的 Q2、Q3 结果相除。", ""]
    cache_jobs = [job for job in coverage["jobs"] if job["question"] == 3]
    lines.append(table(["案例", "核数", "同方案回放完成", "Q2 无 Cache", "Q3 有 Cache", "周期比 Q2/Q3", "未完成原因"],
        [(job["case"], job["cores"], (job["cache_pair"] or {}).get("complete", False), (job["cache_pair"] or {}).get("no_cache_makespan"), (job["cache_pair"] or {}).get("with_cache_makespan"), (job["cache_pair"] or {}).get("ratio"), (job["cache_pair"] or {}).get("reason")) for job in cache_jobs]))
    lines += ["", "## 逐例正式指标", "", "— 表示尚无可引用的实测值。新增搬运与 Spill 分别列出，单位为字节；Cache 字节命中率是 0–1 比例。solve_s 在各 variant 行重复显示整个作业耗时，不是该 variant 独立耗时。各次官方调用用时单独保存在 evaluation_times.csv。", "",
        table(["案例", "Q", "核", "variant", "官方状态", "Makespan", "单核加速比", "新增搬运", "Spill", "Cache 字节命中率", "solve_s"],
              [(row["case"], row["question"], row["cores"], row["variant"], row["evaluation_status"], row["makespan"], row["speedup"], row["partition_added_copy_bytes"], row["spill_added_copy_bytes"], row["cache_byte_hit_rate"], display(row["solve_seconds"]) + "*" if row.get("timing_affected_by_interruption") else row["solve_seconds"]) for row in rows]),
        "", "## 官方记录中的诊断线索", "", "下表只展示最好合法方案的官方统计与时间线汇总。计算负载比为各核 PIPE_M/PIPE_V 操作时长总和的最大值/均值，不是端到端等待占比。依赖/跨核传输数量不是关键路径等待周期；尚未把缓存访问顺序或等待的相关性证明为因果。", "",
        table(["作业", "负载最大/均值", "任务依赖数", "跨核传输数", "Spill 字节", "Cache hit/miss 事件"],
              [(job["job_id"], job["best_diagnostics"].get("compute_load_max_over_mean"), job["best_diagnostics"].get("task_dependency_count"), job["best_diagnostics"].get("cross_core_transfer_count"), (job["best_diagnostics"].get("data_movement_bytes") or {}).get("spill_added_copy_bytes"), json.dumps(job["best_diagnostics"].get("cache_event_counts", {}), ensure_ascii=False)) for job in coverage["jobs"] if job["legal_incumbent"]]),
        "", "## 下界、缺项与失败轨迹", "", f"bound_violation 数量：{len(analysis['bound_violations'])}。计算松弛下界保留原值，不截断；未经实际官方语义确认，不能称为已认证最优性缺口。"]
    if analysis["bound_violations"]:
        lines += ["", table(["作业", "原始下界", "官方 Makespan"], [(row["job_id"], row["bound"], row["official_makespan"]) for row in analysis["bound_violations"]])]
    structure = analysis["structure"]
    lines += ["", table(["记录检查", "数量"], [(key, len(value)) for key, value in structure.items()]),
        "", "重复与缺项均按 case/question/cores/variant 检查；未生成任何文件指纹。详情见 coverage_detailed.json。读取错误与原始响应缺项见 analysis.json。", ""]
    exceptional = [job for job in coverage["jobs"] if job["classification"] != "complete" or job["has_timeout_event"] or job["worker_error"]]
    lines.append(table(["作业", "分类", "supervisor", "result", "评估超时", "失败日志/结果"],
        [(job["job_id"], job["classification"], job["supervisor_status"], job["result_status"], job["evaluation_timeout_events"], job["result_path"] + "; " + job["job_log"]) for job in exceptional]))
    lines += ["", "## 结论与证据边界", "", analysis["claims"]["old_paper_comparison"],
        "", "保留：已经通过官方链的合法方案、原始响应与全部失败轨迹；维持逐问逐核配对和固定同方案 Cache 回放口径。",
        "", "需要修正：对无合法方案、评估超时或缺少回放的作业先定位其真实错误和时间消耗；若构造器未优于 components 或 best 没有改进，应先检查官方跨核依赖、负载、额外搬运、Spill 与缓存时序。不得仅以‘搜索不足’解释效果。",
        "", "证据不足：本表不证明代理模型准确、不证明超越旧论文，也不证明预算增加必然获益。方法改动及后续轮次应独立记录算法版本、输出目录、参数与代价，不拼接不同版本逐图最优值。",
        "", "本报告中的正式指标均为实测记录；负载比例和几何均值是这些记录的统计派生量。修改建议是待验证推测。本脚本不启动任何后续实验。", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--command", help="Exact command actually used, supplied by operator; never inferred")
    parser.add_argument("--interpreter", help="Actual experiment interpreter executable path")
    parser.add_argument("--note", help="Operator-provided factual note, for example a compatibility repair")
    args = parser.parse_args()
    run = args.run_directory
    if not run.exists():
        run = PACKAGE / run
    run = run.resolve()
    if not run.is_dir() or not run.is_relative_to(PACKAGE / "runs"):
        parser.error("Choose an existing run directory under this package's runs/ directory")
    analysis, coverage, evaluation_rows = analyze(run, args.command, args.interpreter, args.note)
    write_json(run / "analysis.json", analysis)
    write_json(run / "coverage_detailed.json", coverage)
    fields = ["job_id", "case", "job_question", "evaluation_question", "cores", "evaluation_index", "label", "status", "official_seconds", "makespan", "raw_present", "raw_makespan_matches", "raw_path", "error", "machine", "timing_affected_by_interruption"]
    with (run / "evaluation_times.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(evaluation_rows)
    (run / "REPORT.md").write_text(report_markdown(analysis, coverage), encoding="utf-8")
    print(json.dumps({"output_directory": str(run), "coverage": analysis["coverage_by_question"], "bound_violations": len(analysis["bound_violations"]), "read_warnings": len(analysis["read_warnings"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
