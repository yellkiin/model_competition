"""Check body citation count and actual superscript clusters/links in the PDF.

This gate deliberately separates citation placement from source authenticity:
matching an AUX key or a publisher URL does not prove bibliographic truth.
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
from collections import Counter
import json
from pathlib import Path
import re
import statistics
import sys

from paper_contract import balanced, expand_fragment, strip_comments
from ai_disclosure import AI_KEY


def citation_calls(text: str) -> list[list[str]]:
    """Literal natbib citations, with both optional prenote/postnote arguments."""
    text = strip_comments(text)
    calls = []
    for match in re.finditer(r'\\(cite[a-zA-Z]*)(?![a-zA-Z])\*?\s*', text):
        if match[1] not in {'cite', 'citep'}:
            raise ValueError('统一编号上标引用应使用 cite/citep；发现 '+match[1])
        pos = match.end()
        for _ in range(2):
            if pos < len(text) and text[pos] == '[':
                _, pos = balanced(text, pos, '[', ']')
                while pos < len(text) and text[pos].isspace():
                    pos += 1
        raw, _ = balanced(text, pos)
        keys = list(dict.fromkeys(key.strip() for key in raw.split(',')))
        if not keys or any(not key or re.search(r'[\s\\{}*]', key) for key in keys):
            raise ValueError('引用键必须为字面量且非空：'+raw)
        calls.append(keys)
    return calls


def audit_citation_keys(manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    calls, errors = [], []
    for chapter in manifest['chapters']:
        if chapter['role'] in {'references', 'appendix', 'abstract'}:
            continue
        try:
            text = expand_fragment(manifest_path.parent, manifest_path.parent/chapter['tex_path'])
            calls += [{'chapter_id': chapter['chapter_id'], 'keys': keys} for keys in citation_calls(text)]
        except (ValueError, OSError) as exc:
            errors.append(str(exc))
    keys = list(dict.fromkeys(key for call in calls for key in call['keys']))
    ordinary_keys = [key for key in keys if key != AI_KEY]
    if len(ordinary_keys) < 10:
        errors.append(f'正文须实际引用至少10条不同文献（AI工具披露不计入）；源码目前只有{len(ordinary_keys)}条。摘要、附录和nocite不计数。')
    return {'status': 'FAIL' if errors else 'PASS', 'failures': errors, 'keys': keys, 'ordinary_keys': ordinary_keys, 'calls': calls,
            'scope': 'Literal body citation preflight; actual rendering and source authenticity are separate gates.'}


def audit_source(manifest_path: Path) -> dict:
    from reference_evidence import audit_references
    report = audit_citation_keys(manifest_path)
    evidence = audit_references(manifest_path, report)
    report['reference_evidence'] = evidence
    report['failures'] += evidence['failures']
    report['status'] = 'FAIL' if report['failures'] else 'PASS'
    report['scope'] = 'Body citation keys and current source/metadata/relevance evidence; actual PDF rendering checked separately.'
    return report


def require_source_pass(manifest_path: Path) -> dict:
    report = audit_source(manifest_path)
    if report['status'] != 'PASS':
        raise ValueError('正文文献引用预检未通过：' + '; '.join(report['failures']))
    return report


def expand_numbers(value: str) -> tuple[list[int], set[int]]:
    numbers, visible = [], set()
    # Some TeX font ToUnicode tables map the semicolon glyph to U+037E.
    # It is canonically equivalent to ';' and occupies the same single glyph.
    for token in re.split(r'[,;;]', value):
        parts = re.split(r'[-–−]', token)
        if len(parts) == 1:
            first = int(parts[0]); last = first
        elif len(parts) == 2:
            first, last = map(int, parts)
            if first >= last:
                raise ValueError('文献范围必须递增：'+value)
        else:
            raise ValueError('无法解析的文献编号：'+value)
        if first < 1 or last > 100000:
            raise ValueError('无效文献编号：'+value)
        visible.update((first, last))
        numbers.extend(range(first, last+1))
    if numbers != sorted(set(numbers)):
        raise ValueError('文献编号须递增且不重复：'+value)
    return numbers, visible


def auxiliary_numbers(main: Path) -> dict[str, int]:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'华为杯_求解规范/tools'))
    from bibliography_inputs import auxiliary_inputs
    result = {}
    for path in sorted(auxiliary_inputs(main)):
        text = path.read_text(encoding='utf-8-sig')
        for match in re.finditer(r'\\bibcite\s*', text):
            key, end = balanced(text, match.end())
            while end < len(text) and text[end].isspace():
                end += 1
            raw, _ = balanced(text, end)
            number = balanced(raw, 0)[0] if raw.startswith('{') else raw
            if not number.isdigit() or key in result:
                raise ValueError('无效或重复的bibcite：'+key)
            result[key] = int(number)
    if len(set(result.values())) != len(result):
        raise ValueError('不同文献复用相同编号')
    return result


def audit_pdf(pdf_path: Path, main: Path, manifest_path: Path) -> dict:
    import pymupdf as fitz
    from audit_pdf_layout import destination, glyphs, rectangle
    source = audit_source(manifest_path)
    failures = list(source['failures'])
    clusters = []
    printed = {'status': 'FAIL', 'failures': ['实际书目检查尚未完成'], 'references': []}

    def check(code, ok):
        if not ok:
            failures.append(code)

    try:
        numbers = auxiliary_numbers(main)
        ai_keys = {r['key'] for r in source.get('reference_evidence', {}).get('references', [])
                   if r.get('reference_type') == 'ai_tool'}
        ordinary_keys = [key for key in source['keys'] if key not in ai_keys]
        if ai_keys:
            # The fixed disclosure is generated by the builder and may not be
            # a source-side citation call; it is still part of the printed list.
            missing_ai = ai_keys - set(numbers)
            check('ai_disclosure_has_generated_bibliography_entry', not missing_ai)
        check('bibliography_exactly_body_cited', set(numbers) == (set(source['keys']) | ai_keys))
        q = sum(c['role']=='problem' for c in json.loads(manifest_path.read_text(encoding='utf-8-sig'))['chapters'])
        with fitz.open(pdf_path) as doc:
            names = doc.resolve_names()
            first = destination(doc, names, 'section.1')
            refs = destination(doc, names, 'section.'+str(q+5))
            appendix = destination(doc, names, 'section.'+str(q+6))
            if not first or not refs or not appendix or not first[0] < refs[0] < appendix[0]:
                raise ValueError('缺少或错误的正文/参考文献/附录实际PDF边界')
            for key, number in numbers.items():
                target = destination(doc, names, 'cite.'+key)
                check('bibliography_destination:'+key, target is not None and refs[0] <= target[0] < appendix[0])
                if target:
                    chars = glyphs(doc[target[0]])
                    raw = ''.join(c['c'] for c in chars)
                    matches = [chars[m.start():m.end()] for m in re.finditer(re.escape('['+str(number)+']'), raw)]
                    check('bibliography_visible_number:'+key, any(
                        abs(cs[0]['origin'][1]-target[2]) < 20 for cs in matches))
            from reference_evidence import audit_printed_references
            printed = audit_printed_references(doc, names, numbers, appendix, source['reference_evidence'])
            failures += printed['failures']
            for page_no in range(first[0], refs[0]):
                page = doc[page_no]
                chars = glyphs(page)
                raw = ''.join(c['c'] for c in chars)
                links = [link for link in page.get_links() if link.get('nameddest', '').startswith('cite.')]
                used = Counter()
                for match in re.finditer(r'\[([0-9]+(?:[,;;–−-][0-9]+)*)\]', raw):
                    cs = chars[match.start():match.end()]
                    box = fitz.Rect(rectangle(cs))
                    linked = [(i, link) for i, link in enumerate(links) if box.intersects(fitz.Rect(link['from']))]
                    if not linked:
                        continue
                    ids, visible = expand_numbers(match[1])
                    neighbor = [c for c in chars if c not in cs and c['size'] >= 11.85 and
                        abs(c['origin'][1]-cs[0]['origin'][1]) < 12 and
                        min(abs(c['bbox'][2]-box.x0), abs(c['bbox'][0]-box.x1)) < 40]
                    base = statistics.median(c['origin'][1] for c in neighbor) if neighbor else None
                    superscript = (base is not None and all(c['size'] < 10 and base-c['origin'][1] >= 2 for c in cs)
                                   and max(c['origin'][1] for c in cs)-min(c['origin'][1] for c in cs) < .5)
                    check(f'whole_citation_superscript:p{page_no+1}:{match[0]}', superscript)
                    linked_numbers = set()
                    for i, link in linked:
                        used[i] += 1
                        key = link['nameddest'][5:]
                        link_box = fitz.Rect(link['from'])
                        digits = ''.join(c['c'] for c in cs if c['c'].isdigit() and
                            link_box.contains(fitz.Point((c['bbox'][0]+c['bbox'][2])/2, c['origin'][1]-1)))
                        number = numbers.get(key)
                        check('citation_link_number:'+key, bool(digits) and number == int(digits))
                        linked_numbers.add(number)
                    check(f'citation_visible_endpoints_linked:p{page_no+1}:{match[0]}', linked_numbers == visible)
                    clusters.append({'physical_page': page_no+1, 'text': match[0], 'numbers': ids,
                                     'bbox': list(box), 'superscript': superscript})
                check(f'all_citation_links_have_brackets:p{page_no+1}', set(used) == set(range(len(links))) and
                      all(count == 1 for count in used.values()))
        actual = Counter(tuple(c['numbers']) for c in clusters)
        expected = Counter(tuple(sorted(numbers[k] for k in c['keys'] if k in numbers)) for c in source['calls'])
        check('source_and_pdf_citation_clusters_match', actual == expected)
        seen = list(dict.fromkeys(n for c in clusters for n in c['numbers']))
        evidence_rows = source.get('reference_evidence', {}).get('references', [])
        ai_keys = {r['key'] for r in evidence_rows if r.get('reference_type') == 'ai_tool'}
        ordinary_keys = [key for key in source['keys'] if key not in ai_keys]
        ordinary_numbers = [numbers[key] for key in ordinary_keys if key in numbers]
        check('at_least_ten_actual_body_references', len([n for n in seen if n not in {numbers.get(k) for k in ai_keys}]) >= 10)
        check('exactly_one_ai_disclosure', len(ai_keys) == 1)
        if ai_keys:
            ai_numbers = [numbers[key] for key in ai_keys if key in numbers]
            check('ai_disclosure_is_last_number', ai_numbers == [len(ordinary_keys)+1])
        check('numbered_by_first_body_appearance', ordinary_numbers == list(range(1, len(ordinary_keys)+1)))
        check('pdf_numbered_by_first_body_appearance', [n for n in seen if n not in {numbers.get(k) for k in ai_keys}] == list(range(1, len(ordinary_keys)+1)))
    except (ValueError, KeyError, TypeError, OSError, IndexError) as exc:
        failures.append('citation_evidence_invalid: '+str(exc))
    return {'status': 'FAIL' if failures else 'PASS', 'failures': failures,
            'source': source, 'clusters': clusters, 'printed_references': printed,
            'scope': 'Citation count, physical bracket/number/punctuation typography and link targets. '
                     'Bibliographic truth and scientific relevance require independent source review.'}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', type=Path, required=True)
    ap.add_argument('--pdf', type=Path)
    ap.add_argument('--source', type=Path)
    ap.add_argument('--report', type=Path, required=True)
    args = ap.parse_args()
    if bool(args.pdf) != bool(args.source):
        ap.error('--pdf and --source must be supplied together')
    result = audit_pdf(args.pdf, args.source, args.manifest) if args.pdf else audit_source(args.manifest)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'failures': result['failures']}, ensure_ascii=False))
    raise SystemExit(result['status'] != 'PASS')
