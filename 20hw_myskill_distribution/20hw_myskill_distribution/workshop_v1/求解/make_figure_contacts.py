"""Internal contact sheets for actual visual review of the formal plots."""

from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont


folder = Path(__file__).resolve().parent / "正式图件"
font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 24)
for question, count in (("q1", 6), ("q2", 6), ("q3", 6)):
    if len(sys.argv) > 1 and question not in sys.argv[1:]:
        continue
    images = [(f"{question}-F{index:02d}", Image.open(folder / f"{question}-F{index:02d}.png").convert("RGB"))
              for index in range(1, count+1)]
    thumb_w = 1000
    thumb_h = 610
    rows = (count + 1)//2
    sheet = Image.new("RGB", (2*thumb_w, rows*thumb_h), "#F2F4F7")
    draw = ImageDraw.Draw(sheet)
    for i, (name, original) in enumerate(images):
        x = (i%2)*thumb_w
        y = (i//2)*thumb_h
        draw.text((x+18, y+6), name, fill="#1C2C41", font=font)
        original.thumbnail((thumb_w-26, thumb_h-48), Image.Resampling.LANCZOS)
        sheet.paste(original, (x+(thumb_w-original.width)//2, y+40))
    sheet.save(folder / f"{question}_contact.png")
    print(question, sheet.size)
