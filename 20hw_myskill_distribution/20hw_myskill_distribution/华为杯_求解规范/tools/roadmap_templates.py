"""First-chapter roadmap template selection; receipts never prove visual review."""
from __future__ import annotations

if __name__ == '__main__':
    import sys
    sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

from filesystem_paths import native_path
from workspace_context import bounded, resource_path, shared_context

SIDES = {'codex': '.agents', 'claude': '.claude'}


def load(path):
    return json.loads(native_path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(native_path(path).read_bytes()).hexdigest()


def meaningful(value):
    return isinstance(value, str) and len(value.strip()) >= 6 and not any(
        word in value.lower() for word in ('待填写', 'todo', 'pending'))


def tool_reference(value):
    return isinstance(value, str) and bool(value.strip())


def is_roadmap(diagram):
    return (diagram.get('kind') == 'flowchart' and diagram.get('problem_id') is None
            and diagram.get('placement') == 'body')


def contract_digest(diagram):
    # Status and QA change during rendering; scientific/layout changes need review.
    keys = ('diagram_id', 'problem_id', 'kind', 'placement', 'scientific_question',
            'backend', 'backend_reason', 'source', 'dependencies', 'outputs',
            'target_width_mm', 'sources', 'panels', 'connections', 'paper')
    payload = {key: diagram.get(key) for key in keys}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode('utf8')).hexdigest()


def catalog(root, runtime):
    prefix = f'{SIDES[runtime]}/skills/sci-box-main/sci-box-main/skills/scibox-diagram'
    raw = prefix + '/assets/catalog.json'
    file = resource_path(root, raw, runtime)
    data = load(file)
    entries = data['templates']
    ids = [entry['template_id'] for entry in entries]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError('模板目录为空或ID重复')
    directories = {p.name for p in native_path(file).parent.iterdir()
                   if p.is_dir() and (p / 'example.json').is_file()}
    if set(ids) != directories:
        raise ValueError('catalog 与 assets 模板目录不一致，须先维护完整目录')
    for entry in entries:
        tid = entry['template_id']
        if not isinstance(tid, str) or PurePosixPath(tid).name != tid or '\\' in tid:
            raise ValueError('无效模板ID')
        for key, suffix in (('preview', 'preview.png'), ('example', 'example.json')):
            if entry['paths'][key] != f'assets/{tid}/{suffix}':
                raise ValueError('模板预览或内容源不属于对应 assets 目录')
    return prefix, {'path': raw, 'sha256': sha(file)}, entries


def source_assets(root, runtime, prefix, entry):
    required = {entry['paths'][key] for key in ('preview', 'example', 'entry', 'documentation')}
    required.update(entry.get('file_sha256', {}))
    records = []
    for raw in sorted(required):
        p = PurePosixPath(raw)
        if p.is_absolute() or '..' in p.parts or '\\' in raw:
            raise ValueError('模板资产路径越界')
        full = prefix + '/' + raw
        records.append({'path': full, 'sha256': sha(resource_path(root, full, runtime))})
    return records


def prepare(root, runtime, diagram):
    if not is_roadmap(diagram):
        raise ValueError('仅为正文总体路线图准备模板选型记录')
    prefix, stamp, entries = catalog(root, runtime)
    gallery = []
    for entry in entries:
        raw = prefix + '/' + entry['paths']['preview']
        gallery.append({'template_id': entry['template_id'], 'preview_path': raw,
                        'preview_sha256': sha(resource_path(root, raw, runtime)),
                        'reviewed': False, 'observation': '', 'tool_ref': ''})
    return {'schema_version': '1.0', 'runtime': runtime, 'diagram_id': diagram['diagram_id'],
            'diagram_contract_sha256': contract_digest(diagram), 'catalog': stamp,
            'gallery': gallery, 'candidates': [], 'selected_template_id': '',
            'source_assets': [], 'adaptation': {'rationale': '', 'preserved_style': '',
                'changes': '', 'semantic_mapping': []}, 'status': 'pending'}


