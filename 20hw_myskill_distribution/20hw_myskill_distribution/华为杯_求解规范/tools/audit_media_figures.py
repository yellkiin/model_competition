"""Provenance and review gate for native media, domain rendering and mixed panels."""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)


import argparse
from contextvars import ContextVar
from datetime import date
import json
from pathlib import Path

from build_academic_figure_asset_index import safe, sha, write_json
from visual_routes import (SIDES, MAP_KINDS, academic_panels, contract_digest, figures,
                           media_sidecar, primary_output, route, routed_panels, routing_errors)

MAP_CHECKS = ('boundary_source', 'boundary_integrity', 'south_china_sea', 'taiwan',
              'diaoyu_chiwei', 'western_boundary', 'extent', 'layer_occlusion',
              'crs_alignment', 'source_credit', 'precision', 'sensitive_content',
              'scale_bar', 'orientation', 'coordinate_grid', 'legend')
PARAMETERS = {
    'source_image': ('pages_frames', 'display_transform'),
    'video_frame': ('frame_numbers', 'timestamps_seconds', 'selection_rule', 'native_size'),
    'reconstructed_image': ('shape', 'dtype', 'byte_order', 'channel_order', 'layout'),
    'image_annotation': ('pages_frames', 'annotations', 'display_transform'),
    'image_sequence': ('frame_numbers', 'selection_rule', 'layout'),
    'gis_map': ('source_crs', 'target_crs', 'transform', 'geometry_attributes'),
    'remote_sensing': ('bands', 'nodata', 'units', 'source_crs', 'target_crs', 'resampling', 'display_transform'),
    'terrain': ('bands', 'nodata', 'units', 'source_crs', 'target_crs', 'resampling', 'derivation'),
    'spatial_field': ('variables', 'dimensions', 'coordinates', 'units', 'missing_values', 'selection'),
    'point_cloud': ('coordinates', 'units', 'attributes', 'view', 'decimation'),
    'physical_3d': ('coordinates', 'units', 'view', 'projection'),
    'spectrogram': ('sample_rate', 'channels', 'window', 'hop_length', 'fft_size', 'scale'),
    'mfcc': ('sample_rate', 'channels', 'window', 'hop_length', 'fft_size', 'n_mfcc', 'mel_parameters'),
    'evidence_network': ('entities', 'relations', 'extraction_method', 'source_locators'),
}
_ACTIVE_MEDIA = ContextVar('active_media_figures', default=frozenset())


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def meaningful(value):
    return isinstance(value, str) and len(value.strip()) >= 6 and not any(
        s in value.lower() for s in ('todo', 'pending', '待填写', 'needs_review'))


def filled(value):
    return value is not None and value != '' and value != [] and value != {}


def prepare(plan_path, runtime, purpose='production'):
    if runtime not in SIDES:
        raise ValueError('Explicit runtime required')
    records = []
    for f in figures(load(plan_path)):
        panels = routed_panels(f)
        if not panels:
            continue
        records.append({
            'figure_id': f['figure_id'], 'status': 'planned', 'target_width_mm': 0,
            'paper_geometry': {'source_tex': '', 'source_sha256': '', 'basis': ''},
            'output_kind': 'raster', 'scientific_contribution': '', 'count_role': 'unreviewed',
            'classification_review': {'reviewed': False, 'observation': '', 'tool_ref': ''},
            'run_record_path': '', 'qa_path': '',
            'panels': [{'panel_id': p['panel_id'], 'rendering_route': route(p),
                        'content_kind': p.get('content_kind', ''), 'sources': [],
                        'dependencies': [], 'parameters': {k: None for k in PARAMETERS.get(p.get('content_kind'), ())},
                        'interpretation': '', 'encoding': {'kind': 'unreviewed', 'description': ''},
                        'geographic': None, 'map_review': None,
                        'structure_reference': None} for p in panels]})
    return {'schema_version': '1.0', 'runtime': runtime, 'purpose': purpose,
            'figures': records, 'paper_review_path': ''}


