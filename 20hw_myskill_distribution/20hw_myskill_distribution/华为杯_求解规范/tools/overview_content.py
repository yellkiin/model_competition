"""Overview content contracts augment, rather than replace, source/render gates."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REVIEW_KEYS = ('result_integration', 'mechanism_value', 'rectangular_composition',
               'palette', 'navigation', 'non_text_graphics', 'thumbnail_detail_link')
RELATION_TYPES = {'data', 'derivation', 'sequence', 'validation', 'geometry',
                  'shared_weight', 'gradient', 'comparison', 'correspondence'}
MECHANISM_KINDS = {'object', 'geometry', 'algorithm'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode('utf8')).hexdigest()


def content_digest(diagram):
    # Bind observations to semantics/layout as well as the existing byte inventory.
    return digest({k: v for k, v in diagram.items() if k not in {'status', 'qa_path'}})


def pending_design(plan, problem_id):
    problem = next((p for p in plan.get('problems', []) if p['problem_id'] == problem_id), {})
    return {
        'version': '2.0', 'status': 'pending',
        'verification': {'status': 'pending', 'evidence': []},
        'result_selection': [{'figure_id': f['figure_id'], 'decision': 'pending', 'reason': ''}
                             for f in problem.get('figures', [])],
        'omission_reason': '',
        'mechanism': {'applicable': None, 'category': '', 'panel_ids': [], 'reason': ''},
        'layout': {'strategy': '', 'reading_order': [], 'reason': ''},
        'theme': {'palette_ref': 'overview-macaron', 'connector_family': '', 'reason': ''},
    }


def pending_review():
    return {key: {'status': 'pending', 'observation': ''} for key in REVIEW_KEYS}


def audit_content(root, plan, diagram, stage, *, purpose='production', qa=None):
    from audit_diagram_workflow import meaningful, path, sha
    from audit_academic_figure_assets import schema_errors
    checks = []

    def add(code, ok, **details):
        checks.append({'code': code, 'ok': bool(ok), **details})

    design = diagram.get('overview_design')
    final = stage != 'plan' or diagram.get('status') == 'qa_pass'
    if not isinstance(design, dict):
        add('overview_content_v2_required', not final,
            action='Use --prepare-overviews, then complete current evidence; old PASS is not migrated.')
        return checks
    schema = json.loads((Path(__file__).resolve().parents[1] / '综合图内容.schema.json').read_text(encoding='utf8'))
    errors = schema_errors(design, schema)
    add('overview_content_schema', not errors, errors=errors)
    if errors:
        return checks
    if not final and design['status'] == 'pending':
        add('overview_planning_pending', diagram.get('status') in {'planned', 'incomplete'})
        return checks
    add('overview_content_ready', design['status'] == 'ready')
    verify = design['verification']
    evidence = verify['evidence']
    add('science_verification_before_composition', verify['status'] == 'verified' and
        {'result', 'independent_validation'} <= {e.get('role') for e in evidence})
    tracked = set(diagram.get('dependencies', [])) | {s['path'] for s in diagram.get('sources', [])}
    if final:
        add('verification_evidence_current', bool(evidence) and all(
            e['path'] in tracked and path(root, e['path']).is_file() and
            sha(path(root, e['path'])) == e['sha256'] and meaningful(e['locator']) for e in evidence))
    own = next((p for p in plan['problems'] if p['problem_id'] == diagram.get('problem_id')), {})
    candidates = {f['figure_id']: f for f in own.get('figures', [])}
    selection = design['result_selection']
    considered = [s['figure_id'] for s in selection]
    add('result_candidates_exact', len(considered) == len(set(considered)) and set(considered) == set(candidates))
    add('result_selection_reasoned', all(s['decision'] != 'pending' and meaningful(s['reason']) for s in selection))
    selected = {s['figure_id'] for s in selection if s['decision'] == 'selected'}
    panels = diagram.get('panels', [])
    results = [p for p in panels if p.get('kind') == 'result']
    local_results = {p.get('visual_figure_id') or p.get('academic_figure_id') for p in results
                     if not p.get('cross_question_input')}
    add('selected_results_in_panels', selected == local_results)
    add('results_reused_or_specific_exception', bool(selected) or meaningful(design.get('omission_reason')))
    if final:
        add('selected_results_verified', all(candidates.get(fid, {}).get('status') == 'qa_pass' for fid in selected))
    add('thumbnail_detail_links', all(
        p.get('detail_figure_id') == (p.get('visual_figure_id') or p.get('academic_figure_id'))
        and p.get('reuse_mode') in {'direct', 'crop', 'reexport'} for p in results))
    mechanism = design['mechanism']
    mids = mechanism['panel_ids']
    by_id = {p['panel_id']: p for p in panels}
    add('mechanism_assessment_specific', isinstance(mechanism['applicable'], bool) and meaningful(mechanism['reason']))
    if mechanism['applicable'] is True:
        add('mechanism_panels_linked', bool(mids) and len(mids) == len(set(mids)) and all(
            pid in by_id and by_id[pid].get('kind') in MECHANISM_KINDS and
            by_id[pid].get('mechanism_skill') in {'engineering-physics-mechanism-diagram', 'algorithm-mechanism-diagram'}
            for pid in mids))
        add('mechanism_category', mechanism['category'] in {'physics', 'system', 'geometry', 'state', 'algorithm'})
        add('mechanism_skill_references', all(
            by_id.get(pid, {}).get('diagram_id') or any(
                ('/' + str(by_id.get(pid, {}).get('mechanism_skill')) + '/') in r.get('path', '').replace('\\', '/')
                for r in diagram.get('references', [])) for pid in mids))
    else:
        add('mechanism_exception_has_no_false_links', not mids)
    layout = design['layout']
    order = layout['reading_order']
    add('rectangular_layout_planned', layout['strategy'] in {
        'aligned_partitions', 'shared_background', 'weak_outer_boundary', 'borderless_tiling'}
        and meaningful(layout['reason']) and bool(order) and len(order) == len(set(order))
        and set(order) == set(by_id))
    theme = design['theme']
    add('theme_and_connectors_declared', bool(theme['palette_ref']) and bool(theme['connector_family'])
        and meaningful(theme['reason']))
    if theme['palette_ref'] != 'overview-macaron':
        add('custom_theme_tracked', theme['palette_ref'] in tracked)
    if purpose == 'production':
        add('production_not_demo_evidence', all(
            not any(token in str(e['path']).lower() for token in ('demo', 'fixture', 'example')) for e in evidence))
    if final:
        qa = qa or {}
        add('overview_semantics_current', qa.get('overview_design_sha256') == content_digest(diagram))
        review = qa.get('overview_review', {})
        review_errors = schema_errors(review, schema['$defs']['review'])
        add('overview_review_schema', not review_errors, errors=review_errors)
        for key in REVIEW_KEYS:
            item = review.get(key, {})
            add('overview_review_' + key, item.get('status') == 'pass' and meaningful(item.get('observation')))
    return checks


def audit_result_source(root, parent, panel, linked_plan, linked, stage, purpose):
    """Preserve canonical identity; crops are checked against actual source pixels."""
    from audit_diagram_workflow import path, sha, meaningful, load
    from visual_routes import primary_output
    checks = []

    def add(code, ok):
        checks.append({'code': code, 'ok': bool(ok)})

    canonical = {p for p in (primary_output(linked), linked.get('outputs', {}).get('preview')) if p}
    fid = panel.get('visual_figure_id') or panel.get('academic_figure_id')
    owners = [p['problem_id'] for p in linked_plan.get('problems', [])
              if any(f.get('figure_id') == fid for f in p.get('figures', []))]
    add('result_owner_or_explicit_input', owners == [parent.get('problem_id')] or
        (len(owners) == 1 and meaningful(panel.get('cross_question_input'))))
    if purpose == 'production':
        add('result_not_demo', linked_plan.get('purpose', 'production') != 'demo' and
            linked.get('purpose', 'production') != 'demo')
    raw = panel.get('source_path')
    derivation = panel.get('derivation')
    tracked = set(parent.get('dependencies', [])) | {s['path'] for s in parent.get('sources', [])}
    add('result_plan_tracked', (panel.get('visual_plan') or panel.get('academic_plan')) in tracked)
    if not derivation:
        add('canonical_figure_source', raw in canonical and panel.get('reuse_mode', 'direct') == 'direct')
        return checks
    operation = derivation.get('operation')
    original = derivation.get('original_path')
    add('derived_canonical_source', original in canonical and raw not in canonical and original in tracked
        and panel.get('reuse_mode') == operation and operation in {'crop', 'reexport'})
    if stage == 'plan':
        return checks
    add('derived_original_current', bool(original) and path(root, original).is_file()
        and sha(path(root, original)) == derivation.get('original_sha256'))
    if not all(c['ok'] for c in checks):
        return checks
    if operation == 'crop':
        from PIL import Image
        source = path(root, original)
        box = derivation.get('crop_box', [])
        with Image.open(source) as im:
            valid = (len(box) == 4 and all(isinstance(v, int) for v in box)
                     and 0 <= box[0] < box[2] <= im.width and 0 <= box[1] < box[3] <= im.height)
            add('crop_box_valid', valid)
            if valid:
                with Image.open(path(root, raw)) as actual:
                    expected = im.crop(box).convert('RGBA')
                    add('crop_pixels_match', actual.size == expected.size and actual.convert('RGBA').tobytes() == expected.tobytes())
    elif operation == 'reexport':
        receipt_path = derivation.get('run_path')
        add('reexport_run_tracked', receipt_path in tracked)
        if receipt_path not in tracked:
            return checks
        receipt = load(path(root, receipt_path))
        inputs = receipt.get('inputs', {})
        add('reexport_run_current', receipt.get('exit_code') == 0 and bool(receipt.get('command'))
            and receipt.get('output_path') == raw and receipt.get('output_sha256') == sha(path(root, raw))
            and inputs.get(original) == sha(path(root, original))
            and all(p in tracked and path(root, p).is_file() and sha(path(root, p)) == h for p, h in inputs.items())
            and all(receipt.get(k) in inputs for k in ('script', 'config', 'result_path')))
    return checks


def prepare_overviews(plan_path):
    """Only add missing pending design fields; never touch existing QA or history."""
    from audit_diagram_workflow import load, sidecar
    plan = load(plan_path)
    out = sidecar(plan_path)
    data = load(out)
    changed = []
    for d in data['diagrams']:
        if d.get('kind') == 'comprehensive' and 'overview_design' not in d:
            d['overview_design'] = pending_design(plan, d.get('problem_id'))
            changed.append(d['diagram_id'])
    if changed:
        old = out.with_name(out.name + '.before-content-v2')
        if old.exists():
            raise ValueError('Preserve earlier migration history: ' + str(old))
        old.write_bytes(out.read_bytes())
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    return changed
