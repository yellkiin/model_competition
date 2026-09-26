#!/usr/bin/env python3
"""Verify exact edit scope, all four palettes, source preservation and exports."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import fitz
from PIL import Image
from build import HERE, NS, TAG, THEMES, SOURCE_HASHES, A_DY, TITLE_DY, PRIVATE_X, FILL_CURVE, find, erase, git_hash


def signature(node, colors=False):
    def clean(value):
        if colors:
            value = re.sub(r'#[0-9a-fA-F]{6}', '#COLOR', value)
            value = re.sub(r'v6-tip-[0-9a-fA-F]{6}', 'v6-tip-COLOR', value)
        return value
    attrs = tuple(sorted((k, clean(v)) for k, v in node.attrib.items() if not (colors and k == 'data-palette')))
    return node.tag, attrs, clean((node.text or '').strip()), tuple(signature(child, colors) for child in node)


def exact_scope(old, new):
    """Undo only the declared V7 changes, then compare every XML object to V6."""
    undo = deepcopy(new)
    undo.attrib.clear()
    undo.attrib.update(old.attrib)
    for ident in ('title', 'desc'):
        find(undo, ident).text = find(old, ident).text
    erase(undo, find(undo, 'v7-private-arrow'))
    links = find(old, 'section-links-v6')
    undo.insert(list(old).index(links), deepcopy(links))
    base = find(undo, 'source-a')
    group = find(base, 'base-diagram-v7')
    index = list(base).index(group)
    base.remove(group)
    for offset, child in enumerate(list(group)):
        base.insert(index + offset, child)
    pool_old = find(old, 'neighborhoods-v6')
    subtitle = find(old, 'selection-subtitle')
    find(undo, 'neighborhoods-v6').insert(list(pool_old).index(subtitle), deepcopy(subtitle))
    for ident in ('selection-principle', 'ddr-to-l2-fill', *(f'pipe-private-{i}' for i in range(4))):
        node = find(undo, ident)
        node.attrib.clear()
        node.attrib.update(find(old, ident).attrib)
    assert signature(undo) == signature(old), 'Undeclared SVG changes outside the five requested edits'


def main():
    rows, palette_signatures = [], {}
    reviewed_path = HERE / 'docs/REVIEWED_SVG_SHA256.json'
    reviewed = json.loads(reviewed_path.read_text()) if reviewed_path.exists() else None
    for name in THEMES:
        counts = []
        for index, tail in enumerate(('', '_editable')):
            old_path = HERE.parent / 'ink_v6/assets' / f'workflow_{name}_v6{tail}.svg'
            assert git_hash(old_path) == SOURCE_HASHES[name][index], 'V6 source changed'
            path = HERE / 'assets' / f'workflow_{name}_v7{tail}.svg'
            old, root = ET.parse(old_path).getroot(), ET.parse(path).getroot()
            exact_scope(old, root)
            assert root.get('data-version') == 'ink_v7' and root.get('data-input-version') == 'ink_v6'
            assert root.get('viewBox') == '0 235 3500 1550'
            ids = [n.get('id') for n in root.iter() if n.get('id')]
            assert len(ids) == len(set(ids)), 'Duplicate IDs'
            for node in root.iter():
                for value in node.attrib.values():
                    for target in re.findall(r'url\(#([^\)]+)\)', value):
                        assert target in ids, 'Broken reference: ' + target
            assert not root.findall('.//s:image', NS) and not root.findall('.//s:font', NS)
            assert all(ident not in ids for ident in ('section-01-to-02', 'section-02-to-03', 'selection-subtitle'))
            for ident in ('pool-to-complete-candidate', 'current-to-candidate', 'candidate-to-evaluation',
                          'evaluation-to-feedback', 'feedback-to-current'):
                find(root, ident)
            assert find(root, 'base-diagram-v7').get('transform') == f'translate(0,{A_DY:g})'
            assert 715 - 36 + A_DY == (594 + 925) / 2 == 759.5
            assert find(root, 'selection-principle').get('transform').startswith(f'translate(0,{TITLE_DY:g})')
            for i, x in enumerate(PRIVATE_X):
                arrow = find(root, f'pipe-private-{i}')
                assert arrow.get('d') == f'M{x},807 V821'
                assert arrow.get('marker-end') == 'url(#v7-private-arrow)'
            assert find(root, 'ddr-to-l2-fill').get('d') == FILL_CURVE
            assert find(root, 'ddr-to-l2-fill').get('stroke-dasharray') == '7 6'
            for letter in 'abcdef':
                find(root, 'source-' + letter)
            for letter, before in [('b', ('AD', 'BC')), ('c', ('ACD', 'B'))]:
                for which, lanes in [('before', before), ('after', ('ABD', 'C'))]:
                    state = find(root, f'{letter}-{which}-state')
                    assert (state.get('data-k1'), state.get('data-k2')) == lanes
            assert find(root, 'source-d').get('data-partition') == 'B1={o2};B2={o4};B1->B2'
            count = len(root.findall('.//s:text', NS))
            counts.append(count)
            assert count == (0 if index == 0 else 100)
            if index == 0:
                assert gzip.decompress(path.with_suffix('.svgz').read_bytes()) == path.read_bytes()
            sig = hashlib.sha256(repr(signature(root, colors=True)).encode()).hexdigest()
            if index not in palette_signatures:
                palette_signatures[index] = sig
            assert sig == palette_signatures[index], 'Geometry/text differ across colors'
            if reviewed:
                assert hashlib.sha256(path.read_bytes()).hexdigest() == reviewed[path.name], 'Published SVG differs from reviewed SVG'
        base = HERE / 'exports' / f'workflow_{name}_v7'
        with Image.open(base.with_suffix('.png')) as image:
            assert image.size == (6000, 2657)
        with Image.open(base.with_name(base.name + '_preview.png')) as image:
            assert image.size == (2100, 930)
        with fitz.open(base.with_suffix('.pdf')) as pdf:
            assert len(pdf) == 1 and not pdf[0].get_fonts() and not pdf[0].get_images()
        rows.append({'palette': name, 'five_requested_changes': 'PASS', 'exact_scope_reversal': 'PASS',
                     'unmodified_source_hashes': 'PASS', 'unchanged_scientific_content': 'PASS',
                     'a_and_b_c_graphics_center_y': 759.5, 'private_arrows': '4 straight downward arrows',
                     'portable_text_nodes': counts[0], 'editable_text_nodes': counts[1],
                     'pdf_pages': 1, 'pdf_fonts': 0, 'pdf_images': 0,
                     'png': [6000, 2657], 'preview': [2100, 930]})
    report = {'version': 'ink_v7', 'variants': rows, 'color_normalized_signatures': palette_signatures,
              'coverage_in_prose': {'Q1': 'abcd', 'Q2': 'abcde', 'Q3': 'abcdef'},
              'scope': 'Only ink_v7; no solver, experiment, existing paper or earlier figure changes.'}
    (HERE / 'docs').mkdir(exist_ok=True)
    (HERE / 'docs/OBJECT_REVIEW.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