def extend_draft(plan_path, runtime, purpose='production'):
    """Append new blank records, preserving all existing review history."""
    import copy
    fresh = prepare(plan_path, runtime, purpose)
    sidecar = media_sidecar(plan_path)
    if not sidecar.is_file():
        return fresh
    old = load(sidecar)
    if old.get('runtime') != runtime or old.get('purpose') != purpose:
        raise ValueError('Existing media runtime/purpose differs; do not transfer reviews across contexts')
    previous = {r['figure_id']: r for r in old['figures']}
    current = {r['figure_id']: r for r in fresh['figures']}
    if not set(previous) <= set(current):
        raise ValueError('Removed media figures require explicit archived migration')
    merged = copy.deepcopy(old)
    for record in merged['figures']:
        template = current[record['figure_id']]
        known = {p['panel_id']: p for p in record['panels']}
        desired = {p['panel_id']: p for p in template['panels']}
        if not set(known) <= set(desired) or any(
                (p['rendering_route'], p['content_kind']) !=
                (desired[k]['rendering_route'], desired[k]['content_kind']) for k, p in known.items()):
            raise ValueError('Changed panel routes require explicit archived migration')
        additions = [p for p in template['panels'] if p['panel_id'] not in known]
        if additions:
            record['panels'].extend(additions)
            record['status'] = 'planned'
            record['classification_review'] = template['classification_review']
    merged['figures'].extend(r for r in fresh['figures'] if r['figure_id'] not in previous)
    return merged


def media_input_path(root, raw, rec, runtime=None):
    """Only the declared paper geometry may refer to a shared template file."""
    if raw == rec['paper_geometry']['source_tex']:
        from workspace_context import reference_path, shared_context
        context = shared_context(root, runtime)
        return reference_path(root, raw, context.runtime if context else runtime)
    return safe(root, raw)


def current_files(root, f, rec, runtime=None):
    raw = {f['script']} | {p['result_file'] for p in f['panels']}
    raw.add(rec['paper_geometry']['source_tex'])
    for p in rec['panels']:
        raw.update(s['path'] for s in p['sources'])
        raw.update(p.get('dependencies', []))
        for s in p['sources']:
            raw.add(s['inventory_path'])
            inventory = load(safe(root, s['inventory_path']))
            item = next(x for x in inventory['files'] if x['path'] == s['path'])
            raw.update(item.get('related_files', {}))
        if p.get('map_review'):
            raw.update(s['path'] for s in p['map_review'].get('evidence', []) if s.get('kind') != 'review')
        if p.get('structure_reference'):
            from audit_diagram_workflow import sidecar
            raw.add(str(sidecar(p['structure_reference']['plan_path'])))
    return {s: sha(media_input_path(root, s, rec, runtime)) for s in sorted(raw)}


