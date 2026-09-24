"""Source-position regressions; these synthetic blocks do not certify diagrams."""
import tempfile
import unittest
from pathlib import Path

from audit_diagram_positions import source_position, label_destinations


class Positions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'figure.pdf').write_bytes(b'not a PDF; source binding test only')
        self.main = self.root / 'main.tex'
        self.chapter = {'order': 4}
        self.diagram = {'diagram_id': 'q1-overview', 'problem_id': 'q1',
                        'paper': {'label': 'fig:o', 'caption': '对象与方法'},
                        'outputs': {'vector': 'figure.pdf'}}
        self.figure = (r'\begin{figure}[htbp]\includegraphics{figure.pdf}'
                       r'\caption{对象与方法}\label{fig:o}\end{figure}')
        self.lead = r'此处描述本问的研究对象与方法关系，见图\ref{fig:o}。'
        self.text = r'\section{问题一求解与分析}\subsection{问题的描述与分析}' + self.lead + self.figure + r'\subsection{模型}'

    def audit(self, text):
        return source_position(text, self.chapter, self.diagram, self.main, self.root)

    def test_valid(self):
        r = self.audit(self.text)
        self.assertEqual(r['status'], 'PASS')
        self.assertEqual(r['upper_anchor'], 'subsection.4.2')

    def test_wrong_subsection(self):
        r = self.audit(self.text.replace(self.figure, '').replace(r'\subsection{模型}', r'\subsection{模型}'+self.figure))
        self.assertIn('one_figure_in_required_section', r['failures'])

    def test_intro_outside_subsection(self):
        text = self.lead + self.text.replace(self.lead, '')
        self.assertIn('introduced_within_required_section', self.audit(text)['failures'])

    def test_caption_mismatch(self):
        self.assertIn('caption_matches_plan', self.audit(self.text.replace('caption{对象与方法}', 'caption{另一图题}'))['failures'])

    def test_wrong_asset(self):
        self.assertIn('label_bound_to_expected_vector', self.audit(self.text.replace('figure.pdf', 'missing.pdf'))['failures'])

    def test_missing_or_repeated(self):
        for text in [self.text.replace(self.figure, ''), self.text.replace(self.figure, self.figure*2)]:
            self.assertEqual(self.audit(text)['status'], 'FAIL')

    def test_roadmap(self):
        self.diagram['problem_id'] = None
        self.chapter['order'] = 1
        text = r'\section{问题重述}\subsection{问题背景}背景\subsection{问题重述}' + self.lead + self.figure
        r = self.audit(text)
        self.assertEqual(r['status'], 'PASS')
        self.assertEqual(r['lower_anchor'], 'subsection.1.2')
        self.assertEqual(r['upper_anchor'], 'section.2')
        self.assertEqual(self.audit(text.replace(self.figure, '').replace('背景\\subsection', self.figure+'背景\\subsection'))['status'], 'FAIL')

    def test_aux_balanced_caption(self):
        self.assertEqual(label_destinations(r'\newlabel{fig:o}{{1}{4}{对象{与}方法}{figure.caption.1}{}}'),
                         {'fig:o': 'figure.caption.1'})

    def test_nested_input_uses_main_directory(self):
        from audit_visual_plan import body_tex
        (self.root / 'chapters').mkdir()
        (self.root / 'chapters/q.tex').write_text(r'\input{detail}', encoding='utf-8')
        (self.root / 'detail.tex').write_text('正确的正文', encoding='utf-8')
        (self.root / 'chapters/detail.tex').write_text('错误的同名文件', encoding='utf-8')
        self.main.write_text(r'\begin{document}\maketoc\input{chapters/q}\end{document}', encoding='utf-8')
        self.assertIn('正确的正文', body_tex(self.main))
        self.assertNotIn('错误的同名文件', body_tex(self.main))

    def test_missing_input_is_not_silently_omitted(self):
        from audit_visual_plan import body_tex
        self.main.write_text(r'\input{missing}', encoding='utf-8')
        with self.assertRaises(ValueError):
            body_tex(self.main)


if __name__ == '__main__':
    unittest.main()
