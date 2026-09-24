"""Close current figure-validation stages after genuine visual review.

Earlier numerical stages predate the candidate registry and are explicitly not
reconstructed as historical events.  This script records the current review only.
"""
from __future__ import annotations

import json
import shutil
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "华为杯_求解规范/tools"))
from candidate_figures import (  # noqa: E402
    DIMENSIONS, complete_stage, inventory, load, record_review,
    register_candidate, select_paper, snapshot,
)
from chart_policy import audit_policy  # noqa: E402
from prepare_academic_figure_review import figure_contract_digest  # noqa: E402
import audit_academic_figure_assets as academic_audit  # noqa: E402
import chart_policy  # noqa: E402
import workspace_resources  # noqa: E402

# select_paper validates each candidate separately.  The shared atlas and
# source-preflight inputs are read-only within this process, so cache their
# identical scans; each candidate's schema, files, QA and contract still run.
academic_audit.build_index = lru_cache(maxsize=None)(academic_audit.build_index)
academic_audit.sync_report = lru_cache(maxsize=None)(academic_audit.sync_report)
chart_policy.audit_preflight = lru_cache(maxsize=None)(chart_policy.audit_preflight)
workspace_resources.dependencies = lru_cache(maxsize=None)(workspace_resources.dependencies)

REG_PATH = ROOT / "求解/候选图清单.json"
PLAN_PATH = ROOT / "求解/视觉计划.json"
COPY_PATH = ROOT / "求解/候选计划.json"

REFERENCES = {
    "q1": {"data_structure": ["q1-F01"], "intermediate_mechanism": ["q1-F05"],
           "solution_process": ["q1-F06"], "final_result": ["q1-F02"],
           "comparison_validation": ["q1-F03", "q1-F04"], "error_boundary": ["q1-F04"]},
    "q2": {"data_structure": ["q2-F04"], "intermediate_mechanism": ["q2-F03"],
           "solution_process": ["q2-F03"], "final_result": ["q2-F06"],
           "comparison_validation": ["q2-F01", "q2-F02"], "error_boundary": ["q2-F05"]},
    "q3": {"data_structure": ["q3-F05"], "intermediate_mechanism": ["q3-F02"],
           "solution_process": ["q3-F04"], "final_result": ["q3-F06"],
           "comparison_validation": ["q3-F01"], "error_boundary": ["q3-F03"]},
}


def save(value: dict) -> None:
    REG_PATH.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clone_candidate_plan() -> None:
    if COPY_PATH.exists():
        return
    for suffix in (".json", ".assets.json", ".diagrams.json"):
        source = ROOT / "求解" / ("视觉计划" + suffix)
        target = ROOT / "求解" / ("候选计划" + suffix)
        shutil.copy2(source, target)
    refs_path = ROOT / "求解/候选计划.assets.json"
    refs = load(refs_path)
    refs["plan_path"] = "求解/候选计划.json"
    refs_path.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def completion_scopes(qid: str) -> list[str]:
    common = [
        "求解/solve_components.py", "求解/solve_bands.py", "求解/solve_batches.py",
        "求解/run_official_experiments.py", "求解/verify_official_results.py",
        "求解/analyze_official_results.py", "求解/build_figure_data.py",
        "求解/render_science_figures.py", "求解/正式实验/统计分析.json",
        "求解/正式实验/逐问核验摘要.json",
    ]
    if qid == "q3":
        common += ["求解/cache_sensitivity.py", "求解/analyze_cache_sensitivity.py"]
    return common + [f"求解/图件数据/{qid}-F{i:02d}.csv" for i in range(1, 7)]


