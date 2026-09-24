"""Render contact sheets for visual inspection of the current final PDF."""

from pathlib import Path
import sys
import pymupdf
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1]
version = sys.argv[1] if len(sys.argv) > 1 else "v3"
out = root / f"论文/验收输出/final-visual-{version}"
out.mkdir(parents=True, exist_ok=True)
with pymupdf.open(root / "论文/论文.pdf") as doc:
    page_count = len(doc)
    for start in range(1, len(doc) + 1, 8):
        end = min(start + 7, len(doc))
        sheet = Image.new("RGB", (2400, 1680), "#dedede")
        draw = ImageDraw.Draw(sheet)
        for page_number in range(start, end + 1):
            index = page_number - start
            pix = doc[page_number - 1].get_pixmap(matrix=pymupdf.Matrix(0.95, 0.95), alpha=False)
            page = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            page.thumbnail((565, 780))
            x = 20 + (index % 4) * 595 + (565 - page.width) // 2
            y = 35 + (index // 4) * 820
            sheet.paste(page, (x, y))
            draw.text((x, y - 22), f"p{page_number}", fill="#202020")
        sheet.save(out / f"contact-{start:02d}-{end:02d}.png", optimize=True)
print(f"Rendered {page_count} pages into {out}")
