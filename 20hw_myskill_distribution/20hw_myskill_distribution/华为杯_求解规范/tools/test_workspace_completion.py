"""Lifecycle checks do not fabricate successful final scientific audits."""
import copy
import unittest
from unittest.mock import patch

import test_workspace_context as fixtures
import workspace_context as wc
from workspace_completion import artifact_inventory, finish, list_runs


class CompletionTests(unittest.TestCase):
    setUp = fixtures.WorkspaceTests.setUp
    tearDown = fixtures.WorkspaceTests.tearDown

    def test_creation_and_demo_never_count_as_completed(self):
        wc.create_workspace(self.root, 'codex')
        demo = wc.create_workspace(self.root, 'claude', purpose='demo')
        self.assertEqual(list_runs(self.root)['completed_paper_count'], 0)
        with self.assertRaisesRegex(ValueError, 'DEMO'):
            finish(demo)

    def test_manual_complete_without_final_audit_is_invalid(self):
        c = wc.create_workspace(self.root, 'codex')
        data = copy.deepcopy(c.manifest)
        data.update(status='complete', completed_at=wc.now())
        wc.atomic_json(c.workspace_root / wc.MANIFEST, data)
        listing = list_runs(self.root)
        self.assertEqual(listing['completed_paper_count'], 0)
        self.assertIn('最终审计', listing['runs'][0]['reason'])

    def test_finish_requires_registered_problem_and_real_files(self):
        c = wc.create_workspace(self.root, 'codex')
        with self.assertRaisesRegex(ValueError, '题目输入'):
            finish(c)
        c = wc.create_workspace(self.root, 'codex', ['题目/题目.txt'])
        with self.assertRaisesRegex(ValueError, '文件缺失'):
            finish(c)

    def test_final_gate_failure_preserves_incomplete_status(self):
        c = wc.create_workspace(self.root, 'codex', ['题目/题目.txt'])
        for raw in ('论文/论文输入.json', '论文/论文.tex', '论文/论文.pdf',
                    '求解/视觉计划.json', '求解/支撑材料清单.json', '求解/候选图清单.json'):
            (c.workspace_root / raw).write_text('invalid fixture', encoding='utf8')
        # This test only exercises a failing audit; it grants no synthetic PASS.
        with patch('workspace_execution.execute', return_value={'status': 'FAIL',
                'report_path': str(c.workspace_root / '求解/failed.json')}) as execute:
            report = finish(c)
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(report['status'], 'FINAL_AUDIT_FAILED')
        self.assertEqual(wc.resolve_context(c.workspace_root).manifest['status'], 'incomplete')
        self.assertEqual(list_runs(self.root)['completed_paper_count'], 0)

    def test_inventory_binds_science_and_review_but_not_runtime_logs(self):
        c = wc.create_workspace(self.root, 'codex')
        root = c.workspace_root
        for raw in ('求解/结果.json', '求解/验收输出/图件.qa.json', '求解/验收输出/工作区运行/日志.txt'):
            path = root / raw
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('first', encoding='utf8')
        first = artifact_inventory(root)
        (root / '求解/验收输出/工作区运行/日志.txt').write_text('later', encoding='utf8')
        self.assertEqual(first, artifact_inventory(root))
        (root / '求解/验收输出/图件.qa.json').write_text('changed review', encoding='utf8')
        self.assertNotEqual(first, artifact_inventory(root))


if __name__ == '__main__':
    unittest.main()
