"""离线回归测试；外网检索只用协议替身，真实编译按环境能力执行。"""
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from huaweicup_agent.core import initialize, digest, save, validate_sources
from huaweicup_agent.audit import audit, freeze
from huaweicup_agent.research import search_crossref, add_source, eligible_sources
from huaweicup_agent.publication import metric_rows, tex, compile_tex
from huaweicup_agent.workflow import task_prompt, log_ai
from huaweicup_agent.visuals import plot_csv
from huaweicup_agent.demo import run_demo


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = initialize(Path(self.tmp.name) / "work")
        self.ws.seal()

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_overwrite(self):
        with self.assertRaises(ValueError):
            initialize(self.ws.root)

    def test_bad_mode(self):
        with self.assertRaises(ValueError):
            initialize(Path(self.tmp.name) / "another", "other")

    def test_path_traversal(self):
        for name in ("../x", "/tmp/x", "C:\\x", "inputs/../../x", ""):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.ws.path(name)

    def test_symlink(self):
        (self.ws.root / "inputs" / "escape").symlink_to(self.tmp.name)
        with self.assertRaises(ValueError):
            self.ws.path("inputs/escape/x")

    def test_input_edit(self):
        self.ws.path("problem.md").write_text("changed")
        self.assertTrue(self.ws.input_errors())

    def test_input_add(self):
        self.ws.path("inputs/new.csv").write_text("x\n1")
        self.assertTrue(self.ws.input_errors())

    def test_transitive_staleness(self):
        for name, dependencies in (("results/a.txt", ["problem.md"]),
                                   ("paper/b.tex", ["results/a.txt"])):
            self.ws.path(name).write_text("original")
            self.ws.record(name, dependencies)
        self.ws.path("results/a.txt").write_text("changed")
        self.assertTrue(any("paper/b.tex" in e for e in self.ws.artifact_errors()))

    def test_cycles(self):
        for name in ("notes/a", "notes/b"):
            self.ws.path(name).write_text("x")
        self.ws.record("notes/a", ["notes/b"])
        self.ws.record("notes/b", ["notes/a"])
        self.assertTrue(any("循环" in e for e in self.ws.artifact_errors()))

    def test_require_fresh_ignores_unrelated_output(self):
        for name in ("notes/a", "notes/b"):
            self.ws.path(name).write_text("x")
            self.ws.record(name, ["problem.md"])
        self.ws.path("notes/b").write_text("stale")
        self.ws.require_fresh(["notes/a"])
        self.assertTrue(self.ws.artifact_errors())

    def test_atomic_nan_rejection(self):
        path = self.ws.path("notes/value.json")
        save(path, {"value": 1})
        with self.assertRaises(ValueError):
            save(path, {"value": float("nan")})
        self.assertEqual(self.ws.read("notes/value.json"), {"value": 1})

    def test_metadata_is_not_read(self):
        source = {"id": "s1", "title": "candidate", "url": "https://example.org",
                  "read_status": "metadata", "verified_by": "", "kind": "paper"}
        add_source(self.ws, source)
        self.assertFalse(eligible_sources(self.ws))
        with self.assertRaises(ValueError):
            add_source(self.ws, source)

    def test_reading_requires_locator(self):
        source = {"id": "s", "title": "paper", "url": "https://example.org",
                  "read_status": "fulltext"}
        self.assertTrue(validate_sources([source]))

    def test_source_id_cannot_inject_tex(self):
        self.assertTrue(validate_sources([{"id": "x}\\input{evil", "title": "x",
                                          "url": "https://example.org", "read_status": "metadata"}]))

    def test_crossref_protocol(self):
        payload = {"message": {"items": [{"title": ["Example"], "DOI": "10.1/test",
                                         "URL": "https://doi.org/10.1/test"}]}}
        def opener(request, timeout):
            self.assertTrue(request.full_url.startswith("https://api.crossref.org/works?"))
            self.assertEqual(timeout, 20)
            return io.BytesIO(json.dumps(payload).encode())
        result = search_crossref("a query", opener=opener)
        self.assertEqual(result[0]["read_status"], "metadata")
        self.assertFalse(result[0]["verified_by"])

    def test_crossref_limits(self):
        with self.assertRaises(ValueError):
            search_crossref("", 100)

    def test_prompt_is_not_execution(self):
        text = task_prompt(self.ws, "modeler")
        self.assertIn("至少三种候选", text)
        self.assertEqual(self.ws.read("artifacts.json"), {})

    def test_log_ai_binds_output(self):
        task_prompt(self.ws, "writer")
        log_ai(self.ws, "host", "configured-model", "drafting", ["tasks/writer.md"])
        record = self.ws.read("ai_usage.json")[0]
        self.assertEqual(record["output_sha256"]["tasks/writer.md"], digest(self.ws.path("tasks/writer.md")))
        self.assertEqual(record["human_review"], "pending")

    def test_tex_escaping(self):
        self.assertEqual(tex("x_1 & 5%"), r"x\_1 \& 5\%")
        self.assertNotIn(r"\input{", tex(r"\input{secret}"))

    def make_metrics(self):
        self.ws.write("results/metrics.json", {"metric": "RMSE", "direction": "min", "rows": [
            {"model": "m", "seed": 1, "split": "test", "n": 4, "sse": 16, "rmse": 2}]})

    def test_metric_recomputation(self):
        self.make_metrics()
        self.assertEqual(metric_rows(self.ws)[0]["rmse"], 2)
        value = self.ws.read("results/metrics.json")
        value["rows"][0]["rmse"] = 0.01
        self.ws.write("results/metrics.json", value)
        with self.assertRaises(ValueError):
            metric_rows(self.ws)

    def test_metric_duplicate(self):
        self.make_metrics()
        value = self.ws.read("results/metrics.json")
        value["rows"] *= 2
        self.ws.write("results/metrics.json", value)
        with self.assertRaises(ValueError):
            metric_rows(self.ws)

    def test_final_gate_closed(self):
        report = audit(self.ws, final=True)
        self.assertFalse(report["ok"])
        self.assertTrue(any("规则" in e for e in report["errors"]))

    def test_compile_requires_explicit_trust(self):
        with self.assertRaises(ValueError):
            compile_tex(self.ws, "paper/a.tex")

    def plot_fixture(self, kind="scatter", data="x,y\n1,2\n2,3\n"):
        self.ws.path("inputs/data.csv").write_text(data)
        self.ws.seal()
        self.ws.write("notes/plot.json", {"data": "inputs/data.csv", "kind": kind,
                      "name": "fixture", "x": "x", "y": "y", "xlabel": "x (s)", "ylabel": "y (m)"})

    def test_plot_real_csv(self):
        self.plot_fixture()
        result = plot_csv(self.ws, "notes/plot.json")
        self.assertEqual(len(result), 2)
        self.assertTrue(audit(self.ws)["ok"])

    def test_plot_unordered_line_rejected(self):
        self.plot_fixture("line", "x,y\n2,2\n1,3\n")
        with self.assertRaises(ValueError):
            plot_csv(self.ws, "notes/plot.json")

    def test_plot_nan_rejected(self):
        self.plot_fixture("scatter", "x,y\n1,nan\n")
        with self.assertRaises(ValueError):
            plot_csv(self.ws, "notes/plot.json")

    @unittest.skipUnless(shutil.which("xelatex") and shutil.which("bibtex"), "TeX toolchain absent")
    def test_real_bibtex_and_recorder(self):
        self.ws.path("paper/refs.bib").write_text("@misc{fixture,title={Unit test fixture}}\n")
        self.ws.path("paper/custom.tex").write_text(r"""\documentclass{article}
\begin{document}Test citation \cite{fixture}.
\bibliographystyle{plain}\bibliography{paper/refs}\end{document}
""")
        self.ws.record("paper/custom.tex", ["paper/refs.bib"])
        output = compile_tex(self.ws, "paper/custom.tex", trusted=True)
        self.assertTrue(self.ws.path(output).is_file())
        self.assertIn("paper/refs.bib", self.ws.read("artifacts.json")[output]["dependencies"])


