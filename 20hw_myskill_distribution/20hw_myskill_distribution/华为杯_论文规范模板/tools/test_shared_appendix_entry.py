"""Shared appendix orchestration tests, not formal-paper acceptance records."""
import json
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '华为杯_求解规范/tools'))
import test_workspace_context as fixtures
import workspace_context as wc
import run_appendix_smoke as smoke


class SharedAppendixEntryTests(unittest.TestCase):
    setUp = fixtures.WorkspaceTests.setUp
    tearDown = fixtures.WorkspaceTests.tearDown

    def prepare(self, runtime='codex', purpose='demo'):
        folder = self.root / '华为杯_求解规范/tools'
        folder.mkdir(exist_ok=True)
        maintained = Path(__file__).resolve().parents[2] / '华为杯_求解规范/tools'
        for name in ('workspace_context.py', 'workspace_execution.py', 'workspace_cli.py', 'workspace_schema.py', 'filesystem_paths.py'):
            shutil.copyfile(maintained / name, folder / name)
        shutil.copyfile(maintained.parent / '工作区清单.schema.json', folder.parent / '工作区清单.schema.json')
        (folder / 'probe.py').write_text("from pathlib import Path\nPath('求解/stage.txt').write_text('actual shared child')\n", encoding='utf8')
        return wc.create_workspace(self.root, runtime, purpose=purpose)

    def test_manifest_demo_is_accepted_without_demo_directory_name(self):
        for runtime in ('codex', 'claude'):
            c = self.prepare(runtime)
            self.assertEqual(smoke.execution_context(c.workspace_root, runtime).workspace_root, c.workspace_root)
            result = smoke.run_stage(c.workspace_root, c, 'probe', '华为杯_求解规范/tools/probe.py', [], c.workspace_root / '求解')
            self.assertEqual(result['returncode'], 0, result)
            self.assertEqual((c.workspace_root / '求解/stage.txt').read_text(), 'actual shared child')
            self.assertEqual(c.check_shared()['status'], 'PASS')

    def test_production_and_runtime_conflict_fail_before_pipeline(self):
        c = self.prepare(purpose='production')
        with self.assertRaisesRegex(ValueError, 'purpose=demo'):
            smoke.execution_context(c.workspace_root, 'codex')
        with self.assertRaisesRegex(ValueError, '冲突'):
            smoke.execution_context(c.workspace_root, 'claude')

    def test_main_threads_shared_template_and_workspace_to_all_stages(self):
        c = self.prepare('claude')
        wc.atomic_json(c.workspace_root / '求解/支撑材料清单.json', {'questions': [{'question_id': 'q1'}]})
        calls = []
        def controlled_stage(root, context, stage, tool, args, evidence):
            self.assertEqual(root, c.workspace_root)
            self.assertEqual(context.template_root, self.root)
            self.assertTrue(evidence.is_relative_to(c.workspace_root / '求解/验收输出'))
            calls.append((stage, tool, args))
            # Stop before actual compilation: this unit fixture has no paper.
            return {'stage': stage, 'argv': args, 'returncode': 1 if stage == 'compile' else 0,
                    'stdout': 'unit-only', 'stderr': 'unit-only'}
        args = ['run_appendix_smoke.py', '--project-root', str(c.workspace_root), '--runtime', 'claude',
                '--work-root', str(self.root.parent / 'outside-reproduction')]
        with patch.object(sys, 'argv', args), patch.object(smoke, 'run_stage', side_effect=controlled_stage), patch('builtins.print'):
            self.assertEqual(smoke.main(), 1)
        self.assertEqual([row[0] for row in calls], ['abstract', 'figure_ledger', 'package', 'reproduction',
            'package_and_auto_appendix', 'question_q1', 'support_final', 'paper', 'appendix', 'tex', 'compile'])
        paper = next(args for stage, tool, args in calls if stage == 'paper')
        self.assertEqual(Path(paper[paper.index('--template-dir') + 1]), self.root / '华为杯_论文规范模板')
        self.assertEqual(paper[paper.index('--runtime') + 1], 'claude')
        self.assertFalse((c.workspace_root / '华为杯_论文规范模板').exists())
        report = next((c.workspace_root / '求解/验收输出/附录演练').rglob('report.json'))
        self.assertEqual(json.loads(report.read_text(encoding='utf8'))['status'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
