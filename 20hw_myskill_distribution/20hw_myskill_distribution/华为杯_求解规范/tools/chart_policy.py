"""Evidence-bound dual-source selection, conditional 3D preference and body diversity."""
from __future__ import annotations
import copy
import json
from pathlib import Path
from build_academic_figure_asset_index import digest, sha, safe
from drawing_sources import PROVIDERS, audit_preflight, DEFAULT_PREFLIGHT

FAMILIES = ('heatmap', 'bar', 'line', 'scatter', 'box', 'violin', 'density', 'histogram',
            'ecdf', 'surface', 'contour', 'trajectory', 'ribbon', 'waterfall', 'forest',
            'radar', 'pie', 'area', 'hexbin', 'network', 'sankey', 'venn', 'upset',
            'ternary', 'rose', 'gantt', 'taylor', 'biplot', 'bubble', 'qq')


def selection_digest(figure):
    value = copy.deepcopy(figure)
    for key in ('status', 'selection'):
        value.pop(key, None)
    return digest(value)


def portfolio_digest(figures):
    return digest(sorted((f['figure_id'], selection_digest(f)) for f in figures))


def current_evidence(root, records):
    try:
        return bool(records) and all(safe(root, p).is_file() and sha(safe(root, p)) == h for p, h in records.items())
    except (ValueError, OSError, TypeError, AttributeError):
        return False


def required(plan, root=None):
    from visual_routes import figures, modelviz_panels
    from workspace_context import MANIFEST
    return (plan.get('schema_version') == '1.2' or any(modelviz_panels(f) for f in figures(plan))
            or bool(root and (Path(root) / MANIFEST).is_file()))


