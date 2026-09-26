#!/usr/bin/env python3
"""Add only the right-hand COPY labels and tensor pictograms to published V7.

Both the outlined and editable SVGs retain all existing objects. New objects
are exact copies of the left-hand annotations, translated horizontally.
No original arrow, font, palette, layout or scientific content is changed.
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

HERE = Path(__file__).resolve().parent
SVG = 'http://www.w3.org/2000/svg'
NS = {'s': SVG}
TAG = lambda name: '{' + SVG + '}' + name
ET.register_namespace('', SVG)
ET.register_namespace('inkscape', 'http://www.inkscape.org/namespaces/inkscape')
THEMES = ('qinglu', 'qianjiang', 'yanlan', 'mono')
SOURCE_HASHES = {
    'qinglu': ('88384ab6a287578de4185866440382b9b1b9ad0d', '9eb2dde749a33fabed0f991c03ba341a674f0db3'),
    'qianjiang': ('e6dddf0b629d7f507fd008745c781536b6670ea8', 'fd5c6b8b654b96956b40dc03d8a2b99c9dd41d0a'),
    'yanlan': ('aefdcf05b89223a882ffffc0da3a32e31b8b1c9e', '15e6bbe87ea6b3648495871dbac101f38248cf44'),
    'mono': ('93ce3a9a6cdb05edb8201465928069427f5da2ca', 'd432a9c853ff3d6ee7801e80ee55ae92f856cf91'),
}
# The existing right COPY arcs are offset about 432 units from the left arcs.
# Keep their geometry intact, including their slightly different curvature.
# Translate annotations only: labels remain at y=958; both cubes keep size .78.
COPY_DX = 432
COPIES = (
    ('copy-out-label', 'right-copy-out-label-v8', 'right-copy-out'),
    ('copy-in-label', 'right-copy-in-label-v8', 'right-copy-in'),
    ('copy-out-tensor-v6', 'right-copy-out-tensor-v8', 'right-copy-out'),
    ('copy-in-tensor-v6', 'right-copy-in-tensor-v8', 'right-copy-in'),
)


def find(root: ET.Element, ident: str) -> ET.Element:
    node = root.find(".//*[@id='" + ident + "']")
    if node is None:
        raise ValueError('Missing expected SVG object: ' + ident)
    return node


def git_hash(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def apply(root: ET.Element) -> ET.Element:
    if root.get('data-version') != 'ink_v7':
        raise ValueError('Input must be published ink_v7, not an already edited output')
    group = ET.Element(TAG('g'), {
        'id': 'right-copy-annotations-v8', 'transform': f'translate({COPY_DX},0)',
        'data-source': 'left-copy-annotations',
    })
    label_map = {'copy-out-label': 'right-copy-out-label-v8',
                 'copy-in-label': 'right-copy-in-label-v8'}
    for source_id, target_id, arrow_id in COPIES:
        source = find(root, source_id)
        # Published source objects have no descendant IDs. Fail rather than
        # accidentally duplicate IDs if someone changes the input later.
        if any(child.get('id') for child in source.iter() if child is not source):
            raise ValueError('Unexpected child IDs in ' + source_id)
        node = copy.deepcopy(source)
        node.set('id', target_id)
        node.set('data-transfer-path', arrow_id)
        if node.get('data-label-id'):
            node.set('data-label-id', label_map[node.get('data-label-id')])
        group.append(node)
    find(root, 'hardware-cutaway-v6').append(group)
    root.set('data-version', 'ink_v8')
    root.set('data-input-version', 'ink_v7')
    root.set('data-v8-changes', 'right-copy-labels-and-tensor-pictograms-only')
    find(root, 'title').text = '图1.1 第八版：联合决策、子图切分与归核、统一执行评价'
    find(root, 'desc').text = (
        '基于第七版，仅在右侧核心与DDR之间的既有箭头处补充COPY_OUT、COPY_IN文字及对应小立方体。'
        '新增标注直接复制左侧原有对象，仅水平平移；左右均为写出和读入的对应示意。'
        '保留全部原有对象、箭头、布局、字体与配色。a至f为候选操作示意而非串行阶段；'
        '当前最优仅指已评价可行候选中的最好结果。'
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
    parser.add_argument('--source', type=Path, default=HERE.parent / 'ink_v7')
    parser.add_argument('--svg-only', action='store_true')
    parser.add_argument('--png-width', type=int, default=6000)
    args = parser.parse_args()
    if args.png_width <= 0:
        parser.error('PNG width must be positive')
    (HERE / 'assets').mkdir(exist_ok=True)
    for name in THEMES if args.all else [args.palette]:
        for index, tail in enumerate(('', '_editable')):
            source = args.source / 'assets' / f'workflow_{name}_v7{tail}.svg'
            if git_hash(source) != SOURCE_HASHES[name][index]:
                raise ValueError('Published V7 source has changed: ' + str(source))
            root = apply(ET.parse(source).getroot())
            target = HERE / 'assets' / f'workflow_{name}_v8{tail}.svg'
            ET.ElementTree(root).write(target, encoding='utf-8', xml_declaration=True)
            if index == 0:
                target.with_suffix('.svgz').write_bytes(gzip.compress(target.read_bytes(), mtime=0))
                if not args.svg_only:
                    export(target, args.png_width)
        print(name + ': V8 built', flush=True)


if __name__ == '__main__':
    main()
