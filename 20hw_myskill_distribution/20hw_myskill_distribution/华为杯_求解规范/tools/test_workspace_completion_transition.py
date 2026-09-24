"""Unit-only lifecycle fixtures: mocked gates grant no real paper completion."""
from pathlib import Path
import unittest
from unittest.mock import patch

import test_workspace_context as fixtures
import workspace_context as wc
from workspace_completion import finish, list_runs


class CompletionTransitionTests(unittest.TestCase):
    setUp = fixtures.WorkspaceTests.setUp
    tearDown = fixtures.WorkspaceTests.tearDown

    def test_complete_then_artifact_or_receipt_change_invalidates_count(self):
        for changed in ('论文/论文.tex', '求解/review.json', 'receipt'):
            c = wc.create_workspace(self.root, 'codex', ['题目/题目.txt'])
            for raw in ('论文/论文输入.json', '论文/论文.tex', '论文/论文.pdf',
                        '求解/视觉计划.json', '求解/支撑材料清单.json', '求解/候选图清单.json', '求解/review.json'):
                (c.workspace_root / raw).write_text('UNIT FIXTURE ONLY', encoding='utf8')
            executed = []
            def fake_gate(context, tool, args, **kwargs):
                executed.append(tool)
                output = context.workspace_root / args[args.index('--report') + 1]
                wc.atomic_json(output, {'status': 'PASS', 'unit_fixture': True})
                log = output.with_suffix('.log')
                log.write_text('mocked gate, not actual scientific verification')
                relative = log.relative_to(context.workspace_root).as_posix()
                return {'status': 'PASS', 'report_path': str(log), 'stdout': relative, 'stderr': relative}
            with patch('workspace_execution.execute', side_effect=fake_gate):
                result = finish(c)
            self.assertEqual(result['status'], 'COMPLETE', result)
            self.assertEqual([Path(p).name for p in executed],
                             ['audit_supporting_materials.py', 'audit_appendix.py', 'audit_tex.py', 'audit_paper.py'])
            self.assertEqual(list_runs(self.root)['completed_paper_count'], 1)
            target = Path(result['report_path']) if changed == 'receipt' else c.workspace_root / changed
            target.write_text('changed after unit-only completion', encoding='utf8')
            self.assertEqual(list_runs(self.root)['completed_paper_count'], 0)


if __name__ == '__main__':
    unittest.main()
