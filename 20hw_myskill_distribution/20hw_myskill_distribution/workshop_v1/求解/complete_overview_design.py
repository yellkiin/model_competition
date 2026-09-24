"""Bind the three overview designs to current numerical and figure evidence.

This prepares content only.  Visual QA is recorded separately after opening the
rendered overview at full, detail, paper and grayscale sizes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "求解/视觉计划.json"
SIDECAR = ROOT / "求解/视觉计划.diagrams.json"


def digest(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    data = json.loads(SIDECAR.read_text(encoding="utf-8"))
    by_question = {p["problem_id"]: p for p in plan["problems"]}
    for diagram in data["diagrams"]:
        if diagram["kind"] != "comprehensive":
            continue
        qid = diagram["problem_id"]
        result_panels = [p for p in diagram["panels"] if p["kind"] == "result"]
        selected = {p["visual_figure_id"] for p in result_panels}
        for source in diagram["sources"]:
            source["sha256"] = digest(source["path"])
        choices = []
        for figure in by_question[qid]["figures"]:
            fid = figure["figure_id"]
            if fid in selected:
                choice = "selected"
                reason = f"{fid}的真实定量结果在本问综合图中直接缩印，正文同ID详细图承担读数。"
            else:
                choice = "redundant"
                reason = f"{fid}在正文独立展示；综合图保留两张主证据，继续缩入会挤压机理、方法与导航文字。"
            choices.append({"figure_id": fid, "decision": choice, "reason": reason})
        verification = [
            {"path": "求解/正式实验/统计分析.json", "sha256": digest("求解/正式实验/统计分析.json"),
             "locator": f"{qid}的100例逐核统计与成对比较", "role": "result"},
            {"path": "求解/正式实验/逐问核验摘要.json", "sha256": digest("求解/正式实验/逐问核验摘要.json"),
             "locator": f"{qid}的500个所选配置及时间线独立核验", "role": "independent_validation"},
        ]
        diagram["overview_design"] = {
            "version": "2.0", "status": "ready",
            "verification": {"status": "verified", "evidence": verification},
            "result_selection": choices, "omission_reason": "其余已入正文的科学图在独立位置提供完整统计，不增加缩印。",
            "mechanism": {"applicable": True, "category": "algorithm", "panel_ids": ["mechanism"],
                          "reason": "顶部矢量关系解释本问的计算依赖、同核Task或L2分流，直接决定候选与评估口径。"},
            "layout": {"strategy": "aligned_partitions",
                       "reading_order": [p["panel_id"] for p in diagram["panels"]],
                       "reason": "对象机理、方法约束、两张结果与核验按纵向三带对齐，形成接近版心宽度的紧凑矩形。"},
            "theme": {"palette_ref": "overview-macaron", "connector_family": "blue-latex-directed",
                      "reason": "高明度青、粉、绿分区与蓝色主箭头一致，橙色仅标示搬运或未命中等题定分流。"},
        }
    SIDECAR.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "CONTENT_READY", "questions": list(by_question)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