def review_map(root, p, tag, stage, add, primary=None):
    m = p.get('map_review') or {}
    add(tag + ':map_review_required', bool(m))
    add(tag + ':map_scope', m.get('scope') in {'china_full', 'china_local', 'world', 'other'})
    add(tag + ':map_use', m.get('intended_use') in {'internal', 'public'})
    add(tag + ':china_boundary_decision', isinstance(m.get('shows_china_boundary'), bool))
    add(tag + ':china_boundary_scope', not m.get('shows_china_boundary') or
        m.get('scope') in {'china_full', 'china_local', 'world'})
    add(tag + ':full_china_boundary_required', m.get('scope') != 'china_full' or
        m.get('shows_china_boundary') is True)
    laws = m.get('official_sources', [])
    from urllib.parse import urlparse
    def official(s):
        host = urlparse(s.get('url', '')).hostname or ''
        try:
            checked = date.fromisoformat(s['checked_date'])
            valid_date = checked <= date.today()
        except (ValueError, KeyError, TypeError):
            valid_date = False
        return host.endswith('.gov.cn') and valid_date and s.get('reviewed') is True and all(
            meaningful(s.get(k)) for k in ('title', 'version', 'applicability', 'sections', 'observation'))
    add(tag + ':official_rules_verified', bool(laws) and all(official(s) for s in laws))
    add(tag + ':law_and_project_distinguished', meaningful(m.get('project_stricter_rules')))
    ev = m.get('evidence', [])
    source_evidence = {s['path'] for s in ev if s.get('kind', 'source') == 'source'}
    add(tag + ':map_evidence_roles', all(s.get('kind', 'source') in {'source', 'review'} for s in ev))
    add(tag + ':map_evidence_current', bool(ev) and all(
        safe(root, s['path']).is_file() and s.get('sha256') == sha(safe(root, s['path'])) for s in ev))
    checks = m.get('checks', {})
    add(tag + ':map_checks_exact', set(checks) == set(MAP_CHECKS))
    for k in MAP_CHECKS:
        c = checks.get(k, {})
        allowed_states = {'pass', 'not_applicable', 'pending'} if stage == 'plan' else {'pass', 'not_applicable'}
        add(tag + ':map:' + k, c.get('status') in allowed_states
            and meaningful(c.get('reason')) and bool(c.get('evidence_paths'))
            and set(c['evidence_paths']) <= {s['path'] for s in ev})
    if m.get('scope') == 'china_full' and stage != 'plan':
        add(tag + ':full_china_elements', all(checks.get(k, {}).get('status') == 'pass' for k in (
            'boundary_source', 'boundary_integrity', 'south_china_sea', 'taiwan', 'diaoyu_chiwei',
            'western_boundary', 'extent', 'layer_occlusion', 'source_credit')))
    if m.get('scope') in {'china_full', 'china_local', 'world'} and m.get('shows_china_boundary'):
        base = m.get('basemap', {})
        add(tag + ':approved_boundary_source', base.get('kind') in {'official_standard', 'verified_boundary'}
            and meaningful(base.get('source')) and base.get('verified') is True
            and base.get('path') in source_evidence)
        if base.get('kind') == 'official_standard':
            add(tag + ':basemap_review_number', bool(base.get('review_number')))
    params = p.get('parameters', {})
    add(tag + ':crs_explicit', bool(params.get('source_crs')) and bool(params.get('target_crs')))
    try:
        from pyproj import CRS
        for key in ('source_crs', 'target_crs'):
            CRS.from_user_input(params[key])
        add(tag + ':crs_parseable', True)
    except Exception as exc:
        add(tag + ':crs_parseable', False, error=str(exc))
    reg = m.get('registration', {})
    add(tag + ':registration_verified', reg.get('verified') is True and meaningful(reg.get('method'))
        and meaningful(reg.get('accuracy_evidence')) and bool(reg.get('evidence_paths'))
        and set(reg['evidence_paths']) <= source_evidence)
    legal = m.get('legal_review', {})
    add(tag + ':legal_review_separate', legal.get('status') in {'required_pending', 'approved', 'not_required'}
        and meaningful(legal.get('basis')))
    if legal.get('status') == 'approved':
        add(tag + ':final_map_approval', bool(legal.get('review_number'))
            and legal.get('approval_path') in {s['path'] for s in ev})
        if stage != 'plan':
            add(tag + ':approved_artifact_current', primary is not None and
                safe(root, primary).is_file() and legal.get('approved_output_sha256') == sha(safe(root, primary)))
    if m.get('intended_use') == 'public' and stage != 'plan':
        add(tag + ':public_release_authorized', legal.get('status') in {'approved', 'not_required'})
    add(tag + ':public_ready_not_overclaimed', m.get('public_ready') is not True or (
        m.get('intended_use') == 'public' and legal.get('status') in {'approved', 'not_required'}))


