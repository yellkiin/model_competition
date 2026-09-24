#!/usr/bin/env python3
"""Inspect physical PDF glyphs, destinations and links; unknowns fail closed.

This supplements scientific/asset/visual review. A caption measurement in a TeX
log cannot prove a line fits the final PDF: we also inspect every rendered glyph
and require the expected source caption and a current destination in the PDF.
"""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from pathlib import Path as _WorkflowPath
    _workflow_sys.path.insert(0, str(_WorkflowPath(__file__).resolve().parents[2] / "华为杯_求解规范/tools"))
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)

import argparse
import hashlib
import json
import re
from pathlib import Path
import statistics

import pymupdf as fitz
from paper_contract import HEADINGS, audit_structure, commands, expand_fragment, strip_comments
from first_chapters_pdf import chapter_ranges, page_limits, symbol_measurements, prepare_review
from restatement_prose import measure_prose

PT_TO_BP = 72 / 72.27


def norm(text: str) -> str:
    return re.sub(r'\s+', '', text)


def plain_tex(text: str) -> str:
    """Simple searchable text only; mathematical caption proofs use the glyph box.

    Do not silently equate an unknown macro with its name. Return an empty value
    for formulas that require a separate source/render visual comparison.
    """
    if '$' in text or re.search(r'\\[([]', text):
        return ''
    text = re.sub(r'\\([%&#_{}])', r'\1', text)
    if '\\' in text:
        return ''
    return norm(text.replace('~', ' '))


def glyphs(page) -> list[dict]:
    output = []
    for block in page.get_text('rawdict')['blocks']:
        for line in block.get('lines', []):
            for span in line['spans']:
                for char in span['chars']:
                    if not char['c'].isspace():
                        output.append({**char, 'size': span['size'], 'font': span['font'],
                                       'flags': span['flags'], 'dir': line['dir']})
    return output


def rectangle(chars) -> list[float]:
    if not chars:
        return []
    return [min(c['bbox'][0] for c in chars), min(c['bbox'][1] for c in chars),
            max(c['bbox'][2] for c in chars), max(c['bbox'][3] for c in chars)]


def find_glyph_text(chars, text: str) -> list[list[dict]]:
    raw = ''.join(c['c'] for c in chars)
    text = norm(text)
    return [chars[m.start():m.end()] for m in re.finditer(re.escape(text), raw)] if text else []


def destination(doc, names: dict, name: str) -> tuple[int, float, float] | None:
    item = names.get(name)
    if not item or not isinstance(item.get('page'), int) or not 0 <= item['page'] < len(doc):
        return None
    point = item.get('to')
    if point is None:
        return None
    # MuPDF's named XYZ destinations are in PDF user space (bottom-left).
    point = fitz.Point(point) * doc[item['page']].transformation_matrix
    return item['page'], float(point.x), float(point.y)


def is_bold(char, traces) -> bool:
    if char['flags'] & 16 or re.search(r'bold|semibold|demi', char['font'], re.I):
        return True
    # XeCJK's AutoFakeBold renders a fill and a matching stroked glyph. Its font
    # name/flags remain SimSun, so testing font names alone misses real bold.
    return any(t['type'] == 1 and (t.get('linewidth') or 0) > 0 and
               any(c[0] == ord(char['c']) and abs(c[2][0] - char['origin'][0]) < .15 and
                   abs(c[2][1] - char['origin'][1]) < .15 for c in t['chars']) for t in traces)


