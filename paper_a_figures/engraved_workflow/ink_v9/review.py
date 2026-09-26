#!/usr/bin/env python3
"""Render all four PDFs independently and produce full/cropped review sheets."""
import fitz
from PIL import Image, ImageDraw
from build import HERE, THEMES


def main():
    docs = HERE / 'docs'
    docs.mkdir(exist_ok=True)
    sheet = Image.new('RGB', (2800, 1310), 'white')
    details = Image.new('RGB', (2560, 1370), 'white')
    names = {'qinglu': 'QINGLU', 'qianjiang': 'QIANJIANG', 'yanlan': 'YANLAN', 'mono': 'MONO'}
    for i, name in enumerate(THEMES):
        with fitz.open(HERE / 'exports' / f'workflow_{name}_v9.pdf') as doc:
            page = doc[0]
            factor = page.rect.width / 3500
            pix = page.get_pixmap(matrix=fitz.Matrix(1 / factor, 1 / factor), alpha=False)
            image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            tile = image.resize((1400, 620), Image.Resampling.LANCZOS)
            x, y = (i % 2) * 1400, (i // 2) * 655
            sheet.paste(tile, (x, y + 30))
            ImageDraw.Draw(sheet).text((x + 20, y + 9), names[name], fill='#202724')
            # SVG page has viewBox origin y=235. Inspect both original and new pairs.
            box = (2600, 790, 3420, 1200)
            rect = fitz.Rect(box[0] * factor, (box[1] - 235) * factor,
                             box[2] * factor, (box[3] - 235) * factor)
            crop = page.get_pixmap(matrix=fitz.Matrix(1.56 / factor, 1.56 / factor), clip=rect, alpha=False)
            detail = Image.frombytes('RGB', (crop.width, crop.height), crop.samples)
            dx, dy = (i % 2) * 1280, (i // 2) * 685
            details.paste(detail, (dx, dy + 28))
            ImageDraw.Draw(details).text((dx + 20, dy + 8), names[name], fill='#202724')
            if name == 'qinglu':
                crop.save(docs / 'detail_memory_clean.png')
                pix.save(docs / 'qinglu_full_pdf_review.png')
    sheet.save(docs / 'four_palettes_review.png')
    details.save(docs / 'four_palettes_memory_detail.png')
    print('Four PDF full views and memory detail views rendered.')


if __name__ == '__main__':
    main()
