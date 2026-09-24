"""Behavioral tests; fixtures make no claims of genuine visual review."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import candidate_figures as cf
from prepare_academic_figure_review import select_figures
from supporting_contract import FORBIDDEN_PARTS


class StageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / '求解/候选图清单.json'
        (self.root / 'science').mkdir()
        (self.root / 'science/model.py').write_text('result = sum(range(5))\n', encoding='utf-8')
        (self.root / 'science/result.json').write_text('{"value": 10}\n', encoding='utf-8')
        self.files = cf.snapshot(self.root, ['science/model.py', 'science/result.json'])
        self.r = cf.initialize(self.root, self.path, ['q1'])
        q = self.r['questions'][0]
        q.update(problem_types=['optimization', 'regression'], type_reason='This mixed problem fits a response model and optimizes its decision.',
                 type_reviews=[dict(problem_type=t, risk_review='Inspect error structure and sensitivity using actual numerical outputs.', evidence=self.files) for t in ['optimization', 'regression']],
                 expected_stages=['q1_fit'])
        cf.open_stage(self.root, self.r, 'q1', 'q1_fit', 'model_training', ['science/model.py'])
        cf.complete_stage(self.root, self.r, 'q1_fit', ['science/result.json'])
        self.s = self.r['stages'][0]
        for c in self.s['checks']:
            c.update(scientific_question=cf.DIMENSIONS[c['dimension']], decision='text_table',
                     reason='This exact finite calculation is reproducible from the stored scalar and source.',
                     evidence=self.files, resolved=True)
        cf.record_review(self.root, self.r, 'q1_fit')
        q['completion_review'] = dict(observation='Reviewed the numerical source and scalar result for all listed stages.',
                                      scopes=['science'], files=self.files, stage_ids=['q1_fit'])

    def tearDown(self):
        self.temp.cleanup()

    def audit(self, final=True):
        cf.write_json(self.path, self.r)
        return cf.audit_registry(self.root, self.path, 'codex', 'question' if final else 'progress', 'q1')

    def expect_failure(self, code):
        r = self.audit()
        self.assertEqual(r['status'], 'FAIL', r)
        self.assertIn(code, json.dumps(r['failures']))

    def test_zero_figures_valid_when_all_dimensions_have_evidence(self):
        self.assertEqual(self.audit()['status'], 'PASS', self.audit())

    def test_missing_stage(self):
        self.r['questions'][0]['expected_stages'].append('q1_validation')
        self.expect_failure('stage_not_triggered')

    def test_missing_dimension(self):
        self.s['checks'].pop()
        self.expect_failure('seven_dimensions_missing')

    def test_duplicate_dimension(self):
        self.s['checks'][0]['dimension'] = self.s['checks'][1]['dimension']
        self.expect_failure('seven_dimensions_missing_or_duplicate')

    def test_empty_reason(self):
        self.s['checks'][0]['reason'] = 'already checked'
        self.s['checks'][0]['decision'] = 'pending'
        self.expect_failure('unreasoned_decision')

    def test_unsupported_na(self):
        self.s['checks'][0].update(decision='not_applicable', reason='无必要', evidence={})
        self.expect_failure('missing_or_stale_evidence')

    def test_changed_result_invalidates_review(self):
        (self.root / 'science/result.json').write_text('{"value": 11}\n', encoding='utf-8')
        self.expect_failure('stage_evidence_stale')

    def test_new_result_detected_by_reenumeration(self):
        (self.root / 'science/unreviewed.json').write_text('{"new": true}\n', encoding='utf-8')
        self.expect_failure('completion_inventory_review_missing_or_stale')

    def test_revision_replaces_stale_stage_without_rewriting_history(self):
        original_event = self.s['completion_event']
        (self.root / 'science/result.json').write_text('{"value": 11}\n', encoding='utf-8')
        self.r['questions'][0]['expected_stages'].append('q1_revision')
        cf.open_stage(self.root, self.r, 'q1', 'q1_revision', 'method_result_change', ['science/model.py'], 'q1_fit')
        cf.complete_stage(self.root, self.r, 'q1_revision', ['science/result.json'])
        revised = self.r['stages'][-1]
        revised['checks'] = copy.deepcopy(self.s['checks'])
        fresh = cf.snapshot(self.root, list(self.files))
        for c in revised['checks']: c['evidence'] = fresh
        cf.record_review(self.root, self.r, 'q1_revision')
        q = self.r['questions'][0]
        q['completion_review'].update(files=fresh, stage_ids=q['expected_stages'])
        for r in q['type_reviews']: r['evidence'] = fresh
        self.assertEqual(self.audit()['status'], 'PASS', self.audit())
        self.assertEqual(self.s['completion_event'], original_event)

    def test_candidate_id_survives_revision_without_quality_transfer(self):
        cf.register_candidate(self.root, self.r, self.make_candidate())
        self.r['candidates'][0]['quality'] = 'qualified'
        self.r['questions'][0]['expected_stages'].append('q1_revision')
        cf.open_stage(self.root, self.r, 'q1', 'q1_revision', 'method_result_change', ['science/model.py'], 'q1_fit')
        self.assertEqual(self.r['candidates'][0]['quality'], 'stale')
        cf.complete_stage(self.root, self.r, 'q1_revision', ['science/result.json'])
        cf.revise_candidate(self.root, self.r, 'q1_F01', 'q1_revision')
        self.assertEqual(self.r['candidates'][0]['figure_id'], 'q1_F01')
        self.assertEqual(self.r['candidates'][0]['quality'], 'review_required')

    def test_changed_checks_require_new_receipt(self):
        self.s['checks'][0]['reason'] = 'The new interpretation changes the scientific question of this stage.'
        self.expect_failure('stage_review_receipt_missing_or_changed')

    def test_invalid_reuse(self):
        self.s['checks'][0]['reuse'] = dict(stage_id='missing', dimension='data_structure', checks_digest='a' * 64)
        self.expect_failure('invalid_reuse')

    def test_promised_candidate_missing(self):
        self.s['checks'][0].update(decision='new_figure', candidate_ids=['missing'])
        self.expect_failure('promised_figure_not_qualified')

    def test_blocked_cannot_be_resolved_by_flag(self):
        self.s['checks'][0].update(decision='blocked', followup='Acquire the missing measurement before drawing conclusions.', resolved=True)
        self.expect_failure('unresolved_action')

    def test_new_analysis_requires_completed_evidence_decision(self):
        self.s['checks'][0].update(decision='new_analysis', followup='Run a new sensitivity analysis before selecting the evidence.', resolved=True)
        self.expect_failure('unresolved_action')

    def test_another_stage_may_start_before_prior_review(self):
        self.s['review_event'] = None
        self.r['questions'][0]['expected_stages'].append('q1_independent')
        cf.open_stage(self.root, self.r, 'q1', 'q1_independent', 'validation', ['science/model.py'])
        self.assertEqual(len(self.r['stages']), 2)

    def test_deleted_stage_detected_from_events(self):
        self.r['stages'] = []
        self.r['questions'][0]['expected_stages'] = []
        self.expect_failure('stage_event_missing_from_registry')

    def test_mixed_type_review_missing(self):
        self.r['questions'][0]['type_reviews'].pop()
        self.expect_failure('type_review_missing')

    def test_unknown_candidate_question(self):
        c = self.make_candidate()
        c['question_id'] = 'missing'
        self.r['candidates'].append(c)
        self.expect_failure('question_ids_duplicate_or_unresolved')

    def make_candidate(self):
        return dict(figure_id='q1_F01', question_id='q1', stage_id='q1_fit', plan_path='plan.json',
                    quality='planned', destination='reserve', scientific_question='How does the stored response depend on the decision?',
                    selection_reason='The response needs a detailed inspection before paper selection.',
                    conclusion='', limitations='', recommended_section='q1', statistical_unit='independent run', discovery_event='')

    def test_registration_creates_real_event_without_qa(self):
        cf.register_candidate(self.root, self.r, self.make_candidate())
        c = self.r['candidates'][0]
        self.assertTrue(c['discovery_event'])
        self.assertEqual(c['quality'], 'planned')
        self.assertEqual(self.audit()['status'], 'PASS')

    def test_selected_unqualified(self):
        cf.register_candidate(self.root, self.r, self.make_candidate())
        self.r['candidates'][0]['destination'] = 'paper'
        self.expect_failure('selected_but_not_qualified')

    def test_stale_render_cannot_pass_registry(self):
        cf.register_candidate(self.root, self.r, self.make_candidate())
        self.r['candidates'][0]['quality'] = 'qualified'
        with patch.object(cf, 'audit_figure', return_value={'status': 'FAIL', 'failures': ['stale']}):
            self.expect_failure('visual_render_failed_or_stale')

    def test_no_html_injection_from_pending_candidates(self):
        c = self.make_candidate(); c['figure_id'] = '<script>alert(1)</script>'
        cf.register_candidate(self.root, self.r, c)
        cf.write_json(self.path, self.r)
        out = self.root / '待选图库'
        cf.build_gallery(self.root, self.path, out, 'codex')
        page = (out / 'index.html').read_text(encoding='utf-8')
        self.assertNotIn('<script>', page)
        self.assertNotIn('<article>', page)

    def test_waiting_gallery_forbidden_in_submission(self):
        self.assertIn('待选图库', FORBIDDEN_PARTS)

    def test_reserve_cannot_bypass_through_additional_files(self):
        c = self.make_candidate()
        cf.register_candidate(self.root, self.r, c)
        cf.write_json(self.root / 'plan.json', {'global_figures': [dict(figure_id='q1_F01', outputs={'vector': 'science/result.pdf', 'preview': 'science/result.png'})]})
        cf.write_json(self.path, self.r)
        errors = cf.package_selection_errors(self.root, self.path, {'questions': [], 'additional_files': [{'path': 'science/result.pdf'}]}, 'codex')
        self.assertIn('unselected_candidate_in_package', ';'.join(errors))

    def test_unregistered_pdf_table_is_not_assumed_to_be_a_figure(self):
        cf.write_json(self.path, self.r)
        manifest = {'questions': [{'question_id': 'q1', 'supplementary_materials': [{'path': 'science/long_table.pdf'}]}]}
        self.assertEqual(cf.package_selection_errors(self.root, self.path, manifest, 'codex'), [])

    def test_unregistered_pdf_declared_as_figure_is_rejected(self):
        cf.write_json(self.path, self.r)
        manifest = {'questions': [{'question_id': 'q1', 'supplementary_materials': [
            {'path': 'science/map.pdf', 'material_type': 'figure'}]}]}
        self.assertIn('supplement_figure_not_registered', ';'.join(
            cf.package_selection_errors(self.root, self.path, manifest, 'codex')))

    def test_missing_candidate_input_returns_failed_audit(self):
        self.assertEqual(cf.audit_figure(self.root, 'missing.json', 'missing', 'render', 'codex')['status'], 'FAIL')

    def test_contract_digest_detects_style_and_size_change(self):
        f = {'figure_id': 'f', 'status': 'planned'}
        r = {'style': {'size': 128}, 'status': 'incomplete'}
        before = cf.figure_contract_digest(f, r)
        f['status'] = 'qa_pass'; r['status'] = 'qa_pass'
        self.assertEqual(before, cf.figure_contract_digest(f, r))
        r['style']['size'] = 100
        self.assertNotEqual(before, cf.figure_contract_digest(f, r))


class SelectionTests(unittest.TestCase):
    def test_only_selected_figure_enters_scope(self):
        plan = {'global_figures': [], 'problems': [{'figures': [{'figure_id': 'ready'}, {'figure_id': 'pending'}]}]}
        refs = {'figures': [{'figure_id': 'ready'}, {'figure_id': 'pending', 'broken': True}]}
        selected, records = select_figures(plan, refs, ['ready'])
        self.assertEqual([f['figure_id'] for f in selected['problems'][0]['figures']], ['ready'])
        self.assertEqual(len(records['figures']), 1)
        self.assertEqual(len(plan['problems'][0]['figures']), 2)

    def test_unknown_selection_rejected(self):
        with self.assertRaises(ValueError):
            select_figures({'global_figures': []}, {'figures': []}, ['missing'])


if __name__ == '__main__':
    unittest.main()