def audit_media(plan_path, stage, root, runtime, allow_demo=False, main_tex=None, figure_ids=None):
    root = Path(root).resolve()
    checks, failures = [], []
    def add(code, ok, **details):
        row = {'code': code, 'ok': bool(ok), **details}
        checks.append(row)
        if not ok:
            failures.append(row)
    try:
        plan_path = safe(root, str(plan_path))
        plan = load(plan_path)
        fs = [f for f in figures(plan) if routed_panels(f)]
        if figure_ids is not None:
            fs = [f for f in fs if f['figure_id'] in figure_ids]
        add('media_runtime_explicit', runtime in SIDES)
        if not fs:
            return {'status': 'FAIL' if failures else 'PASS', 'checks': checks, 'failures': failures}
        data = load(media_sidecar(plan_path))
        from jsonschema import Draft202012Validator
        spec = load(Path(__file__).resolve().parents[1] / '视觉素材证据.schema.json')
        errs = [e.message for e in Draft202012Validator(spec).iter_errors(data)]
        add('media_schema', not errs, errors=errs)
        add('media_runtime_matches', data.get('runtime') == runtime)
        demo = data.get('purpose') == 'demo'
        add('media_demo_isolated', not demo or (allow_demo and stage != 'paper' and
            plan_path.is_relative_to(root / '求解/验收输出') and 'demo' in plan_path.as_posix().lower()))
        records = {r['figure_id']: r for r in data['figures']}
        expected = {f['figure_id'] for f in figures(plan) if routed_panels(f)}
        add('media_figures_exact', len(records) == len(data['figures']) and set(records) == expected)
        for f in fs:
            fid = f['figure_id']
            dependency = (str(plan_path.resolve()), fid)
            if dependency in _ACTIVE_MEDIA.get():
                add(fid + ':cyclic_visual_dependency', False)
                continue
            active_token = _ACTIVE_MEDIA.set(_ACTIVE_MEDIA.get() | {dependency})
            try:
                rec = records[fid]
                add(fid + ':routing', not routing_errors(f), errors=routing_errors(f))
                review = rec.get('classification_review', {})
                add(fid + ':classification_reviewed', review.get('reviewed') is True and
                    meaningful(review.get('tool_ref')) and meaningful(review.get('observation')))
                add(fid + ':scientific_contribution', meaningful(rec.get('scientific_contribution')))
                add(fid + ':count_role', rec.get('count_role') in {'independent_science', 'illustration'}
                    and rec.get('count_role') == f.get('count_role'))
                geo = rec.get('paper_geometry', {})
                add(fid + ':paper_geometry', isinstance(rec.get('target_width_mm'), (int, float))
                    and rec['target_width_mm'] > 0 and meaningful(geo.get('basis'))
                    and geo.get('source_sha256') == sha(media_input_path(root, geo['source_tex'], rec, runtime)))
                add(fid + ':output_kind', rec.get('output_kind') in {'raster', 'mixed', 'vector'})
                ps = {p['panel_id']: p for p in rec['panels']}
                add(fid + ':media_panels_exact', len(ps) == len(rec['panels']) and
                    set(ps) == {p['panel_id'] for p in routed_panels(f)})
                for panel in routed_panels(f):
                    tag = fid + ':' + panel['panel_id']
                    p = ps[panel['panel_id']]
                    add(tag + ':route_matches', p['rendering_route'] == route(panel)
                        and p['content_kind'] == panel['content_kind'])
                    add(tag + ':interpretation', meaningful(p.get('interpretation')))
                    sources = p.get('sources', [])
                    add(tag + ':sources_present', bool(sources))
                    add(tag + ':result_source_link', panel['result_file'] in
                        {s['path'] for s in sources} | set(p.get('dependencies', [])))
                    for s in sources:
                        raw = s['path']
                        source = safe(root, raw)
                        add(tag + ':source_current:' + raw, source.is_file() and s.get('sha256') == sha(source))
                        add(tag + ':source_role:' + raw, s.get('role') in {'observation', 'reference', 'derived'}
                            and meaningful(s.get('origin')) and meaningful(s.get('permission')))
                        add(tag + ':reference_not_result:' + raw, s.get('role') != 'reference' or
                            rec.get('count_role') == 'illustration')
                        inventory = load(safe(root, s['inventory_path']))
                        item = next(x for x in inventory['files'] if x['path'] == raw)
                        add(tag + ':inventory_verified:' + raw, item['sha256'] == s['sha256']
                            and item.get('read_status') == 'readable' and item.get('metadata')
                            and s.get('metadata_reviewed') is True and meaningful(s.get('metadata_observation')))
                        metadata = item.get('metadata', {})
                        add(tag + ':related_files_current:' + raw, all(
                            safe(root, name).is_file() and sha(safe(root, name)) == digest
                            for name, digest in item.get('related_files', {}).items()))
                        declared_crs = p.get('parameters', {}).get('source_crs')
                        actual_crs = metadata.get('crs') or next((x.get('crs') for x in metadata.get('layers', []) if x.get('crs')), None)
                        if actual_crs and declared_crs:
                            from pyproj import CRS
                            add(tag + ':source_crs_matches_metadata', CRS.from_user_input(actual_crs).equals(CRS.from_user_input(declared_crs)))
                        if p['content_kind'] == 'video_frame':
                            pars = p.get('parameters', {})
                            streams = [x for x in metadata.get('streams', []) if x.get('codec_type') == 'video']
                            if streams:
                                st = streams[0]
                                add(tag + ':native_frame_size', pars.get('native_size') == [st.get('width'), st.get('height')])
                            nums, times = pars.get('frame_numbers', []), pars.get('timestamps_seconds', [])
                            add(tag + ':frame_selection', isinstance(nums, list) and isinstance(times, list)
                                and len(nums) == len(times) > 0 and len(set(nums)) == len(nums)
                                and all(isinstance(n, int) and n >= 0 for n in nums)
                                and all(isinstance(t, (int, float)) and t >= 0 for t in times))
                    pars = p.get('parameters', {})
                    add(tag + ':parameters_recorded', all(filled(pars.get(k)) for k in PARAMETERS.get(p['content_kind'], ())))
                    enc = p.get('encoding', {})
                    add(tag + ':encoding', enc.get('kind') in {'continuous', 'categorical', 'true_color', 'none'}
                        and meaningful(enc.get('description')))
                    if enc.get('kind') == 'continuous':
                        add(tag + ':colorbar', bool(enc.get('variable')) and 'unit' in enc and enc.get('colorbar') is True)
                    if enc.get('kind') == 'categorical':
                        add(tag + ':category_legend', bool(enc.get('categories')) and enc.get('legend') is True)
                    add(tag + ':geographic_decision', isinstance(p.get('geographic'), bool))
                    if p['content_kind'] in MAP_KINDS:
                        add(tag + ':map_is_geographic', p.get('geographic') is True)
                    if p.get('geographic') or p.get('map_review'):
                        review_map(root, p, tag, stage, add, primary_output(f))
                    if route(panel) == 'structure':
                        ref = p.get('structure_reference') or {}
                        from audit_diagram_workflow import audit, sidecar
                        sp = safe(root, ref['plan_path'])
                        ds = load(sidecar(sp))
                        d = next(d for d in ds['diagrams'] if d['diagram_id'] == ref['diagram_id'])
                        add(tag + ':structure_link', d['kind'] == panel['content_kind'] and
                            d.get('outputs', {}).get('vector') == panel['result_file'])
                        gate = audit(sp, 'plan' if stage == 'plan' else 'render', root, runtime,
                                     allow_demo=allow_demo, diagram_ids=[ref['diagram_id']])
                        add(tag + ':structure_gate', gate['status'] == 'PASS', failures=gate['failures'])
                if stage in {'render', 'paper'}:
                    audit_render(root, f, rec, runtime, add)
            except (KeyError, ValueError, TypeError, OSError, StopIteration) as exc:
                add(fid + ':media_record_invalid', False, error=str(exc))
            finally:
                _ACTIVE_MEDIA.reset(active_token)
        if stage == 'paper':
            add('media_paper_main', main_tex is not None)
            if main_tex is not None:
                from visual_routes import paper_specs
                from collect_academic_paper_review import verify_evidence
                errors = verify_evidence(root, load(safe(root, data['paper_review_path'])),
                                         main_tex, runtime, paper_specs(plan_path))
                add('media_paper_evidence', not errors, errors=errors)
    except Exception as exc:
        add('media_gate_input_error', False, error=f'{type(exc).__name__}: {exc}')
    return {'status': 'FAIL' if failures else 'PASS', 'checks': checks, 'failures': failures}


