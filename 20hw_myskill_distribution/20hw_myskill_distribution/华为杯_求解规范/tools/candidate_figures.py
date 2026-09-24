#!/usr/bin/env python3
"""Incremental visual discovery, coverage audit and a read-only candidate gallery.

The registry records judgments; only the existing academic gate validates figure
quality. Neither hashes nor these checks establish scientific completeness.
"""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)


import argparse
import hashlib
import html
import json
import os
import copy
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from build_academic_figure_asset_index import safe, sha, write_json
from prepare_academic_figure_review import plan_figures, sidecar_path, select_figures, figure_contract_digest

DIMENSIONS = {
    'data_structure': '数据如何分布，是否存在分组、相关、异常或时空规律？',
    'processing_effect': '处理前后改变了什么，是否丢失重要信息？',
    'intermediate_mechanism': '特征、状态、参数或中间解揭示了什么？',
    'solution_process': '是否收敛，路径如何变化，约束何时起作用？',
    'final_result': '效果、分布、结构和实际意义是什么？',
    'comparison_validation': '相比基线改善在哪里，独立验证是否支持？',
    'error_boundary': '哪里失败，对哪些条件敏感，是否出现反例？',
}
STAGES = ('data_processing', 'feature_construction', 'model_training',
          'optimization', 'validation', 'method_result_change')
DECISIONS = ('covered', 'new_figure', 'new_analysis', 'text_table',
             'not_applicable', 'blocked')
QUALITY = ('planned', 'review_required', 'qualified', 'failed', 'stale')
DESTINATIONS = ('paper', 'supplement', 'reserve', 'rejected')
DEFAULT_REGISTRY = '求解/候选图清单.json'
DEFAULT_LEDGER = '求解/阶段事件.jsonl'
ASSURANCE = 'Checks verify current records and file links, not cognition or complete scientific discovery.'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def meaningful(value):
    return isinstance(value, str) and len(value.strip()) >= 12 and not any(
        x in value.lower() for x in ('todo', '待填写', '待补充', '已有足够图片'))


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def snapshot(root, paths):
    result = {}
    for raw in paths:
        path = safe(root, raw)
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('Missing or empty evidence: ' + raw)
        result[path.relative_to(Path(root).resolve()).as_posix()] = sha(path)
    return result


def current(root, files):
    try:
        return bool(files) and snapshot(root, files) == files
    except (OSError, ValueError):
        return False


def inventory(root, scopes):
    """Re-enumerate declared scientific folders so new files invalidate reviews."""
    found = []
    for raw in scopes:
        path = safe(root, raw)
        if not path.exists():
            raise ValueError('Missing inventory scope: ' + raw)
        paths = [path] if path.is_file() else sorted(path.rglob('*'))
        found.extend(p.relative_to(Path(root).resolve()).as_posix() for p in paths
                     if p.is_file() and not any(x in p.parts for x in ('__pycache__', '.venv', '.git')))
    return snapshot(root, sorted(set(found)))


def review_inventory_current(root, review):
    try:
        return meaningful(review.get('observation')) and bool(review.get('scopes')) and inventory(root, review['scopes']) == review.get('files') and bool(review.get('files'))
    except (OSError, ValueError):
        return False


def register_candidate(root, registry, candidate):
    if any(c['figure_id'] == candidate['figure_id'] for c in registry['candidates']):
        raise ValueError('Duplicate candidate ID')
    stage = next(s for s in registry['stages'] if s['stage_id'] == candidate['stage_id'])
    if stage['question_id'] != candidate['question_id'] or not stage['completion_event']:
        raise ValueError('Candidate requires a completed numerical stage of the same question')
    candidate = copy.deepcopy(candidate)
    candidate['quality'] = 'planned'
    candidate['destination'] = 'reserve'
    candidate['discovery_event'] = event(root, registry, 'candidate_discovered', {
        'figure_id': candidate['figure_id'], 'stage_id': candidate['stage_id'],
        'scientific_question': candidate['scientific_question'],
        'completion_event': stage['completion_event']})['digest']
    registry['candidates'].append(candidate)