class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.ws = run_demo(str(Path(cls.tmp.name) / "demo"), compile_pdf=bool(shutil.which("xelatex")))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_real_experiment(self):
        self.assertEqual(len(metric_rows(self.ws)), 20)
        self.assertTrue(audit(self.ws)["ok"])

    def test_reproducible_experiment(self):
        subprocess.run([sys.executable, "code/experiment.py", "inputs/synthetic.csv", "results/repeated.json"],
                       cwd=self.ws.root, check=True, capture_output=True, timeout=30)
        self.assertEqual(digest(self.ws.path("results/metrics.json")), digest(self.ws.path("results/repeated.json")))

    def test_not_competition_ready(self):
        self.assertFalse(audit(self.ws, final=True)["ok"])

    @unittest.skipUnless(shutil.which("xelatex"), "XeLaTeX absent")
    def test_freeze_exact_bytes_and_no_overwrite(self):
        result = freeze(self.ws, "build/draft.pdf", "DEMO.pdf", rehearsal=True)
        self.assertEqual(result["md5"], digest(self.ws.path("build/draft.pdf"), "md5"))
        self.assertEqual(result["sha256"], digest(self.ws.path("release_demo/DEMO.pdf")))
        self.assertFalse(result["uploaded"])
        with self.assertRaises(ValueError):
            freeze(self.ws, "build/draft.pdf", "DEMO.pdf", rehearsal=True)


if __name__ == "__main__":
    unittest.main()
