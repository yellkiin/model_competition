"""Publication consistency tests; synthetic count records are not scientific QA."""
import json
from pathlib import Path
import tempfile
import unittest
from build_figure_accounting import (build, audit_publications, INDEX, LIST, START, END)
from figure_accounting import audit_counts
from test_figure_accounting import fixture


class FigurePublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.plan,self.side=fixture()
        self.side.update(runtime='codex',purpose='demo',schema_version='1.0')
        self.path=self.root/'demo/视觉计划.json'
        self.path.parent.mkdir()
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.plan),encoding='utf-8')
        self.path.with_suffix('.diagrams.json').write_text(json.dumps(self.side),encoding='utf-8')

    def publish(self):
        return build(self.root,self.path,'plan','codex')

    def audit(self,stage='plan'):
        counts=audit_counts(self.plan,self.side,'plan',self.root)
        return audit_publications(self.root,self.path,self.plan,self.side,counts,stage,'codex')

    def test_missing_publications_fail_then_generated_views_agree(self):
        self.assertEqual(self.audit()['status'],'FAIL')
        r=self.publish()
        self.assertEqual(r['status'],'GENERATED_NOT_QA')
        self.assertEqual(self.audit()['status'],'PASS')
        data=json.loads((self.root/LIST).read_text(encoding='utf-8'))
        overviews=[f for f in data['figures'] if f['purpose']=='question_overview']
        self.assertEqual(len(overviews),4)
        self.assertTrue(all(not f['per_question'] and not f['paper_total'] for f in overviews))
        self.assertEqual(data['paper_eligible_count'],17)

    def test_republishing_preserves_user_result_prose(self):
        index=self.root/INDEX
        index.parent.mkdir()
        index.write_text('# 结果索引\n\n独立验证与适用条件。\n',encoding='utf-8')
        self.publish()
        first=index.read_text(encoding='utf-8')
        self.publish()
        self.assertEqual(first,index.read_text(encoding='utf-8'))
        self.assertIn('独立验证与适用条件。',first)
        self.assertEqual(first.count(START),1)

    def test_removed_index_row_fails(self):
        self.publish()
        p=self.root/INDEX
        p.write_text('\n'.join(line for line in p.read_text(encoding='utf-8').splitlines() if '| q1-F1 |' not in line),encoding='utf-8')
        self.assertEqual(self.audit()['status'],'FAIL')

    def test_changed_eligibility_fails_even_if_index_is_updated_to_match(self):
        from build_figure_accounting import markdown
        self.publish()
        p=self.root/LIST;data=json.loads(p.read_text(encoding='utf-8'))
        next(f for f in data['figures'] if f['purpose']=='question_overview')['paper_total']=True
        p.write_text(json.dumps(data),encoding='utf-8')
        (self.root/INDEX).write_text(markdown(data),encoding='utf-8')
        self.assertEqual(self.audit()['status'],'FAIL')

    def test_plan_or_output_changes_require_regeneration(self):
        self.publish()
        (self.root/'q1-1.pdf').write_bytes(b'New output version, not a real scientific PDF')
        self.assertEqual(self.audit()['status'],'FAIL')
        self.publish()
        self.assertEqual(self.audit()['status'],'PASS')
        self.side['figure_accounting'][0]['scientific_contribution']+='补充条件'
        self.save()
        self.assertEqual(self.audit()['status'],'FAIL')

    def test_broken_markers_do_not_overwrite_existing_files(self):
        self.publish()
        p=self.root/INDEX;p.write_text(p.read_text(encoding='utf-8')+'\n'+END,encoding='utf-8')
        before=p.read_bytes();listing=(self.root/LIST).read_bytes()
        with self.assertRaisesRegex(ValueError,'markers'):self.publish()
        self.assertEqual(p.read_bytes(),before)
        self.assertEqual((self.root/LIST).read_bytes(),listing)

    def test_paper_stage_cannot_reuse_unmeasured_planned_pages(self):
        self.publish()
        self.assertEqual(self.audit('paper')['status'],'FAIL')

    def test_incorrect_quota_cannot_be_published(self):
        self.side['figure_accounting'][4]['paper_total']=True
        self.save()
        with self.assertRaisesRegex(ValueError,'Quota contract'):self.publish()
        self.assertFalse((self.root/LIST).exists())

    def test_real_diagram_gate_checks_publication_presence(self):
        from audit_diagram_workflow import audit
        report=audit(self.path,'plan',self.root,'codex',allow_demo=True)
        check=next(c for c in report['checks'] if c['code']=='figure_accounting_publications')
        self.assertFalse(check['ok'])
        self.publish()
        report=audit(self.path,'plan',self.root,'codex',allow_demo=True)
        check=next(c for c in report['checks'] if c['code']=='figure_accounting_publications')
        self.assertTrue(check['ok'])
        # These deliberately incomplete diagram records must still fail QA.
        self.assertEqual(report['status'],'FAIL')


if __name__=='__main__':unittest.main()
