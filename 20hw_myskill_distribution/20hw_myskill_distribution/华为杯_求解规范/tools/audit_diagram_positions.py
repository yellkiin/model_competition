"""Bind overview source sections to physical PDF headings, graphics and captions.

Position evidence does not certify that a diagram has scientific substance.
The existing diagram/academic source and visual gates remain mandatory.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PAPER_TOOLS = Path(__file__).resolve().parents[2] / '华为杯_论文规范模板/tools'
if str(PAPER_TOOLS) not in sys.path:
    sys.path.insert(0, str(PAPER_TOOLS))
from paper_contract import FIRST_SUBSECTION, balanced, commands, expand_fragment, strip_comments


def source_position(text, chapter, diagram, main, root, preamble=''):
    """Only literal, unique source bindings qualify; include paths use main cwd."""
    text = strip_comments(text)
    failures = []
    def check(code, ok):
        if not ok:
            failures.append(code)
    label = diagram['paper']['label']
    roadmap = diagram.get('problem_id') is None
    subs = commands(text, ('subsection',))
    slot = 1 if roadmap else 0
    expected = '问题重述' if roadmap else FIRST_SUBSECTION
    check('required_subsection', len(subs) > slot and subs[slot].argument == expected)
    if len(subs) <= slot:
        return {'status': 'FAIL', 'failures': failures}
    lower = subs[slot].end
    upper = subs[slot+1].start if len(subs) > slot+1 else len(text)
    floats = list(re.finditer(r'\\begin\{(figure\*?)\}.*?\\end\{\1\}', text, re.S))
    matches = [m for m in floats if label in [c.argument for c in commands(m.group(), ('label',))]]
    check('one_label_in_chapter', sum(c.argument == label for c in commands(text, ('label',))) == 1)
    check('one_figure_in_required_section', len(matches) == 1 and lower <= matches[0].start() < matches[0].end() <= upper)
    if len(matches) != 1:
        return {'status': 'FAIL', 'failures': failures}
    block = matches[0]
    captions = commands(block.group(), ('caption',))
    normalize = lambda value: re.sub(r'\s+', '', value)
    check('caption_matches_plan', len(captions) == 1 and captions[0].optional is None and
          normalize(captions[0].argument) == normalize(diagram['paper']['caption']))
    before = text[lower:block.start()] if lower <= block.start() <= upper else ''
    before = re.sub(r'\\begin\{(figure\*?|table\*?)\}.*?\\end\{\1\}', '', before, flags=re.S)
    refs = commands(before, ('ref', 'autoref', 'cref'))
    check('introduced_within_required_section', any(c.argument == label for c in refs))
    prose = before
    for c in reversed(commands(prose, ('ref', 'autoref', 'cref', 'label', 'subsubsection', 'paragraph', 'subparagraph'))):
        prose = prose[:c.start] + prose[c.end:]
    # This minimum only rules out a bare figure reference. Scientific adequacy
    # of the problem description remains a separate content review.
    check('description_before_overview', len(re.findall(r'[\u4e00-\u9fffA-Za-z]', prose)) >= 12)
    search = [main.parent]
    for c in commands(strip_comments(preamble), ('graphicspath',)):
        search.extend((main.parent / raw).resolve() for raw in re.findall(r'\{([^{}]+)\}', c.argument))
    resolved = []
    for c in commands(block.group(), ('includegraphics',)):
        for directory in search:
            candidate = (directory / c.argument).resolve()
            if not candidate.suffix:
                candidate = candidate.with_suffix('.pdf')
            if candidate.is_file():
                resolved.append(candidate)
                break
    check('label_bound_to_expected_vector', resolved == [(root / diagram['outputs']['vector']).resolve()])
    section_number = f"{chapter['order']}.{slot+1}"
    upper_anchor = (f"subsection.{chapter['order']}.{slot+2}" if len(subs) > slot+1
                    else f"section.{chapter['order']+1}")
    return {'status': 'FAIL' if failures else 'PASS', 'failures': failures,
            'lower_anchor': 'subsection.'+section_number, 'upper_anchor': upper_anchor,
            'label': label, 'diagram_id': diagram['diagram_id'], 'source_caption': diagram['paper']['caption']}


def source_positions(manifest, manifest_path, main, root, diagrams, questions):
    chapters = manifest['chapters']
    by_id = {d['diagram_id']: d for d in diagrams}
    targets = [(by_id.get(q['overview_id']), next((c for c in chapters if c['chapter_id'] == q['chapter_id']), None))
               for q in questions]
    targets += [(d, chapters[0]) for d in diagrams if d.get('placement') == 'body' and
                d.get('kind') == 'flowchart' and d.get('problem_id') is None]
    result = []
    preamble = main.read_text(encoding='utf-8-sig')
    for d, chapter in targets:
        if not d or not chapter:
            result.append({'status': 'FAIL', 'failures': ['diagram_or_chapter_missing']})
            continue
        text = expand_fragment(main.parent, manifest_path.parent / chapter['tex_path'])
        result.append(source_position(text, chapter, d, main, root, preamble))
    return result


def label_destinations(aux):
    result = {}
    for call in commands(aux, ('newlabel',)):
        pos = call.end
        while pos < len(aux) and aux[pos].isspace():
            pos += 1
        fields, _ = balanced(aux, pos)
        values = []
        pos = 0
        while pos < len(fields):
            if fields[pos].isspace():
                pos += 1
                continue
            value, pos = balanced(fields, pos)
            values.append(value)
        if len(values) >= 4:
            result[call.argument] = values[3]
    return result


def physical_positions(source_records, review, layout, main, root):
    """Call only after verify_evidence has rederived the current PDF coordinates."""
    import pymupdf as fitz
    headings = {h['anchor']: h for h in layout.get('headings', [])}
    figures = {f['figure_id']: f for f in review['figures']}
    labels = label_destinations(strip_comments(main.with_suffix('.aux').read_text(encoding='utf-8-sig')))
    records = []
    with fitz.open(root / review['pdf_path']) as pdf:
        for source in source_records:
            failures = []
            item = {'diagram_id': source.get('diagram_id'), 'failures': failures}
            try:
                if source['status'] != 'PASS':
                    raise ValueError('source_position_failed')
                lower, upper = headings[source['lower_anchor']], headings[source['upper_anchor']]
                start = (lower['physical_page'], lower['bbox'][3])
                end = (upper['physical_page'], upper['bbox'][1])
                occurrences = figures[source['diagram_id']]['occurrences']
                if len(occurrences) != 1:
                    raise ValueError('overview_must_have_one_physical_occurrence')
                graphic = occurrences[0]
                captions = [c for c in layout['captions'] if c['label'] == source['label']]
                if len(captions) != 1 or not captions[0]['bbox']:
                    raise ValueError('one_bound_caption_required')
                caption = captions[0]
                for name, page, box in [('graphic', graphic['page_number'], graphic['pdf_bbox']),
                                        ('caption', caption['physical_page'], caption['bbox'])]:
                    if not (start < (page, box[1]) <= (page, box[3]) < end):
                        failures.append(name+'_outside_required_subsection')
                target = labels[source['label']]
                references = []
                for p in range(start[0]-1, graphic['page_number']):
                    references += [(p+1, list(link['from'])) for link in pdf[p].get_links()
                                   if link.get('nameddest') == target and
                                   start < (p+1, link['from'].y0) and
                                   (p+1, link['from'].y1) < (graphic['page_number'], graphic['pdf_bbox'][1])]
                if not references:
                    failures.append('no_physical_intro_reference_before_graphic')
                item.update(lower_heading=lower, upper_heading=upper,
                            graphic_page=graphic['page_number'], graphic_bbox=graphic['pdf_bbox'],
                            caption_page=caption['physical_page'], caption_bbox=caption['bbox'],
                            preceding_reference_boxes=references)
            except (KeyError, ValueError, IndexError) as exc:
                failures.append(str(exc))
            item['status'] = 'FAIL' if failures else 'PASS'
            records.append(item)
    return records
