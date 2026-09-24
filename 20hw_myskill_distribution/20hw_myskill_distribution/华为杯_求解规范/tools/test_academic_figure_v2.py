"""Current v2 regression suite. All mutations occur in isolated file copies."""
from pathlib import Path
import copy,json,shutil,sys,tempfile,unittest
from build_academic_figure_asset_index import build_index,write_json,sync_report,safe,contact_sheets
from audit_academic_figure_assets import audit_assets
from audit_visual_plan import audit
from prepare_academic_figure_review import prepare
PROJECT=Path(__file__).resolve().parents[2]
BASE=Path('求解/验收输出/academic_figure_integration/upgrade_v2')

class AssetGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='academic_v2_');cls.root=Path(cls.tmp.name)
        for side in ['.agents','.claude']:
            p=Path(side)/'skills/academic-figure-skill'
            shutil.copytree(PROJECT/p,cls.root/p,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        for name in ['cases','gallery']:shutil.copytree(PROJECT/BASE/name,cls.root/BASE/name)
        cls.ip=cls.root/'求解/academic_figure_asset_index.json';cls.index=build_index(cls.root,runtime='codex');write_json(cls.ip,cls.index)
        cls.pp=cls.root/BASE/'cases/demo.visual.json';cls.rp=cls.pp.with_name('demo.visual.assets.json')
        cls.plan=json.loads(cls.pp.read_text(encoding='utf-8'));cls.refs=json.loads(cls.rp.read_text(encoding='utf-8'))
        for p in (cls.root/BASE/'cases').glob('*.run.json'):
            r=json.loads(p.read_text(encoding='utf-8'))
            # Fixtures may have been produced before the project was relocated.
            recorded_root=Path(r.get('cwd',PROJECT))
            command=[]
            for token in r['command']:
                try: token=str(cls.root/Path(token).relative_to(recorded_root))
                except ValueError: pass
                command.append(token)
            r['command']=command;r['cwd']=str(cls.root);write_json(p,r)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):self.saved={};self.r=copy.deepcopy(self.refs);self.p=copy.deepcopy(self.plan)
    def tearDown(self):
        import os
        for path,(data,stat) in self.saved.items():path.write_bytes(data);os.utime(path,ns=(stat.st_atime_ns,stat.st_mtime_ns))
        write_json(self.rp,self.refs);write_json(self.pp,self.plan)
    def mutate(self,raw,fn):
        path=safe(self.root,str(raw));self.saved[path]=(path.read_bytes(),path.stat());v=json.loads(path.read_text(encoding='utf-8'));fn(v);write_json(path,v)
    def check(self,stage='plan',runtime='codex',demo=True):
        write_json(self.rp,self.r);write_json(self.pp,self.p)
        return audit_assets(self.pp,stage,self.root,allow_demo=demo,runtime=runtime)
    def fails(self,code,stage='plan',**kw):
        r=self.check(stage,**kw);self.assertEqual(r['status'],'FAIL');self.assertIn(code,json.dumps(r['failures'],ensure_ascii=False))
    def panel(self):return self.r['figures'][0]['panel_plan'][0]
    def test_demo_assets_pass_but_scientific_completion_fails(self):
        for stage in ['plan','render']:
            r=audit(self.pp,stage,self.root,None,allow_demo=True,runtime='codex')
            # Historical asset-only fixture lacks the now-mandatory diagram sidecar.
            unexpected=[x for x in r['failures'] if not (x['code'].endswith((':figure_count_range', ':validation_has_evidence')) or x['code'] in {'paper_figure_minimum','diagram_workflow_gate'})]
            self.assertFalse(unexpected,unexpected)
            self.assertIn('paper_figure_minimum',{x['code'] for x in r['failures']})
            diagram_gate=next(x for x in r['checks'] if x['code']=='diagram_workflow_gate')
            self.assertFalse(diagram_gate['ok'])
            self.assertIn('diagram_input_valid',json.dumps(diagram_gate['failures']))
            self.assertTrue(next(x['ok'] for x in r['checks'] if x['code']=='academic_asset_gate'))
    def test_runtime_both_roots_and_mismatch(self):
        self.fails('asset_gate_input_error',runtime='claude');c=build_index(self.root,runtime='claude')
        self.assertTrue(all(x['path'].startswith('.claude/') for x in c['inventory']));self.assertEqual(self.index['counts'],c['counts']);self.assertEqual(sync_report(self.root)['status'],'PASS')
        with self.assertRaises(ValueError):build_index(self.root)
        with self.assertRaises(ValueError):build_index(self.root,skill='.agents/skills/academic-figure-skill',runtime='claude')
    def test_blank_initializer_full_search(self):
        draft=prepare(self.root,self.pp,self.ip,'demo','codex',self.r['gallery_review_path'])
        for f in draft['figures']:
            self.assertEqual(f['target_width_mm'],0)
            for p in f['panel_plan']:
                self.assertFalse(p['candidate_search']['reviewed']);self.assertEqual(p['atlas_reference'],'');self.assertEqual(p['candidate_review'],[]);self.assertEqual(len(p['candidate_search']['results']),len(self.index['families']))
    def test_incremental_ignores_unfinished_other_questions(self):
        fid = self.p['problems'][0]['figures'][0]['figure_id']
        self.p['problems'][1]['claims'] = []
        self.p['problems'][1]['evidence_matrix'] = []
        self.r['figures'][1]['panel_plan'][0]['candidate_review'] = []
        write_json(self.rp, self.r); write_json(self.pp, self.p)
        incremental = audit_assets(self.pp, 'plan', self.root, allow_demo=True, runtime='codex', figure_ids=[fid])
        self.assertEqual(incremental['status'], 'PASS', incremental['failures'])
        self.assertEqual(audit_assets(self.pp, 'plan', self.root, allow_demo=True, runtime='codex')['status'], 'FAIL')
    def test_gallery_missing_receipt(self):
        self.mutate(self.r['gallery_review_path'],lambda x:x['pages'].pop());self.fails('gallery_all_sheets_reviewed')
    def test_gallery_empty_observation(self):
        self.mutate(self.r['gallery_review_path'],lambda x:x['asset_observations'][0].update(visual_features=''));self.fails('gallery_observation')
    def test_stale_asset_digest(self):self.r['scan_digest']='0'*64;self.fails('scan_fingerprint_current')
    def test_search_not_preselected_only(self):self.panel()['candidate_search']['results'].pop();self.fails('full_catalog_search')
    def test_candidate_coverage(self):self.panel()['candidate_review'].pop();self.fails('candidate_review_coverage')
    def test_metadata_not_viewing(self):self.panel()['candidate_review'][0]['method']='metadata';self.fails('view_attestation')
    def test_wrong_source(self):self.panel()['production_asset']=self.r['figures'][1]['panel_plan'][0]['production_asset'];self.fails('source_in_family')
    def test_no_other_backend(self):self.r['figures'][0]['backend']='scibox-figure';self.fails('backend')
    def test_style_coverage(self):self.panel()['style_contract'].pop('palette');self.fails('style_contract_coverage')
    def test_geometry(self):self.r['figures'][0]['target_width_mm']=183;self.fails('paper_geometry')
    def test_demo_not_production(self):self.fails('demo_not_in_production',demo=False);self.fails('demo_not_in_production','paper')
    def test_main_schema_unchanged(self):self.p['problems'][0]['figures'][0]['illegal']='x';self.fails('schema:视觉计划.schema.json')
    def test_path_escape(self):self.r['index_path']='../escape.json';self.fails('asset_gate_input_error')
    def test_failed_run(self):self.mutate(self.r['figures'][0]['run_record_path'],lambda x:x.update(returncode=1));self.fails('execution_success','render')
    def test_old_output(self):self.mutate(self.r['figures'][0]['run_record_path'],lambda x:x.update(started_at_ns=2**63-1));self.fails('outputs_written_by_run','render')
    def test_output_hash(self):self.mutate(self.r['figures'][0]['visual_qa_path'],lambda x:x['artifact_sha256'].update(png='0'*64));self.fails('qa_current:png','render')
    def test_blank_comparison(self):self.mutate(self.r['figures'][0]['visual_qa_path'],lambda x:x['reference_comparison'].update(reviewed=False));self.fails('comparison_review','render')
    def test_dimensions_independent(self):self.mutate(self.r['figures'][0]['visual_qa_path'],lambda x:x['review_dimensions']['scientific_validity'].update(status='FAIL'));self.fails('three_review_dimensions','render')
    def test_stale_data(self):self.mutate(self.panel()['data_profile_path'],lambda x:x.update(sha256='0'*64));self.fails('real_data_revalidated','render')
    def test_actual_asset_change(self):
        p=safe(self.root,self.panel()['production_asset']);self.saved[p]=(p.read_bytes(),p.stat());p.write_bytes(p.read_bytes()+b'\n# changed\n');self.fails('index_fresh_and_derived')
    def test_installed_static_rules(self):
        sys.path.insert(0,str(self.root/'.agents/skills/academic-figure-skill/scripts'))
        import check_dimensions,check_fontsize,qa_validator
        self.assertTrue(check_dimensions.check('plt.subplots(figsize=(128/25.4,90/25.4))',journal='huawei')[1])
        self.assertFalse(check_dimensions.check('plt.subplots(figsize=(128/25.4,90/25.4))',journal='nature')[1])
        self.assertFalse(check_fontsize.check('ax.text(0,0,"x",fontsize=3)',journal='huawei')[1])
        self.assertEqual(qa_validator.check_ap3_four_sided_borders('ax.spines[:].set_visible(True)').category,'WARN')
    def test_multiformat_multiframe_and_corruption(self):
        import pymupdf as fitz
        from PIL import Image
        root=self.root/'synthetic_asset_test';base=root/'.agents/skills/academic-figure-skill'
        (base/'references').mkdir(parents=True,exist_ok=True);(base/'references/directory-map.md').write_text('# Test',encoding='utf-8')
        atlas=base/'assets/figure-atlas';atlas.mkdir(parents=True,exist_ok=True);(base/'assets/figures/empty').mkdir(parents=True,exist_ok=True)
        pdf=fitz.open()
        for n in range(2):pdf.new_page().insert_text((40,40),'page '+str(n))
        pdf.save(atlas/'multi.pdf');pdf.close()
        (atlas/'one.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="90" height="90" fill="blue"/></svg>',encoding='utf-8')
        Image.new('RGB',(80,80),'red').save(atlas/'frames.gif',save_all=True,append_images=[Image.new('RGB',(80,80),'blue')],duration=100)
        idx=build_index(root,runtime='codex');self.assertEqual(idx['visual_units'],5);contact_sheets(root,idx,root/'gallery')
        m=json.loads((root/'gallery/contact_manifest.json').read_text(encoding='utf-8'));self.assertEqual(len(m['units']),5);self.assertFalse(m['errors'])
        v=json.loads((root/'gallery/gallery_review.json').read_text(encoding='utf-8'));self.assertTrue(all(not x['reviewed'] and not x['observation'] for x in v['pages']))
        (atlas/'bad.png').write_bytes(b'bad');self.assertTrue(build_index(root,runtime='codex')['inspection_errors'])

def main():
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AssetGateTests))
    write_json(PROJECT/BASE/'regression.audit.json',{'status':'PASS' if result.wasSuccessful() else 'FAIL','tests':result.testsRun,
        'failures':[{'test':str(t),'traceback':msg} for t,msg in result.failures+result.errors],
        'scope':'Installed tools and isolated v2 copies; actual PDF/SVG/GIF; no Claude harness execution.'})
    return int(not result.wasSuccessful())
if __name__=='__main__':raise SystemExit(main())
