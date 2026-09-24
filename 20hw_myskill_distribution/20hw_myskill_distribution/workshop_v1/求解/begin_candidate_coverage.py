"""Open the current visual-validation stages without backfilling earlier stages."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT.parent / "华为杯_求解规范/tools"
sys.path.insert(0, str(SHARED))
from candidate_figures import load, open_stage, snapshot  # noqa: E402

REGISTRY = ROOT / "求解/候选图清单.json"


def main() -> None:
    registry = load(REGISTRY)
    if registry["stages"] or registry["candidates"]:
        raise RuntimeError("Candidate stages already exist; preserve their real event history")
    for q in registry["questions"]:
        qid = q["question_id"]
        types = ["调度与网络", "组合优化", "事件仿真评价"]
        if qid == "q3":
            types.append("参数敏感性")
        q["problem_types"] = types
        q["type_reason"] = f"{qid}要构造合法多核方案并以官方事件模拟衡量完成时间；统计图需同时检视解结构、比较与失败边界。"
        q["type_reviews"] = [{
            "problem_type": kind,
            "risk_review": {
                "调度与网络": "核序列及前驱关系可能造成等待和局部瓶颈，必须对照合法性与全局时间线。",
                "组合优化": "有限候选族可能遗漏更优切图，须同时呈现选择频数、代价权衡和最优性边界。",
                "事件仿真评价": "搬运、缓存和计算管线可重叠，不能以单一代理量代替官方完工周期。",
                "参数敏感性": "L2容量与带宽网格只覆盖六个目的抽样算例，必须与官方默认配置分开。",
            }[kind],
            "evidence": snapshot(ROOT, ["求解/题面约束清单.md", "求解/正式实验/统计分析.json"]),
        } for kind in types]
        sid = f"{qid}_current_figure_validation"
        q["expected_stages"] = [sid]
        open_stage(ROOT, registry, qid, sid, "validation", [
            "求解/正式实验/统计分析.json", "求解/正式实验/逐问核验摘要.json",
            f"求解/图件数据/{qid}-F02.csv",
        ])
    REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "STAGES_STARTED", "stage_ids": [s["stage_id"] for s in registry["stages"]]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
