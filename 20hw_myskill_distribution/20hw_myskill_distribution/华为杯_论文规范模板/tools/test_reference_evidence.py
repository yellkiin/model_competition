"""Controlled fictitious metadata tests; these records are never paper evidence."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from reference_evidence import audit_references, bibliography, metadata_errors, sha, source_metadata
from ai_disclosure import AI_DISCLOSURE, disclosure_record


class ReferenceEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = self.root/'论文输入.json'
        self.manifest = {'references_evidence_path':'refs.json', 'chapters':[
            {'chapter_id':'q1','role':'problem','tex_path':'body.tex'},
            {'chapter_id':'refs','role':'references','tex_path':'refs.tex'}]}
        self.path.write_text(json.dumps(self.manifest),encoding='utf-8')
        (self.root/'refs.tex').write_text(r'\bibliography{reference}',encoding='utf-8')
        self.report = {'keys':list('abcdefghij'),'calls':[{'chapter_id':'q1','keys':[k]} for k in 'abcdefghij']}
        entries, body, records = [], [], []
        self.quote = 'Feature selection can reduce irrelevant variables.'
        for key in 'abcdefghij':
            title = 'Controlled metadata fixture '+key.upper()
            url = 'https://example.org/testing/'+key
            entry = '@article{'+key+', author={Ada Example}, title={'+title+'}, year={2001}, journal={Fictitious Test Journal}, volume={2}, pages={10--30}, url={'+url+'}}'
            entries.append(entry)
            excerpt = '受控测试中的来源陈述用于校验文本绑定\\cite{'+key+'}。'
            body.append(excerpt)
            raw = ('<meta name="citation_title" content="'+title+'">'
                   '<meta name="citation_author" content="Ada Example">'
                   '<meta name="citation_publication_date" content="2001">'
                   '<meta name="citation_journal_title" content="Fictitious Test Journal">'
                   '<meta name="citation_volume" content="2">'
                   '<meta name="citation_firstpage" content="10">'
                   '<meta name="citation_lastpage" content="30"><p>'+self.quote+'</p>')
            capture = self.root/(key+'.html'); capture.write_text(raw,encoding='utf-8')
            receipt = self.root/(key+'-receipt.json')
            receipt.write_text(json.dumps({'requested_url':url,'final_url':url,'sha256':sha(capture),
                'status':200,'retrieved_utc':'2026-09-08T00:00:00+00:00','fixture':True}),encoding='utf-8')
            source = {'url':url,'authority':'publisher','authority_reason':'受控虚构元数据测试，不是真实学术来源，只测试记录校验。',
                'capture_path':capture.name,'capture_sha256':sha(capture),'receipt_path':receipt.name,
                'receipt_sha256':sha(receipt),'format':'html_meta',
                'review':{'reviewed':True,'tool_ref':'synthetic-test-only',
                          'observation':'受控虚构记录测试元数据匹配，不代表实际来源阅读或论文真实性通过。'}}
            records.append({'key':key,'reference_type':'ordinary','sources':[source],'usages':[{'chapter_id':'q1','body_excerpt':excerpt,
                'source_excerpt':self.quote,'reviewed':True,'tool_ref':'synthetic-test-only',
                'relevance':'受控测试中的特征选择摘录与正文引用绑定，用于检验软件行为而非学术结论。'}]})
        (self.root/'reference.bib').write_text('\n'.join(entries),encoding='utf-8')
        (self.root/'body.tex').write_text('\n'.join(body),encoding='utf-8')
        self.evidence={'schema_version':'1.1','bibliography_files':[], 'references':records+[disclosure_record()]}
        self.refresh()

    def refresh(self):
        self.evidence['bibliography_files']=[{'path':'reference.bib','sha256':sha(self.root/'reference.bib')}]
        self.save()

    def save(self):
        (self.root/'refs.json').write_text(json.dumps(self.evidence,ensure_ascii=False),encoding='utf-8')

    def audit(self):
        self.save()
        return audit_references(self.path,self.report)

    def test_supported_fields_and_bound_prose(self):
        self.assertEqual(self.audit()['status'],'PASS')

    def test_missing_manifest_evidence(self):
        self.manifest.pop('references_evidence_path')
        self.path.write_text(json.dumps(self.manifest),encoding='utf-8')
        self.assertEqual(self.audit()['status'],'FAIL')

    def test_each_metadata_field_is_checked_even_after_hash_refresh(self):
        path=self.root/'reference.bib'; original=path.read_text(encoding='utf-8')
        for old,new,field in [('Ada Example','Fake Author','authors'),('fixture A','fake title','title'),
                              ('2001','2099','year'),('10--30','1030','pages'),('Test Journal','Other Journal','container')]:
            with self.subTest(field=field):
                path.write_text(original.replace(old,new,1),encoding='utf-8'); self.refresh()
                self.assertTrue(any('元数据不符：'+field in e for e in self.audit()['failures']))
        path.write_text(original,encoding='utf-8')

    def test_invented_doi_is_not_admitted_by_syntax(self):
        p=self.root/'reference.bib'
        p.write_text(p.read_text(encoding='utf-8').replace('author=', 'doi={10.9999/fabricated}, author=',1),encoding='utf-8')
        self.refresh()
        self.assertTrue(any('元数据不符：doi' in e for e in self.audit()['failures']))

    def test_changed_capture_and_receipt_are_rejected(self):
        with (self.root/'a.html').open('a',encoding='utf-8') as f:f.write('changed')
        errors=self.audit()['failures']
        self.assertTrue(any('快照哈希变化' in e for e in errors))
        self.assertTrue(any('获取记录不匹配' in e for e in errors))

    def test_unreviewed_sources_and_usages_are_not_approved(self):
        self.evidence['references'][0]['sources'][0]['review']['reviewed']=False
        self.evidence['references'][1]['usages'][0]['reviewed']=False
        errors=self.audit()['failures']
        self.assertTrue(any('尚未实际阅读' in e for e in errors))
        self.assertTrue(any('相关性审阅' in e for e in errors))

    def test_source_and_body_excerpts_must_exist_with_citation(self):
        self.evidence['references'][0]['usages'][0]['source_excerpt']='A nonexistent experimental claim'
        self.evidence['references'][1]['usages'][0]['body_excerpt']='没有引用键的正文'
        errors=self.audit()['failures']
        self.assertTrue(any('论据摘录不在' in e for e in errors))
        self.assertTrue(any('未绑定实际引文' in e for e in errors))

    def test_missing_usage_or_extra_key_fails(self):
        self.report['calls'].append({'chapter_id':'q2','keys':['a']})
        self.assertTrue(any('每个实引章节' in e for e in self.audit()['failures']))
        self.report['keys'].append('unknown')
        self.assertTrue(any('一一对应' in e for e in self.audit()['failures']))

    def test_duplicate_work_under_different_key(self):
        path=self.root/'reference.bib'
        first=path.read_text(encoding='utf-8').splitlines()[0]
        path.write_text(first+'\n'+first.replace('@article{a,','@article{b,'),encoding='utf-8')
        self.evidence['references'][1]['sources']=copy.deepcopy(self.evidence['references'][0]['sources'])
        self.refresh()
        self.assertTrue(any('同一著作不同键' in e for e in self.audit()['failures']))

    def test_manual_metadata_cannot_override_bibtex(self):
        actual=bibliography(self.root,self.manifest)[0]['a']
        self.evidence['references'][0]['manual_metadata']=actual
        self.assertTrue(any('不能以手填metadata覆盖' in e for e in self.audit()['failures']))

    def test_manual_bibliography_with_initials_remains_supported(self):
        entries=bibliography(self.root,self.manifest)[0]
        lines=[r'\begin{thebibliography}{2}']
        for record in self.evidence['references']:
            if record['reference_type'] == 'ai_tool': continue
            key=record['key']; meta=entries[key]
            record['manual_metadata']=meta
            lines.append('\\bibitem{'+key+'} Example A. '+meta['title']+'. Fictitious Test Journal, 2:10--30, 2001.')
        lines.append(r'\end{thebibliography}')
        path=self.root/'refs.tex'; path.write_text('\n'.join(lines),encoding='utf-8')
        self.evidence['bibliography_files']=[{'path':'refs.tex','sha256':sha(path)}]
        self.assertEqual(self.audit()['status'],'PASS')

    def test_bibtex_strings_and_nested_accent_are_parsed(self):
        path=self.root/'reference.bib'
        raw=path.read_text(encoding='utf-8')
        raw='@string{journalname="Fictitious Test Journal"}\n'+raw.replace('{Fictitious Test Journal}','journalname')
        raw=raw.replace('Ada Example',r'Ad{\"a} Example')
        path.write_text(raw,encoding='utf-8'); self.refresh()
        self.assertEqual(self.audit()['status'],'PASS')

    def test_undefined_bibtex_string_returns_a_failed_report(self):
        path=self.root/'reference.bib'
        path.write_text('@article{a,title=undefinedMacro}',encoding='utf-8'); self.refresh()
        self.assertTrue(any('BibTeX解析失败' in e for e in self.audit()['failures']))

    def test_page_range_is_not_equal_to_concatenated_digits(self):
        source={'title':'Test','authors':['Ada Example'],'year':'2001','pages':'10--30'}
        self.assertIn('元数据不符：pages',metadata_errors(dict(source,pages='1030'),source))

    def test_csl_pointer_and_field_quote_sources(self):
        path=self.root/'csl.json'
        path.write_text(json.dumps({'record':{'title':'Example','author':[{'given':'Ada','family':'Example'}],
            'issued':{'date-parts':[[2001]]},'container-title':'Journal','volume':'2','page':'10-30'}}),encoding='utf-8')
        meta,_=source_metadata(path,{'format':'csl_json','json_pointer':'/record'})
        self.assertEqual(meta['authors'],['Ada Example'])
        self.assertEqual(meta['year'],'2001')
        path=self.root/'excerpt.txt'; path.write_text('A book by Ada Example, published in 2001.',encoding='utf-8')
        record={'format':'field_quotes','field_quotes':{'authors':[{'value':'Ada Example','quote':'by Ada Example'}],
                                                       'year':[{'value':'2001','quote':'published in 2001'}]}}
        meta,_=source_metadata(path,record); self.assertEqual(meta['year'],'2001')
        record['field_quotes']['year'][0]['value']='2099'
        with self.assertRaises(ValueError):source_metadata(path,record)

    def test_book_pages_and_network_access_date_remain_required(self):
        source={'title':'Book','authors':['Ada Example'],'year':'2001','publisher':'Press'}
        errors=metadata_errors(dict(source,kind='book'),source)
        self.assertTrue(any('pages' in e for e in errors))
        self.assertTrue(any('访问日期' in e for e in metadata_errors(dict(source,kind='software'),source)))

    def test_ai_disclosure_requires_fixed_fields_and_is_not_ordinary_source(self):
        ai = {'key':'ai_tool_disclosure','reference_type':'ai_tool','ai_disclosure':dict(AI_DISCLOSURE),
              'sources':[],'usages':[]}
        candidate = copy.deepcopy(self.evidence)
        candidate['references'].append(ai)
        candidate['references'][0]['reference_type'] = 'ordinary'
        candidate['references'][1]['reference_type'] = 'ordinary'
        candidate['references'][0]['ai_disclosure'] = dict(AI_DISCLOSURE)
        candidate['references'][0]['sources'][0]['review']['reviewed'] = True
        self.evidence = candidate
        errors = self.audit()['failures']
        self.assertTrue(any('AI工具披露' in e or 'reference_evidence_invalid' in e for e in errors))

    def test_inventory_gate_accepts_ten_ordinary_plus_ai_and_rejects_nine(self):
        from reference_evidence import reference_inventory_errors
        ordinary = [{'key': str(i), 'reference_type': 'ordinary'} for i in range(10)]
        ai = {'key': 'ai_tool_disclosure', 'reference_type': 'ai_tool',
              'ai_disclosure': dict(AI_DISCLOSURE), 'sources': [], 'usages': []}
        self.assertFalse(reference_inventory_errors(ordinary + [ai], [str(i) for i in range(10)]))
        self.assertTrue(any('至少10条普通' in e for e in reference_inventory_errors(ordinary[:-1] + [ai], [str(i) for i in range(9)])))
        bad = dict(ai, ai_disclosure={**AI_DISCLOSURE, 'date': '2026-09-22'})
        self.assertTrue(any('固定' in e for e in reference_inventory_errors(ordinary + [bad], [str(i) for i in range(10)])))


if __name__=='__main__':unittest.main()