def event(root, registry, kind, payload):
    """Append tool-timestamped events, never synthesize prior review events."""
    path = safe(root, registry['event_log'])
    prior = read_events(path)
    item = {'sequence': len(prior) + 1, 'time': datetime.now(timezone.utc).isoformat(),
            'kind': kind, 'payload': payload, 'previous': prior[-1]['digest'] if prior else ''}
    item['digest'] = fingerprint(item)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(item, ensure_ascii=False) + '\n')
    return item


def read_events(path):
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    for i, row in enumerate(rows):
        body = {k: v for k, v in row.items() if k != 'digest'}
        if row['sequence'] != i + 1 or row['previous'] != (rows[i - 1]['digest'] if i else '') or row['digest'] != fingerprint(body):
            raise ValueError('Broken stage event chain')
    return rows


def initialize(root, path, questions, purpose='production'):
    if Path(path).exists():
        raise ValueError('Refusing to overwrite a candidate registry')
    value = {'schema_version': '1.0', 'purpose': purpose, 'event_log': DEFAULT_LEDGER,
             'questions': [{'question_id': q, 'problem_types': [], 'type_reviews': [],
                            'expected_stages': [], 'completion_review': None} for q in questions],
             'stages': [], 'candidates': [], 'final_review': None}
    write_json(path, value)
    return value


def open_stage(root, registry, question_id, stage_id, kind, paths, supersedes=None):
    if kind not in STAGES or any(s['stage_id'] == stage_id for s in registry['stages']):
        raise ValueError('Unsupported kind or duplicate stage ID; use a new ID for a revision')
    q = next(q for q in registry['questions'] if q['question_id'] == question_id)
    if supersedes:
        prior = next((s for s in registry['stages'] if s['stage_id'] == supersedes), None)
        if kind != 'method_result_change' or not prior or prior['question_id'] != question_id or not prior['completion_event'] or any(s.get('supersedes') == supersedes for s in registry['stages']):
            raise ValueError('Revision must replace one completed, not already superseded stage of the same question')
    if stage_id not in q['expected_stages']:
        raise ValueError('Declare this stage in the question expected_stages before starting it')
    files = snapshot(root, paths)
    if not files:
        raise ValueError('Stage requires its scientific source/input evidence')
    receipt = event(root, registry, 'stage_started', {'stage_id': stage_id, 'question_id': question_id,
                                                     'kind': kind, 'files': files, 'supersedes': supersedes})
    registry['stages'].append({'stage_id': stage_id, 'question_id': question_id, 'kind': kind,
                               'start_event': receipt['digest'], 'completion_event': None,
                               'evidence': files, 'checks': [], 'review_event': None,
                               'supersedes': supersedes})
    if supersedes:
        for c in registry['candidates']:
            if c['stage_id'] == supersedes:
                c['quality'] = 'stale'


def revise_candidate(root, registry, figure_id, stage_id):
    candidate = next(c for c in registry['candidates'] if c['figure_id'] == figure_id)
    stage = next(s for s in registry['stages'] if s['stage_id'] == stage_id)
    if not stage['completion_event'] or stage['question_id'] != candidate['question_id'] or stage.get('supersedes') != candidate['stage_id']:
        raise ValueError('Candidate revision must follow its superseding completed stage')
    receipt = event(root, registry, 'candidate_revised', {
        'figure_id': figure_id, 'stage_id': stage_id, 'scientific_question': candidate['scientific_question'],
        'completion_event': stage['completion_event'], 'previous_discovery': candidate['discovery_event']})
    candidate.update(stage_id=stage_id, quality='review_required', discovery_event=receipt['digest'])


def complete_stage(root, registry, stage_id, paths):
    s = next(s for s in registry['stages'] if s['stage_id'] == stage_id)
    if s['completion_event']:
        raise ValueError('Stage already completed; register method_result_change for revisions')
    s['evidence'].update(snapshot(root, paths))
    receipt = event(root, registry, 'stage_completed', {'stage_id': stage_id, 'files': s['evidence']})
    s['completion_event'] = receipt['digest']
    s['checks'] = [dict(dimension=k, scientific_question=v, decision='pending', reason='',
                       evidence={}, candidate_ids=[], followup='', resolved=False,
                       reuse=None) for k, v in DIMENSIONS.items()]
    s['review_event'] = None


