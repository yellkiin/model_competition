"""Synthetic contract fixtures; never scientific results or actual visual reviews."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from roadmap_templates import audit, catalog, contract_digest, prepare, sha, source_assets


class RoadmapTemplates(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.runtime = 'codex'
        self.prefix = '.agents/skills/sci-box-main/sci-box-main/skills/scibox-diagram'
        self.entries = []
        for tid in ('first', 'second'):
            paths = {'preview': f'assets/{tid}/preview.png', 'example': f'assets/{tid}/example.json',
                     'entry': f'scripts/{tid}.py', 'documentation': f'references/{tid}.md'}
            for raw in paths.values():
                file = self.root/self.prefix/raw
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text('Synthetic fixture only: '+raw, encoding='utf8')
            self.entries.append({'template_id': tid, 'paths': paths})
        self.catalog_file = self.root/self.prefix/'assets/catalog.json'
        self.write(self.catalog_file, {'templates': self.entries})
        self.diagram = {'diagram_id': 'global', 'kind': 'flowchart', 'problem_id': None,
                        'placement': 'body', 'backend': 'drawio', 'status': 'planned',
                        'template_selection_path': 'selection.json',
                        'panels': [{'panel_id': 'p1'}, {'panel_id': 'p2'}],
                        'connections': [{'from': 'p1', 'to': 'p2', 'type': 'data'}],
                        'references': [{'path': self.prefix+'/assets/first/preview.png'}]}
        self.record = prepare(self.root, self.runtime, self.diagram)
        self.record.update(status='reviewed', selected_template_id='first')
        for item in self.record['gallery']:
            item.update(reviewed=True, observation='Synthetic layout observation for regression only',
                        tool_ref='synthetic-fixture-not-actual-review')
        self.record['candidates'] = [{'template_id': tid, 'fit': 'Synthetic fit of parallel tasks',
                                     'decision': 'Synthetic comparison and decision'} for tid in ('first','second')]
        self.record['source_assets'] = source_assets(self.root, self.runtime, self.prefix, self.entries[0])
        self.record['adaptation'] = {'rationale': 'Synthetic task structure mapping',
            'preserved_style': 'Synthetic preservation of bands and headings', 'changes': 'Synthetic removal of unused slots',
            'semantic_mapping': [{'panel_id': pid, 'template_slot': 'Synthetic template input stage',
                                  'adaptation': 'Synthetic mapping to real-input placeholder'} for pid in ('p1','p2')]}

    @staticmethod
    def write(file, value):
        file.write_text(json.dumps(value, ensure_ascii=False), encoding='utf8')

    def failures(self, stage='plan', qa=None):
        self.write(self.root/'selection.json', self.record)
        return {row['code'] for row in audit(self.root, self.runtime, self.diagram, stage, qa) if not row['ok']}

    def qa(self):
        self.write(self.root/'selection.json', self.record)
        return {'template_adaptation_review': {'status': 'pass', 'selection_sha256': sha(self.root/'selection.json'),
                    'style_observation': 'Synthetic style observation, not approval',
                    'truthfulness_observation': 'Synthetic scientific mapping observation',
                    'readability_observation': 'Synthetic physical size observation', 'tool_ref': 'fixture'},
                'views': [{'kind': kind, 'reviewed': True, 'observation': 'Synthetic view observation',
                           'tool_ref': 'fixture'} for kind in ('overall', 'pdf_size')]}

    def test_valid_contract_both_runtimes(self):
        self.assertEqual(self.failures(), set())
        import shutil
        shutil.copytree(self.root/'.agents', self.root/'.claude')
        self.runtime = 'claude'
        self.prefix = self.prefix.replace('.agents', '.claude')
        self.record = json.loads(json.dumps(self.record).replace('.agents', '.claude'))
        self.record['runtime'] = 'claude'
        self.diagram['references'][0]['path'] = self.diagram['references'][0]['path'].replace('.agents', '.claude')
        self.assertEqual(self.failures(), set())

    def test_missing_and_freehand_template_rejected(self):
        del self.diagram['template_selection_path']
        self.assertIn('roadmap_template_record_required', self.failures())
        self.diagram['template_selection_path'] = 'selection.json'
        self.record['selected_template_id'] = 'freehand'
        self.assertIn('roadmap_template_selected_from_assets', self.failures())

    def test_complete_gallery_and_actual_observations_required(self):
        original = copy.deepcopy(self.record)
        for change in ('omitted', 'duplicate', 'unreviewed', 'empty', 'tool', 'null_tool'):
            with self.subTest(change=change):
                self.record = copy.deepcopy(original)
                if change == 'omitted': self.record['gallery'].pop()
                if change == 'duplicate': self.record['gallery'].append(self.record['gallery'][0])
                if change == 'unreviewed': self.record['gallery'][0]['reviewed'] = False
                if change == 'empty': self.record['gallery'][0]['observation'] = ''
                if change == 'tool': self.record['gallery'][0]['tool_ref'] = ''
                if change == 'null_tool': self.record['gallery'][0]['tool_ref'] = None
                self.assertTrue(self.failures())

    def test_comparison_and_mapping_required(self):
        self.record['candidates'].pop()
        self.record['adaptation']['semantic_mapping'].pop()
        self.record['adaptation']['preserved_style'] = ''
        failures = self.failures()
        self.assertIn('roadmap_template_candidate_comparison', failures)
        self.assertIn('roadmap_template_real_panel_mapping', failures)
        self.assertIn('roadmap_template_adaptation_reasoned', failures)

    def test_stale_preview_source_catalog_and_plan_rejected(self):
        for raw in ('assets/second/preview.png', 'scripts/first.py', 'assets/catalog.json'):
            file = self.root/self.prefix/raw
            original = file.read_bytes()
            file.write_bytes(original+b' ')
            self.assertTrue(self.failures(), raw)
            file.write_bytes(original)
        self.diagram['connections'][0]['type'] = 'sequence'
        self.assertIn('roadmap_template_contract_current', self.failures())

    def test_catalog_cannot_hide_an_asset_template(self):
        self.write(self.catalog_file, {'templates': self.entries[:1]})
        self.assertIn('roadmap_template_record_valid', self.failures())

    def test_cross_runtime_and_arbitrary_preview_rejected(self):
        self.record['gallery'][0]['preview_path'] = '.claude/skills/foreign.png'
        self.assertIn('roadmap_template_preview_first', self.failures())
        self.record['runtime'] = 'claude'
        self.assertIn('roadmap_template_identity', self.failures())

    def test_final_reviews_required_and_bound_to_selection(self):
        for stage in ('render', 'tex', 'paper'):
            self.assertIn('roadmap_template_adaptation_visual_review', self.failures(stage))
            self.assertEqual(self.failures(stage, self.qa()), set())
        qa = self.qa()
        self.record['adaptation']['changes'] += ' further layout change'
        self.assertIn('roadmap_template_adaptation_visual_review', self.failures('render', qa))
        qa = self.qa()
        qa['views'].pop()
        self.assertIn('roadmap_template_review_views', self.failures('render', qa))

    def test_other_diagrams_not_forced_to_use_templates(self):
        for kind, owner, placement in [('comprehensive','q1','body'), ('algorithm',None,'body'),
                                        ('flowchart','q1','body'), ('flowchart',None,'panel')]:
            diagram = dict(self.diagram, kind=kind, problem_id=owner, placement=placement)
            diagram.pop('template_selection_path')
            self.assertEqual(audit(self.root, self.runtime, diagram, 'paper'), [])

    def test_preparation_grants_no_review_and_cli_refuses_overwrite(self):
        pending = prepare(self.root, self.runtime, self.diagram)
        self.assertEqual(pending['status'], 'pending')
        self.assertTrue(all(not row['reviewed'] and not row['observation'] for row in pending['gallery']))
        self.write(self.root/'plan.diagrams.json', {'diagrams': [self.diagram]})
        command = [sys.executable, '-B', '-X', 'utf8', str(Path(__file__).with_name('roadmap_templates.py')),
                   '--maintenance', '--project-root', str(self.root), '--runtime', 'codex', '--plan', 'plan.json',
                   '--diagram-id', 'global', '--template-id', 'first', '--output', 'draft.json']
        first = subprocess.run(command, capture_output=True, text=True, encoding='utf8')
        self.assertEqual(first.returncode, 0, first.stderr)
        before = (self.root/'draft.json').read_bytes()
        second = subprocess.run(command, capture_output=True, text=True, encoding='utf8')
        self.assertNotEqual(second.returncode, 0)
        self.assertEqual((self.root/'draft.json').read_bytes(), before)

    def test_main_diagram_gate_calls_template_check(self):
        from audit_diagram_workflow import audit as workflow_audit
        self.write(self.root/'selection.json', self.record)
        plan = self.root/'plan.json'
        self.write(plan, {'problems': []})
        self.write(plan.with_suffix('.diagrams.json'), {'schema_version': '1.0', 'runtime': 'codex',
            'purpose': 'production', 'questions': [], 'diagrams': [self.diagram]})
        result = workflow_audit(plan, 'plan', self.root, 'codex', diagram_ids=['global'])
        codes = {row['code'] for row in result['checks']}
        self.assertIn('global:roadmap_template_selected_from_assets', codes)

    def test_shared_workspace_reads_same_runtime_template_without_copying(self):
        from workspace_context import SHARED, create_workspace
        for name in SHARED:
            file = self.root/name
            if name.endswith('.md'):
                file.write_text('Synthetic workflow instructions', encoding='utf8')
            else:
                file.mkdir(exist_ok=True)
        context = create_workspace(self.root, 'codex', purpose='demo')
        self.write(context.workspace_root/'selection.json', self.record)
        result = audit(context.workspace_root, 'codex', self.diagram, 'plan')
        self.assertTrue(all(row['ok'] for row in result), result)
        self.assertFalse((context.workspace_root/'.agents').exists())
        wrong_runtime = audit(context.workspace_root, 'claude', self.diagram, 'plan')
        self.assertTrue(any(not row['ok'] for row in wrong_runtime))


if __name__ == '__main__':
    unittest.main()
