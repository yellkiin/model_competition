"""Same-runtime drawing skill discovery and versioned, unapproved capability receipts."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

from build_academic_figure_asset_index import sha, digest, safe, write_json
from workspace_context import shared_context, native_path

PROVIDERS = ('academic-figure-skill', 'modelviz-skill')
SIDES = {'codex': '.agents', 'claude': '.claude'}
DEFAULT_PREFLIGHT = '求解/绘图能力预检.json'
SKIP = {'__pycache__', '.git', '.venv', 'node_modules', '.pytest_cache'}


def template_root(root, runtime):
    context = shared_context(root, runtime)
    return context.template_root if context else Path(root).resolve()


def discover(template, runtime, identity, explicit=None):
    if runtime not in SIDES or identity not in PROVIDERS:
        raise ValueError('Explicit runtime and drawing skill identity required')
    base = Path(template).resolve() / SIDES[runtime] / 'skills'
    matches = []
    for entry in native_path(base).rglob('SKILL.md'):
        if set(entry.parts) & SKIP:
            continue
        entry = Path(str(entry).removeprefix('\\\\?\\'))
        text = entry.read_text(encoding='utf-8-sig')
        front = text.split('---', 2)
        match = re.search(r'^name:\s*[\"\']?([^\r\n\"\']+)', front[1], re.M) if len(front) == 3 else None
        if match and match[1].strip() == identity:
            resolved = entry.resolve()
            if not resolved.is_relative_to(base.resolve()):
                raise ValueError('Cross-runtime or linked skill resource: ' + str(entry))
            matches.append(resolved.parent)
    if len(matches) != 1:
        raise ValueError(f'{runtime}:{identity}: expected one same-runtime SKILL.md, found {len(matches)}: {matches}')
    if explicit and (Path(template) / explicit).resolve() != matches[0]:
        raise ValueError('Explicit skill path differs from same-runtime identity: ' + str(explicit))
    return matches[0]


def package_files(skill):
    base=native_path(skill); files={}
    for p in sorted(base.rglob('*')):
        if set(p.parts) & SKIP or p.suffix in {'.pyc','.pyo'}:
            continue
        if p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()) or not p.resolve().is_relative_to(base.resolve()):
            raise ValueError('Skill package contains linked/external resource: '+str(p))
        if p.is_file(): files[p.relative_to(base).as_posix()]=sha(p)
    return files


def catalog(skill):
    import yaml
    rows = yaml.safe_load((skill / 'docs/template_catalog.yaml').read_text(encoding='utf-8-sig'))['templates']
    if not rows or len({x['id'] for x in rows}) != len(rows):
        raise ValueError('Empty catalog or ambiguous template IDs')
    for row in rows:
        for key in ('code_path', 'preview'):
            safe(skill, row[key])  # no cwd-relative references or traversal
    return rows


def blank_review():
    return {'reviewed': False, 'tool_ref': '', 'observation': ''}


def prepare(root, runtime, output=DEFAULT_PREFLIGHT):
    root = Path(root).resolve()
    out = safe(root, output)
    if out.exists():
        raise ValueError('Preserve existing preflight; choose a new output path for changed resources')
    template = template_root(root, runtime)
    records = []
    for identity in PROVIDERS:
        skill = discover(template, runtime, identity)
        files = package_files(skill)
        record = {'source_skill': identity, 'skill_root': skill.relative_to(template).as_posix(),
                  'resource_digest': digest(files), 'capability_review': blank_review(),
                  'capabilities': '', 'data_structures': '', 'limitations': '',
                  'gallery_review_path': '', 'previews': []}
        if identity == 'modelviz-skill':
            rows = catalog(skill)
            overview = out.parent / (out.stem + '_modelviz')
            overview.mkdir(parents=True, exist_ok=False)
            from prepare_academic_figure_qa import raster
            from PIL import Image, ImageDraw
            tiles = []
            for row in rows:
                raw = row['preview']; path = safe(skill, raw)
                item = {'template_id': row['id'], 'path': raw, 'sha256': files.get(raw, ''),
                        'error': '', 'views': [], 'unavailable_reason': ''}
                try:
                    for page, im in enumerate(raster(path), 1):
                        preview = overview / f'{row["id"]}_{page}.png'
                        im.save(preview)
                        item['views'].append({'path': preview.relative_to(root).as_posix(),
                                              'sha256': sha(preview), 'page': page, **blank_review()})
                        tiles.append((row['id'] + f' / {page}', im.copy()))
                except Exception as exc:
                    item['error'] = str(exc)
                record['previews'].append(item)
            for start in range(0, len(tiles), 12):
                sheet = Image.new('RGB', (1600, 1200), 'white'); draw = ImageDraw.Draw(sheet)
                for i, (label, im) in enumerate(tiles[start:start+12]):
                    x, y = i % 4 * 400, i // 4 * 400
                    im.thumbnail((390, 350)); sheet.paste(im, (x, y+35)); draw.text((x+4, y+5), label, fill='black')
                sheet.save(overview / f'overview_{start//12+1:02d}.png')
            write_json(overview / 'catalog.json', rows)
            (overview / 'capabilities.md').write_text('\n'.join(
                f"- {r['id']} | {r['category']} | {r['chart_type']} | {r['description']} | 限制: {r.get('negative_keywords', [])}"
                for r in rows), encoding='utf8')
        records.append(record)
    value = {'schema_version': '1.0', 'runtime': runtime, 'providers': records}
    write_json(out, value)
    return value


def review_ok(value):
    return value.get('reviewed') is True and all(isinstance(value.get(k), str) and len(value[k].strip()) >= 8
                                                for k in ('tool_ref', 'observation'))


def audit_preflight(root, runtime, raw):
    from audit_academic_figure_assets import audit_gallery
    from build_academic_figure_asset_index import build_index
    errors = []
    try:
        value = json.loads(safe(root, raw).read_text(encoding='utf-8-sig'))
        from jsonschema import Draft202012Validator
        schema = json.loads((Path(__file__).parent.parent / 'drawing_preflight.schema.json').read_text(encoding='utf8'))
        errors += ['preflight_schema:' + e.message for e in Draft202012Validator(schema).iter_errors(value)]
        if errors:
            return errors
        if value['runtime'] != runtime or {r['source_skill'] for r in value['providers']} != set(PROVIDERS) or len(value['providers']) != 2:
            errors.append('preflight_runtime_or_providers')
        template = template_root(root, runtime)
        for r in value['providers']:
            skill = discover(template, runtime, r['source_skill'], r['skill_root'])
            if r['resource_digest'] != digest(package_files(skill)):
                errors.append(r['source_skill'] + ':preflight_resource_changed')
            if not review_ok(r['capability_review']) or not all(len(r[k].strip()) >= 8 for k in ('capabilities','data_structures','limitations')):
                errors.append(r['source_skill'] + ':capability_review_required')
            if r['source_skill'] == 'academic-figure-skill':
                index = build_index(root, r['skill_root'], runtime=runtime)
                audit_gallery(root, index, r['gallery_review_path'], lambda code, ok, **kw: errors.append(code) if not ok else None)
            else:
                expected = {x['id']: x for x in catalog(skill)}
                if {x['template_id'] for x in r['previews']} != set(expected) or len(r['previews']) != len(expected):
                    errors.append('modelviz:preview_inventory_incomplete')
                from prepare_academic_figure_qa import raster
                from PIL import Image, ImageChops
                for item in r['previews']:
                    row = expected[item['template_id']]; source = safe(skill, row['preview'])
                    if item['path'] != row['preview'] or item['sha256'] != (sha(source) if source.is_file() else ''):
                        errors.append(item['template_id'] + ':preview_changed')
                    try:
                        pages = raster(source)
                    except Exception:
                        if not item['error'] or len(item['unavailable_reason'].strip()) < 12:
                            errors.append(item['template_id'] + ':unavailable_preview_unrecorded')
                        continue
                    if len(pages) != len(item['views']):
                        errors.append(item['template_id'] + ':preview_pages_missing')
                    for number, (page, view) in enumerate(zip(pages, item['views']),1):
                        path = safe(root, view['path'])
                        with Image.open(path) as actual:
                            equal = actual.size == page.size and ImageChops.difference(actual.convert('RGB'), page.convert('RGB')).getbbox() is None
                        if view['page']!=number or not equal or sha(path) != view['sha256'] or not review_ok(view):
                            errors.append(item['template_id'] + ':actual_preview_review_required')
    except (ValueError, OSError, KeyError, TypeError, ImportError) as exc:
        errors.append('preflight_missing_or_invalid:' + str(exc))
    return errors


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-root', type=Path, default=Path('.')); p.add_argument('--runtime', choices=SIDES, required=True)
    p.add_argument('--output', default=DEFAULT_PREFLIGHT); p.add_argument('--audit', action='store_true')
    a = p.parse_args()
    try:
        result = {'failures': audit_preflight(a.project_root, a.runtime, a.output)} if a.audit else prepare(a.project_root, a.runtime, a.output)
        print(json.dumps(result, ensure_ascii=False)); return bool(result.get('failures'))
    except Exception as exc:
        print(json.dumps({'status': 'FAIL', 'error': str(exc)}, ensure_ascii=False)); return 1


if __name__ == '__main__':
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)
    raise SystemExit(main())
