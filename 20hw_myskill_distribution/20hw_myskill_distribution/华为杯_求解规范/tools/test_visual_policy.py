"""Regression coverage for figure counts and non-graphical validation evidence."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from audit_visual_plan import audit, REQUIRED_CATEGORIES, body_tex
from figure_accounting import audit_counts
from test_figure_accounting import fixture as count_fixture


def fixture():
    problems = []
    for number in range(4):
        pid = f"q{number}"
        figures = []
        for index in range(4):
            fid = f"{pid}_f{index}"
            figures.append({"figure_id": fid, "scope": pid, "scientific_question": "Independent policy fixture " + fid,
                "script": fid + '.py', "statistics_report": fid + '.stats.json', "qa_report": fid + '.qa.json',
                "status": "planned", "claim_ids": [pid], "evidence_ids": [pid + '_main_result'],
                "archetype": "quantitative_grid", "layout": "1x1", "hero_panel": None,
                "panels": [{"panel_id": "a", "figure_family": "comparison_ranking", "result_file": "result.csv",
                    "question": "Metric comparison fixture", "figure_type": "dotplot", "fields": ["value"], "units": ["1"],
                    "visual_encoding": "position", "asset_directory": "test-assets", "asset_mode": "visual_adapt"}],
                "outputs": {"vector": f"{fid}.pdf", "preview": f"{fid}.png"},
                "paper": {"chapter": pid, "label": f"fig:{fid}", "caption": fid, "reference_context": "正文结果"}})
        evidence = [{"evidence_id": f"{pid}_{kind}", "question": "Which evidence validates this claim?", "category": kind, "applicability": "applicable",
                     "data_shape": "single_value", "representation": "table", "result_files": ["proof.tex"],
                     "figure_ids": [], "reason": "通过独立重算检验结果，并保留可复核证据"} for kind in sorted(REQUIRED_CATEGORIES)]
        problems.append({"problem_id": pid, "complexity": "complex", "figures": figures, "schematics": [], "low_figure_exception": None,
                         "claims": [{"claim_id": pid, "text": "具有独立结果的科学问题"}], "evidence_matrix": evidence})
    return {"schema_version": "1.0", "project_title": "test", "plan_status": "ready", "visual_encoding_path": "encoding.md",
            "problems": problems, "global_figures": [], "flowcharts": []}


class VisualPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = fixture()

    def check(self, stage="plan", main_tex=None):
        path = self.root / "plan.json"
        path.write_text(json.dumps(self.plan), encoding="utf-8")
        # Isolate evidence/quotas from asset and diagram-render QA. Counts are
        # still derived by the production counter from the mutated input, not
        # supplied as canned numbers. This is not scientific completion evidence.
        _, side = count_fixture()
        import re
        side = json.loads(re.sub(r'q([1-4])', lambda m: 'q'+str(int(m[1])-1), json.dumps(side)))
        side['figure_accounting'] = [r for r in side['figure_accounting'] if r['purpose'] != 'independent_science']
        for problem in self.plan['problems']:
            for figure in problem['figures']:
                side['figure_accounting'].append({'figure_id':figure['figure_id'],'purpose':'independent_science',
                    'problem_id':problem['problem_id'],'per_question':True,'paper_total':True,'flow_total':False,
                    'scientific_contribution':'隔离政策测试的不同证据 '+figure['figure_id']+'，不代表真实结果'})
        counts = audit_counts(self.plan, side, 'plan', self.root)
        diagram_response={'status':counts['status'],'failures':counts['failures'],'figure_accounting':counts}
        with patch("audit_academic_figure_assets.audit_assets", return_value={"status": "PASS", "failures": [], "assurance": {}}), \
             patch('audit_diagram_workflow.audit', return_value=diagram_response):
            return audit(path, stage, self.root, main_tex, runtime="codex")

    def test_four_per_question_and_sixteen_total_pass_with_tables(self):
        result = self.check()
        self.assertEqual(result["status"], "PASS", result["failures"])

    def test_under_and_over_counts_fail_even_with_legacy_exception(self):
        self.plan["problems"][0]["figures"].pop()
        self.plan["problems"][0]["low_figure_exception"] = "合理理由" * 20
        codes = {x["code"] for x in self.check()["failures"]}
        self.assertIn("q0:figure_count_range", codes)
        # Fifteen question-owned figures plus the global roadmap still reach
        # sixteen, while the deficient question independently fails its quota.
        self.assertNotIn("paper_figure_minimum", codes)
        self.plan["problems"][0]["figures"].pop()
        self.assertIn("paper_figure_minimum", {x["code"] for x in self.check()["failures"]})
        self.plan = fixture()
        self.plan["problems"][0]["figures"] += copy.deepcopy(self.plan["problems"][0]["figures"][:3])
        self.assertIn("q0:figure_count_range", {x["code"] for x in self.check()["failures"]})

    def test_duplicate_label_fails(self):
        self.plan["problems"][0]["figures"][0]["paper"]["label"] = "fig:q1_f0"
        self.assertIn("visual_labels_unique", {x["code"] for x in self.check()["failures"]})

    def test_unavailable_truth_needs_reason_and_alternative(self):
        problem = self.plan["problems"][0]
        item = next(e for e in problem["evidence_matrix"] if e["category"] == "independent_validation")
        item.update(applicability="not_possible", representation="na", result_files=[], reason="目标样本没有真实标签，不能报告准确率；只分析可核验的适用边界")
        self.assertIn("q0:validation_has_evidence", {x["code"] for x in self.check()["failures"]})
        alternate = copy.deepcopy(next(e for e in problem["evidence_matrix"] if e["category"] == "main_result"))
        alternate.update(evidence_id="q0_boundary", category="theoretical_boundary")
        problem["evidence_matrix"].append(alternate)
        result = self.check()
        self.assertEqual(result["status"], "PASS", result["failures"])

    def test_nonvisual_evidence_must_exist_at_render(self):
        codes = {x["code"] for x in self.check("render")["failures"]}
        self.assertIn("q0:q0_independent_validation:evidence_files_exist", codes)
        (self.root / "proof.tex").write_text("independent calculation", encoding="utf-8")
        codes = {x["code"] for x in self.check("render")["failures"]}
        self.assertNotIn("q0:q0_independent_validation:evidence_files_exist", codes)

    def test_panels_cannot_count_as_individual_figures(self):
        main = self.root / "main.tex"
        main.write_text(r"\begin{figure}\includegraphics{a.pdf}\caption{one figure}\label{fig:q0_f0}\label{fig:q0_f1}\end{figure}", encoding="utf-8")
        codes = {x["code"] for x in self.check("paper", main)["failures"]}
        self.assertIn("one_planned_figure_per_environment", codes)
        self.assertIn("planned_visuals_are_numbered_figures", codes)

    def test_body_expands_in_order_and_excludes_appendix(self):
        main = self.root / "main.tex"
        (self.root / "q.tex").write_text("body-figure", encoding="utf-8")
        (self.root / "appendix.tex").write_text(r"\appendix appendix-figure", encoding="utf-8")
        main.write_text(r"\begin{document}abstract\maketoc\input{q}\input{q}\input{appendix}\end{document}", encoding="utf-8")
        text = body_tex(main)
        self.assertEqual(text.count("body-figure"), 2)
        self.assertNotIn("appendix-figure", text)
        self.assertNotIn("abstract", text)


if __name__ == "__main__":
    unittest.main()