def expected_headings(manifest: dict, root: Path) -> tuple[list[dict], list[dict]]:
    headings, captions = [], []
    counts = [0] * 5
    for chapter in manifest['chapters']:
        text = expand_fragment(root, root / chapter['tex_path'])
        if chapter['role'] == 'references':
            headings.append({'level': 1, 'title': '参考文献', 'number': str(chapter['order']),
                             'anchor': 'section.' + str(chapter['order']), 'role': 'references'})
            continue
        for cmd in commands(text, HEADINGS):
            level = HEADINGS.index(cmd.name) + 1
            counts[level - 1] += 1
            counts[level:] = [0] * (5 - level)
            number = '.'.join(map(str, counts[:level]))
            headings.append({'level': level, 'title': cmd.argument, 'number': number,
                             'anchor': cmd.name + '.' + number, 'role': chapter['role']})
        # Match formal float environments, not subfloat/panel headings.
        for env in re.finditer(r'\\begin\{(figure\*?|table\*?|longtable)\}(.*?)\\end\{\1\}', text, re.S):
            kind = 'figure' if env[1].startswith('figure') else 'table'
            for cmd in commands(env[2], ('caption',)):
                labels = commands(env[2], ('label',))
                captions.append({'kind': kind, 'title': cmd.argument, 'plain': plain_tex(cmd.argument),
                                 'label': labels[0].argument if len(labels) == 1 else None,
                                 'chapter_id': chapter['chapter_id']})
    q = sum(c['role'] == 'problem' for c in manifest['chapters'])
    headings.append({'level': 1, 'title': '附录', 'number': str(q + 6),
                     'anchor': f'section.{q + 6}', 'role': 'appendix'})
    return headings, captions


