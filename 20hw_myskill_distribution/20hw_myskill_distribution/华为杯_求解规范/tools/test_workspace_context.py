"""Real filesystem tests; no scientific or visual QA is manufactured here."""
import concurrent.futures
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest

import workspace_context as wc


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / '中文 template with spaces'
        self.root.mkdir()
        for name in wc.SHARED:
            p = self.root / name
            if name.endswith('.md'):
                p.write_text('shared rule', encoding='utf8')
            else:
                p.mkdir()
                (p / 'resource.txt').write_text('read only asset', encoding='utf8')
        for side in wc.RUNTIMES.values():
            skill = self.root / side / 'skills/example'
            skill.mkdir(parents=True)
            (skill / 'SKILL.md').write_text('reference: ../../resource.txt', encoding='utf8')
        (self.root / '题目').mkdir()
        (self.root / '数据/原始').mkdir(parents=True)
        (self.root / '题目/题目.txt').write_text('explicit problem', encoding='utf8')
        (self.root / '数据/原始/input.csv').write_text('a,b\n1,2', encoding='utf8')

    def tearDown(self):
        for p in wc.native_path(self.tmp.name).rglob('*'):
            if p.is_file():
                p.chmod(stat.S_IWRITE | stat.S_IREAD)
        # Extended paths are needed for native Windows recursive cleanup too.
        target = wc.native_path(self.tmp.name)
        self.assertEqual(target.resolve(), wc.native_path(Path(self.tmp.name).resolve()))
        shutil.rmtree(target)
        self.tmp.cleanup()

    def create(self, runtime='codex'):
        return wc.create_workspace(self.root, runtime, ['题目/题目.txt', '数据/原始/input.csv'])

    def test_create_no_shared_copies_and_intake_snapshot(self):
        c = self.create()
        self.assertEqual(c.workspace_root.name, 'workshop_v1')
        self.assertEqual(c.check_shared()['status'], 'PASS')
        self.assertEqual(c.check_inputs()['status'], 'PASS')
        for name in wc.SHARED:
            self.assertFalse((c.workspace_root / name).exists())
        self.assertTrue((c.workspace_root / '数据/原始/input.csv').is_file())
        (self.root / '数据/原始/input.csv').write_text('new intake', encoding='utf8')
        self.assertEqual(c.check_inputs()['status'], 'PASS')
        self.assertEqual(c.manifest['status'], 'ready')
        self.assertIsNone(c.manifest['completed_at'])

    def test_subdirectory_and_explicit_conflicts(self):
        c = self.create()
        self.assertEqual(wc.resolve_context(c.workspace_root / '求解/验收输出').workspace_root, c.workspace_root)
        with self.assertRaisesRegex(ValueError, '冲突'):
            wc.resolve_context(c.workspace_root, runtime='claude')
        with self.assertRaisesRegex(ValueError, '冲突'):
            wc.resolve_context(c.workspace_root, template_root=self.root.parent)
        with self.assertRaisesRegex(ValueError, '不自动选择'):
            wc.resolve_context(self.root)

    def test_atomic_numbering_and_no_reuse(self):
        (self.root / 'workshop_v3').mkdir()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            runs = list(pool.map(lambda _: wc.create_workspace(self.root, 'codex'), range(4)))
        self.assertEqual(sorted(c.manifest['run_number'] for c in runs), [4, 5, 6, 7])

    def test_resource_white_list_and_runtime(self):
        for runtime in wc.RUNTIMES:
            c = self.create(runtime)
            self.assertTrue((c.skill('example') / 'SKILL.md').is_file())
            self.assertEqual(c.resource_relative(f'{wc.RUNTIMES[runtime]}/skills/example/SKILL.md', '../../resource.txt').read_text(), 'read only asset')
            with self.assertRaises(ValueError):
                c.read_resource('题目/题目.txt')
            other = '.claude' if runtime == 'codex' else '.agents'
            with self.assertRaisesRegex(ValueError, '跨运行时'):
                c.read_resource(other + '/resource.txt')

    def test_write_boundaries_and_originals(self):
        c = self.create()
        for raw in ('../AGENTS.md', '../workshop_v2/a', '.agents/a', '题目/x', '数据/原始/x', wc.MANIFEST):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                c.write_path(raw)
        self.assertEqual(c.write_path('数据/中间/x'), c.workspace_root / '数据/中间/x')

    def test_junction_escape_is_rejected(self):
        c = self.create()
        link = c.workspace_root / '求解/redirect'
        if os.name == 'nt':
            import subprocess
            result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(self.root / '华为杯_求解规范')], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            link.symlink_to(self.root / '华为杯_求解规范', target_is_directory=True)
        try:
            with self.assertRaises(ValueError):
                c.write_path('求解/redirect/output.txt')
        finally:
            if os.name == 'nt':
                link.rmdir()
            else:
                link.unlink()

    def test_move_tree_and_resource_drift(self):
        c = self.create()
        target = self.root.with_name('搬迁后的 template')
        shutil.move(str(self.root), str(target))
        self.root = target
        c = wc.resolve_context(target / c.workspace_root.name)
        self.assertEqual(c.check_shared()['status'], 'PASS')
        (target / 'AGENTS.md').write_text('changed', encoding='utf8')
        self.assertEqual(c.check_shared()['changed_resources'], ['AGENTS.md'])

    def test_missing_template_fails(self):
        c = self.create()
        (self.root / 'CLAUDE.md').unlink()
        with self.assertRaisesRegex(ValueError, '缺失'):
            wc.resolve_context(c.workspace_root)

    def test_legacy_requires_explicit_mode(self):
        with self.assertRaises(ValueError):
            wc.resolve_context(self.root, runtime='codex')
        c = wc.resolve_context(self.root, runtime='codex', legacy=True)
        self.assertEqual(c.mode, 'legacy')
        new = self.create()
        with self.assertRaises(ValueError):
            wc.resolve_context(new.workspace_root, runtime='codex', legacy=True)

    def test_long_path_inventory_does_not_silently_drop_asset(self):
        p = self.root / '.agents' / ('nested-' + 'a' * 70) / ('b' * 70) / ('c' * 70) / '图片.txt'
        wc.native_path(p.parent).mkdir(parents=True)
        wc.native_path(p).write_text('asset', encoding='utf8')
        c = self.create()
        self.assertIn(p.relative_to(self.root).as_posix(), c.manifest['shared_resources']['files'])
        self.assertEqual(c.check_shared()['status'], 'PASS')


if __name__ == '__main__':
    unittest.main()
