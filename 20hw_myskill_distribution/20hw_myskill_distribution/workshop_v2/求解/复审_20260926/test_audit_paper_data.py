"""Regression tests, including deliberately corrupted copies of local paper tables.

Generated rows below are synthetic test data, not new competition experiments.
The integration checks read the actual workspace tables without changing them.
"""
from __future__ import annotations
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

import audit_paper_data as a

WORKSPACE = Path(__file__).resolve().parents[2]


def main_rows(q=1):
    return [dict(case=c,q=str(q),n=str(n),status="ok",makespan="100",
                 added_copy_bytes="10",spill_added_copy_bytes="0")
            for c in sorted(a.CASES) for n in sorted(a.CORES)]


def pair_rows():
    return [dict(case=c,n=str(n),same_plan="True",with_l2="100",without_l2="100",
                 with_l2_added_bytes="10",without_l2_added_bytes="10",hit_rate="0",cache_speedup="1")
            for c in sorted(a.CASES) for n in sorted(a.CORES)]


class ScalarTests(unittest.TestCase):
    def test_missing_is_not_zero(self):
        for value in (None,""," "):
            with self.subTest(value=value), self.assertRaises(a.AuditError):
                a.number(value)

    def test_nonfinite_and_negative_rejected(self):
        for value in ("NaN","Infinity","-Infinity","-1","1e10000"):
            with self.subTest(value=value), self.assertRaises(a.AuditError):
                a.number(value)

    def test_cycle_zero_rejected(self):
        with self.assertRaises(a.AuditError):
            a.number("0",integer=True,minimum=1)

    def test_integrality_and_precision(self):
        self.assertEqual(a.number("9007199254740993",integer=True),9007199254740993)
        self.assertEqual(a.number("3,456",integer=True),3456)
        self.assertEqual(a.number("123.0",integer=True),123)
        for value in ("1.2","12,34","1,2,3"):
            with self.subTest(value=value), self.assertRaises(a.AuditError):
                a.number(value,integer=True)

    def test_boolean_values(self):
        self.assertTrue(a.boolean("True"))
        self.assertFalse(a.boolean("false"))
        for value in (None,"","yes","1"):
            with self.subTest(value=value), self.assertRaises(a.AuditError):
                a.boolean(value)


class CoverageTests(unittest.TestCase):
    def test_valid_main_grid(self):
        self.assertEqual(len(a.validate_main_csv(main_rows(),1)),500)

    def test_missing_case_core(self):
        with self.assertRaises(a.AuditError):
            a.validate_main_csv(main_rows()[1:],1)

    def test_duplicate_does_not_overwrite(self):
        rows=main_rows(); rows[-1]=dict(rows[0])
        with self.assertRaises(a.AuditError):
            a.validate_main_csv(rows,1)

    def test_wrong_question_or_status(self):
        for key,value in (("q","2"),("status","failed"),("n","6")):
            rows=main_rows(); rows[0][key]=value
            with self.subTest(key=key),self.assertRaises(a.AuditError):
                a.validate_main_csv(rows,1)

    def test_missing_spill_not_zero(self):
        rows=main_rows(); rows[0]["spill_added_copy_bytes"]=""
        with self.assertRaises(a.AuditError):
            a.validate_main_csv(rows,1)

    def test_spill_exceeds_copy(self):
        rows=main_rows();rows[0]["spill_added_copy_bytes"]="11"
        with self.assertRaises(a.AuditError):
            a.validate_main_csv(rows,1)

    def test_pair_flag_required(self):
        for flag in ("False","unknown",""):
            rows=pair_rows(); rows[0]["same_plan"]=flag
            with self.subTest(flag=flag),self.assertRaises(a.AuditError):
                a.validate_pairs_csv(rows)

    def test_pair_ratio_checked(self):
        rows=pair_rows();rows[0]["cache_speedup"]="1.1"
        with self.assertRaises(a.AuditError):
            a.validate_pairs_csv(rows)

    def test_pair_coverage_and_hit_bounds(self):
        rows=pair_rows()
        self.assertEqual(len(a.validate_pairs_csv(rows)),500)
        for changed in (rows[:-1],rows+[dict(rows[0])]):
            with self.assertRaises(a.AuditError):a.validate_pairs_csv(changed)
        rows[0]["hit_rate"]="1.01"
        with self.assertRaises(a.AuditError):a.validate_pairs_csv(rows)

    def test_unknown_study_mode(self):
        with self.assertRaisesRegex(a.AuditError,"Unknown grid mode"):
            a.check_grid([dict(mode="misspelled_mode")],{})

    def test_anytime_count_is_computed(self):
        rows=[dict(case=c,q="1",n="5",seconds="30",has_solution=str(i<92))
              for i,c in enumerate(sorted(a.CASES))]
        self.assertEqual(a.check_anytime(rows)["has_solution"],92)
        with self.assertRaises(a.AuditError):a.check_anytime(rows[:-1])
        with self.assertRaises(a.AuditError):a.check_anytime(rows+[dict(rows[0])])

    def test_anytime_includes_q0_reference(self):
        rows=[dict(case=c,q="1",n="5",seconds="30",has_solution="True")
              for c in sorted(a.CASES)]
        rows += [dict(case="case_001",q="0",n="1",seconds="30",has_solution="True")]
        self.assertEqual(a.check_anytime(rows)["rows"],100)
        rows[-1]["n"]="2"
        with self.assertRaises(a.AuditError):a.check_anytime(rows)

    def test_report_uses_computed_comparisons(self):
        main={}
        for q in (1,2,3):main.update(a.validate_main_csv(main_rows(q),q))
        pairs=a.validate_pairs_csv(pair_rows())
        pairs["case_001",5]["without_l2"]=110
        result=a.compute(main,pairs)
        self.assertEqual(result["cache_stats"]["5"]["improved"],1)
        self.assertEqual(result["cache_stats"]["5"]["same"],99)
        result.update(status="PASS_SCOPED",mode="synthetic_test",limitations=[],summary_rows_checked=0,spill_n5={})
        self.assertIn('"improved": 1',a.markdown(result))
        self.assertNotIn("77",a.markdown(result))


class WorkspaceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.workspace=self.root/"workspace"
        for relative in ("论文/章节内容/数据表","求解/规范化数据/combined"):
            source=WORKSPACE/relative
            if not source.is_dir():
                self.skipTest(f"Workspace data missing: {source}")
            self.workspace.joinpath(relative).mkdir(parents=True,exist_ok=True)
        for source in (WORKSPACE/"论文/章节内容/数据表").glob("*.tex"):
            shutil.copy2(source,self.workspace/"论文/章节内容/数据表"/source.name)
        shutil.copy2(WORKSPACE/"求解/规范化数据/combined/cross_question.csv",
                     self.workspace/"求解/规范化数据/combined/cross_question.csv")

    def tearDown(self):self.tmp.cleanup()

    def test_actual_published_tables(self):
        result=a.audit(self.workspace,"tables")
        self.assertEqual(result["displayed_configurations"],1500)
        self.assertEqual(result["displayed_cache_pairs"],500)
        self.assertEqual(result["summary_rows_checked"],20)

    def test_corrupt_summary_fails(self):
        path=self.workspace/"论文/章节内容/数据表/q1_means.tex"
        text=path.read_text(); path.write_text(text.replace("3.9180","3.0000",1))
        with self.assertRaises(a.AuditError):a.audit(self.workspace,"tables")

    def test_missing_main_row_fails(self):
        path=self.workspace/"论文/章节内容/数据表/appendix_results.tex"
        text=path.read_text();lines=text.splitlines();idx=next(i for i,s in enumerate(lines) if s.startswith("001 &"))
        path.write_text("\n".join(lines[:idx]+lines[idx+1:]))
        with self.assertRaises(a.AuditError):a.audit(self.workspace,"tables")

    def test_duplicate_pair_fails(self):
        path=self.workspace/"论文/章节内容/数据表/appendix_pairs.tex"
        text=path.read_text();row=next(s for s in text.splitlines() if s.startswith("001 & 1 &"))
        path.write_text(text.replace(row,row+"\n"+row,1))
        with self.assertRaises(a.AuditError):a.audit(self.workspace,"tables")

    def test_cross_file_mismatch_fails(self):
        path=self.workspace/"求解/规范化数据/combined/cross_question.csv"
        text=path.read_text(encoding="utf-8-sig");path.write_text(text.replace("case_001,47502","case_001,47503",1))
        with self.assertRaises(a.AuditError):a.audit(self.workspace,"tables")

    def test_failed_run_replaces_stale_report(self):
        out=self.root/"output";out.mkdir()
        (out/"report.md").write_text("STALE PASS")
        code=a.main(["--workspace",str(self.workspace),"--mode","csv","--output-dir",str(out)])
        self.assertEqual(code,2)
        result=json.loads((out/"result.json").read_text())
        self.assertEqual(result["status"],"FAIL")
        self.assertNotIn("STALE PASS",(out/"report.md").read_text())
        self.assertNotIn("正文上述待核数字均与记录一致",(out/"report.md").read_text())

    def test_import_has_no_writes(self):
        target=Path(a.__file__)
        before=set(self.workspace.rglob("*"))
        spec=importlib.util.spec_from_file_location("_review_import_test",target)
        module=importlib.util.module_from_spec(spec)
        cwd=Path.cwd()
        try:
            os.chdir(self.workspace)
            spec.loader.exec_module(module)
        finally:
            os.chdir(cwd)
        self.assertEqual(before,set(self.workspace.rglob("*")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
