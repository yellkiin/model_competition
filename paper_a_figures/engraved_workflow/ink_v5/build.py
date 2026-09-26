#!/usr/bin/env python3
"""Deterministic, font-independent edits of the reviewed ink_v4 vector pair.

Only ink_v5 is written. The v4 source SVGs are checked against their published
Git blob hashes. New captions reuse SimSun outlines already in that drawing;
no font files, raster artwork, or new scientific performance data are supplied.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
SVG = 'http://www.w3.org/2000/svg'
NS = {'s': SVG}
TAG = lambda n: '{' + SVG + '}' + n
ET.register_namespace('', SVG)
ET.register_namespace('inkscape', 'http://www.inkscape.org/namespaces/inkscape')
THEMES = ('qinglu', 'qianjiang', 'yanlan', 'mono')
SOURCE_HASHES = {
    'mono': ('7139e7f139d321aa880df3eda64520c27270e67d', '95e046c9a5868f8a385c557da7dd2ef4317638c7'),
    'qinglu': ('a5790592567584a0ab05a375d2da06d61bf3b336', '4543866501547dc6a14231b9bec8e5d46d89e354'),
    'qianjiang': ('3dd7892492f6a5d1bb7246284d7eb698169290d4', '708a398b55bb5a3ad9dffa2e4a79c74afcd53c3f'),
    'yanlan': ('79f89be993b368eb47b010cae8ae528144742e37', '3608b338d93800fd3b720360f77528207a0675a9'),
}
CENTER_X = 516
COPY_CENTERS = {'out': 2210, 'in': 2334}
COPY_BASELINE = 958
CUBE_CENTER_Y = 1001
CUBE_SCALE = .78
MIGRATION_X = 1744.5
CANDIDATE_LABEL = '候选迁移'
SELECTION_LABEL = '完整评价后保留更优'


def find(root, ident):
    node = root.find(".//*[@id='" + ident + "']")
    if node is None:
        raise ValueError('Missing reviewed v4 object: ' + ident)
    return node


def git_hash(path):
    raw = path.read_bytes()
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def load_pair(source, name):
    paths = [source / 'assets' / f'workflow_{name}_v4{tail}.svg' for tail in ('', '_editable')]
    for path, expected in zip(paths, SOURCE_HASHES[name]):
        if git_hash(path) != expected:
            raise ValueError(f'Published v4 source changed: {path.name}; review before rebuilding')
    return ET.parse(paths[1]).getroot(), ET.parse(paths[0]).getroot()


def caption(atlas, parent, ident, value, x, y, size, portable, ink):
    node = atlas.chinese(parent, ident, value, x, y, size, False, portable)
    if portable:
        node.set('fill', ink)
    else:
        node.set('style', f"font-family:'SimSun',serif;fill:{ink}")
    node.set('data-purpose', 'candidate-not-global-optimum')
    return node


def apply(root, atlas, portable):
    # 1. Both connectors use the actual center of the existing 796-unit card.
    find(root, 'graph-to-partition').set('d', f'M{CENTER_X},911 V933')
    find(root, 'partition-to-cores').set('d', f'M{CENTER_X},1033 V1066')

    # 2. One label/cube pair inside each left-hand transfer arc. All COPY paths
    # retain their physical directions: private -> DDR (OUT), DDR -> private (IN).
    for kind, old_x in [('out', 2225), ('in', 2788)]:
        x = COPY_CENTERS[kind]
        label = find(root, f'copy-{kind}-label')
        label.set('transform', f'translate({x},{COPY_BASELINE}) translate(-{old_x},-946)')
        label.set('data-transfer-path', f'left-copy-{kind}')
        cube = find(root, f'copy-{kind}-tensor-v4')
        # Reviewed cube bounds are [-22,24] x [-27,20], so its visual center is
        # (1,-3.5). Align that center, rather than its uncentered local origin.
        cube.set('transform', f'translate({x-CUBE_SCALE:g},{CUBE_CENTER_Y+3.5*CUBE_SCALE:g}) scale({CUBE_SCALE})')
        cube.set('data-transfer-path', f'left-copy-{kind}')
        cube.set('data-label-id', f'copy-{kind}-label')

    # 3. Align the receiving B beneath its ghost. Translate all four native or
    # outlined pieces together, then use a vertical shaft and a symmetric head.
    group = find(root, 'source-structure')
    for node in list(group):
        is_b = (node.get('id') == 'text-063' or
                (node.tag == TAG('rect') and node.get('x') == '1677' and node.get('y') == '741') or
                (node.tag == TAG('path') and node.get('d') in
                 ('M1677,741l8,-8h69l-8,8Z', 'M1746,741l8,-8v46l-8,8Z')))
        if is_b:
            node.set('transform', 'translate(33,0) ' + node.get('transform', ''))
            node.set('data-part', 'migration-target-B')
        if node.tag == TAG('path') and node.get('d') == 'M1593,699H1940':
            # Leave a small gap around the crossing so the two relations are
            # not visually mistaken for a junction. No white masking object.
            node.set('d', 'M1593,699H1738.5 M1750.5,699H1940')
            node.set('id', 'migration-source-axis')
    migration = find(root, 'b-migration-v4')
    migration.set('d', f'M{MIGRATION_X},691 V719')
    migration.set('stroke-linecap', 'butt')
    migration.set('style', 'stroke-linecap:butt;stroke-linejoin:miter')
    migration.set('marker-end', 'url(#migration-arrowhead-v5)')
    migration.set('data-semantics', 'proposed-whole-subgraph-migration; acceptance-requires-full-evaluation')
    defs = root.find('s:defs', NS)
    # Shaft ends at the triangle base; the head extends 8 units to y727.
    # A shaft drawn all the way to the tip would protrude through its taper.
    marker = ET.SubElement(defs, TAG('marker'), {
        'id': 'migration-arrowhead-v5', 'viewBox': '0 0 10 10',
        'refX': '1', 'refY': '5', 'markerWidth': '10', 'markerHeight': '10',
        'markerUnits': 'userSpaceOnUse', 'orient': 'auto'})
    ET.SubElement(marker, TAG('path'), {
        'd': 'M1,1 L9,5 L1,9 Z', 'fill': migration.get('stroke'), 'stroke': 'none'})

    # 4. A migration or split is a candidate, not an optimality certificate.
    # Preserve the authentic whole-plan evaluation and incumbent-feedback loop.
    # The original four blocks provide no durations/bytes/config to prove an
    # optimum; therefore do not fabricate a different allegedly optimal layout.
    ink = find(root, 'v4-arrow-ink').find('s:path', NS).get('fill')
    caption(atlas, group, 'candidate-migration-label', CANDIDATE_LABEL,
            1830, 722, 20, portable, ink)
    caption(atlas, group, 'evaluated-selection-label', SELECTION_LABEL,
            1749, 899, 24, portable, ink)
    group.set('data-solution-status', 'illustrative-candidates-not-proven-optimal')
    group.find('s:title', NS).text = '结构候选：迁移、交换、切分；完整评价后仅保留可行且字典序更优的方案'

    # Namespace all inherited drawing IDs and their url references for v5.
    for node in root.iter():
        for key, value in list(node.attrib.items()):
            node.set(key, value.replace('-v4', '-v5').replace('v4-', 'v5-'))
    root.set('data-version', 'ink_v5')
    root.set('data-input-version', 'ink_v4')
    root.set('data-v5-changes', 'centered-connectors paired-copy-pictograms standard-migration-arrow candidate-selection-semantics')
    root.set('data-text-outlined', 'true' if portable else 'false')
    find(root, 'title').text = '图1.1 第五版：联合决策、多邻域协同与完整评价选优'
    find(root, 'desc').text = ('基于第四版四套既有配色：对齐划分框上下箭头，配对COPY标注与立方体，'
                              '规范迁移箭头；迁移和切分仅表示候选，完整执行评价后保留更优可行方案，'
                              '不宣称图示B迁移或任何有限预算结果已获全局最优证明。')


def export(svg, width):
    exe = shutil.which('inkscape')
    if not exe:
        raise RuntimeError('SVGs written; Inkscape is required for PDF/PNG exports')
    dest = HERE / 'exports'
    dest.mkdir(exist_ok=True)
    for suffix, opts in [('.pdf', []), ('.png', [f'--export-width={width}']),
                         ('_preview.png', ['--export-width=1800'])]:
        result = subprocess.run([exe, str(svg), f'--export-filename={dest/(svg.stem+suffix)}',
                                 '--export-area-page', '--export-background=white',
                                 '--export-background-opacity=1', *opts],
                                capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise RuntimeError(f'Export failed: {svg.name}{suffix}\n{result.stderr}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--palette', choices=THEMES, default='qinglu')
    parser.add_argument('--source', type=Path, default=HERE.parent/'ink_v4')
    parser.add_argument('--svg-only', action='store_true')
    parser.add_argument('--png-width', type=int, default=6000)
    args = parser.parse_args()
    if args.png_width <= 0:
        parser.error('--png-width must be positive')
    spec = importlib.util.spec_from_file_location('reviewed_v4_helpers', args.source/'build.py')
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    ed, portable = load_pair(args.source, 'mono')
    atlas = helpers.TextPair(ed, portable)
    for name in THEMES if args.all else [args.palette]:
        editable, outlined = load_pair(args.source, name)
        for root, tail, is_portable in [(editable, '_editable', False), (outlined, '', True)]:
            apply(root, atlas, is_portable)
            path = HERE/'assets'/f'workflow_{name}_v5{tail}.svg'
            path.parent.mkdir(exist_ok=True)
            ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)
            if is_portable:
                path.with_suffix('.svgz').write_bytes(gzip.compress(path.read_bytes(), mtime=0))
                if not args.svg_only:
                    export(path, args.png_width)
        print(f'{name}: editable SVG, portable SVG/SVGZ' + ('' if args.svg_only else ', PDF, PNG, preview'), flush=True)


if __name__ == '__main__':
    main()
