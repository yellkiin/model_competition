"""Measurements and pending visual evidence from the SAME final XeLaTeX PDF."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
import pymupdf as fitz
from evaluation_contract import REVIEW_DIMENSIONS


def evaluation_pages(layout):
    return sorted({p for r in layout.get('chapter_ranges', []) if r['role'] == 'evaluation' for p in r['content_pages']})


def page_limits(ranges, targets):
    first = ranges[:3]
    pages = sorted({p for r in first for p in r.get('content_pages', [])})
    symbol_pages = first[2].get('content_pages', []) if len(first) == 3 else []
    group = targets.get('first_three_chapters', {'min_pages': 3, 'max_pages': 6})
    checks = [dict(code='first_three_unique_pages', ok=len(first) == 3 and bool(pages), actual=len(pages), pages=pages),
              dict(code='first_three_no_blank_gaps', ok=bool(pages) and pages == list(range(pages[0], pages[-1] + 1))),
              dict(code='symbols_max_two_pages', ok=1 <= len(symbol_pages) <= targets.get('chapter_hard_limits', {}).get('关键性符号说明', 2), actual=len(symbol_pages))]
    checks.append(dict(code='first_three_recommended_range', severity='warning',
                       ok=group['min_pages'] <= len(pages) <= group['max_pages'],
                       actual=len(pages), recommended=[group['min_pages'], group['max_pages']],
                       message='超出推荐范围须复查内容与版面；页数本身不是硬失败。'))
    return checks


def chapter_ranges(doc, headings, names, page_chars, destination):
    ranges, checks = [], []
    margin = 25 / 25.4 * 72
    for i, h in enumerate(headings):
        start, top = h['physical_page'], h['bbox'][1]
        end = destination(doc, names, 'gmcm.chapter.end.' + h['number'])
        if h['role'] == 'appendix':
            end = (len(doc) - 1, 0, doc[-1].rect.height - margin)
        checks.append(dict(code='chapter_end_anchor:' + h['number'], ok=end is not None))
        if end is None:
            continue
        ep, _, ey = end
        ep += 1
        valid = (ep, ey) >= (start, top)
        if i + 1 < len(headings):
            nxt = headings[i + 1]
            valid &= (ep, ey) <= (nxt['physical_page'], nxt['bbox'][1] + 1)
        checks.append(dict(code='chapter_anchor_order:' + h['number'], ok=valid))
        pages, positions = [], []
        for p in range(start, ep + 1):
            lo, hi = (top if p == start else margin - 2), (ey + 2 if p == ep else doc[p-1].rect.height - margin + 2)
            cs = [c for c in page_chars[p-1] if lo <= c['origin'][1] <= hi and c['bbox'][1] < doc[p-1].rect.height - 65]
            shapes = [d['rect'] for d in doc[p-1].get_drawings() if d['rect'].y0 >= lo and d['rect'].y1 <= hi and d['rect'].get_area() > 4]
            pictures = [b for b in doc[p-1].get_text('dict')['blocks'] if b['type'] == 1 and lo <= b['bbox'][1] <= hi]
            if cs or shapes or pictures:
                pages.append(p)
                positions.append(dict(physical_page=p, top=lo, bottom=hi, visible_characters=len(cs)))
        checks.append(dict(code='chapter_content_range:' + h['number'], ok=pages == list(range(start, ep+1)), pages=pages))
        ranges.append({**h, 'start_physical_page': start, 'end_physical_page': ep,
                       'end_position': list(end), 'content_pages': pages, 'content_positions': positions, 'touched_pages': len(pages)})
    return ranges, checks


def symbol_measurements(doc, symbol_range, page_chars):
    checks, fragments = [], []
    if not symbol_range:
        return {'checks': [dict(code='symbol_range_present', ok=False)], 'fragments': []}
    pages = symbol_range['content_pages']
    table_pages = []
    numbers = []
    for p in pages:
        page = doc[p-1]
        position = next(x for x in symbol_range['content_positions'] if x['physical_page'] == p)
        cs = [c for c in page_chars[p-1] if position['top'] <= c['origin'][1] <= position['bottom']]
        rules = []
        for drawing in page.get_drawings():
            r = drawing['rect']
            if r.y0 < position['top'] or r.y1 > position['bottom']:
                continue
            if r.width > 300 and r.height < 3:
                thickness = r.height if drawing.get('fill') is not None else drawing['width']
                rules.append(dict(y=(r.y0+r.y1)/2, x0=r.x0, x1=r.x1, width_bp=thickness, dashed=drawing.get('dashes', '[] 0') not in ('[] 0', '[] 0.0', None)))
            elif r.height > 8 and r.width < 3:
                checks.append(dict(code=f'symbol_no_vertical_rule:{p}', ok=False))
        rules.sort(key=lambda r:r['y'])
        if not rules:
            # A separate note-only third page still counts toward the chapter cap.
            continue
        table_pages.append(p)
        checks.append(dict(code=f'symbol_three_rules:{p}', ok=len(rules)==3, measurements=rules, unit='PDF bp', tolerance_bp=.04))
        if len(rules) != 3:
            continue
        checks.append(dict(code=f'symbol_rule_widths:{p}', ok=all(abs(r['width_bp']-v)<.04 and not r['dashed'] for r,v in zip(rules,(1.5,.75,1.5))), measurements=rules))
        top, mid, bottom = [r['y'] for r in rules]
        extra = [list(d['rect']) for d in page.get_drawings()
                 if top + 1 < d['rect'].y0 < bottom - 1
                 and not (d['rect'].width > 300 and d['rect'].height < 3)]
        checks.append(dict(code=f'symbol_no_extra_borders:{p}',ok=not extra,drawings=extra))
        rows = [c for c in cs if top < c['origin'][1] < bottom]
        checks.append(dict(code=f'symbol_header_with_data:{p}',ok=len([c for c in rows if c['origin'][1]>mid])>=4))
        text = ''.join(c['c'] for c in cs)
        headings = ''.join(c['c'] for c in rows if c['origin'][1] < mid)
        checks.append(dict(code=f'symbol_header:{p}', ok=headings=='类别符号含义单位', actual=headings))
        chinese = [c for c in rows if '\u4e00' <= c['c'] <= '\u9fff']
        checks.append(dict(code=f'symbol_font:{p}', ok=bool(chinese) and all('SimSun' in c['font'] and abs(c['size']-12)<.08 for c in chinese), sizes=sorted({round(c['size'],3) for c in chinese}), fonts=sorted({c['font'] for c in chinese}), expected_bp=12))
        checks.append(dict(code=f'symbol_math_and_text_sizes:{p}',ok=bool(rows) and all(any(abs(c['size']-v)<.08 for v in (12,8*72/72.27,6*72/72.27)) for c in rows),sizes=sorted({round(c['size'],3) for c in rows})))
        caps = [c for c in cs if top-35 < c['origin'][1] < top]
        cap = ''.join(c['c'] for c in caps)
        match = re.search(r'表([\d.]+)(关键性符号说明|（续）)', cap)
        checks.append(dict(code=f'symbol_caption:{p}', ok=bool(match) and ('（续）' in cap)==(len(table_pages)>1), actual=cap))
        if match: numbers.append(match[1])
        checks.append(dict(code=f'symbol_caption_font:{p}', ok=bool(caps) and all(abs(c['size']-12)<.08 for c in caps), sizes=sorted({round(c['size'],3) for c in caps})))
        # Column centres reflect the template's actual p-column widths and padding.
        x0,x1 = rules[0]['x0'], rules[0]['x1']
        w = x1-x0
        centres = [x0+.09*w, x0+.27*w+8, x0+.61*w+4, x1-.07*w]
        bounds = [x0, x0+.18*w+4, x0+.36*w+12, x1-.14*w-4, x1]
        offsets=[]
        for col in range(4):
            chars=[c for c in rows if bounds[col]-.5 <= c['origin'][0] < bounds[col+1]-.5]
            baselines=sorted({round(c['origin'][1],1) for c in chars if c['size'] >= 11.8})
            cells={}
            for c in chars:
                if not baselines: continue
                baseline=min(baselines,key=lambda y:abs(y-c['origin'][1]))
                if abs(baseline-c['origin'][1]) <= 8:
                    cells.setdefault(baseline,[]).append(c)
            for line in cells.values():
                if all(c['size'] < 11.8 for c in line): continue  # superscripts aren't independent lines
                center=(min(c['bbox'][0] for c in line)+max(c['bbox'][2] for c in line))/2
                offsets.append(round(center-centres[col],3))
        checks.append(dict(code=f'symbol_cells_centered:{p}', ok=bool(offsets) and all(abs(d)<4 for d in offsets), offsets_bp=offsets, tolerance_bp=4))
        if caps:
            cc=(min(c['bbox'][0] for c in caps)+max(c['bbox'][2] for c in caps))/2
            checks.append(dict(code=f'symbol_caption_centered:{p}',ok=abs(cc-(x0+x1)/2)<2))
        notes=[c for c in cs if c['origin'][1]>bottom]
        if p==pages[-1]:
            nt=''.join(c['c'] for c in notes)
            checks.append(dict(code='symbol_final_note', ok=nt.startswith('注：') and bool(notes) and all('SimSun' in c['font'] and abs(c['size']-10.5)<.08 for c in notes if '\u4e00'<=c['c']<='\u9fff') and abs(min(c['bbox'][0] for c in notes)-x0)<2, actual=nt, sizes=sorted({round(c['size'],3) for c in notes})))
        else:
            checks.append(dict(code=f'symbol_no_intermediate_note:{p}', ok=not notes))
        fragments.append(dict(physical_page=p, rules=rules, caption=cap, bbox=[x0,top-35,x1, min(position['bottom']+4,page.rect.height-65)]))
    checks.append(dict(code='symbol_one_logical_table',ok=1<=len(table_pages)<=2 and len(set(numbers))==1 and len(numbers)==len(table_pages)))
    checks.append(dict(code='symbol_note_with_final_fragment', ok=bool(table_pages) and table_pages[-1]==pages[-1]))
    return dict(checks=checks, fragments=fragments)


def prepare_review(pdf, layout, output):
    """Render pending pages; never writes reviewed=True. Refuses overwrite."""
    pdf, output = Path(pdf).resolve(), Path(output).resolve()
    if output.exists(): raise ValueError('复核记录已存在；保留旧记录并选择新路径')
    if len(layout.get('chapter_ranges', []))<4: raise ValueError('缺少可核验前三章/第四章边界')
    pages=sorted({p for r in layout['chapter_ranges'][:3] for p in r['content_pages']} | {layout['chapter_ranges'][3]['physical_page']})
    pages = sorted(set(pages) | set(evaluation_pages(layout)))
    work=output.parent/(output.stem+'_pages'); work.mkdir(parents=True,exist_ok=True)
    records=[]
    with fitz.open(pdf) as doc:
        for p in pages:
            path=work/f'page_{p:03d}.png'
            doc[p-1].get_pixmap(matrix=fitz.Matrix(1.7,1.7),alpha=False).save(path)
            records.append(dict(physical_page=p,path=str(path.relative_to(output.parent)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),reviewed=False,tool_ref='',observation='',issues=[]))
        crops=[]
        for f in layout['symbols']['fragments']:
            path=work/f"symbol_{f['physical_page']:03d}.png"
            doc[f['physical_page']-1].get_pixmap(matrix=fitz.Matrix(2.5,2.5),clip=fitz.Rect(f['bbox']),alpha=False).save(path)
            crops.append(dict(physical_page=f['physical_page'],bbox=f['bbox'],path=str(path.relative_to(output.parent)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),reviewed=False,tool_ref='',observation='',issues=[]))
    group_pages=sorted({p for c in layout['chapter_ranges'][:3] for p in c['content_pages']})
    report=dict(pdf=str(pdf),pdf_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),status='REVIEW_REQUIRED',pages=records,symbol_crops=crops,
                first_three_content_pages=group_pages,first_three_unique_page_count=len(group_pages),
                symbol_chapter_page_count=layout['chapter_ranges'][2]['touched_pages'],
                restatement_prose=layout.get('restatement_prose'),
                evaluation_pages=evaluation_pages(layout),
                evaluation_prose=layout.get('evaluation_prose'),
                evaluation_source=layout.get('evaluation_source'),
                evaluation_content_review={d:dict(status='REVIEW_REQUIRED', observation='', evidence_locations=[]) for d in REVIEW_DIMENSIONS},
                page_recommendations=layout.get('warnings', []),
                local_symbol_definitions=layout.get('first_chapters_source'),
                chapter_ranges=layout['chapter_ranges'][:4],measurements=layout['symbols'],recheck='pending',
                assurance='渲染不等于实际看图；逐页与局部观察后填写，PDF变化后重建并重审。')
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def verify_review(pdf, layout, path):
    errors=[]
    try:
        path=Path(path).resolve(); pdf=Path(pdf).resolve()
        r=json.loads(path.read_text(encoding='utf-8-sig'))
        if r['pdf_sha256']!=hashlib.sha256(pdf.read_bytes()).hexdigest() or Path(r['pdf']).resolve()!=pdf:
            errors.append('复核不是当前PDF')
        if r['chapter_ranges']!=layout['chapter_ranges'][:4] or r['measurements']!=layout['symbols']:
            errors.append('页数或测量证据过期')
        group=sorted({p for c in layout['chapter_ranges'][:3] for p in c['content_pages']})
        if r.get('first_three_content_pages')!=group or r.get('first_three_unique_page_count')!=len(group) or r.get('symbol_chapter_page_count')!=layout['chapter_ranges'][2]['touched_pages']:
            errors.append('去重页数记录缺失或不一致')
        if r.get('local_symbol_definitions')!=layout.get('first_chapters_source'):
            errors.append('符号定义审查记录过期')
        if not layout.get('restatement_prose') or r.get('restatement_prose')!=layout['restatement_prose']:
            errors.append('第一章净正文测量缺失或过期')
        if not evaluation_pages(layout) or r.get('evaluation_pages') != evaluation_pages(layout):
            errors.append('评价章逐页范围缺失或过期')
        for key in ('evaluation_prose', 'evaluation_source'):
            if not layout.get(key) or r.get(key) != layout[key]:
                errors.append('评价章源内容或净正文测量缺失或过期: ' + key)
        for dim in REVIEW_DIMENSIONS:
            item = r.get('evaluation_content_review', {}).get(dim, {})
            locations = item.get('evidence_locations')
            if item.get('status') != 'verified' or not isinstance(item.get('observation'), str) or not item['observation'].strip() or not isinstance(locations, list) or not locations or any(not isinstance(v, str) or not v.strip() for v in locations):
                errors.append('评价章尚未实际审查并记录依据位置: ' + dim)
        if r.get('page_recommendations')!=layout.get('warnings', []):
            errors.append('推荐页数复查提示缺失或过期')
        expected=sorted({p for c in layout['chapter_ranges'][:3] for p in c['content_pages']} | {layout['chapter_ranges'][3]['physical_page']})
        expected = sorted(set(expected) | set(evaluation_pages(layout)))
        if [x['physical_page'] for x in r['pages']]!=expected: errors.append('未逐页覆盖前三章、第四章交界及评价章全部页面')
        if [(x['physical_page'],x['bbox']) for x in r['symbol_crops']] != [(x['physical_page'],x['bbox']) for x in layout['symbols']['fragments']]: errors.append('缺少符号表局部复核')
        with fitz.open(pdf) as doc:
            for x in r['pages']+r['symbol_crops']:
                p=(path.parent/x['path']).resolve(); p.relative_to(path.parent)
                if hashlib.sha256(p.read_bytes()).hexdigest()!=x['sha256']: errors.append('复核图片已变化')
                pix=doc[x['physical_page']-1].get_pixmap(matrix=fitz.Matrix(2.5,2.5) if 'bbox' in x else fitz.Matrix(1.7,1.7),clip=fitz.Rect(x['bbox']) if 'bbox' in x else None,alpha=False)
                from PIL import Image
                with Image.open(p) as im:
                    if im.size!=(pix.width,pix.height) or im.convert('RGB').tobytes()!=pix.samples: errors.append('图片并非本次PDF渲染')
                if x.get('reviewed') is not True or not x.get('tool_ref') or not x.get('observation') or x.get('issues'):
                    errors.append('尚未实际复核或存在未解决问题: '+str(x['physical_page']))
        if r.get('status')!='PASS' or r.get('recheck')!='complete': errors.append('修订后尚未复检完成')
    except (KeyError,ValueError,OSError,TypeError,IndexError) as exc:
        errors.append('缺少有效的前三章视觉证据: '+str(exc))
    return dict(status='FAIL' if errors else 'PASS',failures=errors,
                assurance='哈希/像素及逐页观察记录核对；可编辑记录不构成实际看图的独立证明。')
