#!/usr/bin/env python3
"""check_layout.py — 对任意 .drawio 做版式体检（针对中文示意图调校）。

    python3 check_layout.py fig.drawio            # 体检
    python3 check_layout.py fig.drawio --strict   # WARN 也算失败

FAIL：文字溢出、元素越界、id 重复、盒子重叠、连线穿盒、缺少精准证据的内嵌图片。
WARN：端点压在盒边、疑似空盒、字号种类过多、填充色发散。

用中文字宽模型（全角=字号、半角=字号/2、行高=字号+3）；**不**对紧密堆叠的行列间距报警——
学术示意图里 3px 贴合的表格式堆叠是刻意的，不是缺陷。规则详解见 references/preflight-rules.md。
"""
import argparse
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
import json
import hashlib
import base64
import math
from pathlib import Path

FAIL, WARN = [], []


def style_of(s):
    d = {}
    for kv in (s or '').split(';'):
        if '=' in kv:
            k, v = kv.split('=', 1)
            d[k.strip()] = v.strip()
        elif kv.strip():
            d[kv.strip()] = '1'
    return d


def text_w(line, fs):
    return sum(fs if unicodedata.east_asian_width(c) in ('W', 'F') else fs / 2 for c in line)


def plain(v):
    v = re.sub(r'<br\s*/?>', '\n', v or '', flags=re.I)
    v = re.sub(r'<[^>]+>', '', v)
    return v.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')


def seg_rect(x1, y1, x2, y2, r):
    """线段与矩形是否相交（含边界接触）。"""
    rx, ry, rw, rh = r
    # Slab clipping includes contained diagonal segments and corner contact;
    # testing boundary crossings alone misses a line wholly inside the label.
    t0, t1 = 0.0, 1.0
    for origin, delta, low, high in ((x1,x2-x1,rx,rx+rw),(y1,y2-y1,ry,ry+rh)):
        if abs(delta) < 1e-10:
            if origin < low or origin > high:return False
            continue
        lo, hi = sorted(((low-origin)/delta,(high-origin)/delta))
        t0, t1 = max(t0,lo), min(t1,hi)
        if t0 > t1 + 1e-10:return False
    return True


def label_polygon(box):
    """Actual rotated label rectangle; draw.io rotates around its center."""
    x, y, w, h = box['r']
    angle = math.radians(float(box['st'].get('rotation', 0)))
    c, s = math.cos(angle), math.sin(angle)
    cx, cy = x + w / 2, y + h / 2
    return [(cx + dx*c - dy*s, cy + dx*s + dy*c)
            for dx, dy in [(-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2)]]


def labels_overlap(left, right):
    """Separating-axis test, excluding mere border contact like the old check."""
    p, q = label_polygon(left), label_polygon(right)
    for poly in (p, q):
        for i, (x, y) in enumerate(poly):
            xx, yy = poly[(i+1) % 4]
            axis = (y-yy, xx-x)
            a = [px*axis[0] + py*axis[1] for px, py in p]
            b = [px*axis[0] + py*axis[1] for px, py in q]
            if max(a) <= min(b) + 1e-7 or max(b) <= min(a) + 1e-7:
                return False
    return True


