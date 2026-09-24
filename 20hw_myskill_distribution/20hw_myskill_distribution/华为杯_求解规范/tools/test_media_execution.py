"""Real reader/execution regressions; synthetic review fixtures are not visual approvals."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from audit_media_figures import MAP_CHECKS, audit_media, review_map
from build_academic_figure_asset_index import sha, write_json
from extract_visual_materials import extract
from inspect_visual_materials import inspect_file, scan
from run_media_figure import execute, prepare_qa
from test_visual_routes import fixture
from visual_routes import media_sidecar


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pp, self.plan, self.media = fixture(self.root)
        (self.root / 'render.py').write_text(
            "from PIL import Image\nimport json\n"
            "Image.open('data/source.png').save('result.png')\n"
            "with open('stats.json', 'w') as f: json.dump({'operation': 'identity'}, f)\n",
            encoding='utf8')

    def save(self):
        write_json(self.pp, self.plan)
        write_json(media_sidecar(self.pp), self.media)

    def execute_and_prepare(self):
        self.save()
        run = execute(self.root, self.pp, 'native1', 'codex', [], sys.executable)
        self.assertEqual(run['status'], 'EXECUTED_REVIEW_REQUIRED', run)
        qa = prepare_qa(self.root, self.pp, 'native1', 'codex')
        self.assertEqual(qa['status'], 'REVIEW_REQUIRED')
        self.assertTrue(all(v['reviewed'] is False for v in qa['views']))
        return qa

    def fixture_review(self, qa):
        # Deliberately synthetic attestations exercise validation, not actual viewing.
        qa['status'] = 'PASS'
        for v in qa['views']:
            v.update(reviewed=True, tool_ref='UNIT TEST ONLY', observation='Synthetic unit assertion of the review schema')
        for v in qa['dimensions'].values():
            v.update(status='PASS', observation='Synthetic unit assertion of the review schema')
        qa['resolution_review'].update(reviewed=True, observation='Native 200 by 140 test fixture only',
                                       source_pixel_basis='Original fixture uses 200 by 140 pixels')
        self.plan['problems'][0]['figures'][0]['status'] = 'qa_pass'
        self.media['figures'][0]['status'] = 'qa_pass'
        write_json(self.root / 'qa.json', qa)
        self.save()

    def test_real_run_remains_unapproved_until_review(self):
        original = sha(self.root / 'data/source.png')
        qa = self.execute_and_prepare()
        self.assertEqual(audit_media(self.pp, 'render', self.root, 'codex')['status'], 'FAIL')
        self.fixture_review(qa)
        result = audit_media(self.pp, 'render', self.root, 'codex')
        self.assertEqual(result['status'], 'PASS', result['failures'])
        self.assertEqual(original, sha(self.root / 'data/source.png'))
        with self.assertRaisesRegex(ValueError, 'Preserve execution history'):
            execute(self.root, self.pp, 'native1', 'codex', [])

    def test_mixed_evidence_cannot_overwrite_other_route(self):
        f = self.plan['problems'][0]['figures'][0]
        academic = copy.deepcopy(f['panels'][0])
        academic.update(panel_id='b', rendering_route='academic', figure_family='comparison_ranking',
                        asset_directory='assets/ref', asset_mode='visual_adapt')
        f['panels'].append(academic)
        f['outputs'].update(primary='result.pdf', vector='result.pdf')
        self.save()
        write_json(self.pp.with_suffix('.assets.json'), {'figures': [{'figure_id': 'native1',
                   'run_record_path': self.media['figures'][0]['run_record_path']}]})
        # Isolate path validation: the full mixed academic gate has separate integration coverage.
        with patch('candidate_figures.audit_figure', return_value={'status': 'PASS'}), \
                patch('run_academic_figure.execute') as runner:
            with self.assertRaisesRegex(ValueError, 'evidence paths must be distinct'):
                execute(self.root, self.pp, 'native1', 'codex', [])
            runner.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'QA paths must be distinct'):
            prepare_qa(self.root, self.pp, 'native1', 'codex')

    def test_unrelated_pdf_cannot_be_review_evidence(self):
        import pymupdf as fitz
        qa = self.execute_and_prepare()
        v = next(v for v in qa['views'] if v['kind'] == 'pdf_page')
        pdf = self.root / v['pdf_path']
        with fitz.open() as d:
            d.new_page(width=100 * 72 / 25.4, height=70 * 72 / 25.4)
            d.save(self.root / 'unrelated.pdf')
        v.update(pdf_path='unrelated.pdf', pdf_sha256=sha(self.root / 'unrelated.pdf'))
        with fitz.open(self.root / 'unrelated.pdf') as d:
            d[0].get_pixmap(dpi=v['dpi'], alpha=False).save(self.root / v['path'])
        v['sha256'] = sha(self.root / v['path'])
        self.fixture_review(qa)
        result = audit_media(self.pp, 'render', self.root, 'codex')
        self.assertIn('pdf_represents_primary', json.dumps(result['failures']))

    def test_changed_processing_parameter_invalidates_execution(self):
        qa = self.execute_and_prepare()
        self.fixture_review(qa)
        self.media['figures'][0]['panels'][0]['parameters']['display_transform'] = 'contrast transform'
        self.save()
        result = audit_media(self.pp, 'render', self.root, 'codex')
        self.assertIn('media_contract_current', json.dumps(result['failures']))

    def test_gallery_and_body_selection_preserve_media_evidence(self):
        from audit_diagram_workflow import initialize
        from candidate_figures import build_gallery, select_paper
        qa = self.execute_and_prepare()
        self.fixture_review(qa)
        initialize(self.pp, 'codex')
        candidate = {'figure_id': 'native1', 'question_id': 'q1', 'plan_path': 'plan.json',
                     'quality': 'qualified', 'destination': 'reserve',
                     'scientific_question': 'Inspect native fixture geometry',
                     'conclusion': 'Synthetic fixture retains pixel geometry', 'limitations': 'UNIT TEST only',
                     'selection_reason': 'Exercise candidate media display and source links', 'recommended_section': 'q1'}
        registry = self.root / 'registry.json'
        write_json(registry, {'questions': [{'question_id': 'q1', 'completion_review': None}], 'candidates': [candidate]})
        gallery = build_gallery(self.root, registry, self.root / '待选图库', 'codex')
        self.assertEqual(gallery['qualified_reserve_count'], 1)
        page = (self.root / '待选图库/index.html').read_text(encoding='utf8')
        self.assertIn('../result.png', page)
        candidate['destination'] = 'paper'
        write_json(registry, {'candidates': [candidate]})
        result = select_paper(self.root, registry, self.pp, self.root / 'selected.json', 'codex')
        self.assertEqual(result['status'], 'SELECTED_REQUIRES_BODY_AND_PAPER_AUDIT')
        self.assertFalse((self.root / 'selected.assets.json').exists())
        self.assertTrue((self.root / 'selected.media.json').exists())
        selected = audit_media(self.root / 'selected.json', 'render', self.root, 'codex')
        self.assertEqual(selected['status'], 'PASS', selected['failures'])
        with self.assertRaisesRegex(ValueError, 'Preserve existing selected'):
            select_paper(self.root, registry, self.pp, self.root / 'selected.json', 'codex')

    def test_illustration_never_fills_scientific_quota(self):
        from figure_accounting import audit_counts
        f = self.plan['problems'][0]['figures'][0]
        f['count_role'] = 'illustration'
        diagrams = {'questions': [{'problem_id': 'q1', 'overview_id': 'missing'}], 'diagrams': [],
                    'figure_accounting': [{'figure_id': 'native1', 'problem_id': 'q1', 'purpose': 'illustration',
                        'scientific_contribution': 'UNIT TEST illustration has no independent claim',
                        'per_question': False, 'paper_total': False, 'flow_total': False}]}
        result = audit_counts(self.plan, diagrams, 'plan', self.root)
        self.assertEqual(result['paper_eligible_count'], 0)
        self.assertEqual(result['questions'][0]['independent_science_count'], 0)
        self.assertIn('independent_science_4_to_6', json.dumps(result['failures']))

    def test_declared_native_bitmap_review_matches_pdf_pixels(self):
        import pymupdf as fitz
        from audit_diagram_workflow import native_bitmap_review
        with fitz.open() as doc:
            page = doc.new_page(width=300, height=210)
            page.insert_image(page.rect, filename=str(self.root/'data/source.png'))
            item = page.get_images(full=True)[0]
            rect = page.get_image_rects(item[0])[0]
            review = {'path': 'data/source.png', 'sha256': sha(self.root/'data/source.png'),
                      'native_pixels': [200, 140], 'width_mm': rect.width*25.4/72,
                      'height_mm': rect.height*25.4/72, 'reviewed': True,
                      'tool_ref': 'UNIT TEST only', 'observation': 'UNIT TEST declared native pixel resolution'}
            self.assertTrue(native_bitmap_review(self.root, doc, item, rect, [review]))
            review['width_mm'] += 2
            self.assertFalse(native_bitmap_review(self.root, doc, item, rect, [review]))

    def test_renamed_png_detected_by_content(self):
        shutil.copyfile(self.root / 'data/source.png', self.root / 'unknown.payload')
        record = inspect_file(self.root, self.root / 'unknown.payload')
        self.assertEqual(record['read_status'], 'readable')
        self.assertEqual(record['content_signature'], 'image')
        self.assertEqual(record['metadata']['format'], 'PNG')

    def test_multidimensional_and_audio_inventory_records_real_metadata(self):
        import h5py
        import soundfile
        from netCDF4 import Dataset
        with h5py.File(self.root/'science.h5', 'w') as ds:
            v = ds.create_dataset('measurements/temperature', data=np.arange(24).reshape(2,3,4))
            v.attrs['units'] = 'K'
        hdf = inspect_file(self.root, self.root/'science.h5')
        self.assertEqual(hdf['read_status'], 'readable')
        self.assertEqual(hdf['metadata']['variables'][0]['shape'], [2,3,4])
        with Dataset(self.root/'science.nc', 'w') as ds:
            ds.createDimension('time', 2)
            ds.createDimension('height', 3)
            v = ds.createVariable('temperature', 'f4', ('time','height'), fill_value=-9999)
            v.units = 'K'
            v[:] = np.arange(6).reshape(2,3)
        nc = inspect_file(self.root, self.root/'science.nc')
        self.assertEqual(nc['read_status'], 'readable')
        self.assertEqual(nc['metadata']['variables'][0]['shape'], [2,3])
        soundfile.write(self.root/'signal.wav', np.sin(np.arange(800)/10), 8000)
        audio = inspect_file(self.root, self.root/'signal.wav')
        self.assertEqual(audio['metadata']['sample_rate'], 8000)
        self.assertEqual(audio['metadata']['channels'], 1)

    def test_tiff_inventory_includes_every_page_and_subdataset(self):
        from inspect_visual_materials import raster_info
        path = self.root / 'pages.tif'
        pages = [Image.fromarray(np.full((12, 16), n, dtype=np.uint8)) for n in (10, 80, 150)]
        pages[0].save(path, save_all=True, append_images=pages[1:])
        result = raster_info(path, {'crs': 'EPSG:4326', 'crs_evidence': 'UNIT TEST fixture CRS'})
        self.assertEqual(result['image_pages']['frame_count'], 3)
        self.assertTrue(result['image_pages']['all_frames_decoded'])
        self.assertEqual(len(result['subdatasets']), 3)
        self.assertTrue(all(s['size'] == [16, 12] for s in result['subdatasets']))

    def test_xyz_requires_column_meaning_and_matches_all_rows(self):
        np.savetxt(self.root/'cloud.xyz', [[1,2,3],[4,5,6]])
        self.assertEqual(inspect_file(self.root, self.root/'cloud.xyz')['read_status'], 'blocked')
        specs = {'cloud.xyz': {'columns': ['x','y','z'], 'units': 'm', 'evidence': 'UNIT TEST known coordinate schema'}}
        result = inspect_file(self.root, self.root/'cloud.xyz', specs)
        self.assertEqual(result['read_status'], 'readable')
        self.assertEqual(result['metadata']['bounds'], [[1,2,3],[4,5,6]])

    def test_kmz_reads_all_documents_without_extracting_or_following_links(self):
        import zipfile
        path = self.root / 'maps.kmz'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('doc.kml', '<kml><Placemark><Point><coordinates>110,35,2</coordinates></Point></Placemark></kml>')
            archive.writestr('nested/second.kml', '<kml><LineString><coordinates>111,36 112,37</coordinates></LineString><href>https://example.invalid/map</href></kml>')
        original = sha(path)
        record = inspect_file(self.root, path)
        self.assertEqual(record['read_status'], 'needs_interpretation')
        docs = record['metadata']['documents']
        self.assertEqual([d['coordinate_tuples'] for d in docs], [1, 2])
        self.assertEqual(docs[1]['xy_bounds'], [[111,36],[112,37]])
        self.assertFalse((self.root / 'nested').exists())
        self.assertEqual(sha(path), original)

    def test_shapefile_components_and_trusted_missing_prj_recovery(self):
        import fiona
        folder = self.root/'vector'
        folder.mkdir()
        shp = folder/'points.shp'
        with fiona.open(shp, 'w', driver='ESRI Shapefile', crs='EPSG:4326',
                        schema={'geometry': 'Point', 'properties': {'id': 'int'}}) as ds:
            ds.write({'geometry': {'type': 'Point', 'coordinates': (110,35)}, 'properties': {'id': 1}})
        result = inspect_file(self.root, shp)
        self.assertEqual(result['read_status'], 'readable')
        self.assertIn('vector/points.dbf', result['related_files'])
        self.assertEqual(result['metadata']['layers'][0]['features'], 1)
        shp.with_suffix('.prj').unlink()
        self.assertEqual(inspect_file(self.root, shp)['read_status'], 'blocked')
        spec = {'vector/points.shp': {'crs': 'EPSG:4326', 'crs_evidence': 'UNIT TEST original fixture writer CRS'}}
        self.assertEqual(inspect_file(self.root, shp, spec)['read_status'], 'readable')

    def test_raw_and_mat_frames_reconstructed_exactly(self):
        from scipy.io import savemat
        data = np.arange(24, dtype=np.uint8).reshape(2, 3, 4)
        (self.root / 'frames.bin').write_bytes(data.tobytes())
        spec = {'mode': 'raw', 'frames': [0, 1], 'selection_reason': 'Inspect both fixture frames without selective omission',
                'shape': [2, 3, 4], 'dtype': 'uint8', 'byte_order': 'not_applicable', 'channel_order': 'gray',
                'layout': 'C', 'frame_axis': 0, 'evidence': 'UNIT TEST array layout'}
        result = extract(self.root, 'frames.bin', 'raw_frames', spec)
        self.assertEqual(result['status'], 'EXTRACTED_REVIEW_REQUIRED', result)
        for i, row in enumerate(result['frames']):
            self.assertTrue(np.array_equal(np.asarray(Image.open(self.root / row['path'])), data[i]))
        savemat(self.root / 'frames.mat', {'frames': data})
        spec.update(mode='mat', variable='frames', axis_order_evidence='UNIT TEST frame,row,column ordering')
        result = extract(self.root, 'frames.mat', 'mat_frames', spec)
        self.assertEqual(result['status'], 'EXTRACTED_REVIEW_REQUIRED', result)
        for i, row in enumerate(result['frames']):
            self.assertTrue(np.array_equal(np.asarray(Image.open(self.root / row['path'])), data[i]))

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg/ffprobe not installed')
    def test_video_extracts_real_frame_indices_and_timestamps(self):
        subprocess.run([shutil.which('ffmpeg'), '-v', 'error', '-f', 'lavfi', '-i',
                        'testsrc=size=96x64:rate=4:duration=1', '-c:v', 'ffv1',
                        str(self.root / 'frames.mkv')], check=True, capture_output=True)
        result = extract(self.root, 'frames.mkv', 'video_frames', {
            'mode': 'video', 'frames': [0, 2, 3],
            'selection_reason': 'Start, middle and final frames of the one-second UNIT TEST'})
        self.assertEqual(result['status'], 'EXTRACTED_REVIEW_REQUIRED', result)
        self.assertEqual([r['timestamp_seconds'] for r in result['frames']], [0, .5, .75])
        self.assertTrue(all(r['native_size'] == [96, 64] for r in result['frames']))


class MapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'evidence.txt').write_text('UNIT TEST ONLY: no legal or visual approval.', encoding='utf8')
        self.panel = {'parameters': {'source_crs': 'EPSG:4326', 'target_crs': 'EPSG:4326'}, 'map_review': {
            'scope': 'china_local', 'shows_china_boundary': False, 'intended_use': 'internal',
            'official_sources': [{'url': 'https://www.mnr.gov.cn/', 'checked_date': '2026-09-09',
                'title': 'UNIT TEST source', 'version': 'UNIT TEST version', 'applicability': 'UNIT TEST internal',
                'sections': 'UNIT TEST sections', 'observation': 'UNIT TEST source reading fixture', 'reviewed': True}],
            'project_stricter_rules': 'UNIT TEST distinguishes project rules from laws',
            'evidence': [{'path': 'evidence.txt', 'sha256': sha(self.root / 'evidence.txt')}],
            'checks': {k: {'status': 'not_applicable', 'reason': 'UNIT TEST local extent fixture only',
                           'evidence_paths': ['evidence.txt']} for k in MAP_CHECKS},
            'registration': {'verified': True, 'method': 'UNIT TEST native coordinates',
                             'accuracy_evidence': 'UNIT TEST no reprojection', 'evidence_paths': ['evidence.txt']},
            'legal_review': {'status': 'required_pending', 'basis': 'UNIT TEST unresolved public approval'},
            'public_ready': False}}

    def gate(self, stage='plan'):
        failures = []
        def add(code, ok, **details):
            if not ok:
                failures.append(code)
        review_map(self.root, self.panel, 'map', stage, add)
        return failures

    def test_internal_plan_and_public_draft_are_distinct_from_release(self):
        self.assertEqual(self.gate(), [])
        self.panel['map_review']['intended_use'] = 'public'
        self.assertEqual(self.gate(), [])
        self.assertIn('map:public_release_authorized', self.gate('render'))

    def test_invalid_crs_and_boundary_scope_fail(self):
        self.panel['parameters']['source_crs'] = 'EPSG:999999999'
        self.assertIn('map:crs_parseable', self.gate())
        self.panel['map_review'].update(scope='china_full', shows_china_boundary=False)
        self.assertIn('map:full_china_boundary_required', self.gate())
        self.assertIn('map:full_china_elements', self.gate('render'))

    def test_map_review_changes_do_not_rewrite_render_contract(self):
        from visual_routes import contract_digest
        figure = {'status': 'planned', 'figure_id': 'map'}
        rec = {'panels': [copy.deepcopy(self.panel)]}
        before = contract_digest(figure, rec)
        rec['panels'][0]['map_review']['checks']['extent']['status'] = 'pass'
        self.assertEqual(before, contract_digest(figure, rec))
        rec['panels'][0]['parameters']['target_crs'] = 'EPSG:3857'
        self.assertNotEqual(before, contract_digest(figure, rec))

    def test_legal_approval_must_bind_current_map(self):
        self.panel['map_review']['legal_review'].update(status='approved', review_number='UNIT TEST',
                                                       approval_path='evidence.txt', approved_output_sha256='0'*64)
        self.assertIn('map:approved_artifact_current', self.gate('render'))

    def test_pending_checks_cannot_pass_render(self):
        self.panel['map_review']['checks']['crs_alignment']['status'] = 'pending'
        self.assertEqual(self.gate(), [])
        self.assertIn('map:map:crs_alignment', self.gate('render'))

    def test_missing_boundary_source_and_stale_evidence_fail(self):
        self.panel['map_review']['shows_china_boundary'] = True
        self.assertIn('map:approved_boundary_source', self.gate())
        (self.root / 'evidence.txt').write_text('changed evidence', encoding='utf8')
        self.assertIn('map:map_evidence_current', self.gate())

    def test_real_geotiff_crs_mismatch_is_detected(self):
        import rasterio
        from rasterio.transform import from_origin
        pp, plan, media = fixture(self.root)
        with rasterio.open(self.root / 'data/elevation.tif', 'w', driver='GTiff', width=5, height=4,
                           count=1, dtype='float32', crs='EPSG:4326', transform=from_origin(110, 40, .01, .01)) as ds:
            ds.write(np.arange(20, dtype='float32').reshape(4, 5), 1)
        write_json(self.root / 'inventory.json', scan(self.root, ['data']))
        f = plan['problems'][0]['figures'][0]['panels'][0]
        f.update(rendering_route='domain_render', content_kind='terrain', figure_family='domain_spatial', result_file='data/elevation.tif')
        p = media['figures'][0]['panels'][0]
        p.update(rendering_route='domain_render', content_kind='terrain', geographic=True,
                 map_review=copy.deepcopy(self.panel['map_review']),
                 parameters={'bands': [1], 'nodata': 'none', 'units': 'm', 'source_crs': 'EPSG:3857',
                             'target_crs': 'EPSG:4326', 'resampling': 'none', 'derivation': 'Original elevation field'})
        p['sources'][0].update(path='data/elevation.tif', sha256=sha(self.root / 'data/elevation.tif'))
        write_json(pp, plan)
        write_json(media_sidecar(pp), media)
        result = audit_media(pp, 'plan', self.root, 'codex')
        self.assertIn('source_crs_matches_metadata', json.dumps(result['failures']))


if __name__ == '__main__':
    unittest.main()
