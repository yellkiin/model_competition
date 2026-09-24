"""Contract regression fixtures are not scientific results or human review evidence."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image
from audit_diagram_workflow import sha, initialize, sidecar, audit
from overview_content import (audit_content, audit_result_source, content_digest,
                              pending_design, pending_review, prepare_overviews, RELATION_TYPES)
from figure_accounting import inventory

TEMPLATE = Path(__file__).resolve().parents[2]


class OverviewContentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for raw in ('result.json', 'validation.json', 'model.py', 'plan.json'):
            (self.root / raw).write_text('{}', encoding='utf8')
        self.fig = {'figure_id': 'f1', 'status': 'qa_pass',
                    'outputs': {'vector': 'figure.pdf', 'preview': 'figure.png'}}
        self.plan = {'problems': [{'problem_id': 'q1', 'figures': [self.fig]}]}
        design = pending_design(self.plan, 'q1')
        design.update(status='ready', verification={'status': 'verified', 'evidence': [
            {'path': raw, 'sha256': sha(self.root/raw), 'locator': 'Unit-test fixture record, not scientific evidence', 'role': role}
            for raw, role in [('result.json','result'), ('validation.json','independent_validation')]]},
            result_selection=[{'figure_id': 'f1', 'decision': 'selected', 'reason': 'Main result is complementary to the mechanism'}],
            mechanism={'applicable': True, 'category': 'state', 'panel_ids': ['m'],
                       'reason': 'Resource lifetimes explain the model constraints'},
            layout={'strategy': 'borderless_tiling', 'reading_order': ['m','r'], 'reason': 'Aligned partitions with narrow white gutters'},
            theme={'palette_ref': 'overview-macaron', 'connector_family': 'stage_heading',
                   'reason': 'Stage headings guide reading without auxiliary arrows'})
        self.d = {'diagram_id': 'q1-OVERVIEW', 'kind': 'comprehensive', 'problem_id': 'q1',
            'status': 'qa_pass', 'dependencies': ['result.json','validation.json','plan.json'],
            'sources': [], 'overview_design': design,
            'references': [{'path': '.agents/skills/engineering-physics-mechanism-diagram/assets/example.png'}],
            'panels': [{'panel_id': 'm', 'kind': 'geometry', 'mechanism_skill': 'engineering-physics-mechanism-diagram'},
                       {'panel_id': 'r', 'kind': 'result', 'visual_plan': 'plan.json', 'visual_figure_id': 'f1',
                        'detail_figure_id': 'f1', 'source_path': 'figure.png', 'reuse_mode': 'direct'}]}

    def qa(self):
        return {'overview_design_sha256': content_digest(self.d), 'overview_review': {
            k: {'status': 'pass', 'observation': 'Unit fixture only, never a real visual review'} for k in pending_review()}}

    def failures(self, stage='render', qa=None, purpose='production'):
        return {c['code'] for c in audit_content(self.root, self.plan, self.d, stage, purpose=purpose,
                    qa=self.qa() if qa is None else qa) if not c['ok']}

    def test_one_result_and_state_mechanism_pass_without_device_or_quota(self):
        self.assertEqual(self.failures(), set())

    def test_two_verified_results(self):
        self.plan['problems'][0]['figures'].append(dict(self.fig, figure_id='f2'))
        self.d['overview_design']['result_selection'].append({'figure_id':'f2','decision':'selected','reason':'Independent validation evidence selected'})
        self.d['panels'].append(dict(self.d['panels'][1],panel_id='r2',visual_figure_id='f2',detail_figure_id='f2'))
        self.d['overview_design']['layout']['reading_order'].append('r2')
        self.assertEqual(self.failures(), set())

    def test_geometric_panel_does_not_replace_available_result(self):
        self.d['panels'].pop()
        self.assertIn('selected_results_in_panels', self.failures())

    def test_candidates_cannot_be_silently_omitted(self):
        self.plan['problems'][0]['figures'].append(dict(self.fig, figure_id='f2'))
        self.assertIn('result_candidates_exact', self.failures())

    def test_redundant_result_is_reasoned_not_extra_panel(self):
        self.plan['problems'][0]['figures'].append(dict(self.fig,figure_id='f2'))
        self.d['overview_design']['result_selection'].append({'figure_id':'f2','decision':'redundant','reason':'Same trend is already covered by detailed f1'})
        self.assertEqual(self.failures(), set())

    def test_analytic_exception(self):
        self.plan['problems'][0]['figures'] = []
        self.d['panels'].pop()
        des = self.d['overview_design']
        des['result_selection'] = []
        des['omission_reason'] = 'Closed-form geometric derivation has no numerical experiments'
        des['layout']['reading_order'] = ['m']
        self.assertEqual(self.failures(), set())

    def test_mechanism_requires_actual_link_and_skill(self):
        self.d['panels'][0]['kind'] = 'process'
        self.assertIn('mechanism_panels_linked', self.failures())
        self.d['panels'][0]['kind'] = 'geometry'
        self.d['references'] = []
        self.assertIn('mechanism_skill_references', self.failures())

    def test_decorative_or_scattered_review_blocks(self):
        for key in ('mechanism_value', 'rectangular_composition', 'palette', 'navigation', 'non_text_graphics'):
            with self.subTest(key=key):
                qa=self.qa(); qa['overview_review'][key]['status']='fail'
                self.assertIn('overview_review_'+key, self.failures(qa=qa))

    def test_thumbnail_small_text_is_allowed(self):
        qa=self.qa()
        qa['overview_review']['thumbnail_detail_link']['observation']='Axes and legend unreadable at thumbnail size; f1 in body carries all detailed readings'
        self.assertEqual(self.failures(qa=qa), set())

    def test_missing_detail_link_fails(self):
        self.d['panels'][1].pop('detail_figure_id')
        self.assertIn('thumbnail_detail_links',self.failures())

    def test_unverified_results_block_completion_not_planning(self):
        self.d['overview_design']['verification']['status']='pending'
        self.assertIn('science_verification_before_composition',self.failures())
        self.d['status']='planned'; self.d['overview_design']=pending_design(self.plan,'q1')
        self.assertEqual(self.failures(stage='plan'), set())

    def test_independent_verification_cannot_be_just_result(self):
        self.d['overview_design']['verification']['evidence'].pop()
        self.assertIn('science_verification_before_composition',self.failures())

    def test_no_circular_question_completion_prerequisite(self):
        self.assertEqual(self.failures(stage='question'), set())

    def test_stale_result_and_semantics_are_detected(self):
        qa=self.qa()
        (self.root/'result.json').write_text('{"changed":1}')
        self.assertIn('verification_evidence_current',self.failures(qa=qa))
        self.d['overview_design']['theme']['connector_family']='arrow_band'
        self.assertIn('overview_semantics_current',self.failures(qa=qa))

    def test_legacy_readable_but_not_current_pass(self):
        self.d.pop('overview_design'); self.d['status']='planned'
        self.assertEqual(self.failures(stage='plan'),set())
        self.assertIn('overview_content_v2_required',self.failures())

    def test_no_auto_review(self):
        self.assertTrue(all(v['status']=='pending' and not v['observation'] for v in pending_review().values()))
        qa=self.qa();qa['overview_review']=pending_review()
        self.assertIn('overview_review_navigation',self.failures(qa=qa))

    def test_plan_recheck_reads_existing_qa_without_promoting_pending_design(self):
        # Other incomplete fixture fields fail independently; this checks QA loading.
        self.d.update(qa_path='overview.qa.json',references=[],panels=[])
        (self.root/'overview.qa.json').write_text(json.dumps(self.qa()))
        pp=self.root/'plan.json';pp.write_text(json.dumps(self.plan))
        sidecar(pp).write_text(json.dumps({'schema_version':'1.0','purpose':'production','runtime':'codex',
            'questions':[{'problem_id':'q1','overview_id':'q1-OVERVIEW'}],'diagrams':[self.d]}))
        result=audit(pp,'plan',self.root,'codex',diagram_ids=['q1-OVERVIEW'])
        row=next(r for r in result['checks'] if r['code']=='q1-OVERVIEW:overview_semantics_current')
        self.assertTrue(row['ok'])

    def test_custom_theme_requires_dependency(self):
        self.d['overview_design']['theme']['palette_ref']='theme.json'
        self.assertIn('custom_theme_tracked',self.failures())

    def test_comparison_is_supported_but_not_flow(self):
        for relation in ('comparison','correspondence'):
            self.assertIn(relation,RELATION_TYPES)
            d=dict(self.d,placement='body',flow_semantics=True,connections=[{'from':'m','to':'r','type':relation}])
            self.assertFalse(inventory(self.plan,{'diagrams':[d]})[-1]['flow'])

    def test_initialize_and_prepare_do_not_overwrite_qa(self):
        pp=self.root/'plan.json'; pp.write_text(json.dumps(self.plan))
        initialize(pp,'codex')
        data=json.loads(sidecar(pp).read_text())
        self.assertEqual(data['overview_content_version'],'2.0')
        self.d.pop('overview_design');data['diagrams']=[self.d]
        sidecar(pp).write_text(json.dumps(data))
        self.assertEqual(prepare_overviews(pp),['q1-OVERVIEW'])
        self.assertEqual(prepare_overviews(pp),[])
        current=json.loads(sidecar(pp).read_text())['diagrams'][0]
        self.assertEqual(current['overview_design']['status'],'pending')
        self.assertEqual(current['status'],'qa_pass')  # Historical flag cannot bypass the new gate.

    def test_result_source_crop_and_stale_pixels(self):
        im=Image.new('RGB',(30,20),'white'); im.putpixel((8,8),(40,80,90));im.save(self.root/'figure.png')
        im.crop((3,4,20,18)).save(self.root/'crop.png')
        p=self.d['panels'][1]
        self.d['dependencies'].append('figure.png')
        p.update(source_path='crop.png',reuse_mode='crop',derivation={'operation':'crop','original_path':'figure.png',
                 'original_sha256':sha(self.root/'figure.png'),'crop_box':[3,4,20,18]})
        self.assertTrue(all(c['ok'] for c in audit_result_source(self.root,self.d,p,self.plan,self.fig,'render','production')))
        Image.new('RGB',(17,14),'red').save(self.root/'crop.png')
        failures={c['code'] for c in audit_result_source(self.root,self.d,p,self.plan,self.fig,'render','production') if not c['ok']}
        self.assertIn('crop_pixels_match',failures)

    def test_arbitrary_derived_path_and_cross_question(self):
        p=self.d['panels'][1];p['source_path']='arbitrary.png'
        self.assertFalse(all(c['ok'] for c in audit_result_source(self.root,self.d,p,self.plan,self.fig,'plan','production')))
        p['source_path']='figure.png';self.plan['problems'][0]['problem_id']='q2'
        rows=audit_result_source(self.root,self.d,p,self.plan,self.fig,'plan','production')
        self.assertIn('result_owner_or_explicit_input',{r['code'] for r in rows if not r['ok']})
        p['cross_question_input']='Previous question output is an input boundary for this question'
        self.assertTrue(all(c['ok'] for c in audit_result_source(self.root,self.d,p,self.plan,self.fig,'plan','production')))

    def test_reexport_receipt_binds_original_script_config_result_and_output(self):
        for name in ('figure.png', 'export.png', 'config.json'):
            (self.root/name).write_bytes(b'isolated contract fixture')
        tracked = ['figure.png', 'model.py', 'config.json', 'result.json', 'export.run.json']
        self.d['dependencies'].extend(tracked)
        receipt = {'command': ['python', 'model.py'], 'exit_code': 0,
                   'script': 'model.py', 'config': 'config.json', 'result_path': 'result.json',
                   'inputs': {p:sha(self.root/p) for p in tracked[:-1]},
                   'output_path': 'export.png', 'output_sha256': sha(self.root/'export.png')}
        record = self.root/'export.run.json'
        record.write_text(json.dumps(receipt))
        p = self.d['panels'][1]
        p.update(source_path='export.png',reuse_mode='reexport',derivation={
            'operation':'reexport','original_path':'figure.png',
            'original_sha256':sha(self.root/'figure.png'),'run_path':'export.run.json'})
        rows = audit_result_source(self.root,self.d,p,self.plan,self.fig,'render','production')
        self.assertTrue(all(c['ok'] for c in rows),rows)
        (self.root/'config.json').write_bytes(b'changed export configuration')
        rows = audit_result_source(self.root,self.d,p,self.plan,self.fig,'render','production')
        self.assertIn('reexport_run_current',{r['code'] for r in rows if not r['ok']})

    def test_demo_source_rejected(self):
        self.plan['purpose']='demo'
        rows=audit_result_source(self.root,self.d,self.d['panels'][1],self.plan,self.fig,'plan','production')
        self.assertIn('result_not_demo',{r['code'] for r in rows if not r['ok']})


class LayoutAndMirrorTests(unittest.TestCase):
    def check_xml(self, cells):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'layout.drawio'
            source.write_text('<mxfile><diagram><mxGraphModel pageWidth="600" pageHeight="400"><root>'+cells+'</root></mxGraphModel></diagram></mxfile>')
            script=TEMPLATE/'.agents/skills/sci-box-main/sci-box-main/skills/scibox-diagram/scripts/check_layout.py'
            return subprocess.run([sys.executable,'-B',str(script),str(source),'--strict'],capture_output=True)

    def test_background_container_and_embedded_arrow_label(self):
        cells='<mxCell id="bg" vertex="1" style="fillColor=#EEF7F0;strokeColor=none"><mxGeometry x="5" y="5" width="550" height="350"/></mxCell>'
        cells+='<mxCell id="arrow" vertex="1" value="Transfer" style="shape=singleArrow;fontSize=12;fillColor=#D8E8F7"><mxGeometry x="30" y="40" width="180" height="40"/></mxCell>'
        self.assertEqual(self.check_xml(cells).returncode,0)
        self.assertNotEqual(self.check_xml(cells.replace('Transfer','A much too long arrow label overlapping the tip')).returncode,0)

    def test_real_label_collision_and_line_crossing_remain_rejected(self):
        cell='<mxCell id="a" vertex="1" value="Alpha" style="strokeColor=none;fontSize=12"><mxGeometry x="30" y="40" width="100" height="30"/></mxCell>'
        overlap=cell.replace('id="a"','id="b"')
        self.assertNotEqual(self.check_xml(cell+overlap).returncode,0)
        edge='<mxCell id="e" edge="1"><mxGeometry><mxPoint x="20" y="55" as="sourcePoint"/><mxPoint x="150" y="55" as="targetPoint"/></mxGeometry></mxCell>'
        self.assertNotEqual(self.check_xml(cell+edge).returncode,0)

    def test_gallery_and_mirrors(self):
        for skill in ('comprehensive-graphic-text-flowchart','engineering-physics-mechanism-diagram','algorithm-mechanism-diagram'):
            base=TEMPLATE/'.agents/skills'/skill;mirror=TEMPLATE/'.claude/skills'/skill
            for source in base.rglob('*'):
                if source.is_file() and '__pycache__' not in source.parts:
                    self.assertEqual(sha(source),sha(mirror/source.relative_to(base)),str(source))
        base=TEMPLATE/'.agents/skills/comprehensive-graphic-text-flowchart'
        index=json.loads((base/'references/gallery-index.json').read_text(encoding='utf8'))
        self.assertEqual(len(index),10)
        self.assertEqual(len({r['path'] for r in index}),10)
        for r in index:
            self.assertEqual(sha(base/r['path']),r['sha256'])
            if 'source_directory' in r:
                self.assertEqual(sha(Path(r['source_directory'])/r['original_filename']),r['sha256'])


if __name__=='__main__':
    unittest.main()
