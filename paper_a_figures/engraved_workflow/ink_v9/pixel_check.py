#!/usr/bin/env python3
"""Render V8/V9 with the same Inkscape and require zero changes outside the five deleted strip regions."""
import json
from pathlib import Path
import subprocess
import tempfile
from PIL import Image, ImageChops
from build import HERE, THEMES


def main():
    rows = []
    # Coordinates on the 3500x1550 exported page (SVG y origin is 235).
    allowed = [(2643, 651, 2755, 667), (2790, 651, 2902, 667),
               (3058, 651, 3170, 667), (3205, 651, 3317, 667),
               (2688, 910, 3310, 932)]
    with tempfile.TemporaryDirectory(prefix='ink-v9-pixels-') as temp:
        for theme in THEMES:
            images = []
            for ver in (8, 9):
                source = HERE.parent / f'ink_v{ver}/assets' / f'workflow_{theme}_v{ver}.svg'
                target = Path(temp) / f'{theme}-{ver}.png'
                result = subprocess.run(['inkscape', str(source), f'--export-filename={target}',
                    '--export-area-page', '--export-width=3500', '--export-background=white',
                    '--export-background-opacity=1'], capture_output=True, text=True, timeout=180)
                if result.returncode:
                    raise RuntimeError(result.stderr)
                with Image.open(target) as im:
                    images.append(im.convert('RGB'))
            assert images[0].size == images[1].size == (3500, 1550)
            difference = ImageChops.difference(*images)
            bbox = difference.getbbox()
            assert bbox, 'Expected the strip removal to be visible'
            outside = difference.copy()
            for box in allowed:
                assert difference.crop(box).getbbox(), f'Expected visible change in {box}'
                outside.paste((0, 0, 0), box)
            assert outside.getbbox() is None, f'Unexpected pixel changes: {theme}'
            rows.append({'palette': theme, 'changed_bbox_page_pixels': list(bbox),
                         'allowed_regions_page_pixels': [list(box) for box in allowed], 'outside_changed_pixels': 0})
    report = {'version': 'ink_v9', 'renderer': 'Inkscape, same-renderer comparison at 3500x1550',
              'variants': rows}
    (HERE / 'docs/PIXEL_REVIEW.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
