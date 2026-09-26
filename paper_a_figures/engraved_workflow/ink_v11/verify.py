#!/usr/bin/env python3
"""Object, typography, palette, vector-export and same-renderer pixel checks."""
from __future__ import annotations
import copy
import gzip
import hashlib
import json
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
import fitz
from PIL import Image, ImageChops
from build import HERE, NS, THEMES, SOURCE_HASHES, OLD_IDS, LABEL, find, git_hash


def canonical(root):
    return ET.tostring(root, encoding='unicode')


def restore(v11, v9):
    restored = copy.deepcopy(v11)
    hardware = find(restored, 'hardware-cutaway-v6')
    new = find(restored, 'l2-hit-label-v11')
    index = list(hardware).index(new)
    hardware.remove(new)
    original = find(v9, 'hardware-cutaway-v6')
    old_indices = [list(original).index(find(v9, ident)) for ident in OLD_IDS]
    assert old_indices == list(range(index, index + 3))
    for offset, ident in enumerate(OLD_IDS):
        hardware.insert(index + offset, copy.deepcopy(find(v9, ident)))
    restored.attrib = dict(v9.attrib)
    for ident in ('title', 'desc'):
        find(restored, ident).text = find(v9, ident).text
    return restored


def main():
    rows, normalized, hashes = [], {}, {}
    for theme in THEMES:
        row = {'palette': theme}
        for index, tail in enumerate(('', '_editable')):
            original = HERE.parent/'ink_v9/assets'/f'workflow_{theme}_v9{tail}.svg'
            target = HERE/'assets'/f'workflow_{theme}_v11{tail}.svg'
            assert git_hash(original) == SOURCE_HASHES[theme][index]
            old, new = ET.parse(original).getroot(), ET.parse(target).getroot()
            assert canonical(restore(new, old)) == canonical(old), 'Unexpected non-label object changes'
            for ident in ('text-127', 'text-128'):
                assert canonical(find(old, ident)) == canonical(find(new, ident))
            label = find(new, 'l2-hit-label-v11')
            assert label.get('data-label') == LABEL
            assert label.get('data-font-size') == '25'
            assert label.get('font-weight') == '400'
            assert label.get('transform') is None
            assert len(label) == 8
            assert not label.findall('.//*[@class="muted"]')
            if index == 0:
                assert label.get('fill') == find(new, 'text-127').get('fill')
                assert not new.findall('.//s:text', NS)
                for path in label.findall('.//s:path', NS):
                    assert path.get('stroke') in (None, 'none')
                assert gzip.decompress(target.with_suffix('.svgz').read_bytes()) == target.read_bytes()
            else:
                assert len(new.findall('.//s:text', NS)) == 107
                for cell in label:
                    assert cell.get('font-size') == '25'
                    assert 'font-weight:400' in cell.get('style')
            ids = [n.get('id') for n in new.iter() if n.get('id')]
            assert len(ids) == len(set(ids)), 'Duplicate object IDs'
            for ref in re.findall(r'url\(#([^)]+)\)', canonical(new)):
                assert ref in ids, 'Unresolved SVG reference: ' + ref
            norm = re.sub(r'#[0-9a-fA-F]{6}', '#COLOR', canonical(new))
            norm = re.sub(r'v6-tip-[0-9a-fA-F]{6}', 'v6-tip-COLOR', norm)
            norm = norm.replace('data-palette="'+theme+'"', 'data-palette="PALETTE"')
            if tail in normalized:
                assert normalized[tail] == norm, 'Cross-palette geometry or text mismatch'
            else:
                normalized[tail] = norm
            hashes[target.name] = hashlib.sha256(target.read_bytes()).hexdigest()
        pdf = fitz.open(HERE/'exports'/f'workflow_{theme}_v11.pdf')
        assert len(pdf) == 1
        assert not pdf[0].get_fonts(full=True)
        assert not pdf[0].get_images(full=True)
        pdf.close()
        for tail, size in [('.png', (6000, 2657)), ('_preview.png', (2100, 930))]:
            with Image.open(HERE/'exports'/f'workflow_{theme}_v11{tail}') as im:
                assert im.size == size
        row.update({'restore_to_v9_exact': True, 'miss_labels_unchanged': True,
                    'editable_text_objects': 107, 'portable_text_objects': 0,
                    'pdf_pages': 1, 'pdf_font_resources': 0, 'pdf_raster_resources': 0,
                    'font_size_hit_and_miss': 25})
        rows.append(row)
    # Page coordinates subtract the SVG y-origin of 235. The only allowed
    # change region surrounds the original and expanded right-side hit text.
    allowed = (3445, 695, 3495, 960)
    with tempfile.TemporaryDirectory(prefix='v11-pixels-') as temp:
        for row in rows:
            theme = row['palette']
            rendered = []
            for version in (9, 11):
                source = HERE.parent/f'ink_v{version}/assets'/f'workflow_{theme}_v{version}.svg'
                target = Path(temp)/f'{theme}-{version}.png'
                run = subprocess.run(['inkscape', str(source), f'--export-filename={target}',
                    '--export-area-page', '--export-width=3500', '--export-background=white',
                    '--export-background-opacity=1'], capture_output=True, text=True, timeout=180)
                if run.returncode:
                    raise RuntimeError(run.stderr)
                with Image.open(target) as im:
                    rendered.append(im.convert('RGB'))
            assert rendered[0].size == rendered[1].size == (3500, 1550)
            diff = ImageChops.difference(*rendered)
            bbox = diff.getbbox()
            assert bbox, 'Expected a visible hit-label change'
            outside = diff.copy()
            outside.paste((0,0,0), allowed)
            assert outside.getbbox() is None, 'Unexpected pixels outside the hit label'
            row.update({'changed_bbox_page_pixels': list(bbox),
                        'allowed_bbox_page_pixels': list(allowed), 'outside_changed_pixels': 0})
    (HERE/'docs').mkdir(exist_ok=True)
    report = {'version': 'ink_v11', 'base_version': 'ink_v9',
              'label': LABEL, 'variants': rows, 'all_checks_passed': True}
    (HERE/'docs/VERIFICATION.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (HERE/'docs/REVIEWED_SVG_SHA256.json').write_text(json.dumps(hashes, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
