"""Gallery behavior tests. Stub render gates test display only, never scientific QA."""
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image
import candidate_gallery as gallery
from workspace_context import atomic_json, file_hash


class GalleryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.output = self.root / '待选图库'
        (self.root / '求解').mkdir()
        Image.new('RGB', (40, 30), 'red').save(self.root / '求解/source.png')
        for name in ('source.pdf', 'qa.json', 'source.py'):
            (self.root / '求解' / name).write_text('display test only', encoding='utf8')
        self.figure = dict(figure_id='q1_F1', outputs={'preview': '求解/source.png', 'vector': '求解/source.pdf'},
                           qa_report='求解/qa.json', script='求解/source.py')
        atomic_json(self.root / 'plan.json', {'global_figures': [self.figure]})
        self.candidate = dict(figure_id='q1_F1', question_id='q1', quality='qualified', destination='reserve',
                              plan_path='plan.json', scientific_question='用于展示测试的科学问题，不代表通过科学审阅',
                              conclusion='展示测试结论', limitations='仅检验图片副本和网页链接',
                              selection_reason='该独立信息用于补充对照，正文已有核心证据', recommended_section='问题一验证')
        self.registry = {'questions': [{'question_id': 'q1', 'completion_review': None}], 'candidates': [self.candidate]}

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, status='PASS'):
        atomic_json(self.root / 'registry.json', self.registry)
        return gallery.build(self.root, 'registry.json', self.output, 'codex', lambda *a: {'status': status})

    def test_reserve_has_real_copies_and_local_links(self):
        result = self.build()
        self.assertEqual(result['display_copy_count'], 2)
        copies = json.loads((self.output / '展示副本.json').read_text(encoding='utf8'))['files']
        for entry in copies:
            self.assertEqual(file_hash(self.output / '图片' / entry['display_path']), file_hash(self.root / entry['source_path']))
        index = json.loads((self.output / 'index.json').read_text(encoding='utf8'))[0]
        self.assertTrue((self.output / index['display_preview']).is_file())
        self.assertTrue((self.output / index['display_primary']).is_file())
        page = (self.output / 'index.html').read_text(encoding='utf8')
        self.assertIn('<img ', page)
        self.assertIn('未入文原因', page)

    def test_supplement_is_in_default_view_paper_is_separate(self):
        self.candidate['destination'] = 'supplement'
        result = self.build()
        self.assertEqual(result['qualified_supplement_count'], 1)
        page = (self.output / 'index.html').read_text(encoding='utf8')
        self.assertIn('<img ', page.split('<details>')[0])
        self.candidate['destination'] = 'paper'
        self.build()
        page = (self.output / 'index.html').read_text(encoding='utf8')
        self.assertNotIn('<img ', page.split('<details>')[0])
        self.assertIn('<img ', page.split('<details>')[1])

    def test_source_update_refreshes_and_stale_removes_managed_copies(self):
        self.build()
        previous = json.loads((self.output / '展示副本.json').read_text(encoding='utf8'))
        Image.new('RGB', (40, 30), 'blue').save(self.root / '求解/source.png')
        self.build()
        current = json.loads((self.output / '展示副本.json').read_text(encoding='utf8'))
        self.assertNotEqual(previous['files'][0]['sha256'], current['files'][0]['sha256'])
        self.build('FAIL')
        self.assertFalse(list((self.output / '图片').rglob('*.png')))
        self.assertFalse(list((self.output / '图片').rglob('*.pdf')))
        page = (self.output / 'index.html').read_text(encoding='utf8')
        self.assertNotIn('<img ', page)
        self.assertIn('过期', page)

    def test_empty_explains_unreviewed_state(self):
        self.registry['candidates'] = []
        self.build()
        page = (self.output / 'index.html').read_text(encoding='utf8')
        self.assertIn('候选总数：0', page)
        self.assertIn('q1：当前没有合格未入文图', page)
        self.assertIn('尚未填写零剩余原因', page)
        self.assertIn('缺失或过期', page)

    def test_stale_gate_overrides_unchanged_historical_review_files(self):
        from candidate_figures import inventory
        scopes = ['求解/source.py', '求解/qa.json']
        self.registry['questions'][0]['completion_review'] = {
            'scopes': scopes, 'files': inventory(self.root, scopes),
            'observation': '历史复查文件没有变化，但不能据此认定共享资源更新后图件仍然合格。',
            'zero_remaining_reason': '唯一候选使用旧版本审核，当前过期，需重新复核后再展示。'}
        self.build('FAIL')
        page = (self.output / 'index.html').read_text(encoding='utf8')
        self.assertIn('关联图件或共享资源已过期，须重新复核', page)
        self.assertIn('历史复查结论（当前不可沿用）', page)
        self.assertNotIn('文件清单当前一致', page)
        self.assertNotIn('<img ', page)

    def test_malicious_copy_manifest_cannot_delete_unrelated_file(self):
        self.output.mkdir()
        atomic_json(self.output / '展示副本.json', {'files': [{'display_path': '../../求解/source.py', 'sha256': file_hash(self.root / '求解/source.py')}]})
        with self.assertRaises(ValueError):
            self.build()
        self.assertTrue((self.root / '求解/source.py').is_file())

    def test_edited_stale_copy_not_silently_deleted(self):
        self.build()
        index = json.loads((self.output / 'index.json').read_text(encoding='utf8'))[0]
        (self.output / index['display_preview']).write_bytes(b'externally changed')
        with self.assertRaisesRegex(ValueError, '单独修改'):
            self.build('FAIL')
        page = (self.output / 'index.html').read_text(encoding='utf8')
        self.assertNotIn('<img ', page)
        self.assertIn('旧合格展示已撤下', page)

    def test_failed_rebuild_never_keeps_old_qualified_page(self):
        self.build()
        (self.root / '求解/source.png').unlink()
        with self.assertRaises(FileNotFoundError):
            self.build()
        self.assertNotIn('<img ', (self.output / 'index.html').read_text(encoding='utf8'))
        self.assertEqual(json.loads((self.output / 'index.json').read_text(encoding='utf8')), [])
        self.assertEqual(json.loads((self.output / '构建状态.json').read_text(encoding='utf8'))['status'], 'FAILED')

    def test_question_folders_are_chinese_and_stable(self):
        self.build()
        files = list((self.output / '图片/问题一').glob('*'))
        self.assertEqual(len(files), 2)


if __name__ == '__main__':
    unittest.main()
