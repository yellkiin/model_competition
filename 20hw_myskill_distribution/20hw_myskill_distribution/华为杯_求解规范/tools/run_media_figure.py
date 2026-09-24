"""Execute a routed figure and prepare unreviewed, reproducible media comparisons."""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)


import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from build_academic_figure_asset_index import safe, sha, write_json
from audit_media_figures import current_files, media_input_path, load
from visual_routes import (academic_panels, contract_digest, figures, media_sidecar,
                           primary_output, routed_panels)


def execute(root, plan_path, figure_id, runtime, arguments, interpreter=None, allow_demo=False, timeout=600):
    from candidate_figures import audit_figure
    root = Path(root).resolve()
    plan_path = safe(root, str(plan_path))
    gate = audit_figure(root, plan_path, figure_id, 'plan', runtime, allow_demo)
    if gate['status'] != 'PASS':
        raise ValueError('Plan gate failed: ' + json.dumps(gate['failures'], ensure_ascii=False))
    f = next(f for f in figures(load(plan_path)) if f['figure_id'] == figure_id)
    rec = next(r for r in load(media_sidecar(plan_path))['figures'] if r['figure_id'] == figure_id)
    script = safe(root, f['script'])
    executable = Path(interpreter or sys.executable).resolve()
    if not executable.is_file() or script.suffix.lower() != '.py':
        raise ValueError('Provide an existing Python interpreter and reproducible Python entrypoint')
    before = current_files(root, f, rec, runtime)
    from workspace_resources import dependencies
    resource_dependencies = dependencies(root,runtime,'media')
    output_paths = set(f['outputs'].values()) | {f['statistics_report']}
    rp = safe(root, rec['run_record_path'])
    log_path = rp.with_suffix('.log')
    if academic_panels(f):
        from prepare_academic_figure_review import sidecar_path
        academic = next(r for r in load(sidecar_path(plan_path))['figures'] if r['figure_id'] == figure_id)
        ar = safe(root, academic['run_record_path'])
        academic_paths = {ar, ar.with_suffix('.log'), safe(root, f['qa_report'])}
        media_paths = {rp, log_path, safe(root, rec['qa_path'])}
        if academic_paths & media_paths:
            raise ValueError('Mixed figure academic and media evidence paths must be distinct')
        if ar.exists() or ar.with_suffix('.log').exists():
            raise ValueError('Preserve academic execution history; choose a new run_record_path')
    if rp.exists() or log_path.exists():
        raise ValueError('Preserve execution history; choose a new run_record_path')
    protected = {media_input_path(root, p, rec, runtime) for p in before}
    destinations = {safe(root, p) for p in output_paths} | {rp, log_path}
    if protected & destinations or rp in {safe(root, p) for p in output_paths}:
        raise ValueError('Input/output/evidence collision')
    raw_root = root / '数据'
    if any(p.is_relative_to(raw_root) for p in destinations):
        raise ValueError('Figure runner cannot write into the attachment data tree')
    command = [str(executable), str(script), *arguments]
    started = time.time_ns()
    if academic_panels(f):
        from run_academic_figure import execute as execute_academic
        result = execute_academic(root, plan_path, figure_id, runtime, arguments,
                                  str(executable), allow_demo, timeout)
        code = result['returncode']
        text = safe(root, result['log_path']).read_text(encoding='utf8')
        started = result['started_at_ns']
    else:
        env = dict(os.environ, PYTHONUTF8='1', MPLBACKEND='Agg', PYTHONDONTWRITEBYTECODE='1')
        try:
            result = subprocess.run(command, cwd=root, env=env, capture_output=True,
                                    text=True, encoding='utf8', errors='replace', timeout=timeout)
            code, text = result.returncode, result.stdout + '\n' + result.stderr
        except subprocess.TimeoutExpired as exc:
            code, text = 124, str(exc)
    rp.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(command, ensure_ascii=False) + '\n' + text, encoding='utf8')
    after = current_files(root, f, rec, runtime)
    outputs = {p: sha(safe(root, p)) for p in output_paths if safe(root, p).is_file()}
    mtimes = {p: safe(root, p).stat().st_mtime_ns for p in outputs}
    failures = []
    if code:
        failures.append('script_failed')
    if before != after:
        failures.append('input_changed')
    if set(outputs) != output_paths or any(t < started for t in mtimes.values()):
        failures.append('missing_or_old_output')
    result = {'schema_version': '1.0', 'runtime': runtime, 'figure_id': figure_id,
              'resource_dependencies': resource_dependencies,
              'contract_sha256': contract_digest(f, rec), 'command': command, 'cwd': str(root),
              'started_at_ns': started, 'finished_at_ns': time.time_ns(), 'returncode': code,
              'inputs_before': before, 'inputs_after': after, 'outputs': outputs,
              'output_mtime_ns': mtimes, 'log_path': log_path.relative_to(root).as_posix(),
              'log_sha256': sha(log_path), 'failures': failures,
              'status': 'FAIL' if failures else 'EXECUTED_REVIEW_REQUIRED'}
    write_json(rp, result)
    return result