def record_review(root, registry, stage_id):
    s = next(s for s in registry['stages'] if s['stage_id'] == stage_id)
    if not s['completion_event'] or not current(root, s['evidence']):
        raise ValueError('Complete stage and refresh changed evidence before review')
    errors = check_dimensions(root, registry, s, final=False)
    if errors:
        raise ValueError('; '.join(errors))
    receipt = event(root, registry, 'stage_reviewed', {'stage_id': stage_id,
                       'completion_event': s['completion_event'], 'checks_digest': fingerprint(s['checks'])})
    s['review_event'] = receipt['digest']


def check_dimensions(root, registry, stage, final):
    failures = []
    checks = stage.get('checks', [])
    dims = [c.get('dimension') for c in checks]
    prefix = stage['stage_id'] + ':'
    if len(dims) != 7 or set(dims) != set(DIMENSIONS):
        failures.append(prefix + 'seven_dimensions_missing_or_duplicate')
    candidates = {c['figure_id']: c for c in registry['candidates']}
    stages = {s['stage_id']: s for s in registry['stages']}
    for c in checks:
        name = prefix + str(c.get('dimension'))
        if c.get('decision') not in DECISIONS or not meaningful(c.get('scientific_question')) or not meaningful(c.get('reason')):
            failures.append(name + ':unreasoned_decision')
        if not current(root, c.get('evidence', {})):
            failures.append(name + ':missing_or_stale_evidence')
        refs = c.get('candidate_ids', [])
        if any(fid not in candidates for fid in refs):
            failures.append(name + ':unknown_candidate')
        if c.get('decision') in ('covered', 'new_figure') and not refs:
            failures.append(name + ':figure_required')
        if c.get('decision') in ('new_analysis', 'blocked') and not meaningful(c.get('followup')):
            failures.append(name + ':followup_missing')
        if final and (c.get('decision') in ('blocked', 'new_analysis') or not c.get('resolved')):
            failures.append(name + ':unresolved_action')
        if final and c.get('decision') in ('covered', 'new_figure'):
            if any(candidates.get(fid, {}).get('quality') != 'qualified' for fid in refs):
                failures.append(name + ':promised_figure_not_qualified')
        reuse = c.get('reuse')
        if reuse:
            prior = stages.get(reuse.get('stage_id'))
            source = next((x for x in prior['checks'] if x['dimension'] == reuse.get('dimension')), None) if prior else None
            if not source or prior is stage or not prior.get('review_event') or not current(root, prior['evidence']) or reuse.get('checks_digest') != fingerprint(prior['checks']) or source['evidence'] != c['evidence']:
                failures.append(name + ':invalid_reuse')
    return failures


def audit_figure(root, plan_path, figure_id, stage, runtime, allow_demo=False):
    try:
        return _audit_figure(root, plan_path, figure_id, stage, runtime, allow_demo)
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        return dict(status='FAIL', stage=stage, failures=[{'code':'candidate_input_invalid', 'error':str(exc)}], assurance=ASSURANCE)


def _audit_figure(root, plan_path, figure_id, stage, runtime, allow_demo=False):
    """Reuse the applicable panel gates without paper-count prerequisites."""
    from audit_academic_figure_assets import schema_errors
    from visual_routes import audit_routes, academic_panels
    root = Path(root).resolve()
    plan_path = safe(root, str(plan_path))
    plan = load(plan_path)
    refs = load(sidecar_path(plan_path)) if sidecar_path(plan_path).is_file() else {'figures': []}
    selected, _ = select_figures(plan, refs, [figure_id])
    spec = load(Path(__file__).resolve().parent.parent / '视觉计划.schema.json')
    figure = next(f for f in plan_figures(selected) if f['figure_id'] == figure_id)
    errors = schema_errors(figure, spec['$defs']['figure'], spec)
    errors += [f'{figure_id}:plan_not_ready'] if plan.get('plan_status') != 'ready' else []
    claims = {c['claim_id'] for p in plan['problems'] for c in p['claims']}
    evidence = {e['evidence_id'] for p in plan['problems'] for e in p['evidence_matrix']}
    if not set(figure['claim_ids']) <= claims or not set(figure['evidence_ids']) <= evidence:
        errors.append(figure_id + ':unresolved_claim_or_evidence')
    outputs = list(figure['outputs'].values())
    for output in set(outputs):
        roles = {k for k, v in figure['outputs'].items() if v == output}
        if len(roles) > 1 and roles not in ({'primary', 'preview'}, {'primary', 'vector'}):
            errors.append(figure_id + ':duplicate_outputs')
    for other in plan_figures(plan):
        if other.get('figure_id') != figure_id and set(outputs) & set(other.get('outputs', {}).values()):
            errors.append(figure_id + ':output_collision_with_other_candidate')
    result = audit_routes(plan_path, stage, root, runtime, allow_demo=allow_demo,
                          figure_ids=[figure_id])
    if stage == 'render' and result['status'] == 'PASS' and academic_panels(figure):
        rec = next(r for r in refs['figures'] if r['figure_id'] == figure_id)
        qa = load(safe(root, figure['qa_report']))
        if qa.get('contract_sha256') != figure_contract_digest(figure, rec):
            errors.append(figure_id + ':candidate_contract_unreviewed_or_stale')
    result['failures'].extend({'code': e, 'ok': False} for e in errors)
    result['status'] = 'FAIL' if result['failures'] else 'PASS'
    result['scope'] = {'figure_ids': [figure_id], 'paper_completion': False}
    return result


