"""Summarize one finished run's saved evidence; never launch an experiment.

Usage: python -X utf8 -m research_a_aster_rbc.performance_summary runs/<run>
Reads analysis.json, jobs.json, and their exact result.json references only.
Writes PERFORMANCE.md and performance_summary.json in that same run directory.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import statistics


PACKAGE = Path(__file__).resolve().parent
VARIANTS = ("fast", "components", "best")


def numeric(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def positive(value):
    number = numeric(value)
    return number if number is not None and number > 0 else None


def equal(left, right):
    return math.isclose(left, right, rel_tol=1e-10, abs_tol=1e-6)


def legal_evaluation(item):
    return isinstance(item, dict) and item.get("status") == "ok" and positive(item.get("makespan")) is not None


def legal_row(row):
    return bool(row and row.get("legal") is True and positive(row.get("makespan")) is not None)


def geomean(values):
    values = [number for value in values if (number := positive(value)) is not None]
    return math.exp(math.fsum(map(math.log, values)) / len(values)) if values else None


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def result_path(run, job):
    folder = Path(job.get("result_root") or job["id"])
    folder = (folder if folder.is_absolute() else run / folder).resolve()
    if not folder.is_relative_to((PACKAGE / "runs").resolve()):
        raise ValueError(f"Result reference leaves this package runs/: {folder}")
    return folder / "result.json"


def comparison(pairs, planned):
    """Each ratio is reference/candidate; >1 means the candidate is faster."""
    wins = sum(not equal(left, right) and right < left for left, right, _ in pairs)
    ties = sum(equal(left, right) for left, right, _ in pairs)
    losses = len(pairs) - wins - ties
    return dict(planned=planned, paired=len(pairs), missing_pairs=planned - len(pairs),
                improved=wins, equal_makespan=ties, regressed=losses,
                improvement_fraction=wins / len(pairs) if pairs else None,
                geomean_reference_over_candidate=geomean(left / right for left, right, _ in pairs),
                partial_pairs=sum(state == "partial" for _, _, state in pairs))


def build(run):
    analysis = load(run / "analysis.json")
    jobs = load(run / "jobs.json")
    manifest = analysis.get("manifest") or {}
    if not isinstance(jobs, list) or not all(isinstance(job, dict) for job in jobs):
        raise ValueError("jobs.json must be a job list")
    if len(jobs) != len({job["id"] for job in jobs}):
        raise ValueError("Duplicate logical job IDs: refusing to double-count evidence")
    if manifest.get("explicit_job_ids") is not None and set(manifest["explicit_job_ids"]) != {job["id"] for job in jobs}:
        raise ValueError("Explicit retry population differs from jobs.json")
    by_variant = defaultdict(lambda: defaultdict(list))
    for row in analysis.get("records", []):
        if isinstance(row, dict):
            by_variant[row.get("job_id")][row.get("variant")].append(row)
    warnings, details, timing_rows = [], [], []
    duplicate_keys = [{"job_id": job_id, "variant": variant, "count": len(rows)}
                      for job_id, variants in by_variant.items() for variant, rows in variants.items() if len(rows) > 1]
    if duplicate_keys:
        warnings.append("Duplicate analysis rows are excluded from pair comparisons; see duplicate_analysis_keys")
    questionable_evaluations = {(item.get("job_id"), item.get("index")) for item in analysis.get("raw_evidence_issues", []) if isinstance(item, dict)}
    for job in jobs:
        variants = {variant: values[0] for variant, values in by_variant.get(job["id"], {}).items() if len(values) == 1}
        for variant, row in list(variants.items()):
            if (row.get("case"), row.get("question"), row.get("cores")) != (job["case"], job["question"], job["cores"]):
                warnings.append(f"Mismatched analysis case/question/core excluded: {job['id']} {variant}")
                del variants[variant]
        best = variants.get("best") or variants.get("original_singlecore") or {}
        state = best.get("classification", "missing_analysis")
        if not best:
            warnings.append(f"Missing unique analysis best/baseline row: {job['id']}")
        path = result_path(run, job)
        data = {}
        if path.is_file():
            try:
                data = load(path)
            except (OSError, ValueError) as exc:
                warnings.append(f"Cannot read {path}: {exc}")
        if not isinstance(data, dict):
            data = {}
        evaluations = []
        evaluation_indices = set()
        for position, item in enumerate(data.get("evaluations", [])):
            if not isinstance(item, dict):
                continue
            index = item.get("index", position)
            if index in evaluation_indices:
                warnings.append(f"Duplicate recorded official evaluation excluded: {job['id']} index {index}")
                continue
            evaluation_indices.add(index)
            evaluations.append(item)
        labels = {item.get("label"): item for item in evaluations}
        indices = {item.get("index"): item for item in evaluations if item.get("index") is not None}
        for label, index in (data.get("aliases") or {}).items():
            if index in indices:
                labels[label] = indices[index]
        sleep_affected = bool(job.get("timing_affected_by_interruption") or best.get("timing_affected_by_interruption"))
        sleep_affected = sleep_affected or job["id"] in (analysis.get("interruption") or {}).get("timing_affected_jobs", [])
        solve = numeric(data.get("solve_seconds"))
        recorded_seconds = [numeric(item.get("seconds")) for item in evaluations]
        evaluation_seconds = [value for value in recorded_seconds if value is not None and value >= 0]
        timing_rows.append(dict(job_id=job["id"], question=job["question"], cores=job["cores"],
            classification=state, machine=job.get("machine", manifest.get("machine")),
            result_path=os.path.relpath(path, run), retained=bool(job.get("result_root")),
            solve_seconds=solve, solve_is_checkpoint=data.get("status") == "running",
            timing_affected_by_interruption=sleep_affected,
            recorded_official_calls=len(evaluations), calls_with_seconds=len(evaluation_seconds),
            official_seconds_sum=math.fsum(evaluation_seconds),
            official_timeout_calls=sum(item.get("status") == "timeout" for item in evaluations)))
        if job["question"] == 0:
            continue
        seeds = {}
        for label in ("fast", "components", "single_fallback"):
            item = labels.get(label, {})
            # fast/components also have raw-response checks represented in analysis.
            if label in ("fast", "components") and not legal_row(variants.get(label)):
                continue
            if item.get("question", job["question"]) != job["question"]:
                continue
            if (job["id"], item.get("index")) in questionable_evaluations:
                continue
            if legal_evaluation(item):
                if label in ("fast", "components") and not equal(item["makespan"], variants[label]["makespan"]):
                    warnings.append(f"Seed/analysis Makespan mismatch excluded: {job['id']} {label}")
                    continue
                seeds[label] = dict(makespan=positive(item["makespan"]), evaluation_index=item.get("index"),
                    source_label=item.get("label"), alias=label in (data.get("aliases") or {}),
                    partition_added_copy_bytes=item.get("partition_added_copy_bytes"),
                    spill_added_copy_bytes=item.get("spill_added_copy_bytes"))
        seed_min = min((item["makespan"] for item in seeds.values()), default=None)
        ratios = {}
        if legal_row(variants.get("fast")) and legal_row(variants.get("components")):
            ratios["components_over_fast"] = variants["components"]["makespan"] / variants["fast"]["makespan"]
        if legal_row(best) and legal_row(variants.get("fast")):
            ratios["fast_over_best"] = variants["fast"]["makespan"] / best["makespan"]
        if legal_row(best) and seed_min is not None:
            ratios["best_legal_seed_over_best"] = seed_min / best["makespan"]
        cache_ratio = positive(best.get("same_plan_cache_ratio")) if job["question"] == 3 and legal_row(best) else None
        details.append(dict(job_id=job["id"], case=job["case"], question=job["question"], cores=job["cores"],
            classification=state, variants={variant: {key: variants.get(variant, {}).get(key) for key in
                ("legal", "makespan", "speedup", "original_singlecore", "evaluation_status", "cache_byte_hit_rate")}
                for variant in VARIANTS}, legal_seeds=seeds, legal_seed_min_makespan=seed_min,
            all_three_seed_labels_legal=len(seeds) == 3, ratios=ratios,
            same_plan_cache_ratio=cache_ratio,
            same_plan_cache_evidence_source="analysis.records[best].same_plan_cache_ratio" if cache_ratio is not None else None,
            best_cache_byte_hit_rate=numeric(best.get("cache_byte_hit_rate")),
            result_path=os.path.relpath(path, run)))
    groups = []
    for question in (1, 2, 3):
        for cores in (2, 5):
            selected = [row for row in details if (row["question"], row["cores"]) == (question, cores)]
            variant_coverage = []
            for variant in VARIANTS:
                valid = [row["variants"][variant] for row in selected if legal_row(row["variants"][variant])]
                speedups = [row["speedup"] for row in valid if positive(row.get("speedup")) is not None]
                variant_coverage.append(dict(variant=variant, planned=len(selected), legal=len(valid),
                    valid_singlecore_denominator=len(speedups), geomean_speedup=geomean(speedups),
                    missing_legal=len(selected) - len(valid)))
            fc, bf, bs = [], [], []
            complete_seeds_pairs = 0
            for row in selected:
                fast, components, best = (row["variants"][label] for label in VARIANTS)
                if legal_row(fast) and legal_row(components):
                    fc.append((components["makespan"], fast["makespan"], row["classification"]))
                if legal_row(fast) and legal_row(best):
                    bf.append((fast["makespan"], best["makespan"], row["classification"]))
                if legal_row(best) and row["legal_seed_min_makespan"] is not None:
                    bs.append((row["legal_seed_min_makespan"], best["makespan"], row["classification"]))
                    complete_seeds_pairs += row["all_three_seed_labels_legal"]
            seed_comparison = comparison(bs, len(selected))
            seed_comparison["pairs_with_all_three_seed_labels_legal"] = complete_seeds_pairs
            seed_comparison["pairs_with_missing_or_illegal_seed_labels"] = len(bs) - complete_seeds_pairs
            group = dict(question=question, cores=cores, planned=len(selected),
                classification_counts=dict(Counter(row["classification"] for row in selected)),
                variant_coverage=variant_coverage, fast_vs_components=comparison(fc, len(selected)),
                best_vs_fast=comparison(bf, len(selected)), best_vs_evaluated_legal_seeds=seed_comparison,
                legal_seed_label_count_histogram=dict(Counter(len(row["legal_seeds"]) for row in selected)))
            if question == 3:
                paired = [row for row in selected if row["same_plan_cache_ratio"] is not None]
                ratios = [row["same_plan_cache_ratio"] for row in paired]
                rates = [row["best_cache_byte_hit_rate"] for row in selected
                         if legal_row(row["variants"]["best"]) and row["best_cache_byte_hit_rate"] is not None]
                group["same_plan_cache"] = dict(planned=len(selected), completed_evidence=len(paired),
                    missing_evidence=len(selected) - len(paired),
                    ratio_above_one=sum(value > 1 and not equal(value, 1) for value in ratios),
                    ratio_equal_one=sum(equal(value, 1) for value in ratios),
                    ratio_below_one=sum(value < 1 and not equal(value, 1) for value in ratios),
                    geomean_q2_no_cache_over_q3_cache=geomean(ratios),
                    partial_jobs_with_complete_pair=sum(row["classification"] == "partial" for row in paired),
                    hit_byte_rate_count=len(rates), hit_byte_rate_unweighted_mean=statistics.mean(rates) if rates else None,
                    hit_byte_rate_min=min(rates, default=None), hit_byte_rate_max=max(rates, default=None),
                    note="Hit rate summary is an unweighted mean of per-job official byte rates, not a pooled global byte rate.")
            groups.append(group)
    timing = []
    for machine in sorted({str(row["machine"]) for row in timing_rows}):
        selected = [row for row in timing_rows if str(row["machine"]) == machine]
        clean = [row for row in selected if not row["timing_affected_by_interruption"]]
        finished_times = [row["solve_seconds"] for row in clean if row["solve_seconds"] is not None and not row["solve_is_checkpoint"]]
        timing.append(dict(machine=machine, logical_jobs=len(selected), retained_jobs=sum(row["retained"] for row in selected),
            sleep_affected_jobs=[row["job_id"] for row in selected if row["timing_affected_by_interruption"]],
            finalized_solve_time_count=len(finished_times), finalized_solve_seconds_sum=math.fsum(finished_times),
            finalized_solve_seconds_mean=statistics.mean(finished_times) if finished_times else None,
            finalized_solve_seconds_median=statistics.median(finished_times) if finished_times else None,
            checkpoint_only_jobs=[row["job_id"] for row in clean if row["solve_is_checkpoint"]],
            missing_solve_time_jobs=[row["job_id"] for row in clean if row["solve_seconds"] is None],
            clean_recorded_official_calls=sum(row["recorded_official_calls"] for row in clean),
            clean_calls_with_seconds=sum(row["calls_with_seconds"] for row in clean),
            clean_official_seconds_sum=math.fsum(row["official_seconds_sum"] for row in clean),
            clean_official_timeout_calls=sum(row["official_timeout_calls"] for row in clean)))
    return dict(generated_utc=datetime.now(timezone.utc).isoformat(), run_directory=str(run),
        analysis_generated_utc=analysis.get("generated_utc"), manifest=manifest,
        scope="One declared run population; follow its retained result_root only. Never scan or merge other experiment rounds.",
        current_run_supervisor_status=analysis.get("run_status"), coverage_by_question=analysis.get("coverage_by_question"),
        groups=groups, per_job=details, timing_by_machine=timing, timing_per_job=timing_rows,
        duplicate_analysis_keys=duplicate_keys, warnings=warnings,
        old_paper_comparison="本轮尚不能判断是否超过论文：缺少相同案例、核数、小问、配置和单核分母的旧论文逐例证据。")


def fmt(value):
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.5f}".rstrip("0").rstrip(".")
    return str(value).replace("|", "\\|").replace("\n", " ")


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
        + ["| " + " | ".join(fmt(value) for value in row) + " |" for row in rows])


def markdown(summary):
    groups, manifest = summary["groups"], summary["manifest"]
    lines = ["# ASTER 性能分解报告", "", f"来源：`{summary['run_directory']}`。生成：{summary['generated_utc']}。",
        "", f"算法记录：{manifest.get('implementation')}。每作业 {manifest.get('job_seconds')} 秒；每次评估 {manifest.get('eval_seconds')} 秒；官方调用预算 {manifest.get('budget')}。",
        "", "本报告只读取本次逻辑作业及明确引用的旧来源，没有合并六图探索轮或放宽时限补跑。合法但部分完成的方案可参加分数配对，其数量另列；未开始、无合法方案或缺分母不会被补造为成绩。以下几何均值只描述有数据的配对子集。"]
    if manifest.get("run_kind") == "targeted_retry":
        lines += ["", "本目录本身是独立定向补跑。它的结果不构成原固定预算的完整 100 图成绩，也未与原轮逐图择优合并。"]
    lines += ["", "## 合法覆盖与加速比", "", table(["Q", "核", "variant", "计划", "合法", "有效 T1", "加速比几何均值"],
        [(g["question"], g["cores"], v["variant"], v["planned"], v["legal"], v["valid_singlecore_denominator"], v["geomean_speedup"]) for g in groups for v in g["variant_coverage"]]),
        "", "T1 为 analysis 已记录的合法原始整图单核分母；没有 T1 的合法多核方案仍参与同例周期配对，但不参与加速比均值。", "",
        table(["Q", "核", "作业分类"], [(g["question"], g["cores"], json.dumps(g["classification_counts"], ensure_ascii=False)) for g in groups]),
        "", "## 构造器与连通块参照", "", "胜/平/负从 fast 的角度统计；components/fast 大于 1 表示 fast 更快。", "",
        table(["Q", "核", "合法配对/计划", "fast 胜", "平", "fast 负", "配对中 partial", "components/fast 几何均值"],
            [(g["question"], g["cores"], f"{g['fast_vs_components']['paired']}/{g['planned']}", *(g["fast_vs_components"][key] for key in ("improved", "equal_makespan", "regressed", "partial_pairs", "geomean_reference_over_candidate"))) for g in groups]),
        "", "## best 的收益分解", "", "best/fast 的改进包括参照种子择优与定向增强。为避免把种子选择归功于搜索，另将 best 与本作业已实际评估且合法的 fast、components、single_fallback 中最短周期比较。alias 只表示同一真实评估复用，不算新增官方调用。缺失或非法种子不参与最小值，也不假定其成绩。", ""]
    for key, title in (("best_vs_fast", "best 相对 fast"), ("best_vs_evaluated_legal_seeds", "best 相对已评估合法种子的最好周期")):
        lines += ["", f"### {title}", "", table(["Q", "核", "配对/计划", "改善", "平", "退化", "改善比例", "配对中 partial", "参照/best 几何均值"],
            [(g["question"], g["cores"], f"{g[key]['paired']}/{g['planned']}", *(g[key][field] for field in ("improved", "equal_makespan", "regressed", "improvement_fraction", "partial_pairs", "geomean_reference_over_candidate"))) for g in groups])]
    lines += ["", "改善比例的分母为合法配对数，数值为 0–1。与种子最好周期相比的收益表示结果超出已观察种子择优；单次预算实验不能独立证明具体搜索操作的因果贡献。", "",
        table(["Q", "核", "种子比较配对", "三个种子标签均合法", "有缺失/非法种子"],
            [(g["question"], g["cores"], *(g["best_vs_evaluated_legal_seeds"][key] for key in ("paired", "pairs_with_all_three_seed_labels_legal", "pairs_with_missing_or_illegal_seed_labels"))) for g in groups]),
        "", "## 固定同方案 Cache 收益", "", "只使用 analysis 中已经完成同方案证据的 best.same_plan_cache_ratio，即固定 best_plan 的 Q2 无 Cache / Q3 有 Cache。没有将分别优化的 Q2、Q3 最好值相除。", "",
        table(["核", "完成回放/计划", "比值 > 1", "= 1", "< 1", "周期比几何均值", "配对中 partial", "有效字节命中率数", "字节命中率均值"],
            [(g["cores"], f"{g['same_plan_cache']['completed_evidence']}/{g['planned']}", *(g["same_plan_cache"][key] for key in ("ratio_above_one", "ratio_equal_one", "ratio_below_one", "geomean_q2_no_cache_over_q3_cache", "partial_jobs_with_complete_pair", "hit_byte_rate_count", "hit_byte_rate_unweighted_mean"))) for g in groups if g["question"] == 3]),
        "", "命中字节率为每个合法 best 的官方字节比例，表中均值是逐作业等权平均，包含有合法 Q3 但回放未完成者；它不是各作业字节合并后的总命中率。逐作业命中率、回放缺失与来源见 performance_summary.json。",
        "", "## 耗时口径", "", "每个逻辑 job 只计一次。solve_seconds 是整次求解时间，未记录任何 variant 的独立求解时间。休眠污染作业从全部耗时聚合排除，保留在下表；只有 checkpoint 的秒数也不作为最终求解总时间。官方调用合计包含已记录的成功、失败和超时调用，各调用只计一次。并行作业秒数之和不是墙钟耗时。", "",
        table(["机器", "逻辑作业", "继承作业", "完整 solve 计时数", "solve 秒合计", "solve 秒中位数", "有效官方计时次数", "官方秒合计", "官方超时调用"],
            [(t["machine"], t["logical_jobs"], t["retained_jobs"], t["finalized_solve_time_count"], t["finalized_solve_seconds_sum"], t["finalized_solve_seconds_median"], t["clean_calls_with_seconds"], t["clean_official_seconds_sum"], t["clean_official_timeout_calls"]) for t in summary["timing_by_machine"]]),
        "", table(["排除/单列作业", "原因", "记录 solve 秒", "记录官方秒合计"],
            [(row["job_id"], "休眠污染" if row["timing_affected_by_interruption"] else "仅 checkpoint", row["solve_seconds"], row["official_seconds_sum"]) for row in summary["timing_per_job"] if row["timing_affected_by_interruption"] or row["solve_is_checkpoint"]]),
        "", f"当前目录监督器 run_status：`{json.dumps(summary['current_run_supervisor_status'], ensure_ascii=False)}`。续跑目录的该墙钟值只属于续跑窗口，不能用它替代继承作业原运行耗时。",
        "", "## 判断边界", "", summary["old_paper_comparison"],
        "", "实测事实来自已保存官方评估和 analysis 的证据核对；比例、几何均值和胜平负是这些实测值的统计派生量。本报告没有用代理分数替代官方周期，不输出最优性认证，也不将未完成作业视作胜利。",
        "", f"读取警告 {len(summary['warnings'])} 项、重复 analysis 键 {len(summary['duplicate_analysis_keys'])} 项，详情保留在 JSON。", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path)
    args = parser.parse_args()
    run = args.run_directory
    if not run.exists():
        run = PACKAGE / run
    run = run.resolve()
    if not run.is_dir() or not run.is_relative_to((PACKAGE / "runs").resolve()):
        parser.error("Choose an existing run under this package runs/")
    if not (run / "run_status.json").is_file():
        parser.error("Run has not ended: run_status.json is required")
    if not (run / "analysis.json").is_file():
        parser.error("Generate final analysis.json for this run first")
    if (run / "analysis.json").stat().st_mtime < (run / "run_status.json").stat().st_mtime:
        parser.error("analysis.json predates the final run_status; regenerate the final analysis first")
    summary = build(run)
    (run / "performance_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (run / "PERFORMANCE.md").write_text(markdown(summary), encoding="utf-8")
    print(json.dumps({"run_directory": str(run), "groups": len(summary["groups"]),
                      "logical_jobs": len(summary["timing_per_job"]), "warnings": len(summary["warnings"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
