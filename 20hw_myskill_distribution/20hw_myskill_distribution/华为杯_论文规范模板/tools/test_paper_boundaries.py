"""Reference and appendix boundaries must exclude both from body page counts."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from audit_paper import detect_heading_pages_from_toc, role_ranges, body_pages, pdfinfo, printed_page_offset

class PaperBoundaryTests(unittest.TestCase):
    def test_abstract_statistics_are_not_footer_page_numbers(self):
        records=[dict(physical_page=1,spans=[
            dict(text='128',bbox=[146,759,164,771]),
            dict(text='1',bbox=[294,791,301,804])])]
        self.assertEqual(printed_page_offset(records),0)

    def test_starred_reference_and_appendix_sections(self):
        records=[dict(physical_page=i,spans=[]) for i in range(1,55)]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'paper.toc'
            path.write_text(
                '\\contentsline {section}{\\numberline {1}问题分析}{5}{section.1}%\n'
                '\\contentsline {section}{\\numberline {7}模型评价}{37}{section.7}%\n'
                '\\contentsline {section}{参考文献}{40}{section*.40}%\n'
                '\\contentsline {section}{附录}{41}{section*.43}%\n',encoding='utf-8')
            chapters=detect_heading_pages_from_toc(path,records)
            self.assertEqual([c['role'] for c in chapters],['body','body','references','appendix'])
            self.assertEqual(body_pages(role_ranges(chapters,records)),dict(start=5,end=39,pages=35))

    def test_localized_poppler_output(self):
        raw='Pages: 54\nCreationDate: 中国标准时间\n'.encode('gb18030')
        with patch('audit_paper.subprocess.run',return_value=SimpleNamespace(stdout=raw)):
            result=pdfinfo(Path('paper.pdf'))
        self.assertEqual(result['Pages'],'54')
        self.assertEqual(result['CreationDate'],'中国标准时间')

if __name__=='__main__': unittest.main()
