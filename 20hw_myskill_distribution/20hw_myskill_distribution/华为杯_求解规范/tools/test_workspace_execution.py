"""Real child processes using isolated template fixtures, never production rules."""
import json
from pathlib import Path
import shutil
import unittest

import test_workspace_context as fixtures
import workspace_context as wc
from workspace_execution import execute, validate_arguments


class ExecutionTests(unittest.TestCase):
    setUp = fixtures.WorkspaceTests.setUp
    tearDown = fixtures.WorkspaceTests.tearDown

    def prepare(self, body):
        tools = self.root / '华为杯_求解规范/tools'
        tools.mkdir()
        for name in ('workspace_context.py', 'workspace_execution.py', 'filesystem_paths.py', 'workspace_schema.py'):
            shutil.copyfile(Path(__file__).parent / name, tools / name)
        shutil.copyfile(Path(__file__).parent.parent / '工作区清单.schema.json', tools.parent / '工作区清单.schema.json')
        (tools / 'probe.py').write_text(body, encoding='utf8')
        return wc.create_workspace(self.root, 'codex')

    def test_actual_child_writes_only_run_and_local_cache(self):
        c = self.prepare("import os,json\nfrom pathlib import Path\nfrom workspace_context import atomic_json\natomic_json(Path('求解/probe.json'), {'cwd':os.getcwd(),'cache':os.environ['MPLCONFIGDIR']})\n")
        r = execute(c, '华为杯_求解规范/tools/probe.py', [])
        self.assertEqual(r['status'], 'PASS', r)
        result = json.loads((c.workspace_root / '求解/probe.json').read_text(encoding='utf8'))
        self.assertEqual(Path(result['cwd']), c.workspace_root)
        self.assertTrue(Path(result['cache']).is_relative_to(c.workspace_root))
        self.assertEqual(c.check_shared()['status'], 'PASS')

    def test_python_shared_write_rejected_before_mutation(self):
        c = self.prepare("from pathlib import Path\nPath('../AGENTS.md').write_text('must not write')\n")
        before = wc.file_hash(self.root / 'AGENTS.md')
        r = execute(c, '华为杯_求解规范/tools/probe.py', [])
        self.assertEqual(r['status'], 'FAIL')
        self.assertNotEqual(r['returncode'], 0)
        self.assertEqual(before, wc.file_hash(self.root / 'AGENTS.md'))
        self.assertEqual(r['shared_changes'], [])

    def test_root_and_runtime_conflicts_precede_execution(self):
        c = self.prepare("raise AssertionError('must not execute')\n")
        for args in (['--runtime', 'claude'], ['--project-root=..'], ['--template-dir', '论文']):
            with self.subTest(args=args), self.assertRaises(ValueError):
                execute(c, '华为杯_求解规范/tools/probe.py', args)
        self.assertFalse((c.workspace_root / '求解/验收输出/工作区运行').exists())
        validate_arguments(c, ['--project-root', '.', '--runtime=codex', '--template-dir', str(self.root / '华为杯_论文规范模板')])

    def test_chdir_cannot_reinterpret_relative_write_as_workspace_write(self):
        c = self.prepare("import os\nfrom pathlib import Path\nos.chdir('..')\nPath('AGENTS.md').write_text('must not write')\n")
        before = wc.file_hash(self.root / 'AGENTS.md')
        result = execute(c, '华为杯_求解规范/tools/probe.py', [])
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['shared_changes'], [])
        self.assertEqual(wc.file_hash(self.root / 'AGENTS.md'), before)

    def test_declared_resource_drift_blocks_child(self):
        c = self.prepare("raise AssertionError('must not execute')\n")
        (self.root / 'CLAUDE.md').write_text('maintenance changed', encoding='utf8')
        with self.assertRaisesRegex(ValueError, '共享资源变化'):
            execute(c, '华为杯_求解规范/tools/probe.py', [])

    def test_shared_generated_cache_is_in_before_after_inventory(self):
        c = self.prepare("print('probe')\n")
        before = wc.shared_inventory(self.root, include_generated=True)
        cache = self.root / '华为杯_求解规范/tools/__pycache__'
        cache.mkdir()
        (cache / 'new.pyc').write_bytes(b'new cache')
        after = wc.shared_inventory(self.root, include_generated=True)
        self.assertIn('华为杯_求解规范/tools/__pycache__/new.pyc', wc.changes(before, after))
        self.assertEqual(c.check_shared()['status'], 'PASS')  # Content version ignores caches; run audit does not.

    def test_reproduction_external_scope_is_explicit_and_limited(self):
        c = self.prepare("print('unused')\n")
        tool = self.root / '华为杯_求解规范/tools/reproduce_supporting_materials.py'
        tool.write_text("import os,sys\nfrom pathlib import Path\np=Path(sys.argv[sys.argv.index('--work-root')+1])\np.mkdir()\n(p/'result.txt').write_text('real subprocess output')\ntry:\n Path('题目/forbidden.txt').write_text('bad')\nexcept ValueError:\n print('original input write rejected')\nelse:\n raise RuntimeError('original input boundary failed')\n", encoding='utf8')
        # New template version before creation; no accepted evidence is carried.
        c = wc.create_workspace(self.root, 'codex')
        target = self.root.parent / 'independent reproduction'
        r = execute(c, '华为杯_求解规范/tools/reproduce_supporting_materials.py', ['--work-root', str(target)])
        self.assertEqual(r['status'], 'PASS', r)
        self.assertEqual((target / 'result.txt').read_text(), 'real subprocess output')
        self.assertFalse((c.workspace_root / '题目/forbidden.txt').exists())
        self.assertEqual(r['independent_reproduction_root'], str(target))
        with self.assertRaisesRegex(ValueError, '尚不存在'):
            execute(c, '华为杯_求解规范/tools/reproduce_supporting_materials.py', ['--work-root', str(target)])
        with self.assertRaises(ValueError):
            execute(c, '华为杯_求解规范/tools/reproduce_supporting_materials.py', ['--work-root', str(self.root / 'wrong')])


if __name__ == '__main__':
    unittest.main()
