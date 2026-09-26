#!/usr/bin/env python3
"""Render delivered PDFs with MuPDF independently of SVG export."""
from pathlib import Path
import fitz
from PIL import Image, ImageOps, ImageDraw
from build import HERE, THEMES


def main():
    fulls, details = [], []
    for theme in THEMES:
        pdf = fitz.open(HERE/'exports'/f'workflow_{theme}_v11.pdf')
        page = pdf[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(3500/page.rect.width, 3500/page.rect.width), alpha=False)
        image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
        # Full memory annotation region, y coordinates relative to page.
        detail = image.crop((2540, 660, 3500, 1120))
        small = image.resize((1750, 775), Image.Resampling.LANCZOS)
        if theme == 'qinglu':
            image.save(HERE/'docs/qinglu_full_pdf_review.png')
            detail.save(HERE/'docs/cache_labels_detail.png')
        fulls.append((theme, small))
        details.append((theme, detail))
        pdf.close()
    for items, name in [(fulls, 'four_palettes_review.png'),
                         (details, 'four_palettes_cache_detail.png')]:
        width, height = items[0][1].size
        sheet = Image.new('RGB', (width*2, (height+32)*2), 'white')
        draw = ImageDraw.Draw(sheet)
        for i, (theme, image) in enumerate(items):
            x, y = (i%2)*width, (i//2)*(height+32)
            draw.text((x+15,y+8), theme, fill='black')
            sheet.paste(image, (x,y+32))
        sheet.save(HERE/'docs'/name)
    print('Independent MuPDF full-figure and cache-label review sheets written.')


if __name__ == '__main__':
    main()
