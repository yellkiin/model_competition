"""New deployment mode must register shared roots, never copy maintenance trees."""
from pathlib import Path
import unittest
import test_workspace_context as fixtures
from workflow_deployment import deploy
from workspace_context import SHARED


class SharedDeploymentTests(unittest.TestCase):
    setUp = fixtures.WorkspaceTests.setUp
    tearDown = fixtures.WorkspaceTests.tearDown

    def test_default_creates_and_explicit_target_resumes(self):
        report = deploy(self.root, runtime='codex', inputs=['题目/题目.txt'])
        self.assertEqual(report['status'], 'PASS')
        run = Path(report['project_root'])
        self.assertEqual(run.name, 'workshop_v1')
        self.assertEqual(report['copies'], [])
        for name in SHARED:
            self.assertFalse((run / name).exists())
        second = deploy(self.root, run, runtime='codex')
        self.assertEqual(second['project_root'], str(run))
        self.assertFalse((self.root / 'workshop_v2').exists())
        self.assertFalse((self.root / 'output').exists())

    def test_existing_legacy_directory_not_implicitly_updated(self):
        legacy = self.root / '2025E_研究v2'
        legacy.mkdir()
        (legacy / 'AGENTS.md').write_text('historical bytes')
        with self.assertRaises(ValueError):
            deploy(self.root, legacy, runtime='codex')
        self.assertEqual((legacy / 'AGENTS.md').read_text(), 'historical bytes')

    def test_legacy_cannot_copy_into_workshop(self):
        report = deploy(self.root, runtime='codex')
        with self.assertRaisesRegex(ValueError, '禁止'):
            deploy(self.root, report['project_root'], mode='legacy')

    def test_mirror_maintenance_must_be_explicit(self):
        with self.assertRaises(ValueError):
            deploy(self.root, mirrors_only=True)


if __name__ == '__main__':
    unittest.main()
