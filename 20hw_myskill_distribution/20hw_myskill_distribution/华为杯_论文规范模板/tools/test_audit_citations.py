import json
from pathlib import Path
import tempfile
import unittest

from audit_citations import audit_citation_keys as audit_source, auxiliary_numbers, citation_calls, expand_numbers


class CitationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = self.root/'论文输入.json'
        self.manifest = {'chapters': [
            {'chapter_id': 'q1', 'role': 'problem', 'tex_path': 'q1.tex'},
            {'chapter_id': 'refs', 'role': 'references', 'tex_path': 'refs.tex'}]}
        self.path.write_text(json.dumps(self.manifest), encoding='utf-8')
        (self.root/'q1.tex').write_text(''.join('说明\\cite{k'+str(i)+'}。\n' for i in range(10)), encoding='utf-8')
        (self.root/'refs.tex').write_text(r'\bibliography{reference}', encoding='utf-8')

    def test_ten_distinct_direct_body_citations(self):
        report = audit_source(self.path)
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(len(report['keys']), 10)
        self.assertEqual(len(report['calls']), 10)

    def test_repeated_key_never_pads_count(self):
        (self.root/'q1.tex').write_text(r'\cite{k0}'*20, encoding='utf-8')
        report = audit_source(self.path)
        self.assertEqual(report['status'], 'FAIL')
        self.assertIn('只有1条', report['failures'][0])

    def test_nocite_abstract_and_appendix_are_not_body(self):
        (self.root/'q1.tex').write_text(r'\cite{k0,k1,k2,k3,k4,k5,k6,k7,k8}', encoding='utf-8')
        (self.root/'refs.tex').write_text(r'\nocite{*}\cite{k9}\bibliography{reference}', encoding='utf-8')
        (self.root/'abstract.tex').write_text(r'\cite{k9}', encoding='utf-8')
        (self.root/'appendix.tex').write_text(r'\cite{k9}', encoding='utf-8')
        report = audit_source(self.path)
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(len(report['keys']), 9)

    def test_comments_not_citations_and_nested_input_is_counted(self):
        original = (self.root/'q1.tex').read_text(encoding='utf-8')
        (self.root/'sub.tex').write_text(original+'% \\cite{commented}\n', encoding='utf-8')
        (self.root/'q1.tex').write_text(r'\input{sub.tex}', encoding='utf-8')
        report = audit_source(self.path)
        self.assertEqual(report['status'], 'PASS')
        self.assertNotIn('commented', report['keys'])
        (self.root/'sub.tex').unlink()
        self.assertEqual(audit_source(self.path)['status'], 'FAIL')

    def test_two_optional_notes_do_not_become_keys(self):
        self.assertEqual(citation_calls(r'文字\citep[参见][第2页]{a,b}，\cite*{b,b,c}。'), [['a','b'], ['b','c']])

    def test_non_number_commands_and_dynamic_keys_fail_closed(self):
        for value in (r'\citeauthor{a}', r'\citeyear{a}', r'\citet{a}', r'\cite{\dynamic}', r'\cite{a,}', r'\cite{*}'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                citation_calls(value)

    def test_range_and_multiple_citation_expansion(self):
        self.assertEqual(expand_numbers('1–3,5,7–10'), ([1,2,3,5,7,8,9,10], {1,3,5,7,10}))
        self.assertEqual(expand_numbers('1;4;10'), ([1,4,10], {1,4,10}))
        for value in ('3–1', '1,1', '0', '2,1', '1–3,3'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                expand_numbers(value)

    def test_actual_aux_numbers_include_nested_manual_and_natbib_formats(self):
        main = self.root/'paper.tex'
        main.with_suffix('.aux').write_text('\\bibcite{one}{{1}{2000}{{Author}}{{}}}\n\\@input{sub.aux}\n', encoding='utf-8')
        (self.root/'sub.aux').write_text('\\bibcite{two}{2}\n', encoding='utf-8')
        self.assertEqual(auxiliary_numbers(main), {'one':1, 'two':2})
        (self.root/'sub.aux').write_text('\\bibcite{two}{1}\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '相同编号'):
            auxiliary_numbers(main)


if __name__ == '__main__':
    unittest.main()