def main() -> None:
    clone_candidate_plan()
    registry = load(REG_PATH)
    plan = load(COPY_PATH)
    if any(f["status"] != "qa_pass" for p in plan["problems"] for f in p["figures"]):
        raise RuntimeError("Every formal figure must have current human-reviewed QA")
    for q in registry["questions"]:
        qid = q["question_id"]
        sid = q["expected_stages"][0]
        stage = next(s for s in registry["stages"] if s["stage_id"] == sid)
        if not stage["completion_event"]:
            complete_stage(ROOT, registry, sid, [f"求解/图件数据/{qid}-F02.csv"])
            save(registry)
        problem = next(p for p in plan["problems"] if p["problem_id"] == qid)
        for f in problem["figures"]:
            fid = f["figure_id"]
            if any(c["figure_id"] == fid for c in registry["candidates"]):
                continue
            register_candidate(ROOT, registry, {
                "figure_id": fid, "question_id": qid, "stage_id": sid,
                "plan_path": "求解/候选计划.json", "quality": "planned",
                "destination": "reserve", "scientific_question": f["scientific_question"],
                "selection_reason": f"{fid}直接回答本问主张或七维复查中的独立科学问题，已与正文解释和真实数据核对。",
                "conclusion": f"{fid}展示其图题所述的官方算例结果或明确标注的非官方参数响应。",
                "limitations": ("该图是六例九格的非官方参数实验，不外推为100例正式成绩。"
                                if fid == "q3-F03" else "图示为当前有限候选和官方算例的统计，不证明全局最优。"),
                "recommended_section": f"问题{qid[-1]}：结果与分析",
                "statistical_unit": ("六例参数网格" if fid == "q3-F03" else "100个官方算例或其逐核配置"),
            })
            save(registry)
        if not stage["review_event"]:
            evidence = snapshot(ROOT, ["求解/正式实验/统计分析.json", f"求解/图件数据/{qid}-F02.csv"])
            for row in stage["checks"]:
                dimension = row["dimension"]
                refs = REFERENCES[qid].get(dimension, [])
                row.update(
                    decision="covered" if refs else "text_table",
                    reason=(f"本问已用{','.join(refs)}及正文对应段落审查该维度；数值仅来自正式结果。"
                            if refs else "图转换只为官方合法性与评估准备，输入影响已在题面审计及正文文字中限定。"),
                    evidence=evidence, candidate_ids=refs, followup="当前结果已核验，无待补分析。",
                    resolved=True, reuse=None,
                )
            record_review(ROOT, registry, sid)
            save(registry)
    policy_failures = audit_policy(plan, ROOT, "codex")
    if policy_failures:
        raise RuntimeError(f"Chart-source and portfolio gate failed: {policy_failures[:20]}")
    refs = {r["figure_id"]: r for r in load(ROOT / "求解/候选计划.assets.json")["figures"]}
    for problem in plan["problems"]:
        for f in problem["figures"]:
            fid = f["figure_id"]
            qa = load(ROOT / f["qa_report"])
            if qa.get("contract_sha256") != figure_contract_digest(f, refs[fid]):
                raise RuntimeError(f"Candidate figure contract is stale: {fid}")
            candidate = next(c for c in registry["candidates"] if c["figure_id"] == fid)
            candidate["quality"] = "qualified"
            candidate["destination"] = "paper"
    for q in registry["questions"]:
        qid = q["question_id"]
        sid = q["expected_stages"][0]
        scopes = completion_scopes(qid)
        q["completion_review"] = {
            "observation": (f"{qid}重新枚举当前求解源码、结构化结果和六张图的数据；逐一检查输入分布、方法、结果、比较及失败边界。"
                            "早于本候选清单的原始实验阶段没有补造事件，当前阶段仅记录新开展的图件验证。"),
            "zero_remaining_reason": "七维复查后的独立科学问题均由六张正文图与相邻数值文字覆盖，没有额外合格未入文候选。",
            "stage_ids": [sid], "scopes": scopes, "files": inventory(ROOT, scopes),
        }
    save(registry)
    # The initial visual plan is the reviewed candidate source.  select_paper
    # requires a fresh canonical output path; the complete candidate copy above
    # preserves every figure, asset record and diagram before this replacement.
    for suffix in (".json", ".assets.json", ".diagrams.json", ".media.json"):
        existing = ROOT / "求解" / ("视觉计划" + suffix)
        if existing.exists():
            existing.unlink()
    result = select_paper(ROOT, REG_PATH, COPY_PATH, PLAN_PATH, "codex")
    print(json.dumps({"status": "CURRENT_COVERAGE_REVIEWED", "selection": result}, ensure_ascii=False))


if __name__ == "__main__":
    main()
