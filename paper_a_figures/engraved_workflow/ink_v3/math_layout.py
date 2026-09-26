#!/usr/bin/env python3
"""Typeset this figure's math with the paper's Computer Modern (LaTeX 12 pt).

The cache contains rendered formula paths, never font files. It allows later
rebuilds without TeX. Delete assets/math_layout.json to regenerate with pdflatex
and PyMuPDF. Geometry remains vectors; data-tex records the editable expression.
"""
from __future__ import annotations
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

S = 'http://www.w3.org/2000/svg'
X = 'http://www.w3.org/1999/xlink'
NS = {'s': S}
HERE = Path(__file__).resolve().parent
SUB = str.maketrans('₀₁₂₃₄₅₆₇₈₉ₜ', '0123456789t')


def math_runs(node: ET.Element) -> list[tuple[str, str]] | None:
    """A run is ('text', literal) or ('math', LaTeX)."""
    value = ''.join(node.itertext()).strip()
    ident = node.get('id')
    if ident == 'makespan-v3':
        return [('math', r'C_q(y)=\max_j f_j')]
    if ident in ('text-104', 'text-113'):
        return [('text', '核心 '), ('math', 'k_' + ('1' if ident == 'text-104' else '2'))]
    if ident == 'graph-definition':
        return [('math', r'G=(T\cup O,E)')]
    if ident == 'partition-expression':
        return [('math', r'\mathcal{P}=\{A,B,C,D\}')]
    if value == 'x = (𝒫, a, π)':
        return [('math', r'x=(\mathcal{P},a,\pi)')]
    if value.startswith('完整候选 y'):
        return [('text', '完整候选 '), ('math', r'y=(\mathcal{P}^{\prime},a^{\prime},\pi^{\prime})')]
    if value.startswith('核心映射 a'):
        return [('text', '核心映射 '), ('math', 'a'), ('text', '  ·  核内顺序 '), ('math', r'\pi')]
    if value == 'B = {o₂, o₄}':
        return [('math', r'B=\{o_2,o_4\}')]
    if value == 'B₁ | B₂':
        return [('math', r'B_1\mid B_2')]
    if re.fullmatch(r'[tokfes]′?[₀₁₂₃₄₅₆₇₈₉ₜ]', value):
        letter = value[0]
        prime = r'^{\prime}' if '′' in value else ''
        return [('math', letter + prime + '_{' + value[-1].translate(SUB) + '}')]
    return None


def compile_formula(tex: str) -> dict:
    if not shutil.which('pdflatex'):
        raise RuntimeError('Missing cached formula. Install pdflatex and PyMuPDF, or retain assets/math_layout.json.')
    import fitz
    source = r'''\documentclass[12pt]{article}
\usepackage{amsmath,amssymb}
\pagestyle{empty}
\begin{document}
\pdfhorigin=0pt\pdfvorigin=0pt
\setbox0=\hbox{$''' + tex + r'''$}
\pdfpagewidth=\wd0\pdfpageheight=\dimexpr\ht0+\dp0\relax
\shipout\vbox{\offinterlineskip\hbox{\box0}}
\end{document}
'''
    with tempfile.TemporaryDirectory(prefix='ink-v3-math-') as td:
        folder = Path(td)
        (folder / 'formula.tex').write_text(source, encoding='utf-8')
        run = subprocess.run(['pdflatex', '-interaction=batchmode', '-halt-on-error', 'formula.tex'],
                             cwd=folder, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        if run.returncode:
            raise RuntimeError(f'LaTeX failed for {tex}: ' + (folder/'formula.log').read_text(errors='replace')[-3000:])
        doc = fitz.open(folder / 'formula.pdf')
        page = doc[0]
        trace = page.get_texttrace()
        first = next(t for t in trace if t['chars'])
        baseline = first['chars'][0][2][1]
        ref_em = first['size']
        svg = ET.fromstring(page.get_svg_image(text_as_path=True))
        definitions = {e.get('id'): e for e in svg.findall('s:defs/*', NS)}
        paths = []
        for use in svg.findall('s:use', NS):
            path = definitions[use.get('{' + X + '}href').removeprefix('#')]
            paths.append({'d': path.get('d'), 'transform': use.get('transform', '')})
        if not paths:
            raise RuntimeError(f'No math vector paths: {tex}')
        return {'tex': tex, 'width': page.rect.width, 'baseline': baseline, 'em': ref_em,
                'fonts': sorted({t['font'] for t in trace}), 'paths': paths}


def text_advance(value: str, size: float) -> float:
    return sum((1.0 if ord(c) > 0x2fff else .25) * size for c in value)


def apply_math(root: ET.Element, cache_path: Path | None = None) -> None:
    cache_path = cache_path or HERE / 'assets' / 'math_layout.json'
    cache = json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
    for parent in list(root.iter()):
        for node in list(parent):
            if node.tag != '{' + S + '}text':
                continue
            runs = math_runs(node)
            if runs is None:
                continue
            size = float(node.get('font-size', '28'))
            widths = []
            for kind, value in runs:
                if kind == 'math':
                    if value not in cache:
                        cache[value] = compile_formula(value)
                    item = cache[value]
                    widths.append(item['width'] * size / item['em'])
                else:
                    widths.append(text_advance(value, size))
            width = sum(widths)
            x, y = float(node.get('x', '0')), float(node.get('y', '0'))
            anchor = node.get('text-anchor', 'start')
            x -= width / 2 if anchor == 'middle' else width if anchor == 'end' else 0
            attrs = {k: v for k, v in node.attrib.items() if k in ('id', 'class', 'opacity')}
            attrs.update({'data-label': ''.join(node.itertext()), 'data-tex': ' | '.join(v for k,v in runs if k=='math'),
                          'data-math-fonts': 'Computer Modern', 'transform': f'translate({x:.6f},{y:.6f})',
                          'fill': '#232323', 'stroke': 'none'})
            group = ET.Element('{' + S + '}g', attrs)
            pos = 0.0
            for (kind, value), advance in zip(runs, widths):
                if kind == 'text':
                    t = ET.SubElement(group, '{' + S + '}text', {'x':f'{pos:.6f}', 'y':'0', 'font-size':str(size),
                                                               'class':node.get('class', ''), 'xml:space':'preserve'})
                    t.text = value
                else:
                    item = cache[value]
                    scale = size / item['em']
                    g = ET.SubElement(group, '{' + S + '}g',
                        {'transform': f'translate({pos:.6f},0) scale({scale:.8f}) translate(0,{-item["baseline"]:.6f})'})
                    for path in item['paths']:
                        ET.SubElement(g, '{' + S + '}path', path)
                pos += advance
            index = list(parent).index(node)
            parent.remove(node)
            parent.insert(index, group)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
