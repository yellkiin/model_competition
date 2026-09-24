"""Recompile current overview panels and prepare four distinct visual QA views."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "求解/综合图"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", action="append", choices=["q1", "q2", "q3"])
    args = parser.parse_args()
    env = json.loads((ROOT / "求解/环境检测.json").read_text(encoding="utf-8"))
    xelatex = next((r["path"] for r in env["results"] if r.get("capability") == "latex" and r.get("path")), None)
    if not xelatex:
        raise RuntimeError("The registered XeLaTeX executable is missing")
    questions = [int(item[-1]) for item in args.question] if args.question else [1, 2, 3]
    for q in questions:
        stem = f"q{q}-overview"
        tex = OUT / f"{stem}.tex"
        run = subprocess.run([xelatex, "-interaction=nonstopmode", "-halt-on-error", f"-output-directory={OUT}", str(tex)],
                             cwd=OUT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        (OUT / f"{stem}.build.log").write_text(run.stdout + "\n" + run.stderr, encoding="utf-8")
        if run.returncode:
            raise RuntimeError(f"XeLaTeX failed for {stem}: {run.returncode}")
        with fitz.open(OUT / f"{stem}.pdf") as doc:
            pix = doc[0].get_pixmap(dpi=300, alpha=False)
            pix.save(OUT / f"{stem}.png")
            doc[0].get_pixmap(dpi=150, alpha=False).save(OUT / f"{stem}.pdf-size.png")
        with Image.open(OUT / f"{stem}.png") as image:
            rgb = image.convert("RGB")
            rgb.save(OUT / f"{stem}.overall.png")
            width, height = rgb.size
            box = [int(width * .04), int(height * .70), int(width * .96), int(height * .97)]
            rgb.crop(box).save(OUT / f"{stem}.detail.png")
            ImageOps.grayscale(rgb).convert("RGB").save(OUT / f"{stem}.grayscale.png")
        print(json.dumps({"figure": stem, "preview_pixels": [width, height], "detail_box": box}))


if __name__ == "__main__":
    main()
