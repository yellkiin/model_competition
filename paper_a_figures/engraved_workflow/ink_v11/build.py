#!/usr/bin/env python3
"""Make V11 from published V9; edit only the L2-hit annotation.

Reuse published SimSun/Times New Roman glyph outlines. No installed fonts,
font downloads, font substitution or whole-figure re-typesetting are needed.
"""
from __future__ import annotations
import argparse
import copy
import gzip
import hashlib
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path

HERE = Path(__file__).resolve().parent
SVG = 'http://www.w3.org/2000/svg'
NS = {'s': SVG}
ET.register_namespace('', SVG)
ET.register_namespace('inkscape', 'http://www.inkscape.org/namespaces/inkscape')
THEMES = ('qinglu', 'qianjiang', 'yanlan', 'mono')
SOURCE_HASHES = {
    'qinglu': ('c17d41d0ff98ba3b7a2cb11eb711b480fb3c815c', '2a1ad8f91be2bd36758d5178a37391ceb37f4b54'),
    'qianjiang': ('458ab9e4344a162f0462b956459a575016224c1b', 'dff306d50acbdb56f578cdca065d8f9e2320b643'),
    'yanlan': ('46e407e26aff7a6c921191ff61592751493d068c', 'f86bd47359b32e879eec8d165cfbd573a0424b55'),
    'mono': ('a0d5662296293cf21b0a42006c822ae006b87379', 'ded8541f2ef45abd6da9ccbdc69f28765fba4d9e'),
}
OLD_IDS = ('text-129', 'text-130', 'text-131')
LABEL = '命中后读取 L2 数据'
CELLS = ('命', '中', '后', '读', '取', 'L2', '数', '据')
FONT_SIZE = 25
CENTER_X = 2970
BASELINES = tuple(955 + 32 * i for i in range(len(CELLS)))
# label ID, glyph index, glyph advance origin x, baseline, native font size
GLYPHS = {
    '命': ('text-127', 1, 2115, 1253, 25),
    '中': ('text-127', 2, 2140, 1253, 25),
    '后': ('text-128', 3, 2165, 1289, 25),
    '读': ('text-127', 3, 2165, 1253, 25),
    '取': ('text-091', 2, 1595, 1318, 27),
    '数': ('text-068', 0, 1098, 969, 31),
    '据': ('text-068', 1, 1129, 969, 31),
}


def find(root: ET.Element, ident: str) -> ET.Element:
    node = root.find(".//*[@id='" + ident + "']")
    if node is None:
        raise ValueError('Missing SVG object: ' + ident)
    return node


