#!/usr/bin/env python3
"""Deterministic, vector-only V6 -> V7 edits. Never overwrite an earlier version.
All existing glyph outlines, colors and mathematical objects are preserved.
Only the five requested layout/connector corrections are applied.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
SVG = 'http://www.w3.org/2000/svg'
NS = {'s': SVG}
TAG = lambda name: '{' + SVG + '}' + name
ET.register_namespace('', SVG)
ET.register_namespace('inkscape', 'http://www.inkscape.org/namespaces/inkscape')
THEMES = ('qinglu', 'qianjiang', 'yanlan', 'mono')
SOURCE_HASHES = {
    'qinglu': ('ec50b0f0ea6d59f137962d69911fa6416066799a', '5db68b8dfed0bc01fbcc830164d2cacaa56e54dd'),
    'qianjiang': ('4c53bd1dd1a0f7947a0ec137e2dd3cd060ba3085', '4f6157d668ab07a4f3a38b4a5b7132fbde13ca5e'),
    'yanlan': ('fd5fec1b9df6a12daceac3ab2af5a25394d7926a', 'df85c4b5ab2abb8c91eb67c7a20dcda6bcdb3d5a'),
    'mono': ('8dbb4ed33dac253d34b0339f53be873cbbd9e515', 'c81d731d6b973a304921ee0236d56defdd9af832'),
}
A_DY = 80.5
TITLE_DY = 21.2
PRIVATE_X = (2206, 2353, 2621, 2768)
FILL_CURVE = 'M2385,1169 C2311,1174 2269,1209 2269,1245 C2269,1280 2346,1284 2448,1284'


def find(root, ident):
    node = root.find(".//*[@id='" + ident + "']")
    if node is None:
        raise ValueError('Missing expected SVG object: ' + ident)
    return node


def erase(root, node):
    for parent in root.iter():
        if node in list(parent):
            parent.remove(node)
            return
    raise ValueError('Detached SVG object')


def move(node, dy):
    node.set('transform', f'translate(0,{dy:g})' + (' ' + node.get('transform') if node.get('transform') else ''))


def git_hash(path):
    data = path.read_bytes()
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def apply(root):
    if root.get('data-version') != 'ink_v6':
        raise ValueError('Input must be the published ink_v6, not an already edited output')
    # 1. Delete only the two top section arrows; retain the lower feedback loop.
    erase(root, find(root, 'section-links-v6'))
    # 2. Isolate a's diagram from its heading. Its operator center was y=679.
    # The b/c before+after state drawings span y=594..925, center y=759.5.
    # Translate the entire illustration and caption; never stretch the artwork.
    base = find(root, 'source-a')
    children = list(base)
    first = next(i for i, e in enumerate(children) if e.get('class') == 'boundary')
    last = children.index(find(base, 'text-054'))
    graphic = ET.Element(TAG('g'), {
        'id': 'base-diagram-v7', 'transform': f'translate(0,{A_DY:g})',
        'data-alignment-center-y': '759.5', 'data-alignment-reference': 'b/c before+after state geometry',
    })
    for node in children[first:last + 1]:
        base.remove(node)
        graphic.append(node)
    base.insert(first, graphic)
    # 3. Remove the redundant subtitle and optically center the remaining title.
    erase(root, find(root, 'selection-subtitle'))
    move(find(root, 'selection-principle'), TITLE_DY)
    # 4. Four straight down-arrows, with exact tips and equal clearances:
    # processor bottom y=803; memory rear top edge y=825; tips at y=821.
    defs = root.find('s:defs', NS)
    ink = find(root, 'pipe-private-0').get('stroke')
    marker = ET.SubElement(defs, TAG('marker'), {
        'id': 'v7-private-arrow', 'viewBox': '0 0 8 8', 'refX': '8', 'refY': '4',
        'markerWidth': '8', 'markerHeight': '8', 'markerUnits': 'userSpaceOnUse', 'orient': 'auto',
    })
    ET.SubElement(marker, TAG('path'), {'d': 'M0,0 L8,4 L0,8 Z', 'fill': ink, 'stroke': 'none'})
    for i, x in enumerate(PRIVATE_X):
        node = find(root, f'pipe-private-{i}')
        node.set('d', f'M{x},807 V821')
        node.set('marker-end', 'url(#v7-private-arrow)')
        node.set('style', 'stroke-linecap:butt;stroke-linejoin:miter')
    # 5. Keep DDR and L2 endpoints/direction; bring the dashed arc next to text.
    # Text's right edge is about x=2249, so the closest arc keeps ~20 units clear.
    find(root, 'ddr-to-l2-fill').set('d', FILL_CURVE)
    root.set('data-version', 'ink_v7')
    root.set('data-input-version', 'ink_v6')
    root.set('data-v7-changes', 'remove-top-arrows align-a delete-selection-subtitle straight-private-arrows tighter-fill-arc')
    find(root, 'title').text = '图1.1 第七版：联合决策、子图切分与归核、统一执行评价'
    find(root, 'desc').text = (
        '保留六种候选操作a至f及底部候选、评价、反馈闭环。删除顶部01、02、03之间的两条箭头；'
        '基础构造图下移，与迁移和交换的图形中心对齐；删除每轮选择一个来源的副标题；'
        '四条核心至L1或UB的箭头改为竖直向下；DDR未命中填充L2的虚线弧线靠近说明文字。'
        '候选操作并非串行阶段；当前最优限于已评价的可行候选。'
    )
    return root


def export(path, png_width):
    exe = shutil.which('inkscape')
    if not exe:
        raise RuntimeError('Inkscape is required for PDF/PNG exports')
    dest = HERE / 'exports'
    dest.mkdir(exist_ok=True)
    for suffix, extra in [('.pdf', []), ('.png', [f'--export-width={png_width}']),
                          ('_preview.png', ['--export-width=2100'])]:
        result = subprocess.run([
            exe, str(path), f'--export-filename={dest / (path.stem + suffix)}',
            '--export-area-page', '--export-background=white', '--export-background-opacity=1', *extra,
        ], capture_output=True, text=True, timeout=180)
        if result.returncode:
            raise RuntimeError(result.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--palette', choices=THEMES, default='qinglu')
    parser.add_argument('--source', type=Path, default=HERE.parent / 'ink_v6')
    parser.add_argument('--svg-only', action='store_true')
    parser.add_argument('--png-width', type=int, default=6000)
    args = parser.parse_args()
    if args.png_width <= 0:
        parser.error('PNG width must be positive')
    (HERE / 'assets').mkdir(exist_ok=True)
    for name in THEMES if args.all else [args.palette]:
        for index, tail in enumerate(('', '_editable')):
            source = args.source / 'assets' / f'workflow_{name}_v6{tail}.svg'
            if git_hash(source) != SOURCE_HASHES[name][index]:
                raise ValueError('Published V6 source has changed: ' + str(source))
            root = apply(ET.parse(source).getroot())
            target = HERE / 'assets' / f'workflow_{name}_v7{tail}.svg'
            ET.ElementTree(root).write(target, encoding='utf-8', xml_declaration=True)
            if index == 0:
                target.with_suffix('.svgz').write_bytes(gzip.compress(target.read_bytes(), mtime=0))
                if not args.svg_only:
                    export(target, args.png_width)
        print(name + ': V7 built', flush=True)


if __name__ == '__main__':
    main()
