"""Write final reports from two or three finished, separately analysed runs.

Usage: python -X utf8 -m research_a_aster_rbc.write_experiment_report FORMAL_RUN RETRY_RUN [--extended-retry RUN3]
No solver, evaluator, source import, or raw official-response parsing is performed.
The package EXPERIMENT_REPORT.md is replaced only after all evidence validation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import io
import json
import math
import os
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
STATES = ("complete", "failed", "timeout", "partial", "not_started")
ELIGIBLE = {"failed", "timeout", "partial"}
HISTORY = (
    ("第一轮六图", "20260923_151740_574657_Nuggets_s0", 375.7763446),
    ("第二轮六图", "20260923_152653_353696_Nuggets_s0", 467.8306455),
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def relative(path, root):
    return os.path.relpath(path, root).replace("\\", "/")


def link(label, path):
    return f"[{label}]({relative(path, PACKAGE)})"


def resolve_run(value):
    run = Path(value)
    if not run.exists():
        run = PACKAGE / run
    run = run.resolve()
    if not run.is_dir() or not run.is_relative_to((PACKAGE / "runs").resolve()):
        raise ValueError(f"Run must be an existing directory under this package runs/: {run}")
    return run


def logical_key(row):
    return (str(row["case"]), int(row["question"]), int(row["cores"]))


def read_run(run, require_performance=False):
    status_path = run / "run_status.json"
    if not status_path.is_file():
        raise ValueError(f"Run has not ended: {run}")
    for name in ("analysis.json", "coverage_detailed.json"):
        if not (run / name).is_file() or (run / name).stat().st_mtime < status_path.stat().st_mtime:
            raise ValueError(f"Regenerate final {name} after this run ended: {run}")
    manifest = load(run / "manifest.json")
    analysis = load(run / "analysis.json")
    coverage = load(run / "coverage_detailed.json")
    jobs = load(run / "jobs.json")
    status = load(status_path)
    if not all(isinstance(value, dict) for value in (manifest, analysis, coverage, status)) or not isinstance(jobs, list):
        raise ValueError(f"Invalid saved evidence structure: {run}")
    # A changed final manifest must not be paired with a stale analysis snapshot.
    for field in ("cases", "cores", "questions", "budget", "job_seconds", "eval_seconds", "implementation", "explicit_job_ids"):
        if manifest.get(field) != (analysis.get("manifest") or {}).get(field):
            raise ValueError(f"Manifest/analysis disagree about {field}: {run}")
    job_map, coverage_map, best_map = {}, {}, {}
    ids = set()
    for job in jobs:
        key = logical_key(job)
        if key in job_map or job["id"] in ids:
            raise ValueError(f"Duplicate logical job or ID in {run}: {key}")
        job_map[key] = job
        ids.add(job["id"])
    for row in coverage.get("jobs", []):
        key = logical_key(row)
        if key in coverage_map:
            raise ValueError(f"Duplicate coverage row in {run}: {key}")
        coverage_map[key] = row
    for row in analysis.get("records", []):
        if row.get("variant") != ("original_singlecore" if row.get("question") == 0 else "best"):
            continue
        key = logical_key(row)
        if key in best_map:
            raise ValueError(f"Duplicate best/baseline row in {run}: {key}")
        best_map[key] = row
    if set(job_map) != set(coverage_map) or set(job_map) != set(best_map):
        raise ValueError(f"jobs, coverage and analysis populations differ: {run}")
    for key, job in job_map.items():
        cov, best = coverage_map[key], best_map[key]
        if cov.get("job_id") != job["id"] or best.get("job_id") != job["id"]:
            raise ValueError(f"Job identity mismatch: {run} {key}")
        state = cov.get("classification")
        if state not in STATES or best.get("classification") != state:
            raise ValueError(f"Unfinalized/inconsistent classification: {run} {key}")
        legal = best.get("legal") is True and positive(best.get("makespan"))
        if bool(cov.get("legal_incumbent")) != legal:
            raise ValueError(f"Legal incumbent disagreement: {run} {key}")
        if state in ("complete", "partial") and not legal:
            raise ValueError(f"Complete/partial without legal incumbent: {run} {key}")
        if key[1] == 3 and state == "complete":
            pair = cov.get("cache_pair") or {}
            ratio = best.get("same_plan_cache_ratio")
            if not pair.get("complete") or not positive(ratio) or not positive(pair.get("ratio")) or not math.isclose(ratio, pair["ratio"], rel_tol=1e-10, abs_tol=1e-6):
                raise ValueError(f"Q3 complete lacks consistent same-plan evidence: {run} {key}")
        evidence = (run / cov["result_path"]).resolve()
        if not evidence.is_relative_to((PACKAGE / "runs").resolve()):
            raise ValueError(f"Result path escapes package runs/: {evidence}")
    performance = None
    performance_path = run / "performance_summary.json"
    if performance_path.is_file():
        performance = load(performance_path)
        if require_performance and performance_path.stat().st_mtime < (run / "analysis.json").stat().st_mtime:
            raise ValueError(f"Regenerate performance_summary.json after final analysis: {run}")
        if require_performance and Path(performance.get("run_directory", "")).resolve() != run:
            raise ValueError(f"Performance summary belongs to another run: {run}")
    elif require_performance:
        raise ValueError(f"Run performance_summary.py first: {run}")
    return dict(path=run, manifest=manifest, analysis=analysis, coverage=coverage, jobs=job_map,
                best=best_map, coverage_rows=coverage_map, status=status, performance=performance)


def counts(data):
    output = {}
    for question in range(4):
        selected = [row for key, row in data["coverage_rows"].items() if key[1] == question]
        tally = Counter(row["classification"] for row in selected)
        output[f"Q{question}"] = dict(planned=len(selected), **{state: tally[state] for state in STATES},
            legal=sum(bool(row["legal_incumbent"]) for row in selected),
            timeout_events=sum(row.get("evaluation_timeout_events", 0) for row in selected))
    return output


def attempt_fields(data, key, prefix, output_root):
    if key not in data["jobs"]:
        empty = {field: None for field in ("supervisor_status", "result_status", "best_makespan", "original_singlecore", "speedup",
            "same_plan_cache_ratio", "same_plan_evidence_complete", "solve_seconds", "timing_affected_by_interruption", "result_path",
            "plan_path", "official_path", "baseline_result_path", "job_seconds", "eval_seconds", "budget",
            "raw_official_present", "raw_makespan_matches", "raw_evidence_issue_count")}
        empty.update(planned=False, attempted=False, status="not_planned", legal_incumbent=False)
        return {prefix + "_" + field: value for field, value in empty.items()}
    cov, best = data["coverage_rows"][key], data["best"][key]
    path = (data["path"] / cov["result_path"]).resolve()
    legal = best.get("legal") is True
    plan = path.parent / "best_plan.json"
    official = path.parent / "best_official.json"
    values = dict(planned=True, attempted=cov["classification"] != "not_started", status=cov["classification"],
        supervisor_status=cov.get("supervisor_status"), result_status=cov.get("result_status"),
        legal_incumbent=legal, best_makespan=best.get("makespan"), original_singlecore=best.get("original_singlecore"),
        speedup=best.get("speedup"), same_plan_cache_ratio=best.get("same_plan_cache_ratio"),
        same_plan_evidence_complete=bool((cov.get("cache_pair") or {}).get("complete")) if key[1] == 3 else None,
        solve_seconds=cov.get("solve_seconds"), timing_affected_by_interruption=bool(cov.get("timing_affected_by_interruption")),
        result_path=relative(path, output_root), plan_path=relative(plan, output_root) if legal and key[1] != 0 and plan.is_file() else None,
        official_path=relative(official, output_root) if legal and official.is_file() else None,
        job_seconds=data["manifest"].get("job_seconds"), eval_seconds=data["manifest"].get("eval_seconds"), budget=data["manifest"].get("budget"))
    raw = best.get("raw_evidence") or {}
    values.update(raw_official_present=raw.get("present"), raw_makespan_matches=raw.get("matches_recorded_makespan"),
        raw_evidence_issue_count=sum(issue.get("job_id") == cov["job_id"] for issue in data["analysis"].get("raw_evidence_issues", [])))
    baseline_ref = best.get("baseline_result_path")
    values["baseline_result_path"] = relative((data["path"] / baseline_ref).resolve(), output_root) if baseline_ref else None
    return {prefix + "_" + field: value for field, value in values.items()}


def prepare(formal, retry, extended=None):
    fkeys, rkeys = set(formal["jobs"]), set(retry["jobs"])
    expected = {(f"case_{case:03d}", 0, 1) for case in range(1, 101)}
    expected.update((f"case_{case:03d}", q, core) for case in range(1, 101) for q in (1, 2, 3) for core in (2, 5))
    if fkeys != expected:
        raise ValueError("Formal population must be exactly 100 original baselines plus Q1/Q2/Q3 at 2/5 cores (700 unique jobs)")
    if formal["path"] == retry["path"] or not rkeys or not rkeys < fkeys:
        raise ValueError("Retry must be a nonempty strict subset of the separate formal population")
    if len(rkeys) != 33:
        raise ValueError("This experiment report expects the explicitly authorized 33-job retry population")
    explicit = retry["manifest"].get("explicit_job_ids")
    if not isinstance(explicit, list) or len(explicit) != len(set(explicit)) or set(explicit) != {row["id"] for row in retry["jobs"].values()}:
        raise ValueError("Retry manifest explicit IDs do not match its unique job population")
    ineligible = [formal["jobs"][key]["id"] for key in sorted(rkeys) if formal["coverage_rows"][key]["classification"] not in ELIGIBLE]
    if ineligible:
        raise ValueError("Retry includes jobs outside formal failed/timeout/partial: " + ", ".join(ineligible))
    for field in ("implementation", "machine", "cores", "questions", "budget"):
        if formal["manifest"].get(field) != retry["manifest"].get(field):
            raise ValueError(f"Formal/retry differ in {field}; do not merge different algorithm/hardware populations")
    for field in ("input_root", "code_root", "python_executable"):
        if Path(formal["manifest"][field]).resolve() != Path(retry["manifest"][field]).resolve():
            raise ValueError(f"Formal/retry differ in {field}")
    if extended is not None:
        ekeys = set(extended["jobs"])
        if extended["path"] in (formal["path"], retry["path"]):
            raise ValueError("Extended retry must have its own independent directory")
        remaining = {key for key in rkeys if retry["coverage_rows"][key]["classification"] in ELIGIBLE | {"not_started"}}
        if not ekeys or ekeys != remaining:
            raise ValueError("Extended retry IDs must be exactly the second retry's failed/timeout/partial/not_started population")
        extended_ids = extended["manifest"].get("explicit_job_ids")
        if (not isinstance(extended_ids, list) or len(extended_ids) != len(set(extended_ids))
                or set(extended_ids) != {row["id"] for row in extended["jobs"].values()}):
            raise ValueError("Extended retry explicit IDs do not match its unique job population")
        for field in ("implementation", "machine", "cores", "questions", "budget", "workers"):
            if formal["manifest"].get(field) != extended["manifest"].get(field):
                raise ValueError(f"Formal/extended retry differ in {field}")
        for field in ("input_root", "code_root", "python_executable"):
            if Path(formal["manifest"][field]).resolve() != Path(extended["manifest"][field]).resolve():
                raise ValueError(f"Formal/extended retry differ in {field}")
        if (retry["manifest"].get("job_seconds"), retry["manifest"].get("eval_seconds")) != (360, 120):
            raise ValueError("Three-stage registry requires the second stage to be the 360/120-second retry")
        if (extended["manifest"].get("job_seconds"), extended["manifest"].get("eval_seconds"), extended["manifest"].get("budget")) != (600, 600, 6):
            raise ValueError("Extended retry must use the authorized 600/600-second and 6-call limits")
    for stage in [retry] + ([extended] if extended is not None else []):
        for key, job in stage["jobs"].items():
            actual = (stage["path"] / stage["coverage_rows"][key]["result_path"]).resolve()
            expected_path = (stage["path"] / job["id"] / "result.json").resolve()
            if job.get("result_root") or actual != expected_path:
                raise ValueError(f"Retry attempt must retain its own result, not import a prior score: {stage['path']} {job['id']}")
    groups = (formal.get("performance") or {}).get("groups", [])
    if {(row.get("question"), row.get("cores")) for row in groups} != {(q, n) for q in (1, 2, 3) for n in (2, 5)} or len(groups) != 6:
        raise ValueError("Formal performance summary must contain six unique question/core groups")
    if any(row.get("planned") != 100 for row in groups):
        raise ValueError("Formal performance summary planned counts disagree with 100-case population")
    output_root = extended["path"] if extended is not None else retry["path"]
    retry_prefix = "retry360" if extended is not None else "retry"
    stages = [("first", formal), (retry_prefix, retry)]
    if extended is not None:
        stages.append(("retry600", extended))
    resolved_baselines = {}
    for case in sorted({key[0] for key in fkeys}):
        baseline_key = (case, 0, 1)
        original_job = formal["jobs"][baseline_key]
        candidates = []
        for prefix, data in stages:
            if baseline_key not in data["jobs"]:
                continue
            job, best = data["jobs"][baseline_key], data["best"][baseline_key]
            for field in ("graph", "config", "code"):
                if not job.get(field) or Path(job[field]).resolve() != Path(original_job[field]).resolve():
                    raise ValueError(f"Q0 denominator source differs in {field}: {case} {prefix}")
            if best.get("legal") is True and positive(best.get("makespan")):
                evidence_path = (data["path"] / data["coverage_rows"][baseline_key]["result_path"]).resolve()
                candidates.append(dict(stage=prefix, job_id=job["id"], makespan=best["makespan"],
                    result_path=relative(evidence_path, output_root)))
        conflict = bool(candidates and any(not math.isclose(item["makespan"], candidates[0]["makespan"], rel_tol=1e-10, abs_tol=1e-6) for item in candidates[1:]))
        selected = candidates[-1] if candidates and not conflict else None
        resolved_baselines[case] = dict(candidates=candidates, conflict=conflict,
            resolved_original_singlecore=selected["makespan"] if selected else None,
            selected_source=selected, latest_legal_q0_candidate=candidates[-1] if candidates else None)
    registry = []
    for key in sorted(fkeys):
        row = dict(job_id=formal["jobs"][key]["id"], case=key[0], question=key[1], cores=key[2])
        for prefix, data in stages:
            if key in data["jobs"]:
                for field in ("graph", "config", "code"):
                    if Path(data["jobs"][key][field]).resolve() != Path(formal["jobs"][(key[0], 0, 1)][field]).resolve():
                        raise ValueError(f"Attempt and original Q0 differ in {field}: {data['path']} {row['job_id']}")
            row.update(attempt_fields(data, key, prefix, output_root))
        baseline = resolved_baselines[key[0]]
        selected_source = baseline["selected_source"] or {}
        row.update(resolved_original_singlecore=baseline["resolved_original_singlecore"],
            resolved_baseline_conflict=baseline["conflict"], resolved_baseline_source_stage=selected_source.get("stage"),
            resolved_baseline_source_job_id=selected_source.get("job_id"), resolved_baseline_result_path=selected_source.get("result_path"))
        for prefix, _ in stages:
            makespan = row.get(prefix + "_best_makespan")
            denominator = baseline["resolved_original_singlecore"]
            row[prefix + "_ratio_to_resolved_baseline"] = denominator / makespan if denominator is not None and row[prefix + "_legal_incumbent"] and positive(makespan) else None
        row["ever_complete"] = any(row[prefix + "_status"] == "complete" for prefix, _ in stages)
        row["ever_legal_incumbent"] = any(row[prefix + "_legal_incumbent"] for prefix, _ in stages)
        row["completion_source"] = next((prefix for prefix, _ in stages if row[prefix + "_status"] == "complete"), "none")
        registry.append(row)
    combined = dict(generated_utc=datetime.now(timezone.utc).isoformat(), formal_run=str(formal["path"]), retry_run=str(retry["path"]),
        definition="Cross-budget completion coverage only. No selected minimum scores and no mixed-budget performance mean.",
        formal=counts(formal), retry=counts(retry), by_question={},
        extended_retry=counts(extended) if extended is not None else None,
        extended_retry_run=str(extended["path"]) if extended is not None else None,
        registry_directory=str(output_root), registry_stage_prefixes=[prefix for prefix, _ in stages],
        resolved_baseline_rule="Use the latest stage's actually legal original Q0 for the same case/graph/config/code only when all legal Q0 cycles agree. Conflicts leave resolved denominator and every derived ratio blank. Original scores/speedups/GM are unchanged; no aggregate is computed from these derived ratios.",
        resolved_baselines_by_case=resolved_baselines,
        resolved_baseline_conflict_cases=[case for case, value in resolved_baselines.items() if value["conflict"]],
        resolved_baseline_missing_cases=[case for case, value in resolved_baselines.items() if not value["candidates"]],
        eligible_not_selected=[formal["jobs"][key]["id"] for key in sorted(fkeys - rkeys) if formal["coverage_rows"][key]["classification"] in ELIGIBLE])
    for question in range(4):
        selected = [row for row in registry if row["question"] == question]
        combined["by_question"][f"Q{question}"] = dict(planned=len(selected),
            original_complete=sum(row["first_status"] == "complete" for row in selected),
            retry_planned=sum(row[retry_prefix + "_planned"] for row in selected), retry_attempted=sum(row[retry_prefix + "_attempted"] for row in selected),
            completed_by_retry=sum(row["completion_source"] == retry_prefix for row in selected),
            ever_complete=sum(row["ever_complete"] for row in selected),
            still_incomplete=sum(not row["ever_complete"] for row in selected),
            ever_legal_incumbent=sum(row["ever_legal_incumbent"] for row in selected))
        if extended is not None:
            combined["by_question"][f"Q{question}"].update(
                extended_retry_planned=sum(row["retry600_planned"] for row in selected),
                extended_retry_attempted=sum(row["retry600_attempted"] for row in selected),
                completed_by_extended_retry=sum(row["completion_source"] == "retry600" for row in selected))
    return registry, combined


def fmt(value):
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.5f}".rstrip("0").rstrip(".")
    return str(value).replace("|", "\\|").replace("\n", " ")


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
        + ["| " + " | ".join(fmt(value) for value in row) + " |" for row in rows])


def command_block(command):
    return "```powershell\n$env:PYTHONDONTWRITEBYTECODE='1'\n" + command + "\n```"


def saved_command(data):
    command = data["manifest"].get("actual_command") or data["analysis"].get("actual_command")
    if not command:
        raise ValueError(f"Actual execution command missing; record it before reporting: {data['path']}")
    return command


def artifacts(data):
    names = ("summary.csv", "coverage.json", "manifest.json", "REPORT.md", "analysis.json", "evaluation_times.csv", "PERFORMANCE.md")
    return "；".join(link(name, data["path"] / name) for name in names if (data["path"] / name).is_file())


def retry_variant_coverage_lines(data):
    variants = ("fast", "components", "best")
    records = {}
    for record in data["analysis"].get("records", []):
        if record.get("variant") not in variants:
            continue
        key = logical_key(record)
        variant_key = key + (record["variant"],)
        if key not in data["jobs"] or key[1] == 0 or record.get("job_id") != data["jobs"][key]["id"]:
            raise ValueError(f"Variant record does not belong to this retry: {data['path']} {variant_key}")
        if variant_key in records:
            raise ValueError(f"Duplicate retry variant record: {data['path']} {variant_key}")
        records[variant_key] = record
    rows = []
    for question in (1, 2, 3):
        for cores in (2, 5):
            keys = [key for key in data["jobs"] if key[1:] == (question, cores)]
            legal_counts = []
            for variant in variants:
                selected = [records.get(key + (variant,), {}) for key in keys]
                legal = sum(row.get("legal") is True and positive(row.get("makespan")) for row in selected)
                legal_counts.append(f"{legal}/{len(keys)}")
            rows.append((f"Q{question}", cores, *legal_counts))
    return ["", "各变体合法覆盖（只计本档，不汇总成绩）：", "",
        table(["小问", "核", "fast 合法/计划", "components 合法/计划", "best 合法/计划"], rows),
        "", "计划数取本档实际名单，0/0 表示该问/核未列入本档；Q0 仅有 original_singlecore，见上方作业覆盖。缺少变体记录也不计合法。逐例评估状态、未合法变体见 "
        + link("summary.csv", data["path"] / "summary.csv") + " 与 "
        + link("analysis.json", data["path"] / "analysis.json") + "；缺行和缺合法变体的逐项清单见 "
        + link("coverage_detailed.json", data["path"] / "coverage_detailed.json") + "。"]


def variant_metrics_csv(formal, retry, combined, extended=None):
    output_root = extended["path"] if extended is not None else retry["path"]
    data_stages = [formal, retry] + ([extended] if extended is not None else [])
    prefixes = combined["registry_stage_prefixes"]
    if len(prefixes) != len(data_stages):
        raise ValueError("Variant metric stage population differs from the attempt registry")
    expected = {(stage, *key, variant) for stage, data in zip(prefixes, data_stages)
        for key in data["jobs"]
        for variant in (("original_singlecore",) if key[1] == 0 else ("fast", "components", "best"))}
    rows, seen = [], set()
    for stage, data in zip(prefixes, data_stages):
        for original in data["analysis"].get("records", []):
            key = logical_key(original)
            variant = original.get("variant")
            expected_variants = ("original_singlecore",) if key[1] == 0 else ("fast", "components", "best")
            if key not in data["jobs"] or variant not in expected_variants or original.get("job_id") != data["jobs"][key]["id"]:
                raise ValueError(f"Unexpected variant metric identity: {data['path']} {key} {variant}")
            unique = (stage, *key, variant)
            if unique in seen:
                raise ValueError(f"Duplicate variant metric identity: {unique}")
            seen.add(unique)
            baseline = combined["resolved_baselines_by_case"][key[0]]
            selected_source = baseline["selected_source"] or {}
            denominator = baseline["resolved_original_singlecore"]
            makespan = original.get("makespan")
            added = dict(stage=stage, source_run_directory=relative(data["path"], output_root),
                source_analysis_path=relative(data["path"] / "analysis.json", output_root),
                stage_job_seconds=data["manifest"].get("job_seconds"),
                stage_eval_seconds=data["manifest"].get("eval_seconds"), stage_budget=data["manifest"].get("budget"),
                resolved_original_singlecore=denominator,
                resolved_baseline_conflict=baseline["conflict"],
                resolved_baseline_source_stage=selected_source.get("stage"),
                resolved_baseline_source_job_id=selected_source.get("job_id"),
                resolved_baseline_result_path=selected_source.get("result_path"),
                ratio_to_resolved_baseline=denominator / makespan
                    if denominator is not None and original.get("legal") is True and positive(makespan) else None)
            if set(added) & set(original):
                raise ValueError(f"Derived variant fields would overwrite original analysis metrics: {unique}")
            row = dict(original)
            row.update(added)
            rows.append({field: json.dumps(value, ensure_ascii=False, allow_nan=False)
                if isinstance(value, (dict, list)) else value for field, value in row.items()})
    if seen != expected:
        raise ValueError(f"Variant metric records missing from saved analysis: {sorted(expected - seen)}")
    leading = ["stage", "job_id", "case", "question", "cores", "variant", "classification", "evaluation_status",
        "legal", "makespan", "original_singlecore", "speedup", "resolved_original_singlecore",
        "resolved_baseline_result_path", "resolved_baseline_conflict", "ratio_to_resolved_baseline"]
    available = {field for row in rows for field in row}
    fields = [field for field in leading if field in available] + sorted(available - set(leading))
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue(), len(rows)


def report(formal, retry, registry, combined, extended=None):
    fm, rm = formal["manifest"], retry["manifest"]
    interpreter = fm["python_executable"]
    history_command = (f"& '{interpreter}' -X utf8 -u -m research_a_aster_rbc.run --workers 2 --wall-seconds 1800 "
        f"--job-seconds 120 --eval-seconds 45 --budget 6 --input-root '{fm['input_root']}'")
    source = fm.get("continuation_source_manifest") or {}
    source_run = Path(fm.get("continued_from", ""))
    original_command = source.get("actual_command")
    if not original_command:
        raise ValueError("Original 100-case execution command missing from continuation provenance")
    output_root = extended["path"] if extended is not None else retry["path"]
    stage_names = "first/retry360/retry600" if extended is not None else "first/retry"
    lines = ["# ASTER 实际实验总报告", "", f"最终汇总生成于 {combined['generated_utc']}。本文件替换过程快照；原始各轮目录和失败轨迹继续保留。",
        "", f"实际解释器：`{interpreter}`；Python：`{fm.get('python')}`；机器：`{fm.get('machine')}`。源码取得、PR #13 与独立 worktree 的准确说明见 {link('RUN_HISTORY.md', PACKAGE / 'RUN_HISTORY.md')}。用户首选的 `D:\\python\\python.exe` 在本机不存在，使用现有 Python 3.12 环境。",
        "", "没有运行冒烟、单元测试、文件指纹或环境基准；没有修改官方评估器和题定配置，没有提交实验输出或上传赛事平台。", "", "## 两轮六图历史", "",
        table(["阶段", "整轮秒数", "输出与证据"], [(title, elapsed, link(name, PACKAGE / "runs" / name / "REPORT.md")) for title, name, elapsed in HISTORY]),
        "", "六图按评估前文件大小分位选定。第二轮保持初始 fast/components 构造与预算不变，仅加入有限连通块移动。34 个合法 best 配对中，11 个周期改善、23 个相同、0 个退步；第一轮/第二轮 best 周期比几何均值为 1.0040087605。fast/components 周期不变，不能把这项改善称为构造器提升。",
        "", "这两轮共同运行参数如下，解释器和输入路径同上；原始目录分别保留，不与后续 100 图拼接。命令及授权历史以 RUN_HISTORY 和各轮 manifest/REPORT 为准。", "", command_block(history_command),
        "", "## 原预算正式 100 图", "", "原预算为每作业 120 秒、每次官方评估 45 秒、每次求解最多 6 次官方调用；每图含原始 Q0 单核和三问 2/5 核，共 700 个逻辑作业。以下是原预算数据的独立覆盖，失败、超时、部分完成和未开始仍保留。",
        "", "本文 job complete 指作业正常结束、计时未受中断污染且存在已验证合法 best（Q0 为原图单核结果）；Q3 还必须完成固定同方案回放。它不代表 fast、components 各自都成功，也不代表用满 6 次官方调用。变体超时与作业完成可以同时出现，需另看各变体合法覆盖和逐次官方调用记录。", "",
        table(["小问", "计划", "完成", "失败", "超时", "部分完成", "未开始", "合法 incumbent"],
            [(q, *(c[field] for field in ("planned", "complete", "failed", "timeout", "partial", "not_started", "legal"))) for q, c in combined["formal"].items()]),
        "", f"原 100 图启动目录：`{source_run}`。命令：", "", command_block(original_command),
        "", f"续跑目录：`{formal['path']}`。只对旧 478 个未开始作业续跑，旧 222 个状态和证据只读引用；完整 700 个逻辑作业保存在同一份续跑 jobs/summary 中。命令：", "", command_block(saved_command(formal)),
        "", artifacts(formal), "", "## 原预算性能：六个问/核分组", "",
        "只列原预算正式轮。GM 是有合法结果且分母齐全的子集几何均值，不填补缺失样本。fast/components 胜平负从 fast 角度统计；best 对 fast 包含种子选择收益，best 对最好已评估合法种子才把这部分分开。合法 partial 可以配对，详细 partial/缺失覆盖见 PERFORMANCE。", ""]
    groups = formal["performance"]["groups"]
    perf_rows = []
    for group in groups:
        variants = {row["variant"]: row for row in group["variant_coverage"]}
        fc, bf, bs = (group[name] for name in ("fast_vs_components", "best_vs_fast", "best_vs_evaluated_legal_seeds"))
        perf_rows.append((group["question"], group["cores"],
            f"{variants['best']['legal']}/{group['planned']}", variants["best"]["valid_singlecore_denominator"],
            variants["fast"]["geomean_speedup"], variants["components"]["geomean_speedup"], variants["best"]["geomean_speedup"],
            f"{fc['improved']}/{fc['equal_makespan']}/{fc['regressed']} ({fc['paired']})",
            f"{bf['improved']}/{bf['paired']}", f"{bs['improved']}/{bs['paired']}", bs["geomean_reference_over_candidate"]))
    extended_lines = []
    if extended is not None:
        em = extended["manifest"]
        extended_lines = ["", "## 剩余作业的 10 分钟档独立补跑", "",
            f"用户最新明确授权继续补完剩余作业并进一步放宽时间。第三阶段仅含第二阶段仍未 complete 的 {len(extended['jobs'])} 个 failed/timeout/partial/not_started 作业，每项最多再试一次；每作业 {em['job_seconds']} 秒、单次评估上限 {em['eval_seconds']} 秒（实际仍受作业剩余时间约束）、官方调用预算 {em['budget']}、workers={em.get('workers')}。",
            f"第三阶段总窗口为 {em['wall_seconds']} 秒，按剩余待办的一次 600 秒尝试及收尾另行授权；整体已不再受原 3 小时总窗口限制。三个阶段分别保存，旧 33 项目录的汇总不被本次写入覆盖。", "",
            table(["小问", "计划", "完成", "失败", "超时", "部分完成", "未开始", "合法 incumbent"],
                [(q, *(c[field] for field in ("planned", "complete", "failed", "timeout", "partial", "not_started", "legal"))) for q, c in combined["extended_retry"].items()]),
            *retry_variant_coverage_lines(extended),
            "", f"解释器：`{em['python_executable']}`。输出：`{extended['path']}`。实际命令：", "", command_block(saved_command(extended)),
            "", artifacts(extended), "", f"第三阶段监督器耗时：{fmt(extended['status'].get('elapsed_seconds'))} 秒。该档的运行预算与性能只属于本档，不回填或择优替换前两档成绩。"]
    if extended is not None:
        coverage_headers = ["Q", "原计划", "原完成", "360档计划", "360档启动", "360档补齐", "600档计划", "600档启动", "600档补齐", "曾完成", "仍未完整完成", "曾有合法方案"]
        coverage_fields = ("planned", "original_complete", "retry_planned", "retry_attempted", "completed_by_retry",
            "extended_retry_planned", "extended_retry_attempted", "completed_by_extended_retry", "ever_complete", "still_incomplete", "ever_legal_incumbent")
    else:
        coverage_headers = ["Q", "原计划", "原完成", "补跑计划", "补跑实际启动", "由补跑补齐", "曾完成", "仍未完整完成", "曾有合法方案"]
        coverage_fields = ("planned", "original_complete", "retry_planned", "retry_attempted", "completed_by_retry", "ever_complete", "still_incomplete", "ever_legal_incumbent")
    unresolved = [row for row in registry if not row["ever_complete"]]
    final_failure_lines = ["", "## 最终仍未完整完成", "", f"按 ever_complete=false 统计：{len(unresolved)} 项。"]
    if unresolved:
        unresolved_rows = []
        for row in unresolved:
            final_stage = next(prefix for prefix in reversed(combined["registry_stage_prefixes"]) if row[prefix + "_planned"])
            result = (output_root / row[final_stage + "_result_path"]).resolve()
            log = result.parent / "job.log"
            error = result.parent / "worker_error.json"
            evidence_links = [link("result.json", result) if result.is_file() else "结果未生成",
                              link("job.log", log) if log.is_file() else "日志未生成"]
            if error.is_file():
                evidence_links.append(link("worker_error.json", error))
            unresolved_rows.append((row["job_id"], final_stage, row[final_stage + "_status"],
                "是" if row[final_stage + "_legal_incumbent"] else "否",
                "是" if row["ever_legal_incumbent"] else "否", "；".join(evidence_links)))
        final_failure_lines += ["", "最终档指该作业最后被列入的尝试，未启动者仍列 not_started。partial 保留已验证方案，但不等于完整完成；本档无合法方案也不会丢弃此前尝试已验证的方案。", "",
            table(["作业 ID", "最终档", "最终档状态", "本档有已验证 incumbent", "任一档曾有合法方案", "结果与失败日志"], unresolved_rows)]
    else:
        final_failure_lines += ["", "没有仍未完整完成的逻辑作业；这是跨预算完成覆盖，不能称为原固定预算全部成功。"]
    next_steps = ("下一步应先复核上表仍未完整完成作业的实际错误、合法方案和官方评估时间分布。"
        if unresolved else "当前没有逻辑作业待补齐；下一步应结合各变体合法覆盖和逐次官方耗时，检查构造成本与时间分配，不能把全部 job complete 当作所有变体均成功。")
    diagnostic_path = formal["path"] / "FIVE_CORE_DIAGNOSTICS.md"
    if diagnostic_path.is_file():
        next_steps += ("已有 " + link("固定四图五核时序诊断", diagnostic_path)
            + " 记录了五核无操作区间、主核剩余重负载及 Cache 命中但总周期不降的现象。可先基于已保存官方时序检查重负载的可拆分性、跨核依赖等待与重复搬运对关键路径的影响，形成通用分区与调度改进候选；这些局部现象尚未完成因果归因，不据此默认增加搜索预算。")
    next_steps += "本次汇总不启动额外实验、不自动合并或上传结果。所有正式周期来自已保存的官方结果，报告没有使用代理估计填补缺失。"
    lines += [table(["Q", "核", "best合法/计划", "有效T1", "fast GM加速比", "components GM", "best GM", "fast胜/平/负(配对)", "best快于fast", "best快于种子最优", "种子/best GM"], perf_rows),
        "", "### 固定同方案 Cache", "", "仅使用已经完成的固定 best_plan Q2/Q3 回放证据；未使用分别优化的两问最好成绩相除。命中字节率均值是逐作业等权均值，非合并字节的加权率。", "",
        table(["核", "完整同方案回放/计划", "比值>1", "=1", "<1", "Q2/Q3 GM", "命中字节率有效数", "命中字节率均值"],
            [(g["cores"], f"{g['same_plan_cache']['completed_evidence']}/{g['planned']}", *(g["same_plan_cache"][field] for field in ("ratio_above_one", "ratio_equal_one", "ratio_below_one", "geomean_q2_no_cache_over_q3_cache", "hit_byte_rate_count", "hit_byte_rate_unweighted_mean"))) for g in groups if g["question"] == 3]),
        "", "## 超时及部分完成的独立补跑", "",
        f"用户授权将 {len(retry['jobs'])} 个原 failed/timeout/partial 作业各补一次。补跑每作业 {rm['job_seconds']} 秒、每次评估 {rm['eval_seconds']} 秒、预算 {rm['budget']}，窗口 {rm['wall_seconds']} 秒取自续跑原 9240 秒窗口的剩余时间。原失败轨迹不覆盖，补跑未完成者仍如实列出。", "",
        table(["小问", "计划", "完成", "失败", "超时", "部分完成", "未开始", "合法 incumbent"],
            [(q, *(c[field] for field in ("planned", "complete", "failed", "timeout", "partial", "not_started", "legal"))) for q, c in combined["retry"].items()]),
        *retry_variant_coverage_lines(retry),
        "", f"解释器：`{rm['python_executable']}`。输出：`{retry['path']}`。实际命令：", "", command_block(saved_command(retry)),
        "", artifacts(retry),
        "", "补跑只读复用指定来源的合法原始 Q0 分母，本次补跑合法 Q0 优先；没有把补齐的 Q0 回填进原预算性能表，也没有逐图择优生成混合预算成绩。补跑恢复是该次运行的实测事实；放宽上限、运行负载和评估耗时波动各自的贡献未经因果拆分，不将所有恢复归因于放宽上限。",
        *extended_lines, "", "### 跨预算补齐情况（只看覆盖）", "",
        table(coverage_headers, [(q, *(c[field] for field in coverage_fields)) for q, c in combined["by_question"].items()]),
        "", f"原预算不完整且未列入第二阶段补跑名单：{len(combined['eligible_not_selected'])} 项；具体列表在 combined_coverage.json。该覆盖表跨越 {'三个' if extended is not None else '两个'}预算，只说明是否补齐，不是固定预算完整 100 图成绩。",
        "", "逐作业并列追踪：" + "；".join(link(name, output_root / name) for name in ("attempt_registry.csv", "attempt_registry.json", "combined_coverage.json")) + f"。每条记录保留 {stage_names} 状态、独立 best 与分母、同方案证据和真实文件路径；不选择最低周期。原始官方响应是否存在、周期是否匹配以及证据问题数另列，合法结果标记不自动等于原始文件齐全。",
        "", f"注册表另列 resolved_original_singlecore 与各档 ratio_to_resolved_baseline：只用同案例、同图/配置/官方代码路径下最新合法原图 Q0 补齐共享分母，保留来源。跨次合法 Q0 周期不一致时标记冲突并留空分母与派生比值；当前冲突 {len(combined['resolved_baseline_conflict_cases'])} 例、仍无合法 Q0 {len(combined['resolved_baseline_missing_cases'])} 例。原 original_singlecore、speedup 和原固定 120/45 报告的 GM 不改；共享分母派生列不属于该 GM，不生成新的综合成绩。候选分母及规则见 combined_coverage.json。",
        "", "全部变体的独立明细见 " + link("variant_metrics_with_resolved_baseline.csv", output_root / "variant_metrics_with_resolved_baseline.csv")
        + "：逐阶段保留 analysis.records 的原 Makespan、speedup、搬运、Spill、Cache、整次求解与源官方评估耗时等字段，新增同规则共享 T1 及各行 T1/Makespan；无合法值或分母冲突时派生比值留空。按 stage/case/question/cores/variant 唯一，不选择跨阶段最低分，不新增聚合成绩，也不改原 summary.csv。嵌套字段以 JSON 保留；原记录相对路径以 source_run_directory 为基准，该目录列及新增分母路径以本 CSV 所在目录为基准。solve_seconds 仍是整作业时间，在变体行重复出现，不能当作变体独立时间或直接逐行累加。",
        *final_failure_lines, "", "## 实际时间与中断", "",
        "旧前段 222 项在休眠前的实际活跃墙钟约 26 分钟；原记录墙钟 39208.932 秒包含长时间睡眠/休眠，不能当作计算耗时。排除两项受中断影响的计时后，220 个作业 solve_seconds 合计 2935.802 秒，是并发作业累计时间，不能当作墙钟。",
        f"续跑 478 项监督器耗时：{fmt(formal['status'].get('elapsed_seconds'))} 秒；360 秒档补跑监督器耗时：{fmt(retry['status'].get('elapsed_seconds'))} 秒。各阶段各自保留 run_status；第三阶段若列入本报告，其额外总窗口来自用户最新明确授权，整体不再称为原 3 小时内完成。" if extended is not None else f"续跑 478 项监督器耗时：{fmt(formal['status'].get('elapsed_seconds'))} 秒；本次补跑监督器耗时：{fmt(retry['status'].get('elapsed_seconds'))} 秒。原预算与补跑各自保留 run_status，不把已结束的窗口偷偷续期。",
        "", "case_041_q1_n2 与 case_041_q2_n2 原计时受休眠影响，不能当作正常 CPU 用时；有合法方案者计部分完成，无合法者按超时/失败。case_050_q2_n2 原检查点文件替换失败的合法 incumbent 和失败轨迹保留。文件替换兼容补丁只重试文件操作，最多等待 0.75 秒，不重复官方调用；标准库临时防睡眠未修改全局电源设置。",
        "", "solve_seconds 始终是整作业时间，未声称任何 variant 的独立求解耗时。逐次官方调用耗时见各目录 evaluation_times.csv；原预算性能耗时聚合排除休眠污染，checkpoint 只作中途记录。", "", "## 局限、下界与下一步", "",
        f"原预算 bound_violation：{len(formal['analysis'].get('bound_violations', []))}；360 秒档补跑 bound_violation：{len(retry['analysis'].get('bound_violations', []))}" + (f"；600 秒档：{len(extended['analysis'].get('bound_violations', []))}" if extended is not None else "") + "。计算松弛下界保持原值且有语义适用条件，未宣称已认证最优性缺口；异常详情保留在各 analysis.json。",
        "", "本轮尚不能判断是否超过论文：缺少相同案例、核数、小问、题定配置和单核分母的旧论文逐例证据；六图均值和缺项子集均值不能与旧论文全 100 图均值直接比较。",
        "", "保留：完整官方验证链、已验证方案、各预算的独立结果以及可追溯的失败日志。改进证据应分别看构造器胜平负、best 超过已评估种子的配对收益、搬运/Spill 和固定同方案 Cache 效果。尚缺证据的是旧论文逐例对照、下界语义认证，以及搜索操作与性能变化的因果归属。",
        "", next_steps, ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("formalrun")
    parser.add_argument("retryrun")
    parser.add_argument("--extended-retry", help="Optional independently completed 600-second attempt for every unfinished second-retry job")
    args = parser.parse_args()
    formal = read_run(resolve_run(args.formalrun), require_performance=True)
    retry = read_run(resolve_run(args.retryrun))
    extended = read_run(resolve_run(args.extended_retry)) if args.extended_retry else None
    registry, combined = prepare(formal, retry, extended)
    variant_csv, variant_count = variant_metrics_csv(formal, retry, combined, extended)
    final_report = report(formal, retry, registry, combined, extended)
    output_root = extended["path"] if extended is not None else retry["path"]
    fields = sorted({field for row in registry for field in row})
    fields = ["job_id", "case", "question", "cores"] + [field for field in fields if field not in {"job_id", "case", "question", "cores"}]
    csv_output = io.StringIO(newline="")
    writer = csv.DictWriter(csv_output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(registry)
    registry_output = dict(generated_utc=combined["generated_utc"], formal_run=str(formal["path"]), retry_run=str(retry["path"]),
        extended_retry_run=str(extended["path"]) if extended is not None else None,
        stage_prefixes=combined["registry_stage_prefixes"], relative_path_base=str(output_root),
        resolved_baseline_rule=combined["resolved_baseline_rule"], resolved_baselines_by_case=combined["resolved_baselines_by_case"],
        note="Attempt evidence is stored in parallel stage columns, not minimum-score selection. Relative paths use the latest output directory.", jobs=registry)
    # Prepare all serialization before writing; validation failures produce no tables.
    serialized_registry = json.dumps(registry_output, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    serialized_coverage = json.dumps(combined, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    (output_root / "attempt_registry.csv").write_text(csv_output.getvalue(), encoding="utf-8-sig")
    (output_root / "attempt_registry.json").write_text(serialized_registry, encoding="utf-8")
    (output_root / "combined_coverage.json").write_text(serialized_coverage, encoding="utf-8")
    (output_root / "variant_metrics_with_resolved_baseline.csv").write_text(variant_csv, encoding="utf-8-sig")
    (PACKAGE / "EXPERIMENT_REPORT.md").write_text(final_report, encoding="utf-8")
    print(json.dumps({"report": str(PACKAGE / "EXPERIMENT_REPORT.md"), "registry_jobs": len(registry),
        "retry_jobs": len(retry["jobs"]), "extended_retry_jobs": len(extended["jobs"]) if extended is not None else 0,
        "registry_directory": str(output_root), "variant_metric_rows": variant_count,
        "ever_complete": sum(row["ever_complete"] for row in registry)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
