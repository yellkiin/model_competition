"""Routing regressions use actual files/readers; synthetic attestations are unit fixtures only."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from build_academic_figure_asset_index import sha, write_json
from init_visual_plan import make_problem
from inspect_visual_materials import scan, inspect_file
from visual_routes import (route, routing_errors, audit_routes, media_sidecar,
                           academic_panels, primary_output, paper_specs)
from audit_media_figures import prepare, extend_draft, audit_media, MAP_CHECKS
from candidate_figures import audit_figure


def fixture(root):
    (root / 'data').mkdir(exist_ok=True)
    Image.new('RGB', (200, 140), '#236d80').save(root / 'data/source.png')
    (root / 'layout.tex').write_text('Physical page width 160 mm, figure width 100 mm.', encoding='utf8')
    (root / 'render.py').write_text('# isolated fixture source\n', encoding='utf8')
    write_json(root / 'inventory.json', scan(root, ['data']))
    p = make_problem('q1', 'standard')
    p['claims'] = [{'claim_id': 'q1-C01', 'text': 'Inspect a native observation'}]
    f = {'figure_id': 'native1', 'scope': 'q1', 'scientific_question': 'Native observation visibility',
         'claim_ids': ['q1-C01'], 'evidence_ids': ['q1-E01'], 'archetype': 'image_plate_quant',
         'layout': 'single image', 'hero_panel': 'a', 'script': 'render.py', 'status': 'planned',
         'count_role': 'independent_science',
         'outputs': {'primary': 'result.png', 'preview': 'result.png'},
         'statistics_report': 'stats.json', 'qa_report': 'qa.json',
         'paper': {'chapter': 'q1', 'label': 'fig:native1', 'caption': 'Native observation',
                   'reference_context': 'The image preserves spatial evidence.'},
         'panels': [{'panel_id': 'a', 'question': 'Inspect the original observation',
                     'figure_type': 'source image', 'figure_family': 'native_image',
                     'result_file': 'data/source.png', 'fields': ['RGB'], 'units': ['pixel'],
                     'visual_encoding': 'native pixels', 'rendering_route': 'native_media',
                     'content_kind': 'source_image', 'route_reason': 'Direct inspection of the native image pixels'}]}
    p['figures'] = [f]
    plan = {'schema_version': '1.1', 'project_title': 'unit fixture', 'plan_status': 'ready',
            'visual_encoding_path': 'encoding.md', 'global_figures': [], 'flowcharts': [], 'problems': [p]}
    pp = root / 'plan.json'
    write_json(pp, plan)
    media = prepare(pp, 'codex')
    rec = media['figures'][0]
    rec.update(target_width_mm=100, output_kind='raster', scientific_contribution='Independent native spatial evidence',
               count_role='independent_science', run_record_path='run.json', qa_path='qa.json',
               classification_review={'reviewed': True, 'tool_ref': 'UNIT TEST fixture only',
                                      'observation': 'Synthetic attestation for routing validation only'})
    rec['paper_geometry'] = {'source_tex': 'layout.tex', 'source_sha256': sha(root / 'layout.tex'),
                             'basis': 'Test fixture uses 100 mm image width'}
    panel = rec['panels'][0]
    panel.update(sources=[{'path': 'data/source.png', 'sha256': sha(root / 'data/source.png'),
                           'role': 'observation', 'origin': 'Synthetic unit fixture, not contest data',
                           'permission': 'Generated within isolated unit test', 'inventory_path': 'inventory.json',
                           'metadata_reviewed': True, 'metadata_observation': 'UNIT TEST native RGB image 200 x 140'}],
                 interpretation='Direct pixels preserve the original spatial geometry', geographic=False,
                 parameters={'pages_frames': [0], 'display_transform': 'identity'},
                 encoding={'kind': 'true_color', 'description': 'Original RGB values retained unchanged'})
    write_json(media_sidecar(pp), media)
    return pp, plan, media


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pp, self.plan, self.media = fixture(self.root)

    def save(self):
        write_json(self.pp, self.plan)
        write_json(media_sidecar(self.pp), self.media)

    def gate(self, stage='plan'):
        self.save()
        return audit_routes(self.pp, stage, self.root, 'codex')

    def codes(self, result):
        return json.dumps(result['failures'])

    def test_native_passes_without_academic_assets_or_gallery(self):
        with patch('audit_academic_figure_assets.build_index', side_effect=AssertionError('Must not scan atlas')):
            result = self.gate()
        self.assertEqual(result['status'], 'PASS', result['failures'])
        self.assertFalse(self.pp.with_suffix('.assets.json').exists())
        self.assertEqual(audit_figure(self.root, self.pp, 'native1', 'plan', 'codex')['status'], 'PASS')

    def test_legacy_panel_defaults_academic_and_cannot_skip_assets(self):
        f = self.plan['problems'][0]['figures'][0]
        f['outputs'] = {'vector': 'result.pdf', 'preview': 'result.png'}
        p = f['panels'][0]
        for k in ('rendering_route', 'content_kind', 'route_reason'):
            p.pop(k)
        p.update(asset_mode='visual_adapt', asset_directory='assets/reference')
        self.assertEqual(route(p), 'academic')
        self.assertIn('asset_gate_input_error', self.codes(self.gate()))

    def test_statistics_cannot_claim_gis_exemption(self):
        p = self.plan['problems'][0]['figures'][0]['panels'][0]
        p.update(rendering_route='domain_render', content_kind='gis_map', figure_family='comparison_ranking')
        self.assertIn('statistics_require_academic', self.codes(self.gate()))

    def test_unknown_route_is_failure(self):
        self.plan['problems'][0]['figures'][0]['panels'][0]['rendering_route'] = 'anything'
        self.assertIn('unknown_route', self.codes(self.gate()))

    def test_mixed_only_academic_panel_needs_reference(self):
        f = self.plan['problems'][0]['figures'][0]
        p = copy.deepcopy(f['panels'][0])
        p.update(panel_id='b', rendering_route='academic', figure_family='comparison_ranking',
                 asset_mode='visual_adapt', asset_directory='assets/reference')
        f['panels'].append(p)
        f['outputs']['vector'] = 'result.pdf'
        f['outputs']['primary'] = 'result.pdf'
        self.assertEqual([p['panel_id'] for p in academic_panels(f)], ['b'])
        result = self.gate()
        self.assertIn('asset_gate_input_error', self.codes(result))
        self.assertEqual(result['media']['status'], 'PASS', result['media']['failures'])

    def test_missing_source_and_changed_source_fail(self):
        Image.new('RGB', (200, 140), 'red').save(self.root / 'data/source.png')
        self.assertIn('source_current', self.codes(self.gate()))
        (self.root / 'data/source.png').unlink()
        self.assertEqual(self.gate()['status'], 'FAIL')

    def test_pending_classification_and_unknown_metadata_fail(self):
        self.media['figures'][0]['classification_review']['reviewed'] = False
        self.assertIn('classification_reviewed', self.codes(self.gate()))
        self.media['figures'][0]['classification_review']['reviewed'] = True
        self.media['figures'][0]['panels'][0]['sources'][0]['metadata_reviewed'] = False
        self.assertIn('inventory_verified', self.codes(self.gate()))

    def test_source_reference_cannot_count_as_experimental_result(self):
        self.media['figures'][0]['panels'][0]['sources'][0]['role'] = 'reference'
        self.assertIn('reference_not_result', self.codes(self.gate()))

    def test_initializer_does_not_approve(self):
        blank = prepare(self.pp, 'codex')
        self.assertFalse(blank['figures'][0]['classification_review']['reviewed'])
        self.assertEqual(blank['figures'][0]['panels'][0]['sources'], [])
        self.assertEqual(blank['figures'][0]['target_width_mm'], 0)

    def test_extend_initializer_appends_drafts_and_preserves_reviews(self):
        second = copy.deepcopy(self.plan['problems'][0]['figures'][0])
        second['figure_id'] = 'native2'
        self.plan['problems'][0]['figures'].append(second)
        self.save()
        merged = extend_draft(self.pp, 'codex')
        self.assertEqual(merged['figures'][0], self.media['figures'][0])
        self.assertFalse(merged['figures'][1]['classification_review']['reviewed'])
        with self.assertRaisesRegex(ValueError, 'runtime/purpose differs'):
            extend_draft(self.pp, 'claude')

    def test_render_without_execution_and_viewing_fails(self):
        result = self.gate('render')
        self.assertEqual(result['status'], 'FAIL')

    def test_runtime_mismatch_fails(self):
        self.media['runtime'] = 'claude'
        self.assertIn('media_runtime_matches', self.codes(self.gate()))

    def test_cyclic_structure_media_reference_fails_without_recursion(self):
        from audit_diagram_workflow import sidecar
        f = self.plan['problems'][0]['figures'][0]['panels'][0]
        f.update(rendering_route='structure', content_kind='physics')
        p = self.media['figures'][0]['panels'][0]
        p.update(rendering_route='structure', content_kind='physics',
                 structure_reference={'plan_path': 'plan.json', 'diagram_id': 'physics1'})
        write_json(sidecar(self.pp), {'diagrams': [{'diagram_id': 'physics1', 'kind': 'physics',
                                                   'outputs': {'vector': 'data/source.png'}}]})
        def circular(*args, **kwargs):
            return audit_media(self.pp, 'plan', self.root, 'codex')
        with patch('audit_diagram_workflow.audit', side_effect=circular):
            result = self.gate()
        self.assertIn('cyclic_visual_dependency', self.codes(result))

    def test_structure_component_does_not_require_unrelated_paper_completion(self):
        from audit_diagram_workflow import audit, sidecar
        ref = self.root / '.agents/skills/engineering-physics-mechanism-diagram/reference.txt'
        ref.parent.mkdir(parents=True)
        ref.write_text('UNIT TEST reviewed geometry reference', encoding='utf8')
        facts = self.root / 'facts.txt'
        facts.write_text('UNIT TEST geometry: two positions connected by an observation path.', encoding='utf8')
        d = {'diagram_id': 'physics1', 'kind': 'physics', 'problem_id': 'q1', 'placement': 'panel',
             'backend': 'tikz', 'backend_reason': 'UNIT TEST reversible geometry source',
             'scientific_question': 'Inspect the relationship between two geometric positions',
             'sources': [{'path': 'facts.txt', 'sha256': sha(facts), 'locator': 'whole fixture'}],
             'references': [{'path': ref.relative_to(self.root).as_posix(), 'sha256': sha(ref),
                             'reviewed': True, 'observation': 'UNIT TEST reference geometry inspection',
                             'decision': 'UNIT TEST geometric positioning reuse'}],
             'panels': [{'panel_id': pid, 'kind': 'geometry', 'content': 'Test point '+pid,
                         'source_path': 'facts.txt', 'source_locator': 'fixture first line',
                         'semantic_review': 'UNIT TEST position corresponds to the source description'} for pid in ('a','b')],
             'connections': [{'from': 'a', 'to': 'b', 'type': 'geometry',
                              'meaning': 'Observation path between documented fixture positions',
                              'source_locator': 'fixture first line'}],
             'paper': {'label': 'fig:physics1', 'caption': 'UNIT TEST geometry',
                       'reference_context': 'Geometry explanation for isolated component validation'}}
        write_json(sidecar(self.pp), {'schema_version': '1.0', 'runtime': 'codex', 'purpose': 'production',
            'questions': [{'problem_id': 'q1', 'chapter_id': 'q1', 'supporting_question_id': 'q1', 'overview_id': 'not-ready'}],
            'diagrams': [d], 'figure_accounting': [], 'paper_review_path': ''})
        component = audit(self.pp, 'plan', self.root, 'codex', diagram_ids=['physics1'])
        self.assertEqual(component['status'], 'PASS', component['failures'])
        full = audit(self.pp, 'plan', self.root, 'codex')
        self.assertEqual(full['status'], 'FAIL')
        self.assertIn('figure_accounting_gate', self.codes(full))

    def test_raster_primary_collected_without_vector_claim(self):
        self.assertEqual(primary_output(self.plan['problems'][0]['figures'][0]), 'result.png')
        self.assertEqual(paper_specs(self.pp)[0]['vector_path'], 'result.png')


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_all_gif_frames_and_numbered_sequences(self):
        a, b = Image.new('RGB', (30, 20), 'red'), Image.new('RGB', (30, 20), 'blue')
        a.save(self.root / 'frame001.gif', save_all=True, append_images=[b], duration=100)
        result = scan(self.root, ['.'])
        self.assertEqual(result['files'][0]['metadata']['frame_count'], 2)
        self.assertEqual(len(result['numbered_sequence_candidates']['.']), 1)

    def test_corruption_and_unknown_raw_are_visible(self):
        (self.root / 'bad.png').write_bytes(b'invalid')
        (self.root / 'raw.bin').write_bytes(b'1234')
        result = scan(self.root, ['.'])
        self.assertTrue(all(r['read_status'] == 'blocked' and r['attempts'] for r in result['files']))

    def test_raw_byte_count_and_endianness(self):
        (self.root / 'raw.bin').write_bytes(b'1234')
        specs = {'raw.bin': {'shape': [2, 2], 'dtype': 'uint8', 'byte_order': 'not_applicable',
                             'layout': 'C', 'channel_order': 'gray', 'evidence': 'UNIT TEST raw layout'}}
        self.assertEqual(inspect_file(self.root, self.root / 'raw.bin', specs)['read_status'], 'readable')
        specs['raw.bin']['shape'] = [3, 2]
        self.assertEqual(inspect_file(self.root, self.root / 'raw.bin', specs)['read_status'], 'blocked')

    def test_shapefile_missing_companions(self):
        (self.root / 'map.shp').write_bytes(b'bad')
        result = inspect_file(self.root, self.root / 'map.shp')
        self.assertEqual(result['read_status'], 'blocked')
        self.assertIn('.shx', result['attempts'][0]['error'])


if __name__ == '__main__':
    unittest.main()