def audit_policy(plan, root, runtime, figure_ids=None, body=True):
    from visual_routes import figures, statistical_panels, provider
    selected = [f for f in figures(plan) if statistical_panels(f)]
    if not selected or not required(plan, root):
        return []
    errors = audit_preflight(root, runtime, plan.get('drawing_preflight_path', DEFAULT_PREFLIGHT))
    targets = [f for f in selected if figure_ids is None or f['figure_id'] in figure_ids]
    mapping = json.loads((Path(__file__).parent.parent / 'chart_family_map.json').read_text(encoding='utf8'))
    for f in targets:
        fid = f['figure_id']; s = f.get('selection', {})
        try:
            from jsonschema import Draft202012Validator
            schema = json.loads((Path(__file__).parent.parent / '视觉计划.schema.json').read_text(encoding='utf8'))
            figure_schema = {'$ref':'#/$defs/figure', '$defs':schema['$defs']}
            failures = list(Draft202012Validator(figure_schema).iter_errors(f))
            if failures:
                errors.extend(fid+':selection_schema:'+e.message for e in failures)
                continue
            if s.get('figure_sha256') != selection_digest(f) or not current_evidence(root, s.get('evidence', {})):
                errors.append(fid + ':selection_stale_or_missing')
            checks = s.get('source_checks', [])
            if len(checks) != 2 or {x['source_skill'] for x in checks} != set(PROVIDERS):
                errors.append(fid + ':both_sources_must_be_checked')
            candidates = s.get('candidates', [])
            ids = {x['candidate_id']: x for x in candidates}
            if len(ids) != len(candidates) or not ids:
                errors.append(fid + ':candidate_ids_unique_and_nonempty')
            for c in candidates:
                if c['reference_id'] not in mapping[c['source_skill']]:
                    errors.append(fid + ':unknown_candidate_reference:' + c['reference_id'])
            for check in checks:
                actual = {x['candidate_id'] for x in candidates if x['source_skill'] == check['source_skill']}
                if actual != set(check['candidate_ids']) or len(check['observation'].strip()) < 12 or (not actual and len(check['limitation'].strip()) < 12):
                    errors.append(fid + ':source_search_incomplete:' + check['source_skill'])
            if len(candidates) < 2 and len(s.get('limited_candidates_reason', '').strip()) < 12:
                errors.append(fid + ':compare_alternatives_or_explain')
            chosen = set()
            for p in statistical_panels(f):
                tag = fid + ':' + p['panel_id']; candidate = ids.get(p.get('selected_candidate_id'))
                if p.get('source_skill') not in PROVIDERS or not p.get('chart_type'):
                    errors.append(tag + ':explicit_provider_and_chart_type_required')
                families = p.get('chart_families', [])
                if not families or not set(families) <= set(FAMILIES) or len(families) != len(set(families)):
                    errors.append(tag + ':actual_chart_families_required')
                if not candidate or candidate['source_skill'] != provider(p) or not candidate['suitable']:
                    errors.append(tag + ':selected_candidate_not_registered'); continue
                chosen.add(candidate['candidate_id'])
                if set(families) != set(candidate['chart_families']):
                    errors.append(tag + ':candidate_family_mismatch')
                key = p.get('template_id') if provider(p) == 'modelviz-skill' else Path(p.get('asset_directory','')).name
                known = mapping[provider(p)].get(key)
                if known is None or not set(families) <= set(known):
                    errors.append(tag + ':chart_mapping_requires_reviewed_extension:' + str(key))
                omitted=p.get('omitted_chart_families',[])
                omitted_names={o['chart_family'] for o in omitted}
                if (known is not None and (set(families)|omitted_names != set(known) or set(families)&omitted_names)
                    or len(omitted_names)!=len(omitted) or any(len(o['reason'].strip())<12 for o in omitted)):
                    errors.append(tag + ':mixed_template_families_unaccounted')
                if provider(p) == 'modelviz-skill' and candidate['reference_id'] != p.get('template_id'):
                    errors.append(tag + ':template_candidate_mismatch')
                if len(p.get('chart_review', '').strip()) < 12:
                    errors.append(tag + ':actual_panel_chart_review_required')
            d = s.get('three_d', {})
            three = [c for c in candidates if c['dimension'] == '3d' and c['suitable']]
            chosen_3d = any(ids[c]['dimension'] == '3d' for c in chosen)
            if not isinstance(d.get('applicable'), bool) or len(d.get('reason','').strip()) < 12:
                errors.append(fid + ':three_d_assessment_required')
            if d.get('applicable'):
                if not three or not any(c['dimension'] == '2d' for c in candidates):
                    errors.append(fid + ':compare_real_3d_and_2d_candidates')
                axes = d.get('axes', [])
                if len(axes) != 3 or any(not all(a.get(k) for k in ('field','unit','meaning','result_file')) for a in axes):
                    errors.append(fid + ':three_real_axes_required')
                for axis in axes:
                    if axis['result_file'] not in s.get('evidence', {}) or not any(axis['result_file'] == p['result_file'] and axis['field'] in p['fields'] for p in statistical_panels(f)):
                        errors.append(fid + ':axis_not_bound_to_result')
                if not chosen_3d and len(d.get('disadvantage', '').strip()) < 12:
                    errors.append(fid + ':qualified_3d_preferred_or_concrete_disadvantage_required')
            elif chosen_3d:
                errors.append(fid + ':meaningless_third_axis')
            if chosen_3d and any(len(d.get(k,'').strip()) < 8 for k in ('view','occlusion','projection','quantitative_basis')):
                errors.append(fid + ':three_d_readability_and_quantitative_basis_required')
            if any(c['dimension'] == '3d' and set(c['chart_families']) & {'bar','pie'} for c in candidates if c['candidate_id'] in chosen):
                errors.append(fid + ':decorative_3d_bar_or_pie_forbidden')
        except (KeyError, ValueError, TypeError, OSError) as exc:
            errors.append(fid + ':invalid_selection:' + str(exc))
    if body:
        errors += audit_diversity(selected, root)
    return errors


def audit_diversity(figures, root):
    """Count each actual family once per independent Figure, across both providers."""
    from visual_routes import statistical_panels
    active = [f for f in figures if f.get('count_role', 'independent_science') == 'independent_science']
    counts = {}
    for f in active:
        for family in {k for p in statistical_panels(f) for k in p.get('chart_families', [])}:
            counts.setdefault(family, set()).add(f['figure_id'])
    errors = []; stamp = portfolio_digest(active)
    for family, ids in counts.items():
        if len(ids) <= 2:
            continue
        valid = []
        for f in active:
            if f['figure_id'] not in ids:
                continue
            for e in f.get('selection', {}).get('repetition_exceptions', []):
                alternatives = e.get('alternatives', [])
                if (e.get('chart_family') == family and e.get('portfolio_sha256') == stamp
                    and set(e.get('figure_ids', [])) == ids and len(e.get('scientific_purpose','').strip()) >= 12
                    and len(e.get('reason','').strip()) >= 12 and alternatives
                    and all(a.get('chart_family') in FAMILIES and a['chart_family'] != family
                            and len(a.get('reason','').strip()) >= 12 for a in alternatives)
                    and current_evidence(root, e.get('evidence', {}))):
                    valid.append(f['figure_id'])
        if len(set(valid)) < len(ids)-2:
            errors.append('chart_family_limit:' + family + ':' + ','.join(sorted(ids)) + ':compare alternatives or record current exceptions for excess Figures')
    return errors
