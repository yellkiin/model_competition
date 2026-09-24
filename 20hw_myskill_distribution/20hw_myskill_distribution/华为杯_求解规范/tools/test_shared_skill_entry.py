"""Exercise actual shared skill children and protect simulated-template routing."""
import json
from pathlib import Path
import shutil
import unittest

import test_workspace_context as fixtures
import workspace_context as wc
from workspace_execution import execute
from run_shared_skill import prepare


class SkillEntryTests(unittest.TestCase):
    setUp = fixtures.WorkspaceTests.setUp
    tearDown = fixtures.WorkspaceTests.tearDown

    def fixture(self, runtime='codex', purpose='demo'):
        tools = self.root / '华为杯_求解规范/tools'
        tools.mkdir(exist_ok=True)
        for name in ('workspace_context.py', 'workspace_execution.py', 'filesystem_paths.py',
                     'workspace_schema.py', 'workspace_cli.py', 'run_shared_skill.py'):
            shutil.copyfile(Path(__file__).parent / name, tools / name)
        shutil.copyfile(Path(__file__).parent.parent / '工作区清单.schema.json', tools.parent / '工作区清单.schema.json')
        for side in wc.RUNTIMES.values():
            skill = self.root / side / 'skills/nested/skills/scibox-figure'
            (skill / 'scripts').mkdir(parents=True, exist_ok=True)
            (skill / 'SKILL.md').write_text('fixture', encoding='utf8')
            (skill / 'scripts/render_template.py').write_text(
                "import sys,os,json\nfrom pathlib import Path\n"
                "p=Path(sys.argv[sys.argv.index('--project')+1]);p.mkdir(parents=True)\n"
                "(p/'actual.json').write_text(json.dumps({'cwd':os.getcwd(),'source':__file__}))\n", encoding='utf8')
        return wc.create_workspace(self.root, runtime, purpose=purpose)

    def script(self, runtime='codex'):
        return wc.RUNTIMES[runtime] + '/skills/nested/skills/scibox-figure/scripts/render_template.py'

    def test_both_runtimes_execute_nested_skill_without_shared_writes(self):
        for runtime in wc.RUNTIMES:
            c = self.fixture(runtime)
            result = execute(c, '华为杯_求解规范/tools/run_shared_skill.py', ['--script', self.script(runtime), '--', 'example'])
            self.assertEqual(result['status'], 'PASS', result)
            actual = json.loads((c.workspace_root / '求解/模板演练/绘图复刻/actual.json').read_text())
            self.assertEqual(Path(actual['cwd']), c.workspace_root)
            self.assertEqual(Path(actual['source']), self.root / self.script(runtime))
            self.assertEqual(result['shared_changes'], [])

    def test_rejects_cross_runtime_and_project_escape(self):
        c = self.fixture()
        for script, args in ((self.script('claude'), ['--list']),
                             (self.script(), ['example', '--project', '../wrong']),
                             (self.script(), ['example', '--project', '题目/wrong']),
                             (self.script(), ['example', '--project']),
                             (self.script(), ['example', '--project=a', '--project=b'])):
            with self.subTest(script=script, args=args), self.assertRaises(ValueError):
                prepare(c, script, args)

    def test_production_refuses_simulated_render_but_can_list(self):
        c = self.fixture(purpose='production')
        with self.assertRaisesRegex(ValueError, 'DEMO'):
            prepare(c, self.script(), ['example'])
        self.assertEqual(prepare(c, self.script(), ['--list'])[1], ['--list'])


if __name__ == '__main__':
    unittest.main()
