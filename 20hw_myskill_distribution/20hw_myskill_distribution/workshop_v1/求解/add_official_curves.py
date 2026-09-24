"""Add the three curve obligations explicitly stated in the official problem."""

from __future__ import annotations

import copy
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "求解/视觉计划.json"
REFS_PATH = ROOT / "求解/视觉计划.assets.json"


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def data_fields(fid):
    with (ROOT / f"求解/图件数据/{fid}.csv").open(encoding="utf-8-sig", newline="") as stream:
        return next(csv.reader(stream))


def main():
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    refs = json.loads(REFS_PATH.read_text(encoding="utf-8"))
    by_q = {p["problem_id"]: p for p in plan["problems"]}
    q1 = next(f for f in by_q["q1"]["figures"] if f["figure_id"] == "q1-F02")
    p = q1["panels"][0]
    p.update(figure_type="line", chart_type="line", chart_families=["line"],
             asset_directory=".agents/skills/academic-figure-skill/assets/figures/LineTrend",
             asset_mode="visual_adapt")
    q1["paper"]["caption"] = "问题一1至5核平均加速比与案例分位范围"
    for qid, source_id, new_id, question, caption, evidence_id, fields, units in [
        ("q2", "q2-F05", "q2-F06", "场景B从1核至5核的平均加速比如何变化？",
         "问题二1至5核平均加速比", "q2-E02", data_fields("q2-F06"), ["类别", "核", "倍"]),
        ("q3", "q3-F05", "q3-F06", "固定同一方案时，无L2与有L2的1至5核平均加速比曲线如何比较？",
         "同方案无L2与有L2的核数比较", "q3-E02", data_fields("q3-F06"), ["类别", "核", "倍", "倍"]),
    ]:
        source = next(f for f in by_q[qid]["figures"] if f["figure_id"] == source_id)
        figure = copy.deepcopy(source)
        figure.update(figure_id=new_id, scientific_question=question,
                      evidence_ids=[evidence_id], status="planned",
                      outputs={"vector": f"求解/正式图件/{new_id}.pdf",
                               "preview": f"求解/正式图件/{new_id}.png"},
                      statistics_report=f"求解/正式图件/{new_id}.stats.json",
                      qa_report=f"求解/正式图件/{new_id}.qa.json")
        figure.pop("selection", None)
        figure["paper"].update(caption=caption, label=f"fig:{qid}-f06")
        panel = figure["panels"][0]
        panel.update(question=question, figure_type="line", figure_family="trend_scan",
                     chart_type="line", chart_families=["line"], fields=fields, units=units,
                     result_file=f"求解/图件数据/{new_id}.csv",
                     asset_directory=".agents/skills/academic-figure-skill/assets/figures/LineTrend",
                     asset_mode="visual_adapt",
                     visual_encoding="横轴为1至5核，纵轴为100例逐例加速比平均。")
        panel.pop("selected_candidate_id", None)
        panel.pop("omitted_chart_families", None)
        by_q[qid]["figures"].append(figure)
        next(e for e in by_q[qid]["evidence_matrix"] if e["evidence_id"] == evidence_id)["figure_ids"].append(new_id)
        reference = copy.deepcopy(next(r for r in refs["figures"] if r["figure_id"] == source_id))
        reference.update(figure_id=new_id, scientific_question=question,
                         intended_layout=figure["layout"],
                         final_pdf_path=figure["outputs"]["vector"],
                         final_png_path=figure["outputs"]["preview"],
                         final_svg_path="", statistics_report_path=figure["statistics_report"],
                         visual_qa_path=figure["qa_report"], status="incomplete",
                         run_record_path=f"求解/正式图件/运行记录/{new_id}.run.json")
        reference["panel_plan"][0].update(scientific_question=question, data_schema={
            "fields": fields, "units": units, "shape": "500个正式算例—核数组合", "groups": [qid]})
        refs["figures"].append(reference)
    write(PLAN_PATH, plan)
    write(REFS_PATH, refs)
    print(json.dumps({"status": "official_curves_registered", "figures": sum(len(p["figures"]) for p in plan["problems"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
