#!/usr/bin/env python3
"""Regression tests for the dynamic Huawei Cup appendix workflow."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from audit_appendix import audit_appendix
from build_appendix import build_appendix, sha256
from build_supporting_materials import build
from audit_supporting_materials import audit
from supporting_contract import question_name
from reproduce_supporting_materials import reproduce


class AppendixWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="gmcm-appendix-test-"))
        (self.root / "论文/章节内容").mkdir(parents=True)
        (self.root / "求解").mkdir()
        (self.root / "提交附件/支撑材料").mkdir(parents=True)
        (self.root / "华为杯_论文规范模板/章节模板").mkdir(parents=True)
        template_source = Path(__file__).resolve().parents[1] / "章节模板/附录模板.tex"
        shutil.copy2(template_source, self.root / "华为杯_论文规范模板/章节模板/附录模板.tex")
        shutil.copy2(template_source, self.root / "论文/附录模板.tex")
        # This suite isolates packaging and generated-code facts. Diagram
        # science/visual QA has real-render suites and must not be claimed here.
        (self.root/'求解/视觉计划.json').write_text('{"problems":[]}',encoding='utf-8')
        self.diagram_gate = patch('audit_diagram_workflow.audit', return_value={
            'status':'PASS','failures':[],'figure_accounting':{'figures':[]}})
        self.diagram_mock = self.diagram_gate.start()
        self.addCleanup(self.diagram_gate.stop)
        self.repro_dirs = []

    def tearDown(self) -> None:
        shutil.rmtree(self.root)
        for directory in self.repro_dirs:
            shutil.rmtree(directory)

    def make_fixture(self, problem_count: int = 4) -> None:
        chapters = []
        questions = []
        entries = []
        for index in range(1, problem_count + 1):
            source_rel = f"求解/问题{index}/问题{index}.py"
            source = self.root / source_rel
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(
                "# 数据预处理与核心模型\n"
                "def preprocess_data(values):\n"
                "    \"\"\"构造训练矩阵。\"\"\"\n"
                "    return [float(value) for value in values]\n\n"
                "def solve_model(values):\n"
                "    cleaned = preprocess_data(values)\n"
                "    return sum(cleaned) / max(len(cleaned), 1)\n\n"
                "if __name__ == '__main__':\n"
                "    import json, sys, statistics\n"
                "    from pathlib import Path\n"
                "    if '--verify' in sys.argv:\n"
                "        assert json.loads(Path('result.json').read_text())['mean'] == statistics.mean([1, 2, 3])\n"
                "    else:\n"
                "        Path('result.json').write_text(json.dumps({'mean': solve_model([1, 2, 3])}))\n",
                encoding="utf-8",
            )
            package_rel = f"支撑材料/q{index}/源程序/{source_rel}"
            package = self.root / "提交附件" / package_rel
            package.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, package)
            entries.append({
                "source_path": source_rel,
                "package_path": package_rel,
                "description": f"问题{index}核心求解程序",
                "category": "source_code",
                "question_id": f"q{index}",
                "size_bytes": source.stat().st_size,
                "sha256": sha256(source),
            })
            appendix_code = []
            if index == problem_count:
                appendix_code = [{
                    "file": source_rel,
                    "language": "python",
                    "firstline": 2,
                    "lastline": 8,
                    "firstnumber": 2,
                    "caption": "核心模型与求解逻辑",
                }]
            questions.append({
                "question_id": f"q{index}",
                "title": f"问题{index}",
                "status": "complete",
                "entrypoint": source_rel,
                "run_command": f"python {source_rel}",
                "source_files": [{"path": source_rel, "description": f"问题{index}核心求解程序"}],
                "run_verification": {"status": "pass", "command": "python", "record_path": "record.json", "verified_at": "2026-09-06"},
                "supplementary_materials": [],
                "supplementary_materials_note": "已审查，无额外材料",
                "appendix_code": appendix_code,
            })
            chapters.append({
                "chapter_id": f"q{index}",
                "title": f"问题{index}",
                "role": "problem",
                "order": index,
                "tex_path": f"章节内容/q{index}.tex",
            })

        paper = {
            "title": "动态附录测试",
            "keywords": ["动态附录", "关键代码", "可复现性"],
            "abstract_tex_path": "章节内容/abstract.tex",
            "chapters": chapters,
        }
        support = {
            "schema_version": "2.0",
            "project_title": "动态附录测试",
            "package_status": "complete",
            "questions": questions,
            "external_data": [],
            "external_data_note": "未使用自主数据",
            "official_outputs": [],
        }
        support['readme_source']='求解/支撑材料说明.md'
        support['additional_files']=[]
        support['category_descriptions']={'其他数据':'无','其他支撑材料':'无'}
        lines=['# 支撑材料说明','复现、数据、结果说明']
        actual_runs = []
        for i,q in enumerate(questions,1):
            q['summary']=f'{question_name(i)}源码与环境说明'
            q['environment_doc']=f'求解/env{i}.md'
            q['package_command']='python main.py'
            q['depends_on']=[]
            q['source_files'][0]['package_path']='main.py'
            q['reproduction'] = {
                'commands': [
                    {'purpose':'solve','argv':['{python}','-X','utf8','main.py']},
                    {'purpose':'validate','argv':['{python}','-X','utf8','main.py','--verify']}],
                'outputs':[{'path':'result.json','expected_path':f'求解/问题{i}/result.json','comparison':'json'}]}
            for extra in ([], ['--verify']):
                command = [sys.executable, '-X', 'utf8', str(self.root/q['entrypoint']), *extra]
                run = subprocess.run(command, cwd=(self.root/q['entrypoint']).parent,
                    capture_output=True, text=True, encoding='utf-8', check=True)
                actual_runs.append({'argv':command,'returncode':run.returncode,'stdout':run.stdout,'stderr':run.stderr})
            (self.root/q['environment_doc']).write_text('环境 安装 输入 运行 输出 依赖 python main.py',encoding='utf-8')
            lines.append(question_name(i)+' '+q['summary'])
        lines.extend(['其他数据 无','其他支撑材料 无'])
        (self.root/'record.json').write_text(json.dumps(actual_runs),encoding='utf-8')
        (self.root/support['readme_source']).write_text('\n'.join(lines),encoding='utf-8')
        (self.root / "论文/论文输入.json").write_text(json.dumps(paper, ensure_ascii=False), encoding="utf-8")
        (self.root / "求解/支撑材料清单.json").write_text(json.dumps(support, ensure_ascii=False), encoding="utf-8")
        (self.root / "提交附件/readme.md").write_text("# 真实提交附件\n", encoding="utf-8")
        (self.root / "提交附件/_支撑材料构建清单.json").write_text(
            json.dumps({"entries": entries, "official_outputs": []}, ensure_ascii=False), encoding="utf-8"
        )
        (self.root / "提交附件/SHA256SUMS.txt").write_text("test\n", encoding="utf-8")
        (self.root / "论文/论文.tex").write_text(
            "\\input{附录模板.tex}\n\\input{章节内容/99_附录.generated.tex}\n", encoding="utf-8"
        )
        build(self.root/'求解/支撑材料清单.json',self.root,self.root/'提交附件')
        container = Path(tempfile.mkdtemp(prefix='gmcm-independent-test-'))
        self.repro_dirs.append(container)
        report = reproduce(self.root, self.root/'求解/支撑材料清单.json', self.root/'提交附件', container/'run')
        self.assertEqual(report['status'], 'PASS', report)
        build(self.root/'求解/支撑材料清单.json',self.root,self.root/'提交附件')

    def report(self):
        return audit(self.root/'求解/支撑材料清单.json',self.root,self.root/'提交附件','final',None,'codex')

    def test_three_questions_and_rebuild_remove_stale_files(self):
        self.make_fixture(3)
        self.assertEqual(self.report()['status'],'PASS')
        (self.root/'提交附件/stale.txt').write_text('old',encoding='utf-8')
        self.assertEqual(self.report()['status'],'FAIL')
        build(self.root/'求解/支撑材料清单.json',self.root,self.root/'提交附件')
        self.assertEqual(self.report()['status'],'PASS')
        self.assertFalse((self.root/'提交附件/stale.txt').exists())
        self.assertFalse((self.root/'提交附件/支撑材料文件/问题四').exists())

    def test_tampered_source_and_extra_hidden_directory_fail(self):
        self.make_fixture()
        (self.root/'提交附件/支撑材料文件/问题一/源码/main.py').write_text('changed',encoding='utf-8')
        self.assertEqual(self.report()['status'],'FAIL')
        build(self.root/'求解/支撑材料清单.json',self.root,self.root/'提交附件')
        (self.root/'提交附件/支撑材料文件/问题一/源码/.agents').mkdir()
        self.assertEqual(self.report()['status'],'FAIL')

    def test_missing_environment_document_fails(self):
        self.make_fixture()
        (self.root/'提交附件/支撑材料文件/问题一/代码环境说明.md').unlink()
        self.assertEqual(self.report()['status'],'FAIL')

    def test_changed_internal_record_fails(self):
        self.make_fixture()
        (self.root/'record.json').write_text('{"status":"fail"}',encoding='utf-8')
        self.assertEqual(self.report()['status'],'FAIL')

    def test_bad_destination_and_missing_source_do_not_replace_package(self):
        self.make_fixture()
        manifest_path=self.root/'求解/支撑材料清单.json'
        support=json.loads(manifest_path.read_text(encoding='utf-8'))
        before=sha256(self.root/'提交附件/支撑材料说明.md')
        support['questions'][0]['source_files'][0]['package_path']='../../escape.py'
        manifest_path.write_text(json.dumps(support),encoding='utf-8')
        with self.assertRaises(Exception):build(manifest_path,self.root,self.root/'提交附件')
        self.assertEqual(before,sha256(self.root/'提交附件/支撑材料说明.md'))


    def test_four_problem_appendix_is_dynamic_and_auditable(self) -> None:
        self.make_fixture(4)
        result = build_appendix(
            project_root=self.root,
            paper_manifest_path=Path("论文/论文输入.json"),
            supporting_manifest_path=Path("求解/支撑材料清单.json"),
            submission_dir=Path("提交附件"),
            output_tex=Path("论文/章节内容/99_附录.generated.tex"),
            output_manifest=Path("求解/附录清单.json"),
            runtime='codex',
        )
        self.assertEqual(result["problem_count"], 4)
        self.assertEqual(result["appendix_part_count"], 5)
        self.assertEqual(result['runtime'], 'codex')
        self.assertEqual(self.diagram_mock.call_args.args[3], 'codex')
        tex = (self.root / "论文/章节内容/99_附录.generated.tex").read_text(encoding="utf-8")
        self.assertIn(r"\AppendixPart{1}{附件文件及内容}", tex)
        self.assertIn(r"\AppendixPart{5}{问题四关键代码}", tex)
        self.assertIn(r"\AppendixCodeFile[firstline=2,lastline=8,firstnumber=2]", tex)
        report = audit_appendix(
            project_root=self.root,
            paper_manifest_path=Path("论文/论文输入.json"),
            supporting_manifest_path=Path("求解/支撑材料清单.json"),
            submission_dir=Path("提交附件"),
            appendix_manifest_path=Path("求解/附录清单.json"),
            appendix_tex_path=Path("论文/章节内容/99_附录.generated.tex"),
            appendix_template_path=Path("华为杯_论文规范模板/章节模板/附录模板.tex"),
            main_tex_path=Path("论文/论文.tex"),
            runtime='codex',
        )
        self.assertEqual(report["status"], "PASS", report["failures"])

    def test_failed_diagram_gate_still_blocks_appendix_generation(self):
        self.make_fixture(3)
        self.diagram_mock.return_value={'status':'FAIL','failures':[{'code':'missing_overview'}]}
        with self.assertRaisesRegex(ValueError, 'missing_overview'):
            build_appendix(project_root=self.root,paper_manifest_path=Path('论文/论文输入.json'),
                supporting_manifest_path=Path('求解/支撑材料清单.json'),submission_dir=Path('提交附件'),
                output_tex=Path('论文/章节内容/99_附录.generated.tex'),output_manifest=Path('求解/附录清单.json'),runtime='claude')
        self.assertEqual(self.diagram_mock.call_args.args[3], 'claude')
        self.assertFalse((self.root/'求解/附录清单.json').exists())

    def test_problem_count_mismatch_is_rejected(self) -> None:
        self.make_fixture(4)
        support_path = self.root / "求解/支撑材料清单.json"
        support = json.loads(support_path.read_text(encoding="utf-8"))
        support["questions"].pop()
        support_path.write_text(json.dumps(support, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "问题数"):
            build_appendix(
                project_root=self.root,
                paper_manifest_path=Path("论文/论文输入.json"),
                supporting_manifest_path=Path("求解/支撑材料清单.json"),
                submission_dir=Path("提交附件"),
                output_tex=Path("论文/章节内容/99_附录.generated.tex"),
                output_manifest=Path("求解/附录清单.json"),
            )


if __name__ == "__main__":
    unittest.main()
