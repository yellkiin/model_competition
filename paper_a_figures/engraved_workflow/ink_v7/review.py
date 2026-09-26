#!/usr/bin/env python3
"""Independent MuPDF renders for visual review; not a substitute for inspection."""
from pathlib import Path
import fitz
from PIL import Image, ImageDraw
from build import HERE, THEMES


def main():
    docs = HERE / 'docs'
    docs.mkdir(exist_ok=True)
    sheet = Image.new('RGB', (2200, 1030), 'white')
    names = {'qinglu': 'QINGLU', 'qianjiang': 'QIANJIANG', 'yanlan': 'YANLAN', 'mono': 'MONO'}
    for i, name in enumerate(THEMES):
        with fitz.open(HERE / 'exports' / f'workflow_{name}_v7.pdf') as doc:
            page = doc[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(3500 / page.rect.width, 3500 / page.rect.width), alpha=False)
            image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            tile = image.resize((1100, 487), Image.Resampling.LANCZOS)
            x, y = (i % 2) * 1100, (i // 2) * 515
            sheet.paste(tile, (x, y + 24))
            ImageDraw.Draw(sheet).text((x + 20, y + 6), names[name], fill='#202724')
            if name == 'qinglu':
                regions = {
                    'detail_headers': (0, 235, 3500, 463),
                    'detail_02_alignment': (1030, 480, 2465, 940),
                    'detail_03_arrows': (2605, 770, 3370, 920),
                    'detail_l2_fill': (2570, 1135, 3075, 1342),
                }
                for label, box in regions.items():
                    factor = page.rect.width / 3500
                    rect = fitz.Rect(box[0] * factor, (box[1] - 235) * factor,
                                     box[2] * factor, (box[3] - 235) * factor)
                    scale = 1.5 / factor if label != 'detail_headers' else 0.65 / factor
                    crop = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=rect, alpha=False)
                    crop.save(docs / (label + '.png'))
    sheet.save(docs / 'four_palettes_review.png')
    print('Independent PDF renders and detail crops saved to', docs)


if __name__ == '__main__':
    main()
