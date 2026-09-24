"""Real input transactions, rollback, concurrent ownership and manifest rejection."""
import copy
import json
from pathlib import Path
from unittest.mock import patch
import unittest
import test_workspace_context as fixtures
import workspace_context as wc


class InputTests(unittest.TestCase):
    setUp = fixtures.WorkspaceTests.setUp
    tearDown = fixtures.WorkspaceTests.tearDown

    def test_append_preserves_initial_snapshot_and_logs_source(self):
        c = wc.create_workspace(self.root, 'codex', ['题目/题目.txt'])
        initial = copy.deepcopy(c.manifest['inputs'])
        r = wc.append_inputs(c, ['数据/原始/input.csv'], '新增实验附件用于本次求解的数据审计')
        current = wc.resolve_context(c.workspace_root)
        self.assertEqual(current.manifest['inputs'][:1], initial)
        self.assertEqual(len(current.manifest['inputs']), 2)
        self.assertEqual(current.check_inputs()['status'], 'PASS')
        report = json.loads(Path(r['report_path']).read_text(encoding='utf8'))
        self.assertEqual(report['status'], 'REGISTERED')
        self.assertEqual(report['files'][0]['source_path'], '数据/原始/input.csv')
        self.assertEqual(wc.file_hash(self.root / '数据/原始/input.csv'), report['files'][0]['sha256'])
        self.assertEqual(current.check_shared()['status'], 'PASS')

    def test_duplicate_append_rejected_without_mutating_manifest(self):
        c = wc.create_workspace(self.root, 'codex', ['题目/题目.txt'])
        before = wc.file_hash(c.workspace_root / wc.MANIFEST)
        (self.root / '题目/题目.txt').write_text('changed intake', encoding='utf8')
        with self.assertRaisesRegex(ValueError, '覆盖'):
            wc.append_inputs(c, ['题目/题目.txt'], '不能通过追加操作覆盖以前题目副本')
        self.assertEqual(wc.file_hash(c.workspace_root / wc.MANIFEST), before)
        self.assertEqual(c.check_inputs()['status'], 'PASS')

    def test_changed_source_during_copy_leaves_no_published_inputs(self):
        c = wc.create_workspace(self.root, 'codex')
        before = wc.file_hash(c.workspace_root / wc.MANIFEST)
        original = wc.shutil.copyfile
        def copying(source, destination):
            original(source, destination)
            Path(source).write_text('concurrent upstream change', encoding='utf8')
        with patch.object(wc.shutil, 'copyfile', side_effect=copying), self.assertRaisesRegex(ValueError, '期间'):
            wc.append_inputs(c, ['数据/原始/input.csv'], '验证复制时入口发生变化必须拒绝发布')
        self.assertFalse((c.workspace_root / '数据/原始/input.csv').exists())
        self.assertEqual(wc.file_hash(c.workspace_root / wc.MANIFEST), before)
        reports = list((c.workspace_root / '求解/验收输出/输入变更').glob('*/输入变更.json'))
        self.assertEqual(json.loads(reports[0].read_text(encoding='utf8'))['status'], 'FAILED')

    def test_competing_manifest_owner_not_overwritten(self):
        c = wc.create_workspace(self.root, 'codex')
        with wc.manifest_lock(c.workspace_root):
            with self.assertRaisesRegex(ValueError, '另一操作'):
                wc.append_inputs(c, ['题目/题目.txt'], '验证已有持锁操作期间不覆盖清单')

    def test_malicious_manifest_fields_are_rejected(self):
        c = wc.create_workspace(self.root, 'codex', ['题目/题目.txt'])
        for label, mutation in [
            ('escape', lambda d: d['inputs'][0].update(workspace_path='题目/../../AGENTS.md')),
            ('ads', lambda d: d['inputs'][0].update(workspace_path='题目/题目.txt:hidden')),
            ('negative size', lambda d: d['inputs'][0].update(size_bytes=-1)),
            ('boolean count', lambda d: d.update(run_number=True)),
            ('extra unknown', lambda d: d.update(allow_shared_write=True)),
            ('duplicate', lambda d: d['inputs'].append(copy.deepcopy(d['inputs'][0]))),
        ]:
            data = copy.deepcopy(c.manifest)
            mutation(data)
            wc.atomic_json(c.workspace_root / wc.MANIFEST, data)
            with self.subTest(case=label), self.assertRaises(ValueError):
                wc.resolve_context(c.workspace_root)
        wc.atomic_json(c.workspace_root / wc.MANIFEST, c.manifest)


if __name__ == '__main__':
    unittest.main()
