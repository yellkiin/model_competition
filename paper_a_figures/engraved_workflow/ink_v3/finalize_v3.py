#!/usr/bin/env python3
"""Finalize Figure 1.1 v3 after the ink_v2-based generator runs.

This pass keeps the PR's original build.py as the geometric source of truth and
applies typography/alignment corrections requested during review. It is safe to
run repeatedly. Python 3.10+; Inkscape is needed unless --no-export is used.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
SVG = 'http://www.w3.org/2000/svg'
XML = 'http://www.w3.org/XML/1998/namespace'
ET.register_namespace('', SVG)
NS = {'s': SVG}
PALETTES = ('mono', 'qinglu', 'qianjiang', 'yanlan')


def tag(name: str) -> str:
    return '{' + SVG + '}' + name


def find(root: ET.Element, ident: str) -> ET.Element:
    node = root.find('.//*[@id="' + ident + '"]')
    if node is None:
        raise ValueError(f'Missing SVG object: {ident}')
    return node


def set_attrs(node: ET.Element, **attrs: object) -> None:
    for key, value in attrs.items():
        key = 'class' if key == 'class_' else key.replace('_', '-')
        node.set(key, str(value))


def set_plain_text(node: ET.Element, value: str, **attrs: object) -> None:
    for child in list(node):
        node.remove(child)
    node.text = value
    set_attrs(node, **attrs)


def ensure_font_style(root: ET.Element) -> None:
    defs = root.find('s:defs', NS)
    if defs is None:
        raise ValueError('Missing SVG defs')
    old = defs.find('.//*[@id="paper-font-fix"]')
    if old is not None:
        defs.remove(old)
    style = ET.SubElement(defs, tag('style'), {'id': 'paper-font-fix'})
    style.text = """
