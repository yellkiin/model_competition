"""Behavioral source-gate tests; scientific review cannot be automated here."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from evaluation_contract import inspect_evaluation
from evaluation_fixture import evaluation_text
from paper_contract import fragment_errors, chapter_blueprint
from test_paper_contract import make_fixture
from build_latex import build_main


class EvaluationTests(unittest.TestCase):
    def test_valid_enumerate_and_itemize(self):
        for env in ('enumerate', 'itemize'):
            result = inspect_evaluation(evaluation_text().replace('enumerate', env))
            self.assertEqual(result['failures'], [])
            self.assertEqual(list(result['counts'].values()), [3, 3, 2])

    def test_each_list_requires_three(self):
        text = evaluation_text()
        for title in ('模型优点', '模型缺点'):
            start = text.index('\\subsection{' + title + '}')
            first = text.index(r'\item', start)
            second = text.index(r'\item', first + 5)
            errors = inspect_evaluation(text[:first] + text[second:])['failures']
            self.assertIn(title + '至少3点', errors)

    def test_empty_and_label_only_items_fail(self):
        text = evaluation_text()
        first, second = text.index(r'\item'), text.index(r'\item', text.index(r'\item') + 5)
        for value in ('', r'\textbf{空标签}'):
            self.assertTrue(any('缺少具体解释' in x for x in inspect_evaluation(text[:first] + '\\item ' + value + '\n' + text[second:])['failures']))

    def test_nested_items_do_not_inflate_count(self):
        text = evaluation_text().replace(r'\item', r'\item \begin{itemize}\item 假条目\end{itemize}', 1)
        self.assertTrue(inspect_evaluation(text)['failures'])

    def test_single_outlook_paragraph_rejected(self):
        text = evaluation_text()
        head, tail = text.split(r'\subsection{模型的推广与改进}')
        self.assertIn('模型的推广与改进至少两个自然段', inspect_evaluation(head + r'\subsection{模型的推广与改进}' + tail.strip().replace('\n\n', '\n'))['failures'])

    def test_par_is_a_paragraph_but_linebreak_is_not(self):
        text = evaluation_text()
        self.assertFalse(inspect_evaluation(text.replace('\n\n', '\\par\n'))['failures'])
        self.assertTrue(inspect_evaluation(text.replace('\n\n', '\\\\\n'))['failures'])

    def test_outlook_lists_and_manual_numbers_fail(self):
        text = evaluation_text()
        for prefix in (r'\begin{enumerate}\item ', '（1）', '1. ', '• '):
            wrong = text.replace('就推广场景而言', prefix + '就推广场景而言')
            self.assertTrue(inspect_evaluation(wrong)['failures'])

    def test_comments_cannot_supply_items_or_paragraphs(self):
        text = evaluation_text(short=True)
        first, second = text.index(r'\item'), text.index(r'\item', text.index(r'\item') + 5)
        wrong = text[:first] + '% ' + text[first:second].replace('\n', '\n% ') + text[second:]
        self.assertTrue(inspect_evaluation(wrong)['failures'])

    def test_padding_and_extra_headings_fail(self):
        for addition in (r'\vspace{10cm}', r'\newpage', r'\fontsize{16pt}{30pt}\selectfont', r'\subsubsection{其他}', r'\setlength{\parskip}{20pt}'):
            self.assertTrue(inspect_evaluation(evaluation_text() + addition)['failures'])

    def test_duplicate_items_fail(self):
        text = evaluation_text()
        positions = [m.start() for m in __import__('re').finditer(r'\\item\b', text)]
        wrong = text[:positions[1]] + text[positions[0]:positions[1]] + text[positions[2]:]
        self.assertTrue(any('重复' in x for x in inspect_evaluation(wrong)['failures']))

    def test_role_not_fixed_chapter_seven_and_generator_rejects(self):
        for q in (1, 3, 5):
            with tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                manifest = make_fixture(root, q)
                source, _ = build_main(manifest, root, include_appendix=False)
                self.assertIn('\\def\\GMCMEvaluationSection{' + str(q+4) + '}', source)
                chapter = next(c for c in manifest['chapters'] if c['role']=='evaluation')
                self.assertFalse(fragment_errors(evaluation_text(), chapter))
                p = root / chapter['tex_path']
                p.write_text(evaluation_text().replace(r'\item', '% removed item ', 1), encoding='utf8')
                with self.assertRaises(ValueError):
                    build_main(manifest, root, include_appendix=False)

    def test_calibration_keeps_observations_without_restoring_cap(self):
        tool = Path(__file__).with_name('calibrate_page_targets.py')
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / 'targets.json'
            subprocess.run([sys.executable, '-B', str(tool), '--maintenance', '--baseline', str(tool.parents[1] / '章节页数基线.json'), '--output', str(target)], check=True, capture_output=True)
            data = json.loads(target.read_text(encoding='utf8'))
            self.assertNotIn('模型评价与展望', data['chapter_hard_limits'])
            self.assertNotIn('max_pages', data['role_targets']['evaluation'])
            self.assertEqual(data['evaluation_prose']['minimum_equivalent_pages'], 1)
            self.assertEqual(data['required_body_pages'], 35)
            self.assertEqual(data['chapter_hard_limits']['关键性符号说明'], 2)
            self.assertEqual(data['role_targets']['evaluation']['observed'], [1,1])


if __name__ == '__main__':
    unittest.main()
