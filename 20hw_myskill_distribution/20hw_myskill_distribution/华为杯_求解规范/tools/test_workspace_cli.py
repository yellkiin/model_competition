"""Exercise direct and wrapped entrypoints in real, isolated subprocesses."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

import test_workspace_context as fixtures
import workspace_context as wc
from workspace_execution import execute


class CliModeTests(unittest.TestCase):
    setUp = fixtures.WorkspaceTests.setUp
    tearDown = fixtures.WorkspaceTests.tearDown

    def prepare(self):
        folder = self.root / '华为杯_求解规范/tools'
        folder.mkdir()
        for name in ('workspace_cli.py', 'workspace_context.py', 'workspace_execution.py',
                     'filesystem_paths.py', 'workspace_schema.py'):
            shutil.copyfile(Path(__file__).parent / name, folder / name)
        shutil.copyfile(Path(__file__).parent.parent / '工作区清单.schema.json', folder.parent / '工作区清单.schema.json')
        self.probe = folder / 'probe.py'
        self.probe.write_text('''import sys
sys.dont_write_bytecode = True
from workspace_cli import require_cli_mode
mode = require_cli_mode(__file__)
import argparse, json, os, subprocess
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--output', required=True)
p.add_argument('--project-root')
p.add_argument('--spawn', action='store_true')
a = p.parse_args()
if a.spawn:
    subprocess.run([sys.executable, '-B', __file__, '--output', a.output], check=True)
else:
    Path(a.output).write_text(json.dumps({'mode': mode, 'cwd': str(Path.cwd())}), encoding='utf8')
''', encoding='utf8')
        wc.atomic_json(self.root / wc.MODE_FILE, {'schema_version': '1.0', 'mode': 'template'})

    def invoke(self, args, cwd=None, env=None):
        clean = {k: v for k, v in os.environ.items() if not k.startswith('HUAWEI_')}
        clean['PYTHONUTF8'] = '1'
        clean.update(env or {})
        return subprocess.run([sys.executable, '-B', str(self.probe), *args], cwd=cwd or self.root,
                              env=clean, capture_output=True, text=True, encoding='utf8')

    def test_unmarked_direct_cli_rejects_before_write(self):
        self.prepare()
        result = self.invoke(['--output', 'unexpected.json'])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('未声明工作流模式', result.stderr)
        self.assertFalse((self.root / 'unexpected.json').exists())

    def test_template_and_nested_template_cannot_be_legacy(self):
        self.prepare()
        for cwd in (self.root, self.probe.parent):
            result = self.invoke(['--legacy', '--output', 'unexpected.json'], cwd)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('模板根不是legacy', result.stderr)
            self.assertFalse((cwd / 'unexpected.json').exists())

    def test_explicit_legacy_child_inherits_mode(self):
        self.prepare()
        old = self.root.parent / '旧独立项目'
        old.mkdir()
        result = self.invoke(['--legacy', '--spawn', '--output', 'result.json'], old)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((old / 'result.json').read_text())['mode'], 'legacy')

    def test_explicit_maintenance_and_help(self):
        self.prepare()
        result = self.invoke(['--maintenance', '--output', 'maintenance.json'])
        self.assertEqual(result.returncode, 0, result.stderr)
        for args in (['--help'], ['--maintenance', '--help']):
            result = self.invoke(args)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('--output', result.stdout)

    def test_old_independent_project_inside_template_remains_legacy(self):
        self.prepare()
        old = self.root / '旧项目'
        old.mkdir()
        for name in wc.SHARED:
            if name.endswith('.md'):
                (old / name).write_text('old independent rules')
            else:
                (old / name).mkdir()
        result = self.invoke(['--legacy', '--output', 'result.json'], old)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((old / 'result.json').read_text())['mode'], 'legacy')

    def test_workshop_cannot_downgrade_modes(self):
        self.prepare()
        context = wc.create_workspace(self.root, 'codex')
        for mode in ('--legacy', '--maintenance'):
            result = self.invoke([mode, '--output', 'unexpected.json'], context.workspace_root)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((context.workspace_root / 'unexpected.json').exists())

    def test_wrapped_and_nested_shared_children_both_runtimes(self):
        self.prepare()
        for runtime in ('codex', 'claude'):
            context = wc.create_workspace(self.root, runtime)
            result = execute(context, '华为杯_求解规范/tools/probe.py', ['--spawn', '--output', '求解/result.json'])
            self.assertEqual(result['status'], 'PASS', result)
            actual = json.loads((context.workspace_root / '求解/result.json').read_text())
            self.assertEqual(actual, {'mode': 'shared', 'cwd': str(context.workspace_root)})
            self.assertEqual(context.check_shared()['status'], 'PASS')

    def test_shared_nested_child_cannot_write_template(self):
        self.prepare()
        context = wc.create_workspace(self.root, 'codex')
        before = wc.file_hash(self.root / 'AGENTS.md')
        result = execute(context, '华为杯_求解规范/tools/probe.py', ['--spawn', '--output', '../AGENTS.md'])
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(wc.file_hash(self.root / 'AGENTS.md'), before)
        self.assertEqual(result['shared_changes'], [])


if __name__ == '__main__':
    unittest.main()
