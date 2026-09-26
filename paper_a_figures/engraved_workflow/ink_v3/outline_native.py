#!/usr/bin/env python3
"""Convert only this figure's text into editable vector paths using native fonts.

Requires locally licensed SimSun and Times New Roman. No fonts are bundled,
extracted, uploaded, or silently substituted. The editable SVG is kept beside
the portable SVG. Computer Modern equations are already paths from math_layout.
"""
from __future__ import annotations
import argparse
import gzip
import json
import os
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET
from fontTools.ttLib import TTFont, TTCollection
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

SVG = 'http://www.w3.org/2000/svg'
NS = {'s': SVG}
ET.register_namespace('', SVG)
HERE = Path(__file__).resolve().parent


class NativeFonts:
    def __init__(self, folder: Path):
        needed = [folder / n for n in ('simsun.ttc', 'times.ttf', 'timesbd.ttf')]
        if not all(p.is_file() for p in needed):
            raise RuntimeError('Exact paper fonts required: simsun.ttc, times.ttf, timesbd.ttf. '
                               'Use Windows Fonts or --font-dir with your locally licensed fonts; no fallback is allowed.')
        collection = TTCollection(needed[0])
        song = next(f for f in collection.fonts if f['name'].getDebugName(1) == 'SimSun')
        self.fonts = {'SimSun': song, 'Times New Roman': TTFont(needed[1]),
                      'Times New Roman Bold': TTFont(needed[2])}
        self.cache = {}

    def glyph(self, char: str, bold: bool):
        family = 'SimSun' if ord(char) >= 0x2e80 or char == '—' else ('Times New Roman Bold' if bold else 'Times New Roman')
        font = self.fonts[family]
        key = (family, char)
        if key not in self.cache:
            glyph = font.getBestCmap().get(ord(char))
            if glyph is None:
                raise ValueError(f'{family} has no glyph for U+{ord(char):04X} {char!r}')
            self.cache[key] = (font.getGlyphSet(), glyph, font['hmtx'][glyph][0], font['head'].unitsPerEm, family)
        return self.cache[key]


def css_fill(root: ET.Element, classes: str) -> str:
    result = '#232323'
    wanted = set(classes.split())
    for style in root.findall('.//s:style', NS):
        for selector, body in re.findall(r'([^{}]+)\{([^{}]+)\}', style.text or ''):
            fill = re.search(r'(?:^|;)\s*fill\s*:\s*([^;]+)', body)
            if not fill:
                continue
            selectors = [s.strip() for s in selector.split(',')]
            if 'text' in selectors or any('.' + c in selectors for c in wanted):
                result = fill.group(1).strip()
    return result


def outline(svg: Path, fonts: NativeFonts) -> dict:
    root = ET.parse(svg).getroot()
    if root.get('data-text-outlined') == 'true':
        return {'file': svg.name, 'status': 'already outlined'}
    editable = svg.with_name(svg.stem + '_editable.svg')
    shutil.copyfile(svg, editable)
    labels = []
    for parent in list(root.iter()):
        for node in list(parent):
            if node.tag != '{' + SVG + '}text':
                continue
            if len(node):
                raise ValueError('Unresolved mixed text; run finalize_v3.py first: ' + str(node.attrib))
            value = node.text or ''
            size = float(node.get('font-size', '28'))
            classes = node.get('class', '')
            bold = 'bold' in classes.split() or node.get('font-weight') in ('bold', '700')
            fill = css_fill(root, classes)
            glyphs = [fonts.glyph(c, bold) for c in value]
            width = sum(advance / upem * size for _, _, advance, upem, _ in glyphs)
            x, y = float(node.get('x', '0')), float(node.get('y', '0'))
            anchor = node.get('text-anchor', 'start')
            x -= width/2 if anchor == 'middle' else width if anchor == 'end' else 0
            attrs = {k:v for k,v in node.attrib.items() if k in ('id', 'transform', 'opacity')}
            attrs.update({'data-label':value, 'data-fonts':','.join(sorted({g[4] for g in glyphs})),
                          'data-anchor':anchor, 'data-width':f'{width:.6f}', 'fill':fill, 'stroke':'none'})
            group = ET.Element('{' + SVG + '}g', attrs)
            paths = []
            for char, (glyphset, name, advance, upem, family) in zip(value, glyphs):
                pen = SVGPathPen(glyphset)
                scale = size/upem
                glyphset[name].draw(TransformPen(pen, (scale,0,0,-scale,x,y)))
                d = pen.getCommands()
                if d:
                    path = {'d':d}
                    if bold and family == 'SimSun':
                        path.update({'stroke':fill, 'stroke-width':f'{size*.018:.6f}', 'stroke-linejoin':'round'})
                    paths.append(path)
                x += advance/upem*size
            if 'halo' in classes.split():
                halo = ET.SubElement(group, '{'+SVG+'}g', {'fill':'white', 'stroke':'white', 'stroke-width':'7',
                                                        'stroke-linejoin':'round', 'aria-hidden':'true'})
                for path in paths:
                    ET.SubElement(halo, '{'+SVG+'}path', {'d':path['d']})
            foreground = ET.SubElement(group, '{'+SVG+'}g', {'stroke':'none'})
            for path in paths:
                ET.SubElement(foreground, '{'+SVG+'}path', path)
            parent.insert(list(parent).index(node), group)
            parent.remove(node)
            labels.append({'id':attrs.get('id'), 'text':value, 'fonts':attrs['data-fonts'], 'width':round(width,4)})
    root.set('data-text-outlined', 'true')
    root.set('data-paper-fonts', 'SimSun;Times New Roman;Computer Modern')
    ET.indent(root, space='  ')
    ET.ElementTree(root).write(svg, encoding='utf-8', xml_declaration=True)
    with svg.with_suffix('.svgz').open('wb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as z:
            z.write(svg.read_bytes())
    return {'file':svg.name,'editable_file':editable.name,'fonts':['SimSun','Times New Roman','Computer Modern'],
            'fallback_fonts':[], 'font_files_bundled':False, 'labels':labels}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, default=HERE)
    p.add_argument('--font-dir', type=Path, default=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts')
    p.add_argument('--palettes', nargs='+', default=['mono','qinglu'])
    a = p.parse_args()
    fonts = NativeFonts(a.font_dir)
    receipts = [outline(a.out/'assets'/f'workflow_{name}_v3.svg', fonts) for name in a.palettes]
    (a.out/'docs').mkdir(parents=True, exist_ok=True)
    (a.out/'docs'/'FONT_AUDIT.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__ == '__main__':
    main()
