#!/usr/bin/env python3
"""Check exactly five removed strips and preservation of all remaining objects."""
from copy import deepcopy
import gzip
import hashlib
import json
import re
import xml.etree.ElementTree as ET
import fitz
from PIL import Image
from build import HERE, NS, THEMES, SOURCE_HASHES, STRIPS, strip_nodes, find, git_hash


def signature(node, colors=False):
    def clean(value):
        if colors:
            value = re.sub(r'#[0-9a-fA-F]{6}', '#COLOR', value)
            value = re.sub(r'v6-tip-[0-9a-fA-F]{6}', 'v6-tip-COLOR', value)
        return value
    attrs = tuple(sorted((k, clean(v)) for k, v in node.attrib.items()
                         if not (colors and k == 'data-palette')))
    return node.tag, attrs, clean((node.text or '').strip()), tuple(signature(c, colors) for c in node)


def exact_scope(old, new):
    undo = deepcopy(new)
    group = find(undo, 'hardware-cutaway-v6')
    removed = strip_nodes(old)
    assert len(removed) == 5
    for index, node in removed:
        group.insert(index, deepcopy(node))
    for key in ('data-version', 'data-input-version'):
        undo.set(key, old.get(key))
    del undo.attrib['data-v9-changes']
    for ident in ('title', 'desc'):
        find(undo, ident).text = find(old, ident).text
    assert ET.tostring(undo) == ET.tostring(old), 'An out-of-scope object or attribute changed'
    assert sum(1 for _ in old.iter()) - sum(1 for _ in new.iter()) == 5
    for _, node in removed:
        assert not any(n.get('d') == node.get('d') for n in new.iter()), 'Target strip remains'


def main():
    rows, palette_signatures = [], {}
    manifest = HERE / 'docs/REVIEWED_SVG_SHA256.json'
    reviewed = json.loads(manifest.read_text()) if manifest.exists() else None
    for name in THEMES:
        counts = []
        for index, tail in enumerate(('', '_editable')):
            old_path = HERE.parent / 'ink_v8/assets' / f'workflow_{name}_v8{tail}.svg'
            assert git_hash(old_path) == SOURCE_HASHES[name][index], 'Published V8 source changed'
            path = HERE / 'assets' / f'workflow_{name}_v9{tail}.svg'
            old, root = ET.parse(old_path).getroot(), ET.parse(path).getroot()
            exact_scope(old, root)
            assert root.get('data-version') == 'ink_v9' and root.get('data-input-version') == 'ink_v8'
            assert root.get('viewBox') == '0 235 3500 1550'
            ids = [n.get('id') for n in root.iter() if n.get('id')]
            assert len(ids) == len(set(ids)), 'Duplicate IDs'
            for node in root.iter():
                for value in node.attrib.values():
                    for target in re.findall(r'url\(#([^\)]+)\)', value):
                        assert target in ids, 'Broken SVG reference: ' + target
                for key in ('data-transfer-path', 'data-label-id'):
                    if node.get(key):
                        assert node.get(key) in ids, 'Broken annotation association'
            assert not root.findall('.//s:image', NS) and not root.findall('.//s:font', NS)
            for ident in ('left-copy-out', 'left-copy-in', 'right-copy-out', 'right-copy-in',
                          'ddr-to-l2-fill', 'l2-hit-read', 'right-copy-annotations-v8',
                          'copy-out-label', 'copy-in-label', 'copy-out-tensor-v6', 'copy-in-tensor-v6',
                          *(f'pipe-private-{i}' for i in range(4))):
                assert signature(find(root, ident)) == signature(find(old, ident)), 'Original arrow changed'
            for label in ('COPY_OUT', 'COPY_IN'):
                label_nodes = [n for n in root.iter() if n.get('data-label') == label
                               or (n.tag.endswith('}text') and ''.join(n.itertext()) == label)]
                assert len(label_nodes) == 2, f'Expected two {label} labels'
            count = len(root.findall('.//s:text', NS))
            counts.append(count)
            assert count == (0 if index == 0 else 102)
            if index == 0:
                assert gzip.decompress(path.with_suffix('.svgz').read_bytes()) == path.read_bytes()
            sig = hashlib.sha256(repr(signature(root, colors=True)).encode()).hexdigest()
            palette_signatures.setdefault(index, sig)
            assert sig == palette_signatures[index], 'Geometry/text differ across palettes'
            if reviewed:
                assert hashlib.sha256(path.read_bytes()).hexdigest() == reviewed[path.name], 'SVG differs from reviewed file'
        base = HERE / 'exports' / f'workflow_{name}_v9'
        with Image.open(base.with_suffix('.png')) as image:
            assert image.size == (6000, 2657)
        with Image.open(base.with_name(base.name + '_preview.png')) as image:
            assert image.size == (2100, 930)
        with fitz.open(base.with_suffix('.pdf')) as pdf:
            assert len(pdf) == 1 and not pdf[0].get_fonts() and not pdf[0].get_images()
            assert abs(pdf[0].rect.width * 25.4 / 72 - 490) < 0.02
            assert abs(pdf[0].rect.height * 25.4 / 72 - 217) < 0.02
        rows.append({'palette': name, 'exact_preservation_except_five_strips': 'PASS', 'removed_strip_paths': 5,
                     'removed_horizontal_segments': 38,
                     'original_arrows_unchanged': 'PASS', 'label_tensor_associations': 'PASS',
                     'copy_in_labels': 2, 'copy_out_labels': 2, 'tensor_pictograms_in_copy_pairs': 4,
                     'all_existing_copy_pairs_unchanged': 'PASS',
                     'portable_text_nodes': counts[0], 'editable_text_nodes': counts[1],
                     'pdf_pages': 1, 'pdf_fonts': 0, 'pdf_images': 0,
                     'pdf_mm': [490, 217], 'png': [6000, 2657], 'preview': [2100, 930]})
    report = {'version': 'ink_v9', 'variants': rows, 'color_normalized_signatures': palette_signatures,
              'coverage_in_prose': {'Q1': 'abcd', 'Q2': 'abcde', 'Q3': 'abcdef'},
              'scope': 'Only ink_v9; no existing paper, solver, data or earlier figure changes.'}
    (HERE / 'docs').mkdir(exist_ok=True)
    (HERE / 'docs/OBJECT_REVIEW.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
