"""Make contact sheets and a factual page-density inventory for draft review."""
from pathlib import Path
import json

import pymupdf
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "论文/论文.pdf"
OUT = ROOT / "论文/验收输出"
OUT.mkdir(parents=True, exist_ok=True)
doc = pymupdf.open(PDF)
font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 16)
pages = []
for index, page in enumerate(doc):
    text = page.get_text()
    pages.append({"page": index + 1, "characters": len(text), "image_count": len(page.get_images()),
                  "drawing_count": len(page.get_drawings()), "first_line": text[:100].replace("\n", " | ")})
    if 3 <= index <= 28:
        pix = page.get_pixmap(dpi=75, alpha=False)
        pix.save(OUT / f"draft-page-{index + 1:02d}.png")
for start in range(3, 29, 8):
    items = list(range(start, min(29, start + 8)))
    w, h = 660, 925
    sheet = Image.new("RGB", (w * 4, h * 2), "#e9edf2")
    draw = ImageDraw.Draw(sheet)
    for j, index in enumerate(items):
        with Image.open(OUT / f"draft-page-{index + 1:02d}.png") as source:
            im = source.convert("RGB")
            im.thumbnail((w - 24, h - 48), Image.Resampling.LANCZOS)
        x, y = (j % 4) * w, (j // 4) * h
        draw.text((x + 12, y + 8), f"PDF {index + 1}", fill="#1b263b", font=font)
        sheet.paste(im, (x + (w - im.width) // 2, y + 38))
    sheet.save(OUT / f"draft-contact-{start + 1:02d}-{items[-1] + 1:02d}.png")
(OUT / "draft-page-inventory.json").write_text(json.dumps(pages, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"pages": len(doc), "contacts": 4}, ensure_ascii=False))
