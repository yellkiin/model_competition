"""Filesystem deployment tests; controlled files are not scientific evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from workflow_deployment import SKILLS, REQUIRED, PROTECTED, deploy_legacy as deploy, source_plan, native_path

class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        # TemporaryDirectory cleanup must also use Windows extended paths when
        # the test deliberately creates assets beyond MAX_PATH.
        self.temp.name=str(native_path(self.temp.name))
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'template'
        self.target=Path(self.temp.name)/'project'
        for rel in ('AGENTS.md','CLAUDE.md','README.md',*REQUIRED):
            path=self.root/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('maintained '+rel,encoding='utf-8')
        for skill in SKILLS:
            path=self.root/'.agents/skills'/skill/'SKILL.md'
            path.parent.mkdir(parents=True,exist_ok=True);path.write_text('controlled skill '+skill,encoding='utf-8')

    def test_complete_trees_and_both_runtimes_are_deployed(self):
        helper=self.root/'华为杯_论文规范模板/tools/new_dependency.py'
        helper.write_text('dependency = True',encoding='utf-8')
        report=deploy(self.root,self.target)
        self.assertEqual(report['status'],'PASS')
        self.assertEqual((self.target/helper.relative_to(self.root)).read_bytes(),helper.read_bytes())
        for skill in SKILLS:
            for runtime in ('.agents','.claude'):
                self.assertEqual((self.target/runtime/'skills'/skill/'SKILL.md').read_bytes(),
                                 (self.root/'.agents/skills'/skill/'SKILL.md').read_bytes())

    def test_scientific_files_preserved_and_not_imported_from_template(self):
        for name in PROTECTED:
            for root,text in ((self.root,'template demo'),(self.target,'existing science')):
                path=root/name/'unchanged.bin';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')
        report=deploy(self.root,self.target)
        self.assertEqual(report['protected_files'],len(PROTECTED))
        self.assertEqual(report['protected_differences'],[])
        for name in PROTECTED:self.assertEqual((self.target/name/'unchanged.bin').read_text(),'existing science')

    def test_replacements_are_backed_up_and_redeploy_is_unchanged(self):
        self.target.mkdir()
        (self.target/'AGENTS.md').write_text('old rules',encoding='utf-8')
        report=deploy(self.root,self.target)
        row=next(r for r in report['copies'] if r['relative_path']=='AGENTS.md')
        self.assertEqual(Path(row['backup']).read_text(),'old rules')
        self.assertTrue(all(not r['changed'] for r in deploy(self.root,self.target)['copies']))

    def test_missing_required_source_rejected_before_any_target_write(self):
        (self.root/REQUIRED[0]).unlink()
        with self.assertRaisesRegex(ValueError,'Missing required'):deploy(self.root,self.target)
        self.assertFalse(self.target.exists())

    def test_destination_conflict_rejected_before_other_files_change(self):
        (self.target/'华为杯_论文规范模板/gmcm-layout.sty').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'not a file'):deploy(self.root,self.target)
        self.assertFalse((self.target/'AGENTS.md').exists())

    def test_cache_excluded_and_mirror_mode_leaves_codex_and_science_untouched(self):
        cache=self.root/'华为杯_论文规范模板/tools/__pycache__/cached.pyc'
        cache.parent.mkdir();cache.write_bytes(b'cache')
        self.assertFalse(any('__pycache__' in name for name in source_plan(self.root)))
        report=deploy(self.root,mirrors_only=True)
        self.assertTrue(all(r['relative_path'].startswith('.claude/') for r in report['copies']))

    def test_ancestor_target_rejected(self):
        with self.assertRaisesRegex(ValueError,'ancestor'):deploy(self.root,self.root.parent)

    def test_long_nested_skill_asset_path_is_copied(self):
        path=self.root/'.agents/skills/academic-figure-skill/assets'/('nested_'*15)/('asset_'*15+'.txt')
        native_path(path.parent).mkdir(parents=True)
        native_path(path).write_bytes(b'controlled long-path asset')
        self.assertGreater(len(str(path)),260)
        report=deploy(self.root,self.target)
        self.assertEqual(report['status'],'PASS')
        self.assertEqual(native_path(self.target/path.relative_to(self.root)).read_bytes(),native_path(path).read_bytes())

    def test_long_asset_inventory_does_not_silently_omit_image(self):
        from PIL import Image
        from build_academic_figure_asset_index import files, file_entry
        raw=str(self.root)
        normal=Path(raw[4:] if raw.startswith('\\\\?\\') else raw)
        path=normal/'assets'/('nested_'*18)/('image_'*18+'.png')
        native_path(path.parent).mkdir(parents=True)
        Image.new('RGB',(8,9),'white').save(native_path(path))
        self.assertGreater(len(str(path)),260)
        self.assertIn(path,files(normal))
        entry=file_entry(path,normal)
        self.assertNotIn('inspection_error',entry)
        self.assertEqual((entry['width'],entry['height']),(8,9))

if __name__=='__main__':unittest.main()