def git_hash(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def transformed_path(d: str, scale: float, dx: float, dy: float) -> str:
    pen = SVGPathPen(None)
    parse_path(d, TransformPen(pen, (scale, 0, 0, scale, dx, dy)))
    return pen.getCommands()


def glyph_paths(portable: ET.Element, token: str, baseline: float) -> list[str]:
    if token != 'L2':
        ident, index, x, y, size = GLYPHS[token]
        src = find(portable, ident)
        paths = src.findall('.//s:path', NS)
        if 'SimSun' not in src.get('data-fonts', ''):
            raise ValueError('Expected published SimSun glyph')
        scale = FONT_SIZE / size
        # Copy only d: synthetic bold strokes on the source heading are excluded.
        return [transformed_path(paths[index].get('d'), scale,
                                 CENTER_X - FONT_SIZE / 2 - scale*x,
                                 baseline - scale*y)]
    src = find(portable, 'text-125')
    if src.get('data-label') != '只读 L2 · FIFO':
        raise ValueError('Unexpected L2 glyph source')
    paths = src.findall('.//s:path', NS)[2:4]
    pen = BoundsPen(None)
    for path in paths:
        parse_path(path.get('d'), pen)
    xmin, _, xmax, _ = pen.bounds
    center = (xmin + xmax) / 2
    scale = FONT_SIZE / 30
    return [transformed_path(p.get('d'), scale,
                             CENTER_X - scale*center,
                             baseline - scale*1301.5) for p in paths]


def new_label(portable: ET.Element, editable: bool) -> ET.Element:
    ink = find(portable, 'text-127').get('fill')
    if find(portable, 'text-128').get('fill') != ink:
        raise ValueError('Miss-label colors differ unexpectedly')
    group = ET.Element('{' + SVG + '}g', {
        'id': 'l2-hit-label-v11', 'data-label': LABEL,
        'data-fonts': 'SimSun,Times New Roman', 'data-font-size': '25',
        'data-font-weight': '400', 'data-color-reference': 'text-127',
        'data-layout': 'vertical-upright-with-horizontal-L2',
        'fill': ink, 'stroke': 'none', 'font-size': '25', 'font-weight': '400',
    })
    for index, (token, baseline) in enumerate(zip(CELLS, BASELINES)):
        if editable:
            family = 'Times New Roman' if token == 'L2' else 'SimSun'
            text = ET.SubElement(group, '{' + SVG + '}text', {
                'id': f'l2-hit-cell-{index+1}-v11', 'x': str(CENTER_X),
                'y': str(baseline), 'font-size': '25', 'text-anchor': 'middle',
                'style': f"font-family:'{family}',serif;font-size:25px;font-weight:400;fill:{ink};stroke:none",
            })
            text.text = token
        else:
            cell = ET.SubElement(group, '{' + SVG + '}g', {
                'id': f'l2-hit-cell-{index+1}-v11', 'data-label': token,
                'data-font-size': '25', 'data-baseline': str(baseline),
            })
            for d in glyph_paths(portable, token, baseline):
                ET.SubElement(cell, '{' + SVG + '}path', {'d': d})
    group.tail = '\n      '
    return group


def apply(root: ET.Element, portable: ET.Element, editable: bool) -> ET.Element:
    if root.get('data-version') != 'ink_v9':
        raise ValueError('Input must be published ink_v9')
    hardware = find(root, 'hardware-cutaway-v6')
    first = list(hardware).index(find(root, OLD_IDS[0]))
    for ident in OLD_IDS:
        hardware.remove(find(root, ident))
    hardware.insert(first, new_label(portable, editable))
    root.set('data-version', 'ink_v11')
    root.set('data-input-version', 'ink_v9')
    root.set('data-v11-changes', 'unify-hit-miss-typography-expand-hit-label-only')
    find(root, 'title').text = '图1.1 第十一版：联合决策、子图切分与归核、统一执行评价'
    find(root, 'desc').text = (
        '基于第九版，仅将右侧命中说明改为“命中后读取 L2 数据”，'
        '与未命中说明统一为SimSun中文、Times New Roman西文、25字号和正文墨色。'
        '保留原竖排方向及其余所有图形、箭头、文字、布局和配色。'
        'a至f为候选操作示意而非串行阶段；当前最优仅指已评价可行候选中的最好结果。'
    )
    return root


def export(path: Path, png_width: int) -> None:
    exe = shutil.which('inkscape')
    if not exe:
        raise RuntimeError('Inkscape is required for PDF/PNG exports')
    dest = HERE / 'exports'
    dest.mkdir(exist_ok=True)
    for suffix, extra in [('.pdf', []), ('.png', [f'--export-width={png_width}']),
                          ('_preview.png', ['--export-width=2100'])]:
        proc = subprocess.run([
            exe, str(path), f'--export-filename={dest / (path.stem + suffix)}',
            '--export-area-page', '--export-background=white',
            '--export-background-opacity=1', *extra,
        ], capture_output=True, text=True, timeout=180)
        if proc.returncode:
            raise RuntimeError(proc.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--palette', choices=THEMES, default='qinglu')
    parser.add_argument('--source', type=Path, default=HERE.parent / 'ink_v9')
    parser.add_argument('--svg-only', action='store_true')
    parser.add_argument('--png-width', type=int, default=6000)
    args = parser.parse_args()
    if args.png_width <= 0:
        parser.error('PNG width must be positive')
    (HERE / 'assets').mkdir(exist_ok=True)
    for name in THEMES if args.all else [args.palette]:
        source = args.source / 'assets' / f'workflow_{name}_v9.svg'
        portable = ET.parse(source).getroot()
        for index, tail in enumerate(('', '_editable')):
            source = args.source / 'assets' / f'workflow_{name}_v9{tail}.svg'
            if git_hash(source) != SOURCE_HASHES[name][index]:
                raise ValueError('Published V9 source changed: ' + str(source))
            root = apply(ET.parse(source).getroot(), portable, bool(index))
            target = HERE / 'assets' / f'workflow_{name}_v11{tail}.svg'
            ET.ElementTree(root).write(target, encoding='utf-8', xml_declaration=True)
            if index == 0:
                target.with_suffix('.svgz').write_bytes(gzip.compress(target.read_bytes(), mtime=0))
                if not args.svg_only:
                    export(target, args.png_width)
        print(name + ': V11 built; hit/miss labels use matching 25-unit native typography', flush=True)


if __name__ == '__main__':
    main()