def segment_in_label_space(x1, y1, x2, y2, box):
    """Inverse rotation lets the existing line/rectangle gate check real text."""
    angle = -math.radians(float(box['st'].get('rotation', 0)))
    c, s = math.cos(angle), math.sin(angle)
    x, y, w, h = box['r']; cx, cy = x+w/2, y+h/2
    def local(px, py):
        dx, dy = px-cx, py-cy
        return (cx+dx*c-dy*s, cy+dx*s+dy*c)
    return (*local(x1,y1), *local(x2,y2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('drawio')
    ap.add_argument('--strict', action='store_true')
    ap.add_argument('--exceptions', help='Per-cell embedded bitmap evidence; never disables global checks')
    a = ap.parse_args()
    FAIL.clear(); WARN.clear()
    exceptions = json.loads(Path(a.exceptions).read_text(encoding='utf-8-sig')) if a.exceptions else {}
    bitmap_records = exceptions.get('bitmap_panels', {})
    used_bitmaps = set()

    root = ET.parse(a.drawio).getroot()
    model = root.iter('mxGraphModel').__next__()
    pw, ph = float(model.get('pageWidth', 0) or 0), float(model.get('pageHeight', 0) or 0)

    boxes, edges, ids = [], [], {}
    for c in root.iter('mxCell'):
        cid = c.get('id')
        if cid in ids:
            FAIL.append(f'id 重复: {cid}')
        ids[cid] = 1
        st = style_of(c.get('style'))
        g = c.find('mxGeometry')
        if c.get('vertex') == '1' and g is not None:
            x, y = float(g.get('x', 0)), float(g.get('y', 0))
            w, h = float(g.get('width', 0)), float(g.get('height', 0))
            fs = float(st.get('fontSize', 12))
            txt = plain(c.get('value'))
            raw_style = c.get('style') or ''
            if re.search(r'(?:^|;)image=', raw_style) or 'data:image/' in raw_style:
                record = bitmap_records.get(cid, {})
                try:
                    from PIL import Image
                    source = (Path(a.exceptions).parent / record['source']).resolve()
                    match = re.search(r'data:image/(?:png|jpeg|gif|webp)(?:;base64)?,([^;]+)', raw_style)
                    if not match: raise ValueError('Only embedded PNG/JPEG/GIF/WebP with source evidence are supported')
                    blob = base64.b64decode(match.group(1), validate=True)
                    digest = hashlib.sha256(source.read_bytes()).hexdigest()
                    if abs(record['width_mm']-w*25.4/96)>0.01 or abs(record['height_mm']-h*25.4/96)>0.01:
                        raise ValueError('Declared size differs from mxGeometry at draw.io 96 units/inch')
                    with Image.open(source) as im:
                        dpi = min(im.width / (record['width_mm']/25.4), im.height / (record['height_mm']/25.4))
                        native_pixels = [im.width, im.height]
                    review = record.get('native_resolution_review', {})
                    native_ok = (review.get('reviewed') is True and review.get('native_pixels') == native_pixels
                                 and len(review.get('observation', '')) >= 12 and bool(review.get('tool_ref'))
                                 and review.get('width_mm') == record['width_mm']
                                 and review.get('height_mm') == record['height_mm'])
                    valid = (record['sha256'] == digest == hashlib.sha256(blob).hexdigest()
                             and (dpi >= 300 or native_ok) and len(record.get('reason','')) >= 12)
                    if not valid: raise ValueError('stale source, low DPI or missing reason')
                    used_bitmaps.add(cid)
                except Exception as exc:
                    FAIL.append(f'{cid}: 位图缺少有效的逐面板来源/尺寸/DPI证据: {exc}')
            is_text = st.get('strokeColor') == 'none' or st.get('style', '').startswith('text')
            is_frame = st.get('dashed') == '1' and st.get('fillColor') == 'none'
            is_shape = 'shape=' in raw_style
            boxes.append(dict(id=cid, r=(x, y, w, h), fs=fs, txt=txt, st=st, shape=is_shape,
                              fill=st.get('fillColor'), solid=not (is_text or is_frame),
                              object=c.get('diagramObject'), role=c.get('diagramRole'),
                              overlap_reason=c.get('overlapReason','')))
            if c.get('diagramRole') == 'surface' and (txt.strip() or not c.get('diagramObject') or len(c.get('overlapReason','')) < 12):
                FAIL.append(f'{cid}: 表面叠层标记只允许有对象ID和具体理由的无文字图元')
            if (not txt.strip() and not is_text and not is_frame and not is_shape
                    and st.get('fillColor') not in (None, 'none')):
                WARN.append(f'{cid}: 有填充有描边却没有文字，疑似漏填')
            if pw and (x < -1 or y < -1 or x + w > pw + 1 or y + h > ph + 1):
                FAIL.append(f'{cid}: 越出画布 ({x:g},{y:g} {w:g}×{h:g})')
            if txt.strip() and w and h:
                lines = txt.split('\n')
                label_w, label_h = w, h
                if st.get('shape') == 'singleArrow':
                    # Check the centered rectangular shaft, never waive arrow text.
                    if st.get('direction', 'east') in {'north', 'south'}:
                        label_h = h - 2 * min(h * .3, w * .5)
                    else:
                        label_w = w - 2 * min(w * .3, h * .5)
                for ln in lines:
                    # 单字居中时边距极小（竖排堆叠常见），多字才按两侧各 4px 估
                    usable = label_w - (8 if len(ln) > 1 else 2)
                    if text_w(ln, fs) > usable:
                        FAIL.append(f'{cid}: 文字溢出 "{ln[:18]}" 需 {text_w(ln, fs):.0f}px'
                                    f' > 可用 {usable:.0f}px')
                        break
                if len(lines) * (fs + 3) > label_h * (1.4 if is_text else 1.0):
                    FAIL.append(f'{cid}: {len(lines)} 行放不下（槽高 {h:g}px）')
        elif c.get('edge') == '1' and g is not None:
            pts = []
            sp, tp = g.find("mxPoint[@as='sourcePoint']"), g.find("mxPoint[@as='targetPoint']")
            arr = g.find("Array[@as='points']")
            if sp is not None:
                pts.append((float(sp.get('x')), float(sp.get('y'))))
            if arr is not None:
                pts += [(float(p.get('x')), float(p.get('y'))) for p in arr]
            if tp is not None:
                pts.append((float(tp.get('x')), float(tp.get('y'))))
            if len(pts) >= 2:
                edges.append((cid, pts))

    solid = [b for b in boxes if b['solid']]
    for i in range(len(solid)):
        for j in range(i + 1, len(solid)):
            (x1, y1, w1, h1), (x2, y2, w2, h2) = solid[i]['r'], solid[j]['r']
            if x1 < x2 + w2 and x2 < x1 + w1 and y1 < y2 + h2 and y2 < y1 + h1:
                b1,b2=solid[i],solid[j]
                if (b1['role']==b2['role']=='surface' and b1['object']==b2['object']
                    and b1['object'] and not b1['txt'].strip() and not b2['txt'].strip()
                    and len(b1['overlap_reason'])>=12 and len(b2['overlap_reason'])>=12):
                    continue
                FAIL.append(f"{solid[i]['id']} 与 {solid[j]['id']} 重叠")

    # Label-to-label and line-to-label checks apply even to transparent text cells.
    text_boxes=[b for b in boxes if b['txt'].strip()]
    for b in text_boxes:
        if float(b['st'].get('rotation',0)) % 360:
            if any(px < -1 or py < -1 or (pw and px > pw+1) or (ph and py > ph+1)
                   for px,py in label_polygon(b)):
                FAIL.append(f'{b["id"]}: 旋转后的文字区域越出画布')
    for i,b in enumerate(text_boxes):
        for c in text_boxes[i+1:]:
            if labels_overlap(b,c):
                FAIL.append(f'{b["id"]} 与 {c["id"]} 标签区域重叠')
    if set(bitmap_records)!=used_bitmaps:
        FAIL.append('位图例外含未使用或无效cell，不允许通配/过期例外')

    for cid, pts in edges:
        for k in range(len(pts) - 1):
            x1, y1 = pts[k]
            x2, y2 = pts[k + 1]
            for b in solid + [b for b in text_boxes if not b['solid']]:
                lx1,ly1,lx2,ly2=segment_in_label_space(x1,y1,x2,y2,b)
                bx, by, bw, bh = b['r']
                on_border = (abs(lx1 - bx) < 0.6 or abs(lx1 - bx - bw) < 0.6 or
                             abs(ly1 - by) < 0.6 or abs(ly1 - by - bh) < 0.6)
                ends_here = (k == 0 and bx - 0.6 <= lx1 <= bx + bw + 0.6
                             and by - 0.6 <= ly1 <= by + bh + 0.6)
                if ends_here and on_border:
                    WARN.append(f'{cid}: 端点压在 {b["id"]} 边界上，建议外移 1px')
                    continue
                if seg_rect(lx1, ly1, lx2, ly2, b['r']):
                    FAIL.append(f'{cid}: 穿过盒子 {b["id"]}')
                    break

    # 字号与配色收敛度
    sizes = sorted({b['fs'] for b in boxes if b['txt'].strip()})
    if len(sizes) > 4:
        WARN.append(f'字号 {len(sizes)} 种（{sizes}），层级过多，建议收敛到 2–3 种')
    fills = {b['fill'] for b in solid if b['fill'] not in (None, 'none')}
    if len(fills) > 20:
        WARN.append(f'填充色 {len(fills)} 种，配色发散，建议同语义同色')

    seen = set()
    fails = [x for x in FAIL if not (x in seen or seen.add(x))]
    warns = [x for x in WARN if not (x in seen or seen.add(x))]
    print(f'{a.drawio}: 顶点 {len(boxes)} / 连接器 {len(edges)}'
          f'  FAIL {len(fails)}  WARN {len(warns)}')
    for x in fails:
        print(f'  FAIL  {x}')
    for x in warns:
        print(f'  WARN  {x}')
    if fails or (a.strict and warns):
        sys.exit(1)
    print('PASS: 版式体检通过')


if __name__ == '__main__':
    main()