def audit_registry(root, path, runtime, stage='progress', question_id=None, allow_demo=False, paper_plan=None):
    root = Path(root).resolve()
    failures, details = [], []
    try:
        registry = load(path)
        import jsonschema
        jsonschema.Draft202012Validator(load(Path(__file__).resolve().parent.parent / '候选图清单.schema.json')).validate(registry)
        if registry['purpose'] == 'demo' and not (allow_demo and safe(root, str(path)).is_relative_to(root / '求解/验收输出/academic_figure_integration')):
            failures.append('demo_outside_isolation_or_not_allowed')
        events = read_events(safe(root, registry['event_log']))
        by_event = {e['digest']: e for e in events}
        by_stage = {s['stage_id']: s for s in registry['stages']}
        superseded = {s['supersedes'] for s in registry['stages'] if s.get('supersedes')}
        for s in registry['stages']:
            if s.get('supersedes'):
                prior = by_stage.get(s['supersedes'])
                start = by_event.get(s['start_event'], {})
                if not prior or prior['question_id'] != s['question_id'] or start.get('payload', {}).get('supersedes') != s['supersedes'] or by_event.get(prior['completion_event'], {}).get('sequence', 10**12) >= start.get('sequence', 0):
                    failures.append(s['stage_id'] + ':invalid_supersession')
        if len(by_stage) != len(registry['stages']):
            failures.append('duplicate_stage_ids')
        all_ids = [c['figure_id'] for c in registry['candidates']]
        if len(all_ids) != len(set(all_ids)):
            failures.append('duplicate_candidate_ids')
        questions = [q for q in registry['questions'] if not question_id or q['question_id'] == question_id]
        if not questions:
            failures.append('unknown_question')
        qids = {q['question_id'] for q in questions}
        all_qids = [q['question_id'] for q in registry['questions']]
        if len(all_qids) != len(set(all_qids)) or any(s['question_id'] not in all_qids for s in registry['stages']) or any(c['question_id'] not in all_qids for c in registry['candidates']):
            failures.append('question_ids_duplicate_or_unresolved')
        expected_started = {e['payload']['stage_id'] for e in events if e['kind'] == 'stage_started' and e['payload']['question_id'] in qids}
        if expected_started != {s['stage_id'] for s in registry['stages'] if s['question_id'] in qids}:
            failures.append('stage_event_missing_from_registry')
        final = stage in ('question', 'final')
        for q in questions:
            if not q['problem_types'] or not meaningful(q.get('type_reason')):
                failures.append(q['question_id'] + ':problem_types_unreviewed')
            types = {r['problem_type'] for r in q['type_reviews']}
            if types != set(q['problem_types']) or len(types) != len(q['type_reviews']):
                failures.append(q['question_id'] + ':type_review_missing')
            for r in q['type_reviews']:
                if not meaningful(r.get('risk_review')) or not current(root, r.get('evidence', {})):
                    failures.append(q['question_id'] + ':type_risk_unreviewed_or_stale')
            if final:
                if not q['expected_stages']:
                    failures.append(q['question_id'] + ':stage_inventory_empty')
                missing = set(q['expected_stages']) - set(by_stage)
                failures.extend(s + ':stage_not_triggered' for s in sorted(missing))
                if any(by_stage[s]['question_id'] != q['question_id'] for s in q['expected_stages'] if s in by_stage):
                    failures.append(q['question_id'] + ':expected_stage_wrong_question')
                review = q.get('completion_review') or {}
                if not review_inventory_current(root, review) or set(review.get('stage_ids', [])) != set(q['expected_stages']):
                    failures.append(q['question_id'] + ':completion_inventory_review_missing_or_stale')
                from workspace_context import shared_context
                if shared_context(root, runtime) and not any(
                        c['question_id'] == q['question_id'] and c['quality'] == 'qualified'
                        and c['destination'] in ('reserve', 'supplement') for c in registry['candidates']):
                    if not meaningful(review.get('zero_remaining_reason')):
                        failures.append(q['question_id'] + ':zero_remaining_reason_missing')
        for s in registry['stages']:
            if s['question_id'] not in qids:
                continue
            q = next(q for q in questions if q['question_id'] == s['question_id'])
            start = by_event.get(s['start_event'], {})
            if s['stage_id'] not in q['expected_stages'] or start.get('kind') != 'stage_started' or start.get('payload', {}).get('stage_id') != s['stage_id']:
                failures.append(s['stage_id'] + ':stage_inventory_or_start_invalid')
            if s['stage_id'] in superseded:
                continue
            if not s['completion_event']:
                if final:
                    failures.append(s['stage_id'] + ':not_completed')
                continue
            end = by_event.get(s['completion_event'], {})
            if end.get('kind') != 'stage_completed' or end.get('payload', {}).get('files') != s['evidence'] or end.get('payload', {}).get('stage_id') != s['stage_id']:
                failures.append(s['stage_id'] + ':completion_event_invalid')
            if not current(root, s['evidence']):
                failures.append(s['stage_id'] + ':stage_evidence_stale')
            failures.extend(check_dimensions(root, registry, s, final))
            review = by_event.get(s['review_event'], {})
            if review.get('kind') != 'stage_reviewed' or review.get('payload') != dict(stage_id=s['stage_id'], completion_event=s['completion_event'], checks_digest=fingerprint(s['checks'])):
                failures.append(s['stage_id'] + ':stage_review_receipt_missing_or_changed')
            if not (start.get('sequence', 0) < end.get('sequence', 0) < review.get('sequence', 0)):
                failures.append(s['stage_id'] + ':stage_events_out_of_order')
        for c in registry['candidates']:
            if c['question_id'] not in qids:
                continue
            if c['stage_id'] not in by_stage or by_stage[c['stage_id']]['question_id'] != c['question_id']:
                failures.append(c['figure_id'] + ':candidate_stage_unresolved')
            if not meaningful(c['selection_reason']) or not meaningful(c['scientific_question']):
                failures.append(c['figure_id'] + ':candidate_reason_missing')
            discovered = by_event.get(c.get('discovery_event'), {})
            if discovered.get('kind') not in ('candidate_discovered', 'candidate_revised') or discovered.get('payload', {}).get('figure_id') != c['figure_id'] or discovered.get('payload', {}).get('stage_id') != c['stage_id'] or discovered.get('payload', {}).get('scientific_question') != c['scientific_question']:
                failures.append(c['figure_id'] + ':discovery_event_invalid')
            if c['destination'] in ('paper', 'supplement') and c['quality'] != 'qualified':
                failures.append(c['figure_id'] + ':selected_but_not_qualified')
            if c['quality'] == 'qualified':
                gate = audit_figure(root, c['plan_path'], c['figure_id'], 'render', runtime, allow_demo)
                details.append({'figure_id': c['figure_id'], 'gate': gate})
                if gate['status'] != 'PASS':
                    failures.append(c['figure_id'] + ':visual_render_failed_or_stale')
                else:
                    candidate_plan = load(safe(root, c['plan_path']))
                    f = next(f for f in plan_figures(candidate_plan) if f['figure_id'] == c['figure_id'])
                    from visual_routes import academic_panels
                    stale = False
                    if academic_panels(f):
                        r = next(r for r in load(sidecar_path(safe(root,c['plan_path'])))['figures'] if r['figure_id'] == c['figure_id'])
                        qa = load(safe(root, f['qa_report']))
                        stale = qa.get('contract_sha256') != figure_contract_digest(f, r)
                    if stale or c['scientific_question'] != f['scientific_question']:
                        failures.append(c['figure_id'] + ':candidate_contract_stale_or_unreviewed')
        if stage == 'final':
            review = registry.get('final_review') or {}
            if not review_inventory_current(root, review) or set(review.get('question_ids', [])) != {q['question_id'] for q in registry['questions']}:
                failures.append('final_code_results_claims_review_missing_or_stale')
            if paper_plan is None:
                failures.append('paper_plan_required_for_final')
            else:
                paper = load(safe(root, str(paper_plan)))
                figures = {f['figure_id']: f for f in plan_figures(paper)}
                selected = {c['figure_id']: c for c in registry['candidates'] if c['destination'] == 'paper'}
                if set(selected) != set(figures):
                    failures.append('paper_candidate_ids_not_exact')
                for fid in set(selected) & set(figures):
                    original = next(f for f in plan_figures(load(safe(root, selected[fid]['plan_path']))) if f['figure_id'] == fid)
                    if original != figures[fid]:
                        failures.append(fid + ':paper_not_canonical_candidate')
        return {'status': 'FAIL' if failures else 'PASS', 'stage': stage,
                'failures': failures, 'figure_checks': details, 'assurance': ASSURANCE}
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        return {'status': 'FAIL', 'stage': stage, 'failures': failures + [str(exc)], 'assurance': ASSURANCE}
    except Exception as exc:
        # Schema errors must remain a failed audit, never an unhandled success path.
        return {'status': 'FAIL', 'stage': stage, 'failures': failures + [type(exc).__name__ + ': ' + str(exc)], 'assurance': ASSURANCE}