def audit(root, runtime, diagram, stage, qa=None):
    if not is_roadmap(diagram):
        return []
    checks = []

    def add(code, ok, **details):
        checks.append({'code': 'roadmap_template_' + code, 'ok': bool(ok), **details})

    try:
        raw = diagram.get('template_selection_path')
        add('record_required', isinstance(raw, str) and bool(raw.strip()))
        if not raw:
            return checks
        record = load(bounded(root, raw))
        prefix, stamp, entries = catalog(root, runtime)
        by_id = {entry['template_id']: entry for entry in entries}
        add('identity', record.get('schema_version') == '1.0' and record.get('runtime') == runtime
            and record.get('diagram_id') == diagram['diagram_id'])
        add('catalog_current', record.get('catalog') == stamp)
        add('contract_current', record.get('diagram_contract_sha256') == contract_digest(diagram))
        add('selection_reviewed', record.get('status') == 'reviewed')
        gallery = record.get('gallery', [])
        ids = [item['template_id'] for item in gallery]
        add('full_gallery', len(ids) == len(set(ids)) and set(ids) == set(by_id))
        for item in gallery:
            entry = by_id.get(item['template_id'])
            expected = prefix + '/' + entry['paths']['preview'] if entry else None
            add('preview_' + item['template_id'], expected is not None
                and item.get('preview_path') == expected
                and item.get('preview_sha256') == sha(resource_path(root, expected, runtime))
                and item.get('reviewed') is True and meaningful(item.get('observation'))
                and tool_reference(item.get('tool_ref')))
        candidates = record.get('candidates', [])
        candidate_ids = [item['template_id'] for item in candidates]
        add('candidate_comparison', len(candidates) >= 2 and len(set(candidate_ids)) == len(candidate_ids)
            and set(candidate_ids) <= set(by_id) and all(meaningful(item.get('fit'))
                and meaningful(item.get('decision')) for item in candidates))
        selected = record.get('selected_template_id')
        add('selected_from_assets', selected in by_id and selected in candidate_ids)
        if selected in by_id:
            add('selected_sources_current', record.get('source_assets') ==
                source_assets(root, runtime, prefix, by_id[selected]))
            preview = prefix + '/' + by_id[selected]['paths']['preview']
            add('selected_preview_in_references', any(r.get('path') == preview
                for r in diagram.get('references', [])))
        adaptation = record.get('adaptation', {})
        add('adaptation_reasoned', all(meaningful(adaptation.get(key))
            for key in ('rationale', 'preserved_style', 'changes')))
        mapping = adaptation.get('semantic_mapping', [])
        mapped = [item['panel_id'] for item in mapping]
        add('real_panel_mapping', bool(mapped) and len(set(mapped)) == len(mapped)
            and set(mapped) == {p['panel_id'] for p in diagram.get('panels', [])}
            and all(meaningful(item.get('template_slot')) and meaningful(item.get('adaptation'))
                    for item in mapping))
        if stage != 'plan' or diagram.get('status') == 'qa_pass':
            qa = qa or {}
            review = qa.get('template_adaptation_review', {})
            add('adaptation_visual_review', review.get('status') == 'pass'
                and review.get('selection_sha256') == sha(bounded(root, raw))
                and all(meaningful(review.get(key)) for key in
                    ('style_observation', 'truthfulness_observation', 'readability_observation'))
                and tool_reference(review.get('tool_ref')))
            # Existing workflow additionally re-renders views and audits the actual paper PDF.
            add('review_views', all(any(v.get('kind') == kind and v.get('reviewed') is True
                and meaningful(v.get('observation')) and bool(v.get('tool_ref'))
                for v in qa.get('views', [])) for kind in ('overall', 'pdf_size')))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        add('record_valid', False, error=f'{type(exc).__name__}: {exc}')
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=Path('.'))
    parser.add_argument('--runtime', choices=SIDES, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--diagram-id', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--template-id', help='Populate asset receipts only; never selects or approves for you')
    args = parser.parse_args()
    root = args.project_root.resolve()
    diagrams = load(bounded(root, str(args.plan.with_suffix('.diagrams.json'))))['diagrams']
    matches = [d for d in diagrams if d['diagram_id'] == args.diagram_id]
    if len(matches) != 1:
        raise ValueError('须先登记唯一的总体路线图计划')
    record = prepare(root, args.runtime, matches[0])
    if args.template_id:
        prefix, _, entries = catalog(root, args.runtime)
        entry = next((e for e in entries if e['template_id'] == args.template_id), None)
        if entry is None:
            raise ValueError('指定模板不在当前运行时目录内')
        record['selected_template_id'] = args.template_id
        record['source_assets'] = source_assets(root, args.runtime, prefix, entry)
    context = shared_context(root, args.runtime)
    output = context.write_path(args.output) if context else bounded(root, args.output)
    native_path(output).parent.mkdir(parents=True, exist_ok=True)
    with native_path(output).open('x', encoding='utf8') as stream:
        stream.write(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': 'PENDING', 'output': str(output), 'templates': len(record['gallery']),
                      'assurance': '仅准备版本关联；须实际浏览、比较、适配和看图，禁止自动填写通过。'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
