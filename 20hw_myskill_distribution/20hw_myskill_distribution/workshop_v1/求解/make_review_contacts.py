"""Assemble vector and grayscale previews for actual per-question visual inspection."""
from __future__ import annotations

import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent / "正式图件"
FONT = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 23)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", choices=["q1", "q2", "q3"], required=True)
    args = parser.parse_args()
    for kind, file in (("vector", "vector_render.png"), ("grayscale", "grayscale.png")):
        sheet = Image.new("RGB", (2000, 1830), "#F2F4F7")
        draw = ImageDraw.Draw(sheet)
        for index in range(1, 7):
            fid = f"{args.question}-F{index:02d}"
            path = ROOT / f"{fid}_review" / file
            with Image.open(path) as source:
                image = source.convert("RGB")
                image.thumbnail((970, 560), Image.Resampling.LANCZOS)
            x = ((index-1) % 2)*1000
            y = ((index-1) // 2)*610
            draw.text((x+18, y+6), fid, fill="#1C2C41", font=FONT)
            sheet.paste(image, (x+(1000-image.width)//2, y+40))
        target = ROOT / f"{args.question}_{kind}_contact.png"
        sheet.save(target)
        print(target)


if __name__ == "__main__":
    main()