def audit_render(root, f, rec, runtime, add):
    from PIL import Image, ImageOps
    import pymupdf as fitz
    fid = f['figure_id']
    digest = contract_digest(f, rec)
    qa = load(safe(root, rec['qa_path']))
    run = load(safe(root, rec['run_record_path']))
    from workspace_resources import evidence_current
    add(fid + ':resource_dependencies_current', evidence_current(root,runtime,'media',run)
        and evidence_current(root,runtime,'media',qa))
    inputs = current_files(root, f, rec, runtime)
    outputs = {s: sha(safe(root, s)) for s in set(f['outputs'].values()) | {f['statistics_report']}}
    add(fid + ':media_qa_pass', rec.get('status') == f.get('status') == 'qa_pass' and qa.get('status') == 'PASS')
    add(fid + ':media_contract_current', qa.get('contract_sha256') == digest == run.get('contract_sha256'))
    add(fid + ':media_run_current', run.get('runtime') == runtime and run.get('figure_id') == fid
        and run.get('returncode') == 0 and run.get('inputs_before') == inputs == run.get('inputs_after')
        and run.get('outputs') == outputs and run.get('log_sha256') == sha(safe(root, run['log_path'])))
    add(fid + ':media_execution_command', isinstance(run.get('command'), list) and
        str(safe(root, f['script'])) in run['command'] and run.get('started_at_ns', 0) > 0)
    add(fid + ':media_outputs_written', set(run.get('output_mtime_ns', {})) == set(outputs) and all(
        run['output_mtime_ns'][s] == safe(root, s).stat().st_mtime_ns >= run['started_at_ns'] for s in outputs))
    add(fid + ':media_qa_files_current', qa.get('inputs') == inputs and qa.get('outputs') == outputs)
    for key in ('scientific_validity', 'source_fidelity', 'print_readability'):
        d = qa.get('dimensions', {}).get(key, {})
        add(fid + ':media_dimension:' + key, d.get('status') == 'PASS' and meaningful(d.get('observation')))
    views = qa.get('views', [])
    required = {'final', 'grayscale', 'comparison', 'pdf_page', 'detail'}
    add(fid + ':media_views_exact', {v['kind'] for v in views} == required and len(views) == len(required))
    with Image.open(safe(root, f['outputs']['preview'])) as im:
        original = im.convert('RGB')
    for v in views:
        vp = safe(root, v['path'])
        add(fid + ':media_view:' + v['kind'], v.get('reviewed') is True and meaningful(v.get('tool_ref'))
            and meaningful(v.get('observation')) and v.get('sha256') == sha(vp))
        if v['kind'] in {'final', 'grayscale', 'detail'}:
            expected = original
            if v['kind'] == 'grayscale':
                expected = ImageOps.grayscale(original).convert('RGB')
            if v['kind'] == 'detail':
                box = v.get('crop_box', [])
                if len(box) != 4 or not (0 <= box[0] < box[2] <= original.width and 0 <= box[1] < box[3] <= original.height):
                    raise ValueError('Invalid detail crop')
                expected = original.crop(box)
            with Image.open(vp) as actual:
                add(fid + ':media_derivative:' + v['kind'], expected.size == actual.size and
                    expected.tobytes() == actual.convert('RGB').tobytes())
        if v['kind'] == 'comparison':
            add(fid + ':comparison_sources_current', v.get('source_hashes') == inputs
                and v.get('final_sha256') == sha(safe(root, f['outputs']['preview'])))
            from run_media_figure import comparison_tiles, comparison_image
            tiles, source_views = comparison_tiles(root, f, rec)
            expected = comparison_image(tiles)
            with Image.open(vp) as actual:
                add(fid + ':comparison_actual_sources', v.get('source_views') == source_views and
                    actual.size == expected.size and actual.convert('RGB').tobytes() == expected.tobytes())
        if v['kind'] == 'pdf_page':
            pdf = safe(root, v['pdf_path'])
            add(fid + ':pdf_preview_current', v.get('pdf_sha256') == sha(pdf))
            from run_media_figure import print_pdf_bytes
            with fitz.open(stream=print_pdf_bytes(root, f, rec), filetype='pdf') as expected_doc:
                expected_pix = expected_doc[0].get_pixmap(dpi=v['dpi'], alpha=False)
            with fitz.open(pdf) as doc:
                pix = doc[v.get('page_number', 1) - 1].get_pixmap(dpi=v['dpi'], alpha=False)
                add(fid + ':pdf_represents_primary', len(doc) == 1 and v.get('page_number') == 1
                    and (pix.width, pix.height) == (expected_pix.width, expected_pix.height)
                    and pix.samples == expected_pix.samples)
                with Image.open(vp) as actual:
                    add(fid + ':pdf_preview_pixels', actual.size == (pix.width, pix.height)
                        and actual.convert('RGB').tobytes() == pix.samples)
    primary = safe(root, primary_output(f))
    from visual_routes import statistical_panels
    if not statistical_panels(f):
        add(fid + ':media_qa_is_canonical', safe(root, f['qa_report']) == safe(root, rec['qa_path']))
    if primary.suffix.lower() == '.pdf':
        with fitz.open(primary) as doc:
            add(fid + ':media_pdf_size', len(doc) == 1 and abs(doc[0].rect.width * 25.4 / 72 - rec['target_width_mm']) < 1)
            if rec['output_kind'] == 'vector':
                add(fid + ':vector_not_embedded_raster', bool(doc[0].get_drawings()) and not doc[0].get_images())
    elif primary.suffix.lower() in {'.png', '.jpg', '.jpeg'}:
        add(fid + ':raster_declared', rec['output_kind'] == 'raster')
    resolution = qa.get('resolution_review', {})
    add(fid + ':native_resolution_review', resolution.get('reviewed') is True
        and meaningful(resolution.get('observation')) and meaningful(resolution.get('source_pixel_basis'))
        and resolution.get('target_width_mm') == rec['target_width_mm']
        and resolution.get('preview_pixels') == list(original.size))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-root', type=Path, default=Path('.'))
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--runtime', choices=sorted(SIDES), required=True)
    p.add_argument('--stage', choices=['plan', 'render', 'paper'], default='plan')
    p.add_argument('--prepare', action='store_true')
    p.add_argument('--purpose', choices=['production', 'demo'], default='production')
    p.add_argument('--allow-demo', action='store_true')
    p.add_argument('--main-tex', type=Path)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    root = a.project_root.resolve()
    plan = safe(root, str(a.plan))
    if a.prepare:
        out = media_sidecar(plan)
        value = extend_draft(plan, a.runtime, a.purpose)
        if out.exists() and load(out) != value:
            import uuid
            backup = out.parent / (out.name + '.history') / (uuid.uuid4().hex + '.json')
            write_json(backup, load(out))
        write_json(out, value)
        print(json.dumps({'status': 'DRAFT_REQUIRES_REVIEW', 'path': str(out)}))
        return
    result = audit_media(plan, a.stage, root, a.runtime, a.allow_demo, a.main_tex)
    if a.report:
        write_json(safe(root, str(a.report)), result)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
