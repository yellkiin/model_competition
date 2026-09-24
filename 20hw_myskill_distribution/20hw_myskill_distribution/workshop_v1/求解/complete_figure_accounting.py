"""Declare the distinct contribution and derived count of every current body figure."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "求解/视觉计划.json"
SIDECAR = ROOT / "求解/视觉计划.diagrams.json"


def main() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    diagrams = json.loads(SIDECAR.read_text(encoding="utf-8"))
    rows = []
    for problem in plan["problems"]:
        qid = problem["problem_id"]
        for f in problem["figures"]:
            rows.append({
                "figure_id": f["figure_id"], "problem_id": qid,
                "purpose": "independent_science", "per_question": True,
                "paper_total": True, "flow_total": False,
                "scientific_contribution": "用当前实测数据回答：" + f["scientific_question"],
            })
    for d in diagrams["diagrams"]:
        if d["diagram_id"] == "GLOBAL-ROADMAP":
            purpose, per_question, paper_total = "global_roadmap", False, True
        elif d["kind"] == "comprehensive":
            purpose, per_question, paper_total = "question_overview", False, False
        else:
            raise RuntimeError(f"Unmapped current diagram: {d['diagram_id']}")
        existing = next((r for r in diagrams.get("figure_accounting", [])
                         if r["figure_id"] == d["diagram_id"]), {})
        rows.append({
            "figure_id": d["diagram_id"], "problem_id": d.get("problem_id"),
            "purpose": purpose, "per_question": per_question,
            "paper_total": paper_total, "flow_total": True,
            "scientific_contribution": existing.get("scientific_contribution") or d["scientific_question"],
        })
    diagrams["figure_accounting"] = rows
    SIDECAR.write_text(json.dumps(diagrams, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "DECLARED", "figures": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
