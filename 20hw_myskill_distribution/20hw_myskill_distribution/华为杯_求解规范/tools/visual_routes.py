"""Panel-level routing. Missing routes retain the legacy academic contract."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

ROUTES = {'academic', 'native_media', 'domain_render', 'structure'}
NATIVE = {'source_image', 'video_frame', 'reconstructed_image', 'image_annotation', 'image_sequence'}
DOMAIN = {'gis_map', 'remote_sensing', 'terrain', 'spatial_field', 'point_cloud',
          'physical_3d', 'spectrogram', 'mfcc', 'evidence_network'}
STRUCTURE = {'algorithm', 'physics', 'flowchart', 'comprehensive'}
STATISTICAL_FAMILIES = {'trend_scan', 'comparison_ranking', 'prediction_diagnostic',
                      'classification_clustering', 'optimization_decision',
                      'distribution_uncertainty', 'relationship_correlation'}
MAP_KINDS = {'gis_map', 'remote_sensing', 'terrain'}
SIDES = {'codex': '.agents', 'claude': '.claude'}


def figures(plan):
    return list(plan.get('global_figures', [])) + [
        f for p in plan.get('problems', []) for f in p.get('figures', [])]


def route(panel):
    return panel.get('rendering_route', 'academic')


def academic_panels(figure):
    return [p for p in statistical_panels(figure) if provider(p) == 'academic-figure-skill']


def provider(panel):
    return panel.get('source_skill', 'academic-figure-skill')


def statistical_panels(figure):
    return [p for p in figure.get('panels', []) if route(p) == 'academic']


def modelviz_panels(figure):
    return [p for p in statistical_panels(figure) if provider(p) == 'modelviz-skill']


def routed_panels(figure):
    return [p for p in figure.get('panels', []) if route(p) != 'academic']


def academic_figures(plan):
    return [f for f in figures(plan) if academic_panels(f)]


def media_sidecar(plan_path):
    return Path(plan_path).with_suffix('.media.json')


def primary_output(figure):
    outputs = figure.get('outputs', {})
    return outputs.get('primary') or outputs.get('vector', '')


def routing_errors(figure):
    errors = []
    if routed_panels(figure) and figure.get('count_role') not in {'independent_science', 'illustration'}:
        errors.append(str(figure.get('figure_id')) + ':count_role_required')
    for p in figure.get('panels', []):
        tag = str(figure.get('figure_id')) + ':' + str(p.get('panel_id'))
        r, kind = route(p), p.get('content_kind')
        if r not in ROUTES:
            errors.append(tag + ':unknown_route')
        elif r == 'academic':
            if provider(p) == 'modelviz-skill':
                if not p.get('template_id'):
                    errors.append(tag + ':modelviz_template_required')
                if p.get('asset_directory') or p.get('asset_mode'):
                    errors.append(tag + ':modelviz_must_not_fabricate_academic_assets')
            elif provider(p) != 'academic-figure-skill':
                errors.append(tag + ':unknown_source_skill')
            elif not p.get('asset_directory') or p.get('asset_mode') not in {
                    'native_run', 'visual_adapt', 'cross_type_inherit'}:
                errors.append(tag + ':academic_mapping_required')
        else:
            allowed = NATIVE if r == 'native_media' else DOMAIN if r == 'domain_render' else STRUCTURE
            if kind not in allowed:
                errors.append(tag + ':content_route_mismatch')
            if p.get('figure_family') in STATISTICAL_FAMILIES:
                errors.append(tag + ':statistics_require_academic')
            if not isinstance(p.get('route_reason'), str) or len(p['route_reason'].strip()) < 8:
                errors.append(tag + ':route_reason_required')
            if p.get('asset_directory') or p.get('asset_mode'):
                errors.append(tag + ':do_not_fabricate_academic_mapping')
    outputs = figure.get('outputs', {})
    if statistical_panels(figure):
        if Path(outputs.get('vector', '')).suffix.lower() not in {'.pdf', '.svg'}:
            errors.append(str(figure.get('figure_id')) + ':academic_vector_required')
        if outputs.get('primary') and outputs['primary'] != outputs.get('vector'):
            errors.append(str(figure.get('figure_id')) + ':academic_primary_must_be_vector')
    elif Path(primary_output(figure)).suffix.lower() not in {'.png', '.jpg', '.jpeg', '.pdf', '.svg'}:
        errors.append(str(figure.get('figure_id')) + ':unsupported_primary_output')
    if not primary_output(figure):
        errors.append(str(figure.get('figure_id')) + ':primary_output_required')
    return errors


def contract_digest(figure, record):
    value = [copy.deepcopy(figure), copy.deepcopy(record)]
    value[0].pop('status', None)
    for key in ('status', 'run_record_path', 'qa_path'):
        value[1].pop(key, None)
    # Post-render checks are audited separately; recording a review must not
    # force a rerender of the already reviewed artifact.
    for panel in value[1].get('panels', []):
        review = panel.get('map_review')
        if review:
            for key in ('checks', 'legal_review', 'public_ready'):
                review.pop(key, None)
            review['evidence'] = [s for s in review.get('evidence', []) if s.get('kind') != 'review']
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode('utf8')).hexdigest()


def paper_specs(plan_path):
    """Use real primary files; the historical vector_path key also supports raster."""
    from audit_diagram_workflow import diagram_specs, sidecar
    path = Path(plan_path)
    plan = json.loads(path.read_text(encoding='utf-8-sig'))
    ap = path.with_suffix('.assets.json')
    mp = media_sidecar(path)
    academic = json.loads(ap.read_text(encoding='utf-8-sig')) if ap.is_file() else {'figures': []}
    media = json.loads(mp.read_text(encoding='utf-8-sig')) if mp.is_file() else {'figures': []}
    a = {r['figure_id']: r for r in academic['figures']}
    m = {r['figure_id']: r for r in media['figures']}
    from modelviz_bridge import sidecar as modelviz_sidecar
    modelviz = json.loads(modelviz_sidecar(path).read_text(encoding='utf-8-sig')) if modelviz_sidecar(path).is_file() else {'figures': []}
    v = {r['figure_id']: r for r in modelviz['figures']}
    result = []
    for f in figures(plan):
        rec = a[f['figure_id']] if academic_panels(f) else v[f['figure_id']] if modelviz_panels(f) else m[f['figure_id']]
        records = [group[f['figure_id']] for group in (a, m, v) if f['figure_id'] in group]
        if any(abs(r['target_width_mm'] - rec['target_width_mm']) > 0.01 for r in records):
            raise ValueError('Mixed panel paper widths disagree: ' + f['figure_id'])
        result.append({'figure_id': f['figure_id'], 'vector_path': primary_output(f),
                       'target_width_mm': rec['target_width_mm']})
    if sidecar(path).is_file():
        result += diagram_specs(path)
    return result


def audit_routes(plan_path, stage, root, runtime, allow_demo=False, main_tex=None, figure_ids=None):
    """Both gates run; neither can grant the other's exemption."""
    from audit_academic_figure_assets import audit_assets
    from audit_media_figures import audit_media
    plan = json.loads(Path(plan_path).read_text(encoding='utf-8-sig'))
    selected = [f for f in figures(plan) if figure_ids is None or f['figure_id'] in figure_ids]
    failures = [{'code': e} for f in selected for e in routing_errors(f)]
    if runtime not in SIDES:
        failures.append({'code': 'runtime_required'})
    if figure_ids is not None and set(figure_ids) != {f['figure_id'] for f in selected}:
        failures.append({'code': 'unknown_figure_selection'})
    academic = audit_assets(plan_path, stage, root, allow_demo=allow_demo, runtime=runtime,
                            main_tex=main_tex, figure_ids=figure_ids)
    media = audit_media(plan_path, stage, root, runtime, allow_demo, main_tex, figure_ids)
    failures += academic['failures'] + media['failures']
    from modelviz_bridge import audit_modelviz
    from chart_policy import audit_policy
    modelviz = audit_modelviz(plan_path, stage, root, runtime, allow_demo, main_tex, figure_ids)
    failures += modelviz['failures']
    failures += [{'code': e} for e in audit_policy(plan, root, runtime, figure_ids, body=figure_ids is None)]
    return {'status': 'FAIL' if failures else 'PASS', 'stage': stage, 'failures': failures,
            'academic': academic, 'media': media, 'modelviz': modelviz,
            'assurance': 'Routing and current evidence checks do not prove scientific judgment or actual viewing.'}
