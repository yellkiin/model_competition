"""Net prose volume measured from paragraph destinations and final PDF glyphs.

One equivalent page is floor(textheight / normal baselineskip) distinct lines.
Each natural final paragraph line counts once, regardless of glyph count. White
space and paragraph skips never count. This measures typesetting, not substance.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

PT_TO_BP = 72 / 72.27


def measure_prose(doc, source, page_chars, headings, ranges, captions, destination, targets, scope='restatement'):
    if scope not in ('restatement', 'evaluation'):
        raise ValueError(scope)
    path = Path(source).with_suffix('.gmcmprose' if scope == 'restatement' else '.gmcmevaluation')
    anchor = 'gmcm.prose' if scope == 'restatement' else 'gmcm.evaluation'
    checks, records, lines = [], [], {}

    def check(code, ok, **extra):
        code = code.replace('restatement_prose', scope + '_prose')
        checks.append(dict(code=code, ok=bool(ok), **extra))

    result = dict(method='paragraph_destinations_distinct_baselines_v1',
                  checks=checks, paragraphs=records, lines=[], equivalent_pages=0.0,
                  note='正常段落末行按一行计；空白/段距不计。内容充实度须实际审查。')
    check('restatement_prose_measurements_present', path.is_file())
    if not path.is_file():
        return result
    result['metadata_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        raw = [s.split('|') for s in path.read_text(encoding='utf-8-sig').splitlines() if s.strip()]
        dimension = lambda x: float(x.removesuffix('pt')) * PT_TO_BP
        if not raw or len(raw[0]) != 5 or raw[0][0] != 'format':
            raise ValueError('缺少当前编译的正文格式记录')
        leading, height, width = map(dimension, raw[0][1:4])
        size = float(raw[0][4]) * PT_TO_BP
        if not all(math.isfinite(x) and x > 0 for x in (leading, height, width, size)):
            raise ValueError('非法版心或正文尺寸')
        # Production geometry is fixed by build_latex. Metadata cannot relax it.
        expected_height = (297 - 50) / 25.4 * 72
        expected_width = (210 - 50) / 25.4 * 72
        check('restatement_prose_body_geometry', abs(height-expected_height) < .2 and abs(width-expected_width) < .2,
              height_bp=height, width_bp=width)
        check('restatement_prose_prescribed_format', abs(leading-18*PT_TO_BP)<.1 and abs(size-12*PT_TO_BP)<.1,
              leading_bp=leading, font_size_bp=size)
        first = next(r for r in ranges if (r['number'] == '1' if scope == 'restatement' else r['role'] == 'evaluation'))
        parsed = []
        ids = set()
        for parts in raw[1:]:
            if len(parts) != 8 or parts[0] != 'prose' or parts[2] not in (('1', '2') if scope == 'restatement' else ('1', '2', '3')) or parts[7] not in ('body','excluded'):
                raise ValueError('非法段落记录: ' + '|'.join(parts))
            ident = int(parts[1])
            if ident in ids:
                raise ValueError('重复段落 ID')
            ids.add(ident)
            begin = destination(doc, doc.resolve_names(), f'{anchor}.begin.{ident}')
            end = destination(doc, doc.resolve_names(), f'{anchor}.end.{ident}')
            # Some boxed heads are measured but not shipped; only excluded
            # paragraphs may have no final destinations.
            if parts[7] == 'excluded' and begin is None and end is None:
                continue
            if parts[7] == 'excluded' and begin is not None and end is None:
                # caption builds an outer paragraph around its own boxed
                # paragraph. The outer end is not emitted; accept it only
                # when the independent physical-caption record excludes it.
                cap = next((c for c in captions if c['physical_page']==begin[0]+1 and c.get('bbox') and c['bbox'][1]-1 <= begin[2] <= c['bbox'][3]+1), None)
                if cap is not None:
                    records.append(dict(id=ident, role='excluded_caption_wrapper', begin=list(begin), caption_bbox=cap['bbox']))
                    continue
            check(f'restatement_prose_anchors:{ident}', begin is not None and end is not None)
            if begin is None or end is None:
                continue
            valid = (begin[0],begin[2]) <= (end[0],end[2]) and begin[0]+1 in first['content_pages'] and end[0]+1 in first['content_pages']
            check(f'restatement_prose_anchor_order:{ident}', valid)
            if not valid:
                continue
            parsed.append((parts, begin, end))
        def in_span(p, c, begin, end):
            y = c['origin'][1]
            # Destinations sit at the prose baseline. Superscripts are not
            # independent lines and will be attached to their parent visually.
            return begin[0] <= p <= end[0] and (p > begin[0] or y >= begin[2]-.8) and (p < end[0] or y <= end[2]+.8)
        exclusions = [(b,e) for p,b,e in parsed if p[7]=='excluded']
        for parts, begin, end in parsed:
            if parts[7] != 'body':
                records.append(dict(id=int(parts[1]), role='excluded', begin=list(begin), end=list(end)))
                continue
            selected = {}
            for p in range(begin[0], end[0]+1):
                margin = (doc[p].rect.width-width)/2
                for c in page_chars[p]:
                    if not in_span(p,c,begin,end) or not c['c'].strip():
                        continue
                    if not (margin-.5 <= c['origin'][0] <= margin+width+.5 and (doc[p].rect.height-height)/2-1 <= c['origin'][1] <= (doc[p].rect.height+height)/2+1):
                        continue
                    if any(in_span(p,c,b,e) for b,e in exclusions):
                        continue
                    if any(h['physical_page']==p+1 and h['bbox'][1]-.5 <= c['origin'][1] <= h['bbox'][3]+.5 for h in headings):
                        continue
                    if any(h['physical_page']==p+1 and h.get('bbox') and h['bbox'][1]-1 <= c['origin'][1] <= h['bbox'][3]+1 for h in captions):
                        continue
                    if abs(c['size'] - size) > .15:
                        continue
                    y = round(c['origin'][1], 1)
                    # Fake-bold duplicate glyphs and mixed spans at a shared
                    # baseline still form one line.
                    existing = next((v for v in selected if v[0]==p and abs(v[1]-y)<.6), None)
                    key = existing or (p,y)
                    selected.setdefault(key, []).append(c)
            if selected:
                check(f'restatement_prose_format:{parts[1]}',
                      abs(dimension(parts[3])-leading)<.1 and abs(dimension(parts[4])-height)<.1 and abs(dimension(parts[5])-width)<.1 and abs(float(parts[6])*PT_TO_BP-size)<.15)
            for (p,y), chars in selected.items():
                key = next((k for k in lines if k[0]==p and abs(k[1]-y)<.6), (p,y))
                if key not in lines:
                    chars.sort(key=lambda c:c['origin'][0])
                    lines[key] = dict(physical_page=p+1, baseline_bp=y, paragraph_id=int(parts[1]),
                                     bbox=[min(c['bbox'][0] for c in chars),min(c['bbox'][1] for c in chars),max(c['bbox'][2] for c in chars),max(c['bbox'][3] for c in chars)])
            records.append(dict(id=int(parts[1]), role='body', subsection=int(parts[2]), begin=list(begin), end=list(end), counted_lines=len(selected)))
        capacity = math.floor(height/leading)
        minimum = max(1.0, float(targets.get(scope + '_prose', {}).get('minimum_equivalent_pages', 1.0)))
        equivalent = len(lines)/capacity
        result.update(normal_baselineskip_bp=leading, textheight_bp=height, textwidth_bp=width,
                      normal_font_size_bp=size, full_page_line_capacity=capacity,
                      counted_lines=len(lines), effective_height_bp=len(lines)*leading,
                      equivalent_pages=equivalent, minimum_equivalent_pages=minimum,
                      lines=[lines[k] for k in sorted(lines)], chapter_content_pages=first['content_pages'],
                      excluded_caption_boxes=[c for c in captions if c['physical_page'] in first['content_pages']])
        check('restatement_prose_at_least_one_page', equivalent >= minimum, actual=equivalent, required=minimum, counted_lines=len(lines), full_page_line_capacity=capacity)
    except (ValueError, KeyError, TypeError, StopIteration, ZeroDivisionError, OSError) as exc:
        check('restatement_prose_measurement_valid', False, error=str(exc))
    return result