def audit_layout(pdf: Path, source: Path, manifest_path: Path, targets: dict | None = None) -> dict:
    pdf, source, manifest_path = pdf.resolve(), source.resolve(), manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    if targets is None:
        targets = json.loads((Path(__file__).resolve().parents[1] / 'page_targets.json').read_text(encoding='utf-8-sig'))
    failures, checks, warnings = [], [], []

    def check(code, ok, **evidence):
        entry = {'code': code, 'ok': bool(ok), **evidence}
        checks.append(entry)
        if not ok:
            (warnings if evidence.get('severity') == 'warning' else failures).append(entry)

    structure = audit_structure(manifest, manifest_path.parent)
    check('source_structure', structure['status'] == 'PASS', failures=structure['failures'])
    try:
        wanted, source_captions = expected_headings(manifest, manifest_path.parent)
    except (ValueError, KeyError, OSError) as exc:
        check('source_objects_readable', False, reason=str(exc))
        return {'status': 'FAIL', 'failures': failures, 'checks': checks}
    doc = fitz.open(pdf)
    names = doc.resolve_names()
    page_chars = [glyphs(p) for p in doc]
    traces = [p.get_texttrace() for p in doc]
    log_path = source.with_suffix('.log')
    log = log_path.read_text(encoding='utf-8', errors='replace') if log_path.is_file() else ''
    check('xelatex_log_and_shell_escape', bool(log) and 'XeTeX' in log and r'\write18 enabled.' in log)
    log_errors = re.findall(r'(?m)^!.*|^Missing character:.*|^.*(?:Citation|Reference).*undefined.*|^.*There were undefined.*', log)
    check('compilation_no_fatal_missing_glyph_or_reference', not log_errors, errors=log_errors)
    rerun = re.findall(r'(?im)^.*(?:Rerun to get|Label\(s\) may have changed|Please rerun|Table widths have changed).*$', log)
    check('compilation_references_and_pagination_stable', not rerun, warnings=rerun)
    overflows = [float(v) for v in re.findall(r'Overfull \\hbox \(([0-9.]+)pt too wide\)', log)]
    check('no_unacceptable_horizontal_overflow', all(v <= .5 for v in overflows), overfull_pt=overflows)
    rendered_headings = []
    for h in wanted:
        dest = destination(doc, names, h['anchor'])
        check('heading_destination:' + h['anchor'], dest is not None)
        if dest is None:
            continue
        pno, x, y = dest
        full = h['number'] + h['title']
        matches = find_glyph_text(page_chars[pno], full)
        matches = [cs for cs in matches if abs(min(c['bbox'][1] for c in cs) - y) < 35]
        check('heading_visible:' + h['anchor'], len(matches) == 1, physical_page=pno + 1)
        if len(matches) != 1:
            continue
        cs = matches[0]
        box = rectangle(cs)
        check('heading_bold:' + h['anchor'], all(is_bold(c, traces[pno]) for c in cs),
              physical_page=pno + 1, bbox=box)
        if h['level'] == 1 and h['number'] not in ('2', '3'):
            # Any text or previous-chapter float above the heading is a failure.
            before = [c for c in page_chars[pno] if c['bbox'][3] < box[1] - 1]
            graphics_before = any(r['rect'].y1 < box[1] - 1 and r['rect'].get_area() > 4 for r in doc[pno].get_drawings())
            images_before = any(b.get('type') == 1 and b['bbox'][1] < box[1] for b in doc[pno].get_text('dict')['blocks'])
            check('chapter_new_page:' + h['number'], not before and not graphics_before and not images_before
                  and 55 <= box[1] <= 100, physical_page=pno + 1, bbox=box)
        rendered_headings.append({**h, 'physical_page': pno + 1, 'bbox': box})
        if h['level'] == 1 and h['number'] in ('2', '3'):
            after = [c for c in page_chars[pno] if c['bbox'][1] > box[3] and c['bbox'][1] < doc[pno].rect.height - 72]
            check('chapter_heading_not_orphan:' + h['number'], len(after) >= 12, physical_page=pno + 1)

    level1 = [h for h in rendered_headings if h['level'] == 1]
    expected_level1 = [h['number'] + h['title'] for h in wanted if h['level'] == 1]
    toc = [entry for entry in doc.get_toc(False) if entry[0] == 1 and norm(entry[1]) != '目录']
    check('pdf_outline_continuous_chapters', [norm(e[1]) for e in toc] == expected_level1,
          actual=[e[1] for e in toc], expected=expected_level1)
    required_new = [h for h in level1 if h['number'] not in ('2', '3')]
    check('chapter_starts_distinct_pages_except_two_three', len({h['physical_page'] for h in required_new}) == len(required_new))
    # Verify printed TOC entries and their annotations as well as the outline.
    # A correct PDF bookmark alone does not prove the visible TOC page is right.
    if level1:
        front_pages = range(level1[0]['physical_page'] - 1)
        for h in rendered_headings:
            if h['level'] > 3:
                continue
            hits = [(p, cs) for p in front_pages for cs in
                    find_glyph_text(page_chars[p], h['number'] + h['title'])]
            check('toc_visible:' + h['anchor'], len(hits) == 1)
            if len(hits) != 1:
                continue
            p, cs = hits[0]
            y = cs[-1]['origin'][1]
            page_digits = ''.join(c['c'] for c in page_chars[p]
                                  if abs(c['origin'][1] - y) < 1 and c['bbox'][0] > doc[p].rect.width - 115
                                  and c['c'].isdigit())
            footer = ''.join(c['c'] for c in page_chars[h['physical_page'] - 1]
                             if c['bbox'][1] > doc[h['physical_page'] - 1].rect.height - 65
                             and abs(c['origin'][0] - doc[h['physical_page'] - 1].rect.width / 2) < 25
                             and c['c'].isdigit())
            check('toc_page_number:' + h['anchor'], bool(footer) and page_digits == footer,
                  printed_toc=page_digits, actual_footer=footer)
            links = [link for link in doc[p].get_links() if link.get('nameddest') == h['anchor']
                     and abs(fitz.Rect(link['from']).y1 - y) < 8]
            check('toc_click_target:' + h['anchor'], bool(links) and
                  all(link.get('page') == h['physical_page'] - 1 for link in links))
    ranges, range_checks = chapter_ranges(doc, level1, names, page_chars, destination)
    for c in range_checks + page_limits(ranges, targets):
        check(c['code'], c['ok'], **{k:v for k,v in c.items() if k not in ('code','ok')})
    symbols = symbol_measurements(doc, next((r for r in ranges if r['number'] == '3'), None), page_chars)
    for c in symbols['checks']:
        check(c['code'], c['ok'], **{k:v for k,v in c.items() if k not in ('code','ok')})

    # The abstract is deliberately absent from the TOC, but its heading must be
    # bold and physically present exactly once in the front matter.
    front_limit = level1[0]['physical_page'] - 1 if level1 else min(2, len(doc))
    abstract_hits = [(p, cs) for p in range(front_limit)
                     for cs in find_glyph_text(page_chars[p], '摘要：')]
    check('abstract_heading_bold', len(abstract_hits) == 1 and
          all(is_bold(c, traces[p]) for p, cs in abstract_hits for c in cs))

    measurements = []
    path = source.with_suffix('.gmcmlayout')
    check('physical_caption_measurements_present', path.is_file())
    if path.is_file():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            parts = line.split('|')
            if len(parts) != 9 or parts[0] != 'caption':
                check('caption_measurement_valid', False, record=line)
                continue
            try:
                dimension = lambda s: float(s.removesuffix('pt')) * PT_TO_BP
                measurements.append({'id': int(parts[1]), 'kind': parts[2], 'number': parts[3],
                                     'width': dimension(parts[4]), 'limit': dimension(parts[5]),
                                     'font_size': float(parts[6]) * PT_TO_BP,
                                     'height': dimension(parts[7]), 'depth': dimension(parts[8])})
            except ValueError:
                check('caption_measurement_valid', False, record=line)
    # The generation record order may differ from shipout order; caption IDs
    # resolve directly to PDF coordinates and never assume a particular page.
    caption_records = []
    body_start = level1[0]['physical_page'] if level1 else 1
    ref_page = next((h['physical_page'] for h in level1 if h['role'] == 'references'), len(doc) + 1)
    used_sources = set()
    for m in measurements:
        # Longtable heads are boxed even when the continuation isn't shipped.
        # Inspect every actual symbol fragment independently above; it is one table.
        if m['kind'] == 'symboltable':
            continue
        dest = destination(doc, names, f"gmcm.caption.{m['id']}")
        check(f"caption_destination:{m['id']}", dest is not None)
        if dest is None:
            continue
        p, x, baseline = dest
        if not body_start <= p + 1 < ref_page:
            continue
        clip = fitz.Rect(x - .5, baseline - m['height'] - 2, x + m['width'] + .5, baseline + m['depth'] + 2)
        cs = [c for c in page_chars[p] if clip.contains(fitz.Point(c['origin']))]
        visible = ''.join(c['c'] for c in cs)
        label = ('图' if m['kind'] == 'figure' else '表') + m['number']
        candidates = [i for i, s in enumerate(source_captions) if i not in used_sources and s['kind'] == m['kind']
                      and (not s['plain'] or visible == label + s['plain'])]
        # Unsupported math captions must still have one unambiguous same-kind
        # source after all ordinary titles match, and need manual visual review.
        check(f"caption_source_match:{m['id']}", len(candidates) == 1, actual=visible)
        si = candidates[0] if len(candidates) == 1 else None
        if si is not None:
            used_sources.add(si)
        box = rectangle(cs)
        baselines = sorted({round(c['origin'][1], 1) for c in cs if c['size'] >= 11.8})
        check(f"caption_one_physical_line:{m['id']}", bool(cs) and len(baselines) == 1
              and m['height'] + m['depth'] <= 18, baselines=baselines, bbox=box)
        check(f"caption_prescribed_font:{m['id']}", bool(cs) and all(
            11.85 <= c['size'] <= 12.1 or (c['size'] < 11.85 and (c['flags'] & 1)) for c in cs),
            sizes=sorted({round(c['size'], 3) for c in cs}))
        margin = 25 / 25.4 * 72
        check(f"caption_within_body_width:{m['id']}", bool(box) and m['width'] <= m['limit'] + .2
              and box[0] >= margin - .5 and box[2] <= doc[p].rect.width - margin + .5, bbox=box)
        caption_records.append({**m, 'physical_page': p + 1, 'bbox': box, 'text': visible,
                                'label': source_captions[si]['label'] if si is not None else None,
                                'source_title': source_captions[si]['title'] if si is not None else None})
    check('all_body_captions_inspected', len(used_sources) == len(source_captions)
          and len(caption_records) == len(source_captions), expected=len(source_captions), actual=len(caption_records))

    prose = measure_prose(doc, source, page_chars, rendered_headings, ranges,
                          caption_records, destination, targets)
    for c in prose['checks']:
        check(c['code'], c['ok'], **{k:v for k,v in c.items() if k not in ('code','ok')})
    evaluation_prose = measure_prose(doc, source, page_chars, rendered_headings, ranges,
                                    caption_records, destination, targets, scope='evaluation')
    for c in evaluation_prose['checks']:
        check(c['code'], c['ok'], **{k:v for k,v in c.items() if k not in ('code','ok')})
    from evaluation_contract import inspect_evaluation
    evaluation_source = {}
    for chapter in manifest['chapters']:
        if chapter['role'] == 'evaluation':
            evaluation_source = inspect_evaluation(expand_fragment(manifest_path.parent, manifest_path.parent / chapter['tex_path']))
    # Changing earlier evidence invalidates the evaluation's semantic review.
    evaluation_source['chapter_source_bindings'] = {
        c['chapter_id']: hashlib.sha256(expand_fragment(manifest_path.parent, manifest_path.parent / c['tex_path']).encode('utf8')).hexdigest()
        for c in manifest['chapters']}

    # Inspect actual citation links, glyph size and baseline relative to body
    # text; a source \cite or a small [1] alone does not prove an upper-right link.
    citations = []
    for p in range(body_start - 1, ref_page - 1):
        for link in doc[p].get_links():
            anchor = link.get('nameddest', '')
            if not anchor.startswith('cite.'):
                continue
            box = fitz.Rect(link['from'])
            cs = [c for c in page_chars[p] if box.contains(fitz.Point(c['origin'][0], c['origin'][1] - 1))]
            neighbor = [c for c in page_chars[p] if c['size'] >= 11.85 and
                        abs(c['origin'][1] - (cs[0]['origin'][1] if cs else box.y1)) < 12 and
                        min(abs(c['bbox'][2] - box.x0), abs(c['bbox'][0] - box.x1)) < 40]
            base = statistics.median(c['origin'][1] for c in neighbor) if neighbor else None
            superscript = bool(cs) and base is not None and all(c['size'] < 10 and base - c['origin'][1] >= 2 for c in cs)
            target = destination(doc, names, anchor)
            check('citation_superscript:' + anchor, superscript, physical_page=p + 1)
            check('citation_click_target:' + anchor, target is not None and target[0] + 1 >= ref_page)
            citations.append({'key': anchor[5:], 'physical_page': p + 1, 'bbox': list(box),
                              'superscript': superscript, 'destination': list(target) if target else None})
    report = {'status': 'FAIL' if failures else 'PASS', 'checks': checks, 'failures': failures, 'warnings': warnings,
              'pdf': str(pdf), 'pdf_sha256': hashlib.sha256(pdf.read_bytes()).hexdigest(),
              'headings': rendered_headings, 'chapter_ranges': ranges, 'captions': caption_records,
              'symbols': symbols, 'restatement_prose': prose,
              'evaluation_prose': evaluation_prose, 'evaluation_source': evaluation_source,
              'first_chapters_source': structure.get('first_chapters'),
              'citations': citations,
              'limitations': ['排版检查不证明科学内容、文献真实性、图形质量或支撑材料事实链；这些门禁分别执行。',
                              '含数学公式的标题仍须实际查看源码与成图；缺少可靠文字映射时不得宣称语义一致。']}
    doc.close()
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdf', type=Path, required=True)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--manifest', type=Path, required=True)
    ap.add_argument('--report', type=Path, required=True)
    ap.add_argument('--prepare-first-three-review', type=Path,
                    help='渲染前三章、第四章交界及评价章全部页面，生成待审记录；不自动授予通过')
    args = ap.parse_args()
    report = audit_layout(args.pdf, args.source, args.manifest)
    if args.prepare_first_three_review:
        prepare_review(args.pdf, report, args.prepare_first_three_review)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'failures': report['failures'], 'report': str(args.report)}, ensure_ascii=False))
    raise SystemExit(report['status'] != 'PASS')


if __name__ == '__main__':
    main()
