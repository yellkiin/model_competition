"""Behavioral tests of chapter generation inputs, not matches against rule prose."""
from pathlib import Path
import tempfile
import unittest

from paper_contract import (chapter_blueprint, chinese_number, audit_structure,
                            caption_errors, strip_comments, commands)
from build_latex import build_main, copy_assets


def make_fixture(root: Path, count: int = 3) -> dict:
    chapters = []
    for c in chapter_blueprint(count):
        c = {**c, 'chapter_id': f"c{c['order']}", 'tex_path': f"c{c['order']}.tex"}
        if c['role'] == 'references':
            text = r'\bibliographystyle{gmcm}' + '\n' + r'\bibliography{reference}'
        else:
            text = '\\section{' + c['title'] + '}\n'
            if c['order'] == 1:
                text += '\\subsection{问题背景}\n背景。\n\\subsection{问题重述}\n任务。'
            elif c['order'] == 3:
                text += '\n如表~\\ref{tab:key-symbols}所示。\n\\begin{GMCMSymbolTable}{其余符号在首次使用处定义。}\n\\GMCMSymbolRow{参数}{n}{隔离测试的行数}{1}\n\\end{GMCMSymbolTable}\n'
            elif c['role'] == 'problem':
                text += '\\subsection{问题的描述与分析}\n描述。\n\\subsection{模型与验证}\n推导。'
                c['abstract_type'] = 'theory'
            elif c['role'] == 'evaluation':
                from evaluation_fixture import evaluation_text
                text = evaluation_text()
        (root / c['tex_path']).write_text(text, encoding='utf-8')
        chapters.append(c)
    (root / 'abstract.tex').write_text('隔离单元测试片段，不是已验收摘要。', encoding='utf-8')
    result = {'title': '章节结构隔离测试', 'keywords': ['结构', '编号', '模型'],
            'abstract_tex_path': 'abstract.tex', 'chapters': chapters}
    from test_first_chapters import fixture_evidence
    fixture_evidence(root, result)
    return result


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_question_counts_generate_continuous_structure(self):
        for q in (1, 2, 4, 11):
            manifest = make_fixture(self.root, q)
            self.assertEqual(audit_structure(manifest, self.root)['status'], 'PASS')
            tex, _ = build_main(manifest, self.root, include_appendix=False)
            self.assertIn('\\input{c' + str(q + 5) + '.tex}', tex)
            self.assertEqual(manifest['chapters'][-1]['order'], q + 5)
            self.assertEqual(manifest['chapters'][q + 2]['title'], f'问题{chinese_number(q)}求解与分析')

    def test_extra_independent_validation_chapter_rejected_by_generator(self):
        manifest = make_fixture(self.root)
        c = {'chapter_id': 'extra', 'order': 7, 'title': '独立验证', 'role': 'conclusion', 'tex_path': 'extra.tex'}
        (self.root / 'extra.tex').write_text(r'\section{独立验证}', encoding='utf-8')
        manifest['chapters'].insert(6, c)
        with self.assertRaises(ValueError):
            build_main(manifest, self.root, include_appendix=False)

    def test_wrong_question_first_subsection_rejected(self):
        manifest = make_fixture(self.root)
        p = self.root / 'c4.tex'
        p.write_text(p.read_text(encoding='utf-8').replace('问题的描述与分析', '数据审计'), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '第一个二级标题'):
            build_main(manifest, self.root, include_appendix=False)

    def test_renamed_source_or_extra_subsection_rejected(self):
        manifest = make_fixture(self.root)
        p = self.root / 'c1.tex'
        p.write_text(p.read_text(encoding='utf-8') + '\n\\subsection{额外分析}', encoding='utf-8')
        self.assertEqual(audit_structure(manifest, self.root)['status'], 'FAIL')

    def test_nested_section_not_hidden_from_audit(self):
        manifest = make_fixture(self.root)
        p = self.root / 'c4.tex'
        p.write_text(p.read_text(encoding='utf-8') + '\n\\input{hidden.tex}', encoding='utf-8')
        (self.root / 'hidden.tex').write_text(r'\section{额外的一级章}', encoding='utf-8')
        with self.assertRaises(ValueError):
            build_main(manifest, self.root, include_appendix=False)

    def test_project_bibliography_survives_rebuild(self):
        template = self.root / 'template'
        template.mkdir()
        (template / 'reference.bib').write_text('% empty template', encoding='utf-8')
        bib = self.root / 'reference.bib'
        bib.write_text('@article{real, title={Existing bibliography}}', encoding='utf-8')
        original = bib.read_bytes()
        copy_assets(template, self.root, include_appendix=False)
        self.assertEqual(original, bib.read_bytes())

    def test_short_caption_and_explanatory_note_are_distinct(self):
        self.assertFalse(caption_errors('模型误差分布'))

    def test_template_bibliography_is_not_imported_by_default(self):
        template = self.root / 'sample-template'
        template.mkdir()
        (template / 'reference.bib').write_text('@article{sample,title={Template example}}', encoding='utf8')
        copy_assets(template, self.root, include_appendix=False)
        self.assertFalse((self.root / 'reference.bib').exists())
        copy_assets(template, self.root, include_appendix=False, legacy_bibliography=True)
        self.assertTrue((self.root / 'reference.bib').is_file())
        self.assertTrue(caption_errors('模型误差分布。误差线表示标准差。'))
        self.assertTrue(caption_errors(r'\small 模型误差分布'))
        self.assertEqual(commands(r'\caption{误差 $\mathrm{RMSE}$}', ('caption',))[0].argument,
                         r'误差 $\mathrm{RMSE}$')

    def test_generated_main_has_one_fixed_ai_disclosure_hook(self):
        manifest = make_fixture(self.root)
        tex, _ = build_main(manifest, self.root, include_appendix=False)
        self.assertEqual(tex.count('ai_tool_disclosure'), 1)
        self.assertIn('DeepSeek-V4.1-Flash', tex)
        tex_again, _ = build_main(manifest, self.root, include_appendix=False)
        self.assertEqual(tex_again.count('ai_tool_disclosure'), 1)

    def test_percent_comment_parser_preserves_scientific_values(self):
        self.assertEqual(strip_comments('误差 5\\% 。% comment\n正文'), '误差 5\\% 。\n正文')

    def test_caption_hack_in_nested_input_rejected_before_generation(self):
        manifest = make_fixture(self.root)
        p = self.root / 'c4.tex'
        p.write_text(p.read_text(encoding='utf-8') + '\n\\input{caption.tex}', encoding='utf-8')
        (self.root / 'caption.tex').write_text(
            r'\begin{figure}\caption{\small 被缩小的图题}\end{figure}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '不得通过缩字'):
            build_main(manifest, self.root, include_appendix=False)

    def test_source_newline_is_not_a_physical_caption_line_break(self):
        self.assertFalse(caption_errors('分组\n误差分布'))
        self.assertTrue(caption_errors(r'分组\\误差分布'))


if __name__ == '__main__':
    unittest.main()
