"""Resource adoption is not scientific approval; unrelated assets stay separate."""
import copy
import json
from pathlib import Path
import shutil
import unittest

import test_workspace_context as fixtures
import workspace_context as wc
from workspace_resources import dependencies, evidence_current, adopt_resources, rebind_template


class ResourceTests(unittest.TestCase):
    setUp = fixtures.WorkspaceTests.setUp
    tearDown = fixtures.WorkspaceTests.tearDown

    def create(self):
        for runtime in wc.RUNTIMES.values():
            folder = self.root / runtime / 'skills/academic-figure-skill/assets'
            folder.mkdir(parents=True)
            (folder / 'reference.txt').write_text('first design', encoding='utf8')
        (self.root / '华为杯_求解规范/rules.md').write_text('original scientific gate', encoding='utf8')
        return wc.create_workspace(self.root, 'codex')

    def test_adoption_preserves_record_and_invalidates_affected_stamp(self):
        c = self.create()
        original = {'status': 'PASS', 'resource_dependencies': dependencies(c.workspace_root, 'codex', 'academic')}
        wc.atomic_json(c.workspace_root / '求解/old-qa.json', original)
        original_hash = wc.file_hash(c.workspace_root / '求解/old-qa.json')
        (self.root / '华为杯_求解规范/rules.md').write_text('changed scientific gate', encoding='utf8')
        with self.assertRaisesRegex(ValueError, '共享资源变化'):
            evidence_current(c.workspace_root, 'codex', 'academic', original)
        report = adopt_resources(c, '求解规范修订后采用新版本并重新检查相关图件')
        self.assertEqual(report['status'], 'ADOPTED_REVALIDATION_REQUIRED')
        self.assertIn('求解/old-qa.json', [r['record'] for r in report['affected_evidence']])
        self.assertEqual(wc.file_hash(c.workspace_root / '求解/old-qa.json'), original_hash)
        self.assertFalse(evidence_current(c.workspace_root, 'codex', 'academic', original))
        self.assertTrue((Path(report['report_path']).parent / '变更前清单.json').is_file())

    def test_media_does_not_inherit_unrelated_atlas_changes(self):
        c = self.create()
        media = {'resource_dependencies': dependencies(c.workspace_root, 'codex', 'media')}
        academic = {'resource_dependencies': dependencies(c.workspace_root, 'codex', 'academic')}
        (self.root / '.agents/skills/academic-figure-skill/assets/reference.txt').write_text('new design', encoding='utf8')
        adopt_resources(c, '参考图库更新，仅实际依赖其设计的图件需要重新复核')
        self.assertTrue(evidence_current(c.workspace_root, 'codex', 'media', media))
        self.assertFalse(evidence_current(c.workspace_root, 'codex', 'academic', academic))
        self.assertFalse(evidence_current(c.workspace_root, 'codex', 'media', {'status': 'PASS'}))

    def test_test_code_changes_do_not_invalidate_scientific_stamp(self):
        c = self.create()
        before = dependencies(c.workspace_root, 'codex', 'media')
        (self.root / '华为杯_求解规范/test_extra.py').write_text('# added maintenance unit test', encoding='utf8')
        adopt_resources(c, '仅新增维护测试，生产绘图与科学规范未发生变化')
        self.assertEqual(before, dependencies(c.workspace_root, 'codex', 'media'))

    def test_relink_requires_same_resource_identity(self):
        c = self.create()
        target = self.root.parent / 'new shared resources'
        shutil.copytree(self.root, target, ignore=shutil.ignore_patterns('workshop_v*'))
        (self.root / 'AGENTS.md').unlink()
        r = rebind_template(c.workspace_root, target, 'codex')
        self.assertEqual(r['status'], 'RELINKED_IDENTICAL_RESOURCES')
        new = wc.resolve_context(c.workspace_root)
        self.assertEqual(new.template_root, target)
        self.assertEqual(new.check_shared()['status'], 'PASS')
        (target / 'CLAUDE.md').write_text('different version', encoding='utf8')
        before = wc.file_hash(c.workspace_root / wc.MANIFEST)
        with self.assertRaisesRegex(ValueError, '身份不同'):
            rebind_template(c.workspace_root, target, 'codex')
        self.assertEqual(before, wc.file_hash(c.workspace_root / wc.MANIFEST))

    def test_new_production_dependency_is_listed_as_affected(self):
        c = self.create()
        wc.atomic_json(c.workspace_root / '求解/old-qa.json', {
            'status': 'PASS', 'resource_dependencies': dependencies(c.workspace_root, 'codex', 'media')})
        (self.root / '华为杯_求解规范/new_helper.py').write_text('# new shared producer', encoding='utf8')
        result = adopt_resources(c, '新增生产工具依赖，记录既有审核需重新运行与检查')
        self.assertEqual(result['affected_evidence'][0]['changed_dependencies'], ['华为杯_求解规范/new_helper.py'])

    def test_legacy_compatibility_is_not_new_workspace_approval(self):
        self.assertTrue(evidence_current(self.root, 'codex', 'media', {}))
        c = self.create()
        self.assertFalse(evidence_current(c.workspace_root, 'codex', 'media', {}))


if __name__ == '__main__':
    unittest.main()
