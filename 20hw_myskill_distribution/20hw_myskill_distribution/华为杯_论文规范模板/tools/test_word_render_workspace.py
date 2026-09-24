"""Path and stale-output regression; fake Word is not a PDF visual audit."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '华为杯_求解规范/tools'))
import test_workspace_context as fixtures
import workspace_context as wc
from run_word_render import render


class WordPathTests(unittest.TestCase):
    setUp = fixtures.WorkspaceTests.setUp
    tearDown = fixtures.WorkspaceTests.tearDown

    def prepare(self):
        script = self.root / '华为杯_论文规范模板/tools/render_word.vbs'
        script.parent.mkdir()
        script.write_text('controlled native test stub')
        c = wc.create_workspace(self.root, 'claude')
        (c.workspace_root / '论文/source.docx').write_bytes(b'input fixture')
        return c

    def test_output_escape_rejected_before_native_program(self):
        c = self.prepare()
        for output in ('../shared.pdf', '../workshop_v2/paper.pdf', '题目/paper.pdf'):
            with patch('run_word_render.subprocess.run') as native, self.assertRaises(ValueError):
                render(c, '论文/source.docx', output, '论文/report.json')
            native.assert_not_called()

    def test_stale_pdf_not_accepted_when_native_produces_nothing(self):
        c = self.prepare()
        old = c.workspace_root / '论文/paper.pdf'
        old.write_bytes(b'old result must survive failure')
        with patch('run_word_render.shutil.which', return_value='cscript'), patch('run_word_render.subprocess.run',
                return_value=SimpleNamespace(returncode=0, stdout=b'', stderr=b'')), self.assertRaisesRegex(ValueError, '本次有效 PDF'):
            render(c, '论文/source.docx', '论文/paper.pdf', '论文/report.json')
        self.assertEqual(old.read_bytes(), b'old result must survive failure')
        self.assertEqual(c.check_shared()['status'], 'PASS')

    def test_native_receives_absolute_scoped_paths_and_stages_new_results(self):
        c = self.prepare()
        def fake_native(command, **kwargs):
            self.assertEqual(kwargs['cwd'], c.workspace_root)
            self.assertEqual(Path(command[2]), self.root / '华为杯_论文规范模板/tools/render_word.vbs')
            self.assertTrue(all(Path(p).is_absolute() for p in command[2:]))
            self.assertTrue(all(Path(p).is_relative_to(c.workspace_root) for p in command[3:]))
            Path(command[4]).write_bytes(b'%PDF-fixture-only')
            Path(command[5]).write_text('{"physical_pages": 1, "headings": []}')
            return SimpleNamespace(returncode=0, stdout=b'native fixture', stderr=b'')
        with patch('run_word_render.shutil.which', return_value='cscript'), patch('run_word_render.subprocess.run', side_effect=fake_native):
            result = render(c, '论文/source.docx', '论文/paper.pdf', '论文/report.json')
        self.assertEqual(result['status'], 'RENDERED_REVIEW_REQUIRED')
        self.assertEqual(c.check_shared()['status'], 'PASS')


if __name__ == '__main__':
    unittest.main()
