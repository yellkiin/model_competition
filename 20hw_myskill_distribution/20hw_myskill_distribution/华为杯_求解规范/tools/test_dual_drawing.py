"""Isolated unit fixtures. Review statements below are TEST data, never production evidence."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import subprocess
import sys
from unittest.mock import patch

from build_academic_figure_asset_index import sha, write_json, digest
from chart_policy import audit_policy, audit_diversity, selection_digest, portfolio_digest
from drawing_sources import discover, audit_preflight, package_files
from visual_routes import academic_panels, modelviz_panels, routed_panels, routing_errors, paper_specs
from modelviz_bridge import strict_model, original_schemas, audit_modelviz, sidecar
from init_visual_plan import make_problem

PROJECT=Path(__file__).resolve().parents[2]


def figure(root, fid='f1', source='modelviz-skill', family='heatmap'):
    data=root/'results.csv'
    data.write_text('x,y,z\n0,0,1\n0,1,2\n1,0,3\n1,1,4\n',encoding='utf8')
    p={'panel_id':'a','question':'UNIT TEST compare response values','figure_type':'heatmap','figure_family':'heatmap_surface',
       'result_file':'results.csv','fields':['x','y','z'],'units':['1'],'visual_encoding':'UNIT TEST response color',
       'rendering_route':'academic','source_skill':source,'chart_type':'correlation_heatmap','chart_families':[family],
       'chart_review':'UNIT TEST actual matrix panel encoding','selected_candidate_id':'m'}
    if source=='modelviz-skill': p['template_id']='rel_pearson_correlation_heatmap'
    else: p.update(asset_directory='.agents/skills/academic-figure-skill/assets/figures/CorrelationMatrix',asset_mode='visual_adapt',selected_candidate_id='a')
    f={'figure_id':fid,'scope':'q1','scientific_question':'UNIT TEST response values in a matrix',
       'claim_ids':['q1-C01'],'evidence_ids':['q1-E01'],'archetype':'quantitative_grid','layout':'single panel','hero_panel':'a',
       'panels':[p],'script':'plot.py','outputs':{'vector':fid+'.pdf','preview':fid+'.png'},
       'statistics_report':'stats.json','qa_report':'qa.json','paper':{'chapter':'q1','label':'fig:'+fid,'caption':'test','reference_context':'test'},'status':'planned'}
    candidates=[{'candidate_id':cid,'source_skill':skill,'reference_id':ref,'chart_families':[family],
                 'dimension':'2d','suitable':True,'reason':'UNIT TEST matrix encoding is suitable'} for cid,skill,ref in (
        ('m','modelviz-skill','rel_pearson_correlation_heatmap'),('a','academic-figure-skill','CorrelationMatrix'))]
    f['selection']={'figure_sha256':selection_digest(f),'evidence':{'results.csv':sha(data)},
       'source_checks':[{'source_skill':s,'candidate_ids':[c['candidate_id'] for c in candidates if c['source_skill']==s],
                         'limitation':'','observation':'UNIT TEST inspected the complete source catalog'} for s in ('academic-figure-skill','modelviz-skill')],
       'candidates':candidates,'limited_candidates_reason':'',
       'three_d':{'applicable':False,'reason':'UNIT TEST matrix entries do not represent a continuous spatial surface',
                 'axes':[],'disadvantage':'','view':'','occlusion':'','projection':'','quantitative_basis':''},'repetition_exceptions':[]}
    return f


def plan(f):
    q=make_problem('q1','standard'); q['figures']=[f]; q['claims']=[{'claim_id':'q1-C01','text':'UNIT TEST conclusion'}]
    return {'schema_version':'1.2','project_title':'UNIT TEST','plan_status':'ready','visual_encoding_path':'encoding.md',
            'drawing_preflight_path':'preflight.json','global_figures':[],'problems':[q],'flowcharts':[]}


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='中文 drawing ');self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        for side in ('.agents','.claude'):
            for folder,identity in [('academic-figure-skill','academic-figure-skill'),('different-modelviz-folder','modelviz-skill')]:
                p=self.root/side/'skills'/folder/'SKILL.md';p.parent.mkdir(parents=True);p.write_text('---\nname: '+identity+'\n---\nUNIT TEST',encoding='utf8')

    def test_identity_not_folder_name_both_runtimes(self):
        for runtime,side in [('codex','.agents'),('claude','.claude')]:
            self.assertEqual(discover(self.root,runtime,'modelviz-skill'),self.root/side/'skills/different-modelviz-folder')
            self.assertEqual(discover(self.root,runtime,'academic-figure-skill').name,'academic-figure-skill')

    def test_missing_does_not_cross_runtime(self):
        (self.root/'.claude/skills/different-modelviz-folder/SKILL.md').unlink()
        with self.assertRaisesRegex(ValueError,'found 0'): discover(self.root,'claude','modelviz-skill')

    def test_ambiguity_and_cross_runtime_explicit_path(self):
        with self.assertRaisesRegex(ValueError,'Explicit skill path'): discover(self.root,'codex','modelviz-skill','.claude/skills/different-modelviz-folder')
        p=self.root/'.agents/skills/duplicate';p.mkdir();(p/'SKILL.md').write_text('---\nname: modelviz-skill\n---\n',encoding='utf8')
        with self.assertRaisesRegex(ValueError,'found 2'): discover(self.root,'codex','modelviz-skill')

    def test_missing_preflight_cannot_pass(self):
        self.assertTrue(audit_preflight(self.root,'codex','missing.json'))

    def test_resource_content_change_alters_digest(self):
        skill=discover(self.root,'claude','modelviz-skill')
        first=digest(package_files(skill))
        (skill/'new_reference.py').write_text('# UNIT TEST changed resource',encoding='utf8')
        self.assertNotEqual(first,digest(package_files(skill)))

    def test_blank_review_never_grants_approval(self):
        from drawing_sources import blank_review,review_ok
        self.assertFalse(review_ok(blank_review()))


class ChildIsolationTests(unittest.TestCase):
    """Real subprocesses in temporary jobs; no model or approval mocks."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='中文 drawing ');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.job=self.root/'Figure space';self.job.mkdir()
        self.data=self.root/'results.csv';self.data.write_text('x,y\n1,2\n',encoding='utf8')

    def run_plot(self,code):
        script=self.job/'plot.py';script.write_text(code,encoding='utf8')
        payload=self.job/'payload.json';write_json(payload,{'job_dir':str(self.job),'script':str(script),
            'data_path':str(self.data),'output_dir':str(self.job/'outputs_v2'),'protected_inputs':[str(self.data)]})
        return subprocess.run([sys.executable,'-B',str(PROJECT/'华为杯_求解规范/tools/modelviz_bridge.py'),
                               '--plot-child',str(payload)],cwd=self.job,capture_output=True,text=True,encoding='utf8')

    def test_outputs_inside_declared_job_and_input_unchanged(self):
        before=sha(self.data)
        result=self.run_plot("import os\nfrom pathlib import Path\np=Path(os.environ['OUTPUT_DIR']);p.mkdir();(p/'ok.txt').write_text('UNIT TEST')")
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue((self.job/'outputs_v2/ok.txt').is_file());self.assertEqual(before,sha(self.data))

    def test_escape_and_declared_input_writes_are_blocked(self):
        for code in ["from pathlib import Path\nPath('../outside.txt').write_text('bad')",
                     "import os\nfrom pathlib import Path\nPath(os.environ['DATA_PATH']).write_text('bad')"]:
            result=self.run_plot(code);self.assertNotEqual(result.returncode,0)
            self.assertFalse((self.root/'outside.txt').exists())
            self.assertEqual(self.data.read_text(encoding='utf8'),'x,y\n1,2\n')


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.f=figure(self.root);self.p=plan(self.f)

    def gate(self,body=True):
        with patch('chart_policy.audit_preflight',return_value=[]):
            return audit_policy(self.p,self.root,'codex',body=body)

    def test_sources_equal_no_academic_assets_for_modelviz(self):
        self.assertEqual(self.gate(),[])
        self.assertEqual(academic_panels(self.f),[]); self.assertEqual(len(modelviz_panels(self.f)),1); self.assertEqual(routed_panels(self.f),[])
        self.assertEqual(routing_errors(self.f),[])

    def test_old_academic_route_retains_asset_gate(self):
        f=figure(self.root,source='academic-figure-skill');self.assertEqual(len(academic_panels(f)),1)
        self.assertEqual(routing_errors(f),[])
        f['panels'][0]['source_skill']='modelviz-skill'
        self.assertIn('modelviz_must_not_fabricate_academic_assets',str(routing_errors(f)))

    def test_missing_preflight_and_resource_change_fail_formal_selection(self):
        self.assertIn('preflight_missing_or_invalid',str(audit_policy(self.p,self.root,'codex')))
        with patch('chart_policy.audit_preflight',return_value=['modelviz:preflight_resource_changed']):
            self.assertIn('preflight_resource_changed',str(audit_policy(self.p,self.root,'codex')))

    def test_third_heatmap_cross_provider_and_names(self):
        fs=[figure(self.root,'f'+str(i),source='academic-figure-skill' if i==1 else 'modelviz-skill') for i in range(3)]
        fs[1]['panels'][0]['chart_type']='clustered_heatmap'
        self.assertIn('chart_family_limit:heatmap',str(audit_diversity(fs,self.root)))
        self.assertEqual(audit_diversity(fs[:2],self.root),[])

    def test_homogeneous_panels_once_but_mixed_families_all_count(self):
        fs=[figure(self.root,'f'+str(i)) for i in range(2)]
        p=copy.deepcopy(fs[0]['panels'][0]);p['panel_id']='b';p['comparison_group']='same matrix condition';fs[0]['panels'].append(p)
        self.assertEqual(audit_diversity(fs,self.root),[])
        fs.append(figure(self.root,'f3'));fs[-1]['panels'][0]['chart_families']=['heatmap','scatter']
        self.assertIn('heatmap',str(audit_diversity(fs,self.root)))

    def test_complete_exception_then_selection_change_invalidates(self):
        fs=[figure(self.root,'f'+str(i)) for i in range(3)]
        e={'chart_family':'heatmap','portfolio_sha256':portfolio_digest(fs),'figure_ids':[f['figure_id'] for f in fs],
           'scientific_purpose':'UNIT TEST compare exactly aligned cell locations across the three time conditions',
           'alternatives':[{'chart_family':'scatter','reason':'UNIT TEST scatter loses the exact paired cell adjacency needed here'}],
           'reason':'UNIT TEST same cell locations must be visually paired across these necessary conditions',
           'evidence':{'results.csv':sha(self.root/'results.csv')}}
        fs[-1]['selection']['repetition_exceptions']=[e]
        self.assertEqual(audit_diversity(fs,self.root),[])
        fs[0]['scientific_question']+=' changed'
        self.assertTrue(audit_diversity(fs,self.root))

    def test_uncontrolled_multipanel_family_cannot_hide_heatmap(self):
        self.f['panels'][0]['chart_families']=['multipanel']
        self.assertIn('schema',str(self.gate()))

    def test_reserve_scope_excludes_body_limit(self):
        self.p['problems'][0]['figures']=[figure(self.root,'f'+str(i)) for i in range(3)]
        self.assertEqual(self.gate(body=False),[])
        self.assertIn('chart_family_limit',str(self.gate()))

    def set_3d(self):
        s=self.f['selection'];d=s['three_d'];d.update(applicable=True,reason='UNIT TEST response varies over two real parameters',
            axes=[{'field':k,'unit':'1','meaning':'UNIT TEST parameter or response','result_file':'results.csv','range':'0 to 4'} for k in ('x','y','z')],
            view='UNIT TEST elevated viewpoint',occlusion='UNIT TEST limited occlusion with continuous surface',
            projection='UNIT TEST contour projected onto parameter plane',quantitative_basis='UNIT TEST all values from saved response grid')
        s['candidates'].append({'candidate_id':'s','source_skill':'modelviz-skill','reference_id':'mpn_3d_surface_scatter_report',
            'chart_families':['surface','contour'],'dimension':'3d','suitable':True,'reason':'UNIT TEST continuous response surface with real axes'})
        s['source_checks'][1]['candidate_ids'].append('s')

    def test_qualified_three_d_preferred_and_concrete_2d_fallback(self):
        self.set_3d()
        self.assertIn('qualified_3d_preferred',str(self.gate()))
        self.f['selection']['three_d']['disadvantage']='UNIT TEST narrow print size hides saddle values behind the ridge'
        self.assertEqual(self.gate(),[])

    def test_true_three_d_passes_but_fake_axis_and_bar_fail(self):
        self.set_3d();p=self.f['panels'][0]
        p.update(selected_candidate_id='s',template_id='mpn_3d_surface_scatter_report',chart_families=['surface','contour'])
        self.f['selection']['figure_sha256']=selection_digest(self.f)
        self.assertEqual(self.gate(),[])
        self.f['selection']['three_d']['axes'][2]['field']='invented_height'
        self.assertIn('axis_not_bound_to_result',str(self.gate()))
        self.f['selection']['candidates'][-1]['chart_families']=['bar'];p['chart_families']=['bar']
        self.assertIn('decorative_3d_bar',str(self.gate()))

    def test_mixed_template_omission_requires_explicit_current_reason(self):
        self.set_3d();p=self.f['panels'][0]
        p.update(selected_candidate_id='s',template_id='mpn_3d_surface_scatter_report',chart_families=['surface'])
        self.f['selection']['candidates'][-1]['chart_families']=['surface']
        self.f['selection']['figure_sha256']=selection_digest(self.f)
        self.assertIn('mixed_template_families_unaccounted',str(self.gate()))
        p['omitted_chart_families']=[{'chart_family':'contour','reason':'UNIT TEST separate numeric annotation replaces the basal contour for this specimen'}]
        self.f['selection']['figure_sha256']=selection_digest(self.f)
        self.assertEqual(self.gate(),[])

    def test_changed_input_and_unknown_selection_fields_fail(self):
        (self.root/'results.csv').write_text('changed',encoding='utf8')
        self.assertIn('selection_stale',str(self.gate()))
        self.f['selection']['fake_pass']=True
        self.assertIn('Additional properties',str(self.gate()))

    def test_paper_specs_pure_modelviz_and_mixed(self):
        pp=self.root/'plan.json';write_json(pp,self.p)
        write_json(sidecar(pp),{'figures':[{'figure_id':'f1','target_width_mm':128}]})
        self.assertEqual(paper_specs(pp)[0]['vector_path'],'f1.pdf')
        a=copy.deepcopy(figure(self.root,source='academic-figure-skill')['panels'][0]);a['panel_id']='b';self.f['panels'].append(a);write_json(pp,self.p)
        write_json(pp.with_suffix('.assets.json'),{'figures':[{'figure_id':'f1','target_width_mm':128}]})
        self.assertEqual(paper_specs(pp)[0]['target_width_mm'],128)
        write_json(sidecar(pp),{'figures':[{'figure_id':'f1','target_width_mm':100}]})
        with self.assertRaisesRegex(ValueError,'widths disagree'): paper_specs(pp)

    def test_source_label_alone_cannot_pass(self):
        pp=self.root/'plan.json';write_json(pp,self.p)
        self.assertEqual(audit_modelviz(pp,'plan',self.root,'codex')['status'],'FAIL')

    def test_original_schemas_reused_strictly_without_model_object(self):
        skill=PROJECT/'.agents/skills/modelviz-skill-main';schemas=original_schemas(skill)
        strict_model(schemas.FinalTemplateSelection,{'selected_template_id':'test','selected_template_name':'test'})
        with self.assertRaises(Exception): strict_model(schemas.FinalTemplateSelection,{'invented_field':True})


if __name__=='__main__': unittest.main()
