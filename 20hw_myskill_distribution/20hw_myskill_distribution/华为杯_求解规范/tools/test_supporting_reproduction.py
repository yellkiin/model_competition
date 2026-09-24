"""Actual subprocess and output regressions, independent of visual QA."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from build_supporting_materials import build
from init_supporting_materials import make_question
from reproduce_supporting_materials import audit_reproduction, equal_json, receipt_path, reproduce, save


class SupportingReproductionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gmcm-reproduction-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base/'project'
        self.root.mkdir()
        self.path = self.root/'求解/支撑材料清单.json'
        self.q = make_question('q1', '问题一')
        # This fixture exercises the legacy standalone reproduction contract.
        # Modern workspace model declarations are tested in the registered DEMO.
        self.q.pop('model_selection')
        source = self.root/self.q['entrypoint']
        source.parent.mkdir(parents=True)
        source.write_text(
            "import json, sys, statistics\nfrom pathlib import Path\n"
            "values = [1, 2, 4, 9]\n"
            "if '--verify' in sys.argv:\n"
            "    assert json.loads(Path('result.json').read_text())['mean'] == statistics.mean(values)\n"
            "else:\n"
            "    Path('result.json').write_text(json.dumps({'mean': sum(values)/len(values)}))\n", encoding='utf-8')
        commands = []
        for extra in ([], ['--verify']):
            argv = [sys.executable, '-X', 'utf8', str(source), *extra]
            r = subprocess.run(argv, cwd=source.parent, capture_output=True, text=True, encoding='utf-8', check=True)
            commands.append(dict(argv=argv, returncode=r.returncode, stdout=r.stdout, stderr=r.stderr))
        self.q.update(status='complete', summary='算术平均值演练源码', package_command='python main.py')
        self.q['source_files'][0]['package_path'] = 'main.py'
        self.q['run_verification'].update(status='pass', verified_at='actual subprocess in setUp')
        save(self.root/self.q['run_verification']['record_path'], {'runs':commands})
        self.q['reproduction'] = dict(commands=[
            dict(purpose='solve', argv=['{python}', '-X', 'utf8', 'main.py']),
            dict(purpose='validate', argv=['{python}', '-X', 'utf8', 'main.py', '--verify'])],
            outputs=[dict(path='result.json', expected_path='求解/问题一/result.json', comparison='json')])
        (self.root/self.q['environment_doc']).write_text('环境 安装 输入 运行 输出 依赖 python main.py', encoding='utf-8')
        self.manifest = dict(schema_version='2.0', project_title='隔离复现测试', package_status='complete',
            questions=[self.q], external_data=[], external_data_note='确定性合成输入，无外部数据',
            official_outputs=[], readme_source='求解/支撑材料说明.md', additional_files=[],
            category_descriptions={'其他数据':'无','其他支撑材料':'无'})
        (self.root/self.manifest['readme_source']).write_text(
            '复现 数据 结果\n问题一 算术平均值演练源码\n其他数据 无\n其他支撑材料 无', encoding='utf-8')
        self.rebuild()

    def rebuild(self):
        save(self.path, self.manifest)
        build(self.path, self.root, self.root/'提交附件')

    def run_package(self):
        return reproduce(self.root, self.path, self.root/'提交附件', self.base/'independent')

    def audit(self):
        return audit_reproduction(self.root, self.path, self.root/'提交附件', self.q, 1)

    def test_actual_subprocesses_and_rebuilt_receipt_pass(self):
        report = self.run_package()
        self.assertEqual(report['status'], 'PASS', report)
        self.assertEqual(len(report['questions'][0]['runs']), 2)
        self.rebuild()
        self.assertEqual(self.audit()['status'], 'PASS')

    def test_plain_pass_record_is_not_reproduction(self):
        save(receipt_path(self.root, 'q1'), {'status':'PASS'})
        self.assertEqual(self.audit()['status'], 'FAIL')

    def test_wrong_numeric_reference_fails(self):
        save(self.root/'求解/问题一/result.json', {'mean':400})
        result = self.run_package()
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('differs', result['questions'][0]['errors'][0])

    def test_nonzero_validator_fails_with_log(self):
        self.q['reproduction']['commands'][1]['argv'] = ['{python}', '-c', 'raise SystemExit(7)']
        self.rebuild()
        result = self.run_package()
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['questions'][0]['runs'][-1]['returncode'], 7)

    def test_commands_that_do_not_produce_outputs_fail(self):
        for command in self.q['reproduction']['commands']:
            command['argv'] = ['{python}', '-c', 'pass']
        self.rebuild()
        self.assertEqual(self.run_package()['status'], 'FAIL')

    def test_prepackaged_result_is_not_recomputed_evidence(self):
        self.q['source_files'].append(dict(path='求解/问题一/result.json', description='错误预置输出', package_path='result.json'))
        self.rebuild()
        report = self.run_package()
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(report['questions'][0]['runs'], [])

    def test_modified_manifest_invalidates_receipt_even_after_rebuild(self):
        self.assertEqual(self.run_package()['status'], 'PASS')
        self.manifest['project_title'] = '修改后的说明'
        self.rebuild()
        self.assertEqual(self.audit()['status'], 'FAIL')

    def test_changed_output_or_log_fails(self):
        result = self.run_package()
        self.assertEqual(result['status'], 'PASS')
        log = Path(result['questions'][0]['runs'][0]['stdout'])
        log.write_text('rewritten')
        self.assertEqual(self.audit()['status'], 'FAIL')
        log.write_bytes(b'')
        self.assertEqual(self.audit()['status'], 'PASS')
        (Path(result['questions'][0]['cwd'])/'result.json').write_text('{"mean":999}')
        self.assertEqual(self.audit()['status'], 'FAIL')

    def test_old_or_project_directory_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'outside'):
            reproduce(self.root, self.path, self.root/'提交附件', self.root/'independent')
        self.run_package()
        with self.assertRaisesRegex(ValueError, 'reuse'):
            self.run_package()

    @unittest.skipUnless(os.name == 'nt', 'Windows path identity')
    def test_same_windows_directory_spelling_is_accepted(self):
        self.assertEqual(self.run_package()['status'], 'PASS')
        path = receipt_path(self.root, 'q1')
        receipt = json.loads(path.read_text(encoding='utf-8'))
        receipt['cwd'] = receipt['cwd'].swapcase()
        save(path, receipt)
        self.assertEqual(self.audit()['status'], 'PASS')

    def test_complete_question_cannot_omit_reproduction_recipe(self):
        del self.q['reproduction']
        with self.assertRaisesRegex(Exception, 'reproduction'):
            self.rebuild()

    def test_json_tolerance_preserves_shape_types_and_finite_numbers(self):
        self.assertTrue(equal_json({'x':[1.00001]}, {'x':[1]}, 0.001, 0))
        self.assertFalse(equal_json({'x':[1]}, {'x':[1, 2]}, 10, 0))
        self.assertFalse(equal_json(True, 1, 0, 0))
        self.assertFalse(equal_json(float('nan'), float('nan'), 0, 0))
        self.assertFalse(equal_json(float('inf'), float('inf'), 0, 0))


if __name__ == '__main__':
    unittest.main()
