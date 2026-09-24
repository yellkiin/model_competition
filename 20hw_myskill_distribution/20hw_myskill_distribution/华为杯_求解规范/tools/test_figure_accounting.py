"""Quota behavior only. Synthetic records are NOT scientific QA certificates."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from figure_accounting import audit_counts


def fixture(counts=(4, 4, 4, 4)):
    plan = {'problems': [], 'global_figures': []}
    side = {'questions': [], 'diagrams': [], 'figure_accounting': []}
    for i, count in enumerate(counts, 1):
        pid = f'q{i}'
        figures = [{'figure_id': f'{pid}-F{j}', 'status': 'qa_pass',
                    'outputs': {'vector': f'{pid}-{j}.pdf'}} for j in range(1, count + 1)]
        plan['problems'].append({'problem_id': pid, 'figures': figures})
        overview = pid + '-OVERVIEW'
        side['questions'].append({'problem_id': pid, 'supporting_question_id': pid, 'overview_id': overview})
        side['diagrams'].append({'diagram_id': overview, 'kind': 'comprehensive', 'placement': 'body',
                                'problem_id': pid, 'status': 'qa_pass', 'flow_semantics': True,
                                'connections': [{'from': 'a', 'to': 'b', 'type': 'sequence'}]})
        for f in figures:
            side['figure_accounting'].append({'figure_id': f['figure_id'], 'purpose': 'independent_science',
                'problem_id': pid, 'per_question': True, 'paper_total': True, 'flow_total': False,
                'scientific_contribution': f"隔离口径测试的不同证据条目 {f['figure_id']}，不代表科学结果"})
        side['figure_accounting'].append({'figure_id': overview, 'purpose': 'question_overview',
            'problem_id': pid, 'per_question': False, 'paper_total': False, 'flow_total': True,
            'scientific_contribution': '隔离测试的逐问综合图声明，不代表质量通过'})
    side['diagrams'].append({'diagram_id': 'ROADMAP', 'problem_id': None, 'placement': 'body',
                            'kind': 'flowchart', 'flow_semantics': True, 'status': 'qa_pass',
                            'connections': [{'from': 'a', 'to': 'b', 'type': 'data'}]})
    side['figure_accounting'].append({'figure_id': 'ROADMAP', 'purpose': 'global_roadmap',
        'problem_id': None, 'per_question': False, 'paper_total': True, 'flow_total': True,
        'scientific_contribution': '隔离测试的总体研究路径，不归入任何逐问额度'})
    return plan, side


class FigureAccountingTests(unittest.TestCase):
    def audit(self, plan, side, stage='plan', root=Path('.'), question=None):
        return audit_counts(plan, side, stage, root, question)

    def test_four_scientific_plus_overview_and_global_route(self):
        r = self.audit(*fixture())
        self.assertEqual(r['status'], 'PASS', r['failures'])
        self.assertEqual(r['paper_eligible_count'], 17)
        self.assertEqual(r['flow_count'], 5)
        self.assertTrue(all(q['independent_science_count'] == 4 and q['overview_count'] == 1 for q in r['questions']))

    def test_three_plus_overview_cannot_satisfy_four(self):
        r = self.audit(*fixture((3, 4, 4, 4)))
        self.assertIn('q1:independent_science_4_to_6', [f['code'] for f in r['failures']])

    def test_overviews_cannot_pad_sixteen(self):
        r = self.audit(*fixture((3, 3, 3, 3)))
        self.assertEqual(r['paper_eligible_count'], 13)
        self.assertIn('paper_16_excluding_question_overviews', [f['code'] for f in r['failures']])

    def test_six_plus_overview_is_permitted(self):
        r = self.audit(*fixture((6, 4, 4, 4)))
        self.assertEqual(r['status'], 'PASS', r['failures'])

    def test_declared_true_cannot_reclassify_overview(self):
        p, s = fixture()
        s['figure_accounting'][4]['paper_total'] = True
        self.assertIn('q1-OVERVIEW:paper_total_derived', [f['code'] for f in self.audit(p, s)['failures']])

    def test_missing_overview_and_ledger_are_rejected(self):
        p, s = fixture()
        s['diagrams'] = [d for d in s['diagrams'] if d['diagram_id'] != 'q1-OVERVIEW']
        self.assertEqual(self.audit(p, s)['status'], 'FAIL')
        p, s = fixture()
        s['figure_accounting'] = []
        self.assertEqual(self.audit(p, s)['status'], 'FAIL')

    def test_geometric_edges_cannot_be_declared_as_flow(self):
        p, s = fixture()
        for d in s['diagrams']:
            d['connections'][0]['type'] = 'geometry'
        r = self.audit(p, s)
        self.assertEqual(r['flow_count'], 0)
        self.assertEqual(r['status'], 'FAIL')

    def test_repeated_scientific_claim_not_new_evidence(self):
        p, s = fixture()
        s['figure_accounting'][1]['scientific_contribution'] = s['figure_accounting'][0]['scientific_contribution']
        self.assertIn('independent_contributions_not_repeated', [f['code'] for f in self.audit(p, s)['failures']])

    def test_same_vector_bytes_cannot_be_relabelled(self):
        p, s = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for problem in p['problems']:
                for fig in problem['figures']:
                    (root / fig['outputs']['vector']).write_bytes(fig['figure_id'].encode())
            (root / 'q1-2.pdf').write_bytes((root / 'q1-1.pdf').read_bytes())
            r = self.audit(p, s, 'render', root)
            self.assertIn('independent_vectors_not_duplicates', [f['code'] for f in r['failures']])


if __name__ == '__main__':
    unittest.main()
