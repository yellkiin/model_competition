"""Shared inventory/preview and provenance-boundary integration fixtures."""
import json
from pathlib import Path
import unittest

from PIL import Image
import test_workspace_context as fixtures
import workspace_context as wc
from build_academic_figure_asset_index import build_index, contact_sheets, safe
from visual_routes import routing_errors


class AcademicWorkspaceTests(unittest.TestCase):
    setUp = fixtures.WorkspaceTests.setUp
    tearDown = fixtures.WorkspaceTests.tearDown

    def prepare(self, runtime):
        for side in wc.RUNTIMES.values():
            root = self.root / side / 'skills/academic-figure-skill'
            (root / 'references').mkdir(parents=True)
            (root / 'references/directory-map.md').write_text('| **TestFamily** | fixture | test only | description |\n', encoding='utf8')
            (root / 'assets/figure-atlas').mkdir(parents=True)
            (root / 'assets/figures/TestFamily').mkdir(parents=True)
            Image.new('RGB', (60, 40), 'blue').save(root / 'assets/figure-atlas/reference.png')
            Image.new('RGB', (60, 40), 'red').save(root / 'assets/figures/TestFamily/example.png')
            (root / 'assets/figures/TestFamily/example.py').write_text('# fixture only\n')
        return wc.create_workspace(self.root, runtime)

    def test_index_matches_template_and_contacts_stay_in_workspace(self):
        for runtime in wc.RUNTIMES:
            # Build both runtimes once per fixture root; independent test
            # subdirectories avoid changing an existing run's template hashes.
            if runtime == 'codex':
                c = self.prepare(runtime)
            else:
                c = wc.create_workspace(self.root, runtime)
            expected = build_index(self.root, runtime=runtime)
            actual = build_index(c.workspace_root, runtime=runtime)
            self.assertEqual(actual, expected)
            self.assertEqual(actual['counts']['inventory_files'], 3)
            out = c.write_path('求解/参考总览')
            pages = contact_sheets(c.workspace_root, actual, out)
            self.assertTrue(pages)
            manifest = json.loads((out / 'contact_manifest.json').read_text(encoding='utf8'))
            self.assertEqual(manifest['errors'], [])
            self.assertEqual(len(manifest['units']), 2)
            review = json.loads((out / 'gallery_review.json').read_text(encoding='utf8'))
            self.assertTrue(all(not p['reviewed'] for p in review['pages']))
            self.assertEqual(c.check_shared()['status'], 'PASS')
            for row in manifest['units']:
                self.assertTrue((c.workspace_root / row['preview_path']).is_file())
                self.assertTrue(wc.resource_path(c.workspace_root, row['asset_path'], runtime).is_file())

    def test_shared_reference_does_not_relax_scientific_safe(self):
        c = self.prepare('codex')
        raw = '.agents/skills/academic-figure-skill/assets/figure-atlas/reference.png'
        self.assertTrue(wc.resource_path(c.workspace_root, raw, 'codex').is_file())
        self.assertFalse(safe(c.workspace_root, raw).exists())
        with self.assertRaises(ValueError):
            safe(c.workspace_root, '../' + raw)
        with self.assertRaisesRegex(ValueError, '运行时'):
            build_index(c.workspace_root, runtime='claude')

    def test_statistics_cannot_be_relabelled_as_native(self):
        figure = {'figure_id': 'q1_F1', 'count_role': 'independent_science',
                  'outputs': {'primary': '求解/p.png'},
                  'panels': [{'panel_id': 'a', 'rendering_route': 'native_media', 'content_kind': 'source_image',
                              'route_reason': 'misleading test fixture reason', 'figure_family': 'prediction_diagnostic'}]}
        self.assertIn('q1_F1:a:statistics_require_academic', routing_errors(figure))

    def test_changed_asset_cannot_reuse_index(self):
        c = self.prepare('codex')
        build_index(c.workspace_root, runtime='codex')
        (self.root / '.agents/skills/academic-figure-skill/assets/figures/TestFamily/example.py').write_text('# changed')
        with self.assertRaisesRegex(ValueError, '共享资源已变化'):
            build_index(c.workspace_root, runtime='codex')


if __name__ == '__main__':
    unittest.main()
