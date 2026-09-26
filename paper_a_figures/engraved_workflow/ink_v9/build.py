#!/usr/bin/env python3
"""Remove only five front-bottom hatch strips from published ink_v8.

Preserve all other SVG nodes, glyph outlines, fills, arrows and geometry.
Pin the source to the eight published Git blobs; never rebuild fonts.
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
ET.register_namespace('', SVG)
ET.register_namespace('inkscape', 'http://www.inkscape.org/namespaces/inkscape')
THEMES = ('qinglu', 'qianjiang', 'yanlan', 'mono')
SOURCE_HASHES = {
    'qinglu': ('0027b5787624a9b72a26fad33e7ade54e19502ca', '2084a1de63dd36a50ea7aac558ab794648843a3c'),
    'qianjiang': ('38f4cb62c84c8422fca7d1f20289b6e9696fffbf', '078c4cde7cd7fd13f06103168d483d4d57d88bbd'),
    'yanlan': ('364b3266e84af98ba3f4c119b0265bef5f71eaaa', '33c515384bc6134c34d314ed41f40d9d543b873f'),
    'mono': ('c982420dbd9e65a88b228327baa7852c503c5ba2', 'a1c31ff43156911111c6f4a06d87c8b94a32c673'),
}
# (object, left x, right x, first y, line count, inherited translation)
STRIPS = (
    ('left-L1', 2145, 2253, 858, 7, 'translate(0,30) '),
    ('left-UB', 2292, 2400, 858, 7, 'translate(0,30) '),
    ('right-L1', 2560, 2668, 858, 7, 'translate(0,30) '),
    ('right-UB', 2707, 2815, 858, 7, 'translate(0,30) '),
    ('DDR', 2190, 2808, 1147, 10, None),
)


def find(root: ET.Element, ident: str) -> ET.Element:
    node = root.find(".//*[@id='" + ident + "']")
    if node is None:
        raise ValueError('Missing expected SVG object: ' + ident)
    return node


def git_hash(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def strip_nodes(root: ET.Element) -> list[tuple[int, ET.Element]]:
    group = find(root, 'hardware-cutaway-v6')
    result = []
    for name, x1, x2, y, count, transform in STRIPS:
        path = ' '.join(f'M{x1},{y + 2*i}H{x2}' for i in range(count))
        matches = [(i, n) for i, n in enumerate(group)
                   if n.tag == '{' + SVG + '}path' and n.get('class') == 'hair'
                   and n.get('d') == path and n.get('transform') == transform]
        if len(matches) != 1:
            raise ValueError(f'Expected one published strip for {name}, found {len(matches)}')
        result.append(matches[0])
    return result


def apply(root: ET.Element) -> ET.Element:
    if root.get('data-version') != 'ink_v8':
        raise ValueError('Input must be published ink_v8')
    group = find(root, 'hardware-cutaway-v6')
    for _, node in strip_nodes(root):
        group.remove(node)
    root.set('data-version', 'ink_v9')
    root.set('data-input-version', 'ink_v8')
    root.set('data-v9-changes', 'remove-five-front-bottom-horizontal-hatch-strips-only')
    find(root, 'title').text = '图1.1 第九版：联合决策、子图切分与归核、统一执行评价'
    find(root, 'desc').text = (
        '基于第八版，仅删除左右L1、UB及DDR正面底部的五组横条纹阴影。'
        '保留正面底色、边框、顶面和侧面斜纹、全部COPY文字和张量立方体、箭头、布局与配色。'
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
    parser.add_argument('--source', type=Path, default=HERE.parent / 'ink_v8')
    parser.add_argument('--svg-only', action='store_true')
    parser.add_argument('--png-width', type=int, default=6000)
    args = parser.parse_args()
    if args.png_width <= 0:
        parser.error('PNG width must be positive')
    (HERE / 'assets').mkdir(exist_ok=True)
    for name in THEMES if args.all else [args.palette]:
        for index, tail in enumerate(('', '_editable')):
            source = args.source / 'assets' / f'workflow_{name}_v8{tail}.svg'
            if git_hash(source) != SOURCE_HASHES[name][index]:
                raise ValueError('Published V8 source has changed: ' + str(source))
            root = apply(ET.parse(source).getroot())
            target = HERE / 'assets' / f'workflow_{name}_v9{tail}.svg'
            ET.ElementTree(root).write(target, encoding='utf-8', xml_declaration=True)
            if index == 0:
                target.with_suffix('.svgz').write_bytes(gzip.compress(target.read_bytes(), mtime=0))
                if not args.svg_only:
                    export(target, args.png_width)
        print(name + ': V9 built; removed 5 strips (38 horizontal segments)', flush=True)


if __name__ == '__main__':
    main()
