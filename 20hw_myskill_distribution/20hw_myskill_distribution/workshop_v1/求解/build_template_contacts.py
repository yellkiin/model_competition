"""Produce review-only contact sheets of current shared template previews."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/sci-box-main/sci-box-main/skills/scibox-diagram"
CATALOG = SKILL / "assets/catalog.json"
OUT = WORKSPACE / "求解/模板预览"


def main() -> None:
    templates = json.loads(CATALOG.read_text(encoding="utf-8"))["templates"]
    OUT.mkdir(parents=True, exist_ok=True)
    for page, start in enumerate(range(0, len(templates), 8), 1):
        items = templates[start:start + 8]
        sheet = Image.new("RGB", (2400, 1160), "#f4f5f6")
        draw = ImageDraw.Draw(sheet)
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 23)
        for j, item in enumerate(items):
            col, row = j % 4, j // 4
            x, y = col * 600, row * 580
            path = SKILL / item["paths"]["preview"]
            image = Image.open(path).convert("RGB")
            image.thumbnail((570, 515))
            sheet.paste(image, (x + (600 - image.width) // 2, y + 42 + (515 - image.height) // 2))
            draw.text((x + 15, y + 10), item["template_id"], fill="#111827", font=font)
        sheet.save(OUT / f"scibox_catalog_{page:02d}.png")
    providers = json.loads((WORKSPACE / "求解/绘图能力预检.json").read_text(encoding="utf-8"))["providers"]
    previews = next(p["previews"] for p in providers if p["source_skill"] == "modelviz-skill")
    for page, start in enumerate(range(0, len(previews), 12), 1):
        items = previews[start:start + 12]
        sheet = Image.new("RGB", (2400, 1320), "#f4f5f6")
        draw = ImageDraw.Draw(sheet)
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 21)
        for j, item in enumerate(items):
            col, row = j % 4, j // 4
            x, y = col * 600, row * 440
            path = WORKSPACE / item["views"][0]["path"]
            image = Image.open(path).convert("RGB")
            image.thumbnail((570, 380))
            sheet.paste(image, (x + (600 - image.width) // 2, y + 38 + (380 - image.height) // 2))
            draw.text((x + 9, y + 8), item["template_id"], fill="#111827", font=font)
        sheet.save(OUT / f"modelviz_catalog_{page:02d}.png")
    print(json.dumps({"scibox_templates": len(templates), "scibox_pages": (len(templates) + 7) // 8,
                      "modelviz_templates": len(previews), "modelviz_pages": (len(previews) + 11) // 12,
                      "output": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