def build_gallery(root, path, output, runtime, allow_demo=False):
    from candidate_gallery import build
    return build(root, path, output, runtime, audit_figure, allow_demo=allow_demo)


def select_paper(root, registry_path, skeleton_path, output, runtime, allow_demo=False):
    """Build a derived body plan; scientific evidence choices stay in the skeleton."""
    root = Path(root).resolve()
    registry = load(registry_path)
    plan = load(safe(root, str(skeleton_path)))
    out = safe(root, str(output))
    selected = [c for c in registry['candidates'] if c['destination'] == 'paper']
    if not selected:
        raise ValueError('No paper figures selected')
    from visual_routes import academic_panels, routed_panels, media_sidecar
    from modelviz_bridge import sidecar as modelviz_sidecar
    from visual_routes import modelviz_panels
    from audit_diagram_workflow import sidecar
    if any(p.exists() for p in (out, sidecar_path(out), media_sidecar(out), sidecar(out), modelviz_sidecar(out))):
        raise ValueError('Preserve existing selected plans and reviews; choose a fresh output path')
    records, reference = [], None
    media_records, media_reference = [], None
    modelviz_records, modelviz_reference = [], None
    for p in plan['problems']:
        p['figures'] = []
    plan['global_figures'] = []
    for c in selected:
        if c['quality'] != 'qualified':
            raise ValueError('Selection is not qualified: ' + c['figure_id'])
        source = safe(root, c['plan_path'])
        if source == out:
            raise ValueError('Body plan must be a derived file, not the canonical candidate plan')
        gate = audit_figure(root, source, c['figure_id'], 'render', runtime, allow_demo)
        if gate['status'] != 'PASS':
            raise ValueError('Candidate render gate failed: ' + c['figure_id'])
        refs = load(sidecar_path(source)) if sidecar_path(source).is_file() else {'figures': []}
        source_plan, refs = select_figures(load(source), refs, [c['figure_id']])
        figure = plan_figures(source_plan)[0]
        if source_plan.get('schema_version') == '1.2':
            plan['schema_version'] = '1.2'
            preflight=source_plan['drawing_preflight_path']
            if plan.get('drawing_preflight_path', preflight) != preflight:
                raise ValueError('Selected candidates must share the current preflight')
            plan['drawing_preflight_path']=preflight
        if modelviz_panels(figure):
            vr=load(modelviz_sidecar(source))
            if modelviz_reference is None:
                modelviz_reference=copy.deepcopy(vr)
            elif any(vr[k] != modelviz_reference[k] for k in ('runtime','purpose')):
                raise ValueError('ModelViz candidate runtime/purpose mismatch')
            modelviz_records.extend(r for r in vr['figures'] if r['figure_id']==c['figure_id'])
        if academic_panels(figure):
            if reference is None:
                reference = copy.deepcopy(refs)
            elif any(refs[k] != reference[k] for k in ('runtime', 'purpose', 'index_path', 'scan_digest', 'gallery_review_path', 'gallery_review_sha256', 'skill_root')):
                raise ValueError('Candidate references have incompatible runtime/asset versions')
            records.extend(refs['figures'])
        if routed_panels(figure):
            mr = load(media_sidecar(source))
            if media_reference is None:
                media_reference = copy.deepcopy(mr)
            elif any(mr[k] != media_reference[k] for k in ('runtime', 'purpose')):
                raise ValueError('Candidate media references have incompatible runtime/purpose')
            media_records.extend(r for r in mr['figures'] if r['figure_id'] == c['figure_id'])
        if any(f['figure_id'] == c['figure_id'] for f in source_plan['global_figures']):
            plan['global_figures'].append(figure)
        else:
            source_owner = next(p['problem_id'] for p in source_plan['problems'] if p['figures'])
            if source_owner != c['question_id']:
                raise ValueError('Candidate source question does not match its registry owner')
            problem = next(p for p in plan['problems'] if p['problem_id'] == c['question_id'])
            problem['figures'].append(figure)
    if reference is not None:
        reference['figures'] = records
        reference['plan_path'] = out.relative_to(root).as_posix()
        reference.pop('paper_review_path', None)
    if media_reference is not None:
        media_reference['figures'] = media_records
        media_reference['paper_review_path'] = ''
    from audit_diagram_workflow import sidecar
    diagram_source = sidecar(safe(root, str(skeleton_path)))
    if not diagram_source.is_file():
        raise ValueError('Skeleton lacks required per-question comprehensive diagram plan')
    diagrams = load(diagram_source)
    diagrams['paper_review_path'] = ''
    from chart_policy import required, audit_policy
    if required(plan, root):
        policy=audit_policy(plan,root,runtime)
        if policy:
            raise ValueError('Whole-paper selection policy failed: '+json.dumps(policy,ensure_ascii=False))
    write_json(out, plan)
    if reference is not None:
        write_json(sidecar_path(out), reference)
    if media_reference is not None:
        write_json(media_sidecar(out), media_reference)
    if modelviz_reference is not None:
        modelviz_reference['figures']=modelviz_records
        modelviz_reference['paper_review_path']=''
        write_json(modelviz_sidecar(out),modelviz_reference)
    write_json(sidecar(out), diagrams)
    return {'status': 'SELECTED_REQUIRES_BODY_AND_PAPER_AUDIT', 'path': str(out), 'figures': len(selected)}