/* workshop_v2 typography: Times-style Latin, Song-style Chinese, STIX math. */
text {font-family:'Times New Roman','SimSun','Liberation Serif','Tinos','Noto Serif CJK SC','Songti SC',serif;}
.serif {font-family:'Times New Roman','Liberation Serif','Tinos','Noto Serif CJK SC','SimSun','Songti SC',serif;}
.math {font-family:'STIX Math','STIX','Cambria Math','Times New Roman','Liberation Serif','Tinos',serif;}
"""


def ensure_graph_definition(root: ET.Element) -> None:
    joint = find(root, 'joint-decision-v3')
    existing = root.find('.//*[@id="graph-definition"]')
    if existing is None:
        existing = ET.SubElement(joint, tag('text'), {'id': 'graph-definition'})
    set_plain_text(
        existing,
        'G = (T ∪ O, E)',
        x=914,
        y=380,
        font_size=32,
        text_anchor='end',
        class_='math',
    )


def normalize_b(root: ET.Element) -> None:
    graph = find(root, 'bipartite-example')
    for path in graph.iter(tag('path')):
        if 'structure-hatch' in path.get('style', ''):
            path.attrib.pop('style', None)
            break
    set_attrs(find(root, 'text-024'), class_='serif')

    targets = {
        ('430', '1084'): 'text-031',
        ('1677', '741'): 'text-063',
        ('2572', '453'): 'text-114',
    }
    found: set[tuple[str, str]] = set()
    for rect in root.iter(tag('rect')):
        key = (rect.get('x', ''), rect.get('y', ''))
        if key in targets:
            rect.set('class', 'paper')
            rect.attrib.pop('style', None)
            found.add(key)
    missing = set(targets) - found
    if missing:
        raise ValueError(f'Missing B rectangles: {sorted(missing)}')
    for label in targets.values():
        set_attrs(find(root, label), class_='math')

    for node in root.iter(tag('text')):
        if ''.join(node.itertext()).strip() in {'候选示意：B 迁至 k₂', '候选示意：B 迁至 k2'}:
            set_plain_text(node, '候选示意：迁移 B', font_size=29, class_='bold')


def set_core_label(node: ET.Element, index: int, x: int) -> None:
    for child in list(node):
        node.remove(child)
    set_attrs(node, x=x, y=424, font_size=30, text_anchor='middle', class_='bold')
    node.text = '核心 '
    k = ET.SubElement(node, tag('tspan'), {'class': 'math'})
    k.text = 'k'
    sub = ET.SubElement(
        node,
        tag('tspan'),
        {'baseline-shift': 'sub', 'font-size': '70%', 'class': 'math'},
    )
    sub.text = str(index)
    node.set('{' + XML + '}space', 'preserve')
    node.set('data-tight-text', 'true')


def align_execution_labels(root: ET.Element) -> None:
    set_core_label(find(root, 'text-104'), 1, 2272)
    set_core_label(find(root, 'text-113'), 2, 2687)
    set_plain_text(
        find(root, 'text-122'),
        'COPY_OUT',
        x=2190,
        y=946,
        font_size=22,
        text_anchor='middle',
        class_='serif halo',
    )
    set_plain_text(
        find(root, 'text-123'),
        'COPY_IN',
        x=2821,
        y=946,
        font_size=22,
        text_anchor='middle',
        class_='serif halo',
    )


def fix_makespan_formula(root: ET.Element) -> None:
    formula = find(root, 'makespan-v3')
    for child in list(formula):
        formula.remove(child)
    set_attrs(formula, x=2497, y=1458, font_size=36, text_anchor='middle', class_='math')
    formula.text = 'C'
    formula.set('{' + XML + '}space', 'preserve')
    formula.set('data-tight-text', 'true')
    ET.SubElement(formula, tag('tspan'), {'baseline-shift': 'sub', 'font-size': '70%'}).text = 'q'
    ET.SubElement(formula, tag('tspan')).text = '(y) = '
    ET.SubElement(formula, tag('tspan'), {'font-style': 'normal'}).text = 'max'
    ET.SubElement(formula, tag('tspan'), {'baseline-shift': 'sub', 'font-size': '70%'}).text = 'j'
    ET.SubElement(formula, tag('tspan')).text = ' f'
    ET.SubElement(formula, tag('tspan'), {'baseline-shift': 'sub', 'font-size': '70%'}).text = 'j'


def remove_bottom_q3_note(root: ET.Element) -> None:
    for parent in root.iter():
        for child in list(parent):
            if child.tag == tag('text') and '固定同一方案' in ''.join(child.itertext()):
                parent.remove(child)
    for node in root.iter(tag('text')):
        if ''.join(node.itertext()).strip().startswith('输出：调度方案'):
            node.set('y', '1771')


def tighten_mixed_text(root: ET.Element) -> None:
    for node in root.findall('.//*[@data-tight-text="true"]'):
        for child in list(node):
            child.tail = ''


def write_svg(root: ET.Element, svg: Path) -> None:
    ET.indent(root, space='  ')
    tighten_mixed_text(root)
    ET.ElementTree(root).write(svg, encoding='utf-8', xml_declaration=True)
    svgz = svg.with_suffix('.svgz')
    with svgz.open('wb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as compressed:
            compressed.write(svg.read_bytes())


def export(svg: Path, out_dir: Path, width: int) -> None:
    inkscape = shutil.which('inkscape')
    if not inkscape:
        raise RuntimeError('Final SVG is ready; install Inkscape to export PDF and PNG.')
    exports = out_dir / 'exports'
    exports.mkdir(parents=True, exist_ok=True)
    jobs = [
        (exports / f'{svg.stem}.pdf', ['--export-text-to-path']),
        (exports / f'{svg.stem}.png', [f'--export-width={width}']),
        (exports / f'{svg.stem}_preview.png', ['--export-width=1800']),
    ]
    for target, extra in jobs:
        cmd = [
            inkscape,
            str(svg),
            f'--export-filename={target}',
            '--export-area-page',
            '--export-background=white',
            '--export-background-opacity=1',
            *extra,
        ]
        run = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
        if run.returncode:
            raise RuntimeError(run.stderr)


def update_build_info(out_dir: Path, palettes: list[str]) -> None:
    info_path = out_dir / 'BUILD_INFO.json'
    data: dict[str, object] = {}
    if info_path.exists():
        data = json.loads(info_path.read_text(encoding='utf-8'))
    data.update(
        {
            'finalizer': 'finalize_v3.py',
            'palettes': palettes,
            'bottom_q3_note_removed': True,
            'b_highlight_removed': True,
            'b_operation_label': '迁移 B',
            'font_alignment': 'workshop_v2 Times/SimSun-compatible text with STIX mathematics',
            'alignment_fixes': ['graph definition', 'core labels', 'COPY_IN', 'COPY_OUT', 'makespan formula'],
        }
    )
    info_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def finalize(svg: Path, out_dir: Path, do_export: bool, width: int) -> None:
    root = ET.parse(svg).getroot()
    ensure_font_style(root)
    ensure_graph_definition(root)
    normalize_b(root)
    align_execution_labels(root)
    fix_makespan_formula(root)
    remove_bottom_q3_note(root)
    write_svg(root, svg)
    if do_export:
        export(svg, out_dir, width)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=HERE)
    parser.add_argument('--palettes', nargs='+', choices=PALETTES, default=['mono', 'qinglu'])
    parser.add_argument('--png-width', type=int, default=6000)
    parser.add_argument('--no-export', action='store_true')
    args = parser.parse_args()
    if args.png_width < 1200:
        parser.error('png-width must be at least 1200')
    for name in args.palettes:
        svg = args.out / 'assets' / f'workflow_{name}_v3.svg'
        if not svg.exists():
            raise FileNotFoundError(f'Run build.py --svg-only first: {svg}')
        finalize(svg, args.out, not args.no_export, args.png_width)
        print(svg)
    update_build_info(args.out, args.palettes)


if __name__ == '__main__':
    main()
