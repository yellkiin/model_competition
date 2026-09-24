"""Synthetic maintenance evidence; never real source or AI-use approval."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from ai_disclosure import AI_KEY, AI_TEXT, AI_TEX_HOOK, ensure_evidence_record
from audit_citations import audit_source, audit_citation_keys
from reference_evidence import sha
from run_ai_disclosure_regression import build_fixture


class DisclosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = tempfile.TemporaryDirectory()
        cls.seed_root = Path(cls.seed.name)
        build_fixture(cls.seed_root, early=True)

    @classmethod
    def tearDownClass(cls):
        cls.seed.cleanup()

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)/'paper'
        shutil.copytree(self.seed_root, self.root)
        self.manifest = self.root/'论文输入.json'
        self.path = self.root/'文献证据.json'
        self.evidence = json.loads(self.path.read_text(encoding='utf8'))

    def audit(self):
        self.path.write_text(json.dumps(self.evidence,ensure_ascii=False),encoding='utf8')
        return audit_source(self.manifest)

    def reject(self, text=None):
        result = self.audit()
        self.assertEqual(result['status'],'FAIL',result)
        if text:
            self.assertTrue(any(text in e for e in result['failures']), result['failures'])

    def test_all_english_and_early_ai_pass(self):
        result=self.audit()
        self.assertEqual(result['status'],'PASS',result['failures'])
        self.assertEqual(result['keys'][0],AI_KEY)
        self.assertEqual(len(result['ordinary_keys']),10)

    def test_nine_ordinary_plus_ai_fails_even_with_ten_keys(self):
        body=self.root/'c4.tex'
        body.write_text(body.read_text(encoding='utf8').replace(r'\cite{ref10}',''),encoding='utf8')
        self.evidence['references'].pop(-2)
        self.reject('至少10条')

    def test_unreferenced_and_nocite_cannot_pad(self):
        body=self.root/'c4.tex'
        body.write_text(body.read_text(encoding='utf8').replace(r'\cite{ref10}',r'\nocite{ref10}'),encoding='utf8')
        self.reject('正文实际引用9条')

    def test_missing_ai_fails(self):
        self.evidence['references'].pop()
        self.reject('只能有1条')

    def test_duplicate_ai_fails(self):
        self.evidence['references'].append(copy.deepcopy(self.evidence['references'][-1]))
        self.reject('只能有1条')

    def test_not_last_fails(self):
        self.evidence['references'].insert(0,self.evidence['references'].pop())
        self.reject('之后')

    def test_wrong_model_or_date_fails(self):
        row=self.evidence['references'][-1]
        original=copy.deepcopy(row['ai_disclosure'])
        for field in ('version','date','tool_name','organization'):
            with self.subTest(field=field):
                row['ai_disclosure']={**original,field:'wrong'}
                self.reject()

    def test_missing_classification_and_old_version_fail_without_upgrade(self):
        original=copy.deepcopy(self.evidence)
        self.evidence['references'][0].pop('reference_type')
        self.reject('补齐')
        self.evidence=original
        self.evidence['schema_version']='1.0'
        self.reject('1.1')
        before=self.path.read_bytes()
        with self.assertRaises(ValueError): ensure_evidence_record(self.manifest)
        self.assertEqual(before,self.path.read_bytes())

    def test_ai_classification_cannot_hide_ordinary_record(self):
        self.evidence['references'][0]['reference_type']='ai_tool'
        self.reject()

    def test_missing_ordinary_source_still_fails(self):
        self.evidence['references'][0]['sources']=[]
        self.reject()

    def test_manual_order_still_enforced(self):
        path=self.root/'c6.tex'
        text=path.read_text(encoding='utf8')
        lines=text.splitlines()
        lines[1],lines[2]=lines[2],lines[1]
        path.write_text('\n'.join(lines),encoding='utf8')
        self.evidence['bibliography_files'][0]['sha256']=sha(path)
        self.reject('首次引用顺序')

    def test_actual_use_requires_bound_record_and_review(self):
        ai=self.evidence['references'][-1]
        ai['usages'][0]['ai_output_excerpt']='Invented output absent from actual log'
        self.reject('原始使用记录')

    def test_template_field_is_not_use_fact(self):
        self.evidence['references'][-1]['usage_status']='template_only'
        self.reject('不是实际使用事实')

    def test_ai_cannot_be_scientific_evidence(self):
        self.evidence['references'][-1]['usages'][0]['purpose']='scientific_claim'
        self.reject()

    def test_missing_ai_mark_for_adopted_content_fails(self):
        p=self.root/'c4.tex'
        p.write_text(p.read_text(encoding='utf8').replace(r'\cite{ai_tool_disclosure}',''),encoding='utf8')
        self.reject('关联末尾条目')

    def test_generation_is_idempotent_and_does_not_approve_usage(self):
        self.evidence['references'].pop()
        self.path.write_text(json.dumps(self.evidence),encoding='utf8')
        self.assertTrue(ensure_evidence_record(self.manifest))
        before=self.path.read_bytes()
        self.assertFalse(ensure_evidence_record(self.manifest))
        self.assertEqual(before,self.path.read_bytes())
        row=json.loads(before)['references'][-1]
        self.assertEqual(row['usage_status'],'template_only')
        self.assertEqual(row['usages'],[])
        self.assertEqual((self.root/'论文.tex').read_text(encoding='utf8').count(AI_TEX_HOOK),1)


if __name__=='__main__': unittest.main()