def package_selection_errors(root, registry_path, manifest, runtime):
    """Check selected source paths before copying them into the submission."""
    root = Path(root).resolve(); registry = load(registry_path)
    errors, figures = [], {}
    for c in registry['candidates']:
        plan_path = safe(root, c['plan_path'])
        if not plan_path.is_file():
            continue
        f = next((f for f in plan_figures(load(plan_path)) if f['figure_id'] == c['figure_id']), None)
        if f:
            for raw in f['outputs'].values():
                figures[safe(root, raw)] = c
    for q in manifest['questions']:
        for item in q.get('supplementary_materials', []):
            c = figures.get(safe(root, item['path']))
            if c is None:
                if item.get('material_type') == 'figure' or Path(item['path']).suffix.lower() in ('.png', '.svg', '.jpg', '.jpeg', '.tif', '.tiff', '.webp', '.bmp'):
                    errors.append(item['path'] + ':supplement_figure_not_registered')
                continue
            if c['destination'] != 'supplement' or c['quality'] != 'qualified' or c['question_id'] != q['question_id']:
                errors.append(c['figure_id'] + ':supplement_selection_invalid')
            elif audit_figure(root, c['plan_path'], c['figure_id'], 'render', runtime)['status'] != 'PASS':
                errors.append(c['figure_id'] + ':supplement_render_stale')
    def declared_paths(value):
        if isinstance(value, dict):
            if isinstance(value.get('path'), str):
                yield value['path']
            for child in value.values():
                yield from declared_paths(child)
        elif isinstance(value, list):
            for child in value:
                yield from declared_paths(child)
    for raw in declared_paths(manifest):
        c = figures.get(safe(root, raw))
        if c and (c['destination'] in ('reserve', 'rejected') or c['quality'] != 'qualified'):
            errors.append(c['figure_id'] + ':unselected_candidate_in_package')
    return errors


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-root', type=Path, default=Path('.'))
    p.add_argument('--registry', default=DEFAULT_REGISTRY)
    sub = p.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init'); init.add_argument('--question-id', action='append', required=True)
    init.add_argument('--purpose', choices=('production', 'demo'), default='production')
    begin = sub.add_parser('start'); begin.add_argument('--question-id', required=True)
    begin.add_argument('--kind', choices=STAGES, required=True)
    begin.add_argument('--supersedes')
    for name, parser in [('start', begin), ('complete', sub.add_parser('complete')), ('review', sub.add_parser('review'))]:
        parser.add_argument('--stage-id', required=True)
        if name != 'review': parser.add_argument('--evidence', action='append', required=True)
    check = sub.add_parser('audit'); check.add_argument('--stage', choices=('progress', 'question', 'final'), default='progress')
    check.add_argument('--question-id'); check.add_argument('--paper-plan'); check.add_argument('--report', required=True)
    gallery = sub.add_parser('gallery'); gallery.add_argument('--output', default='待选图库')
    figure = sub.add_parser('figure'); figure.add_argument('--plan', required=True)
    figure.add_argument('--figure-id', required=True); figure.add_argument('--stage', choices=('plan', 'render'), required=True)
    figure.add_argument('--report', required=True)
    select = sub.add_parser('select-paper'); select.add_argument('--skeleton', required=True)
    select.add_argument('--output', required=True)
    register = sub.add_parser('register'); register.add_argument('--record', required=True)
    revision = sub.add_parser('revise-candidate'); revision.add_argument('--figure-id', required=True)
    revision.add_argument('--stage-id', required=True)
    for parser in (check, gallery, figure, select):
        parser.add_argument('--runtime', choices=('codex', 'claude'), required=True)
        parser.add_argument('--allow-demo', action='store_true')
    a = p.parse_args(); root = a.project_root.resolve(); path = safe(root, a.registry)
    try:
        if a.command == 'init':
            initialize(root, path, a.question_id, a.purpose); result = {'status': 'DRAFT_CREATED'}
        elif a.command in ('start', 'complete', 'review', 'register', 'revise-candidate'):
            registry = load(path)
            if a.command == 'start': open_stage(root, registry, a.question_id, a.stage_id, a.kind, a.evidence, a.supersedes)
            elif a.command == 'complete': complete_stage(root, registry, a.stage_id, a.evidence)
            elif a.command == 'register': register_candidate(root, registry, load(safe(root, a.record)))
            elif a.command == 'revise-candidate': revise_candidate(root, registry, a.figure_id, a.stage_id)
            else: record_review(root, registry, a.stage_id)
            write_json(path, registry); result = {'status': 'RECORDED'}
        elif a.command == 'audit':
            result = audit_registry(root, path, a.runtime, a.stage, a.question_id, a.allow_demo, a.paper_plan)
            write_json(safe(root, a.report), result)
        elif a.command == 'figure':
            result = audit_figure(root, a.plan, a.figure_id, a.stage, a.runtime, a.allow_demo)
            write_json(safe(root, a.report), result)
        elif a.command == 'select-paper': result = select_paper(root, path, a.skeleton, a.output, a.runtime, a.allow_demo)
        else: result = build_gallery(root, path, a.output, a.runtime, a.allow_demo)
        printable = {k: v for k, v in result.items() if k not in ('checks', 'figure_checks')}
        print(json.dumps(printable, ensure_ascii=False, indent=2))
        return int(result['status'] == 'FAIL')
    except Exception as exc:
        print(json.dumps({'status': 'FAIL', 'error': str(exc)}, ensure_ascii=False)); return 1


if __name__ == '__main__':
    raise SystemExit(main())
