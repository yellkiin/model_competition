"""Check policy configuration and the production front-matter sequence."""
import json
from pathlib import Path
import tempfile
import unittest

from audit_paper import body_pages
from build_latex import build_main
from audit_abstract import ABSTRACT_TYPE_TERMS
from test_paper_contract import make_fixture

PROJECT = Path(__file__).resolve().parents[2]


class WorkflowPolicyTests(unittest.TestCase):
    def test_both_real_phase_routers_load_first_chapter_contract(self):
        import re
        for runtime in ('codex', 'claude'):
            path=PROJECT/'华为杯_求解规范'/f'总控阶段_{runtime}.md'
            text=path.read_text(encoding='utf8')
            for phase in (1,4,5):
                match=re.search(r'(?m)^#{2,3} [^\n]*?Phase '+str(phase)+r'：[^\n]*\n(.*?)(?=^#{2,3} |\Z)',text,re.S|re.M)
                self.assertIsNotNone(match,(runtime,phase))
                self.assertIn('../华为杯_论文规范模板/前三章写作与验收.md',match[1])
        from paper_contract import audit_structure
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); manifest=make_fixture(root,1)
            manifest.pop('first_chapters_evidence_path')
            self.assertEqual(audit_structure(manifest,root)['status'],'FAIL')
            with self.assertRaises(ValueError):build_main(manifest,root,include_appendix=False)

    def test_manifest_types_match_the_auditor(self):
        schema = json.loads((PROJECT / "华为杯_论文规范模板/agent_manifest.schema.json").read_text(encoding="utf-8"))
        choices = schema["properties"]["chapters"]["items"]["properties"]["abstract_type"]["enum"]
        self.assertEqual(set(choices), set(ABSTRACT_TYPE_TERMS))

    def test_body_minimum_is_35_in_both_configurations(self):
        for name in ("page_targets.json", "章节页数基线.json"):
            data = json.loads((PROJECT / "华为杯_论文规范模板" / name).read_text(encoding="utf-8"))
            self.assertEqual(data["required_body_pages"], 35)
            self.assertIn("目录结束", data["body_definition"])

    def test_body_page_count_excludes_front_matter_and_appendix(self):
        result = body_pages([
            {"role": "problem", "start_physical_page": 4, "end_physical_page": 38},
            {"role": "references", "start_physical_page": 39, "end_physical_page": 40},
            {"role": "appendix", "start_physical_page": 41, "end_physical_page": 70},
        ])
        self.assertEqual(result["pages"], 35)

    def test_generated_abstract_toc_body_sequence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest = make_fixture(root, 1)
            tex, _ = build_main(manifest, root, include_appendix=False)
            self.assertLess(tex.index(r"\end{abstract}"), tex.index(r"\maketoc"))
            self.assertLess(tex.index(r"\maketoc"), tex.index(r"\input{c1.tex}"))
            self.assertIn("\\maketoc\n\\clearpage", tex)

    def test_abstract_skills_are_synchronized(self):
        left = (PROJECT / ".agents/skills/gmcm-abstract/SKILL.md").read_text(encoding="utf-8")
        right = (PROJECT / ".claude/skills/gmcm-abstract/SKILL.md").read_text(encoding="utf-8")
        self.assertEqual(left, right)
        self.assertIn("abstract_type", left)


if __name__ == "__main__":
    unittest.main()