def comparison_tiles(root, f, rec):
    from prepare_academic_figure_qa import raster
    tiles, source_views = [], {}
    for panel in rec['panels']:
        basemap = (panel.get('map_review') or {}).get('basemap', {})
        if basemap.get('path'):
            raw = basemap.get('preview_path') or basemap['path']
            if raw != basemap['path'] and raw not in panel['dependencies']:
                raise ValueError('Basemap preview must be a declared dependency')
            for i, im in enumerate(raster(safe(root, raw))):
                tiles.append((f"BASEMAP / {Path(raw).name} / {i}", im))
            source_views[raw] = sha(safe(root, raw))
        for source in panel['sources']:
            raw = source.get('preview_path') or source['path']
            if source.get('preview_path') and raw not in panel['dependencies']:
                raise ValueError('Professional source preview must be a declared dependency')
            path = safe(root, raw)
            for i, im in enumerate(raster(path)):
                tiles.append((f"{panel['panel_id']} / {Path(raw).name} / {i}", im))
            source_views[raw] = sha(path)
    tiles.append(('CURRENT / ' + f['figure_id'], raster(safe(root, f['outputs']['preview']))[0]))
    return tiles, source_views


def comparison_image(tiles):
    from PIL import Image, ImageDraw, ImageFont
    width, height, columns = 700, 580, min(3, len(tiles))
    canvas = Image.new('RGB', (columns * width, ((len(tiles) + columns - 1) // columns) * height), '#eeeeee')
    draw = ImageDraw.Draw(canvas)
    font_path = Path('C:/Windows/Fonts/msyh.ttc')
    font = ImageFont.truetype(str(font_path), 17) if font_path.exists() else ImageFont.load_default()
    for i, (title, source) in enumerate(tiles):
        im = source.copy()
        im.thumbnail((width - 24, height - 70))
        x, y = (i % columns) * width, (i // columns) * height
        draw.text((x + 12, y + 10), title[:65], font=font, fill='#222222')
        canvas.paste(im, (x + (width - im.width) // 2, y + 55 + (height - 70 - im.height) // 2))
    return canvas


def print_pdf_bytes(root, f, rec):
    """Build the print-size view from the actual primary, preserving SVG vectors."""
    import pymupdf as fitz
    primary = safe(root, primary_output(f))
    if primary.suffix.lower() == '.pdf':
        return primary.read_bytes()
    width = rec['target_width_mm'] * 72 / 25.4
    with fitz.open(primary) as source:
        converted = source.convert_to_pdf()
    with fitz.open(stream=converted, filetype='pdf') as source, fitz.open() as doc:
        rect = source[0].rect
        page = doc.new_page(width=width, height=width * rect.height / rect.width)
        page.show_pdf_page(page.rect, source, 0)
        return doc.tobytes()


def prepare_qa(root, plan_path, figure_id, runtime):
    from PIL import Image, ImageOps
    import pymupdf as fitz
    root = Path(root).resolve()
    plan_path = safe(root, str(plan_path))
    media = load(media_sidecar(plan_path))
    if runtime != media['runtime']:
        raise ValueError('Runtime mismatch')
    f = next(f for f in figures(load(plan_path)) if f['figure_id'] == figure_id)
    rec = next(r for r in media['figures'] if r['figure_id'] == figure_id)
    qp = safe(root, rec['qa_path'])
    if academic_panels(f) and safe(root, f['qa_report']) == qp:
        raise ValueError('Mixed figure academic and media QA paths must be distinct')
    if not academic_panels(f) and safe(root, f['qa_report']) != qp:
        raise ValueError('Pure media figure qa_report must point to its media QA')
    out = qp.parent / (qp.stem + '_files')
    if qp.exists() or out.exists():
        raise ValueError('Keep existing visual evidence; choose a fresh qa_path')
    out.mkdir(parents=True)
    preview = safe(root, f['outputs']['preview'])
    primary = safe(root, primary_output(f))
    with Image.open(preview) as im:
        source = im.convert('RGB')
    grayscale = out / 'grayscale.png'
    ImageOps.grayscale(source).save(grayscale)
    box = [source.width // 4, source.height // 4, 3 * source.width // 4, 3 * source.height // 4]
    detail = out / 'detail.png'
    source.crop(box).save(detail)
    tiles, view_hashes = comparison_tiles(root, f, rec)
    comparison = out / 'source_vs_current.png'
    comparison_image(tiles).save(comparison)
    if primary.suffix.lower() == '.pdf':
        pdf = primary
    else:
        pdf = out / 'print_size.pdf'
        pdf.write_bytes(print_pdf_bytes(root, f, rec))
    pdf_preview = out / 'pdf_page.png'
    with fitz.open(pdf) as doc:
        doc[0].get_pixmap(dpi=144, alpha=False).save(pdf_preview)
    relative = lambda p: p.relative_to(root).as_posix()
    views = [{'kind': k, 'path': relative(p), 'sha256': sha(p), 'reviewed': False,
              'tool_ref': '', 'observation': ''} for k, p in (
                  ('final', preview), ('grayscale', grayscale), ('comparison', comparison),
                  ('pdf_page', pdf_preview), ('detail', detail))]
    inputs = current_files(root, f, rec, runtime)
    from workspace_resources import dependencies
    views[2].update(source_hashes=inputs, final_sha256=sha(preview), source_views=view_hashes)
    views[3].update(pdf_path=relative(pdf), pdf_sha256=sha(pdf), page_number=1, dpi=144)
    views[4]['crop_box'] = box
    value = {'status': 'REVIEW_REQUIRED', 'contract_sha256': contract_digest(f, rec),
             'resource_dependencies': dependencies(root,runtime,'media'),
             'inputs': inputs, 'outputs': {p: sha(safe(root, p)) for p in set(f['outputs'].values()) | {f['statistics_report']}},
             'views': views, 'dimensions': {k: {'status': 'REVIEW_REQUIRED', 'observation': ''} for k in (
                 'scientific_validity', 'source_fidelity', 'print_readability')},
             'resolution_review': {'reviewed': False, 'observation': '', 'source_pixel_basis': '',
                                   'target_width_mm': rec['target_width_mm'], 'preview_pixels': list(source.size)}}
    write_json(qp, value)
    return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-root', type=Path, default=Path('.'))
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--figure-id', required=True)
    p.add_argument('--runtime', choices=['codex', 'claude'], required=True)
    p.add_argument('--interpreter')
    p.add_argument('--allow-demo', action='store_true')
    p.add_argument('--prepare-qa', action='store_true')
    p.add_argument('--timeout', type=int, default=600)
    p.add_argument('arguments', nargs=argparse.REMAINDER)
    a = p.parse_args()
    if a.prepare_qa:
        result = prepare_qa(a.project_root, a.plan, a.figure_id, a.runtime)
    else:
        arguments = a.arguments[1:] if a.arguments[:1] == ['--'] else a.arguments
        result = execute(a.project_root, a.plan, a.figure_id, a.runtime, arguments,
                         a.interpreter, a.allow_demo, a.timeout)
    print(json.dumps({'status': result['status'], 'failures': result.get('failures', [])}, ensure_ascii=False))
    raise SystemExit(1 if result.get('failures') else 0)


if __name__ == '__main__':
    main()
