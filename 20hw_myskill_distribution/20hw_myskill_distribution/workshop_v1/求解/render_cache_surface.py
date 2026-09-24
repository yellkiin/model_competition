"""Render q3-F03 with an explicit visible height unit for the two 3D panels."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "求解/图件数据/q3-F03.csv"
OUT = ROOT / "求解/正式图件"

plt.rcParams.update({
    "font.family": "Microsoft YaHei", "pdf.fonttype": 42,
    "font.size": 9, "axes.labelsize": 9, "axes.titlesize": 10,
    "axes.edgecolor": "#728298", "axes.labelcolor": "#1C2C41",
    "xtick.color": "#1C2C41", "ytick.color": "#1C2C41", "text.color": "#1C2C41",
    "savefig.facecolor": "white", "figure.facecolor": "white",
})


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--figure", choices=["q3-F03"], required=True)
    args = parser.parse_args()
    with DATA.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    fig = plt.figure(figsize=(160 / 25.4, 91 / 25.4), layout="constrained")
    for index, case in enumerate(("case_044", "case_083"), 1):
        ax = fig.add_subplot(1, 2, index, projection="3d")
        sub = [r for r in rows if r["case"] == case]
        xs = sorted({float(r["capacity_bytes"]) / 1048576 for r in sub})
        ys = sorted({float(r["bandwidth_bytes_per_cycle"]) for r in sub})
        mesh = np.array([[next(float(r["makespan_cycles"]) / 1000 for r in sub
                          if float(r["capacity_bytes"]) / 1048576 == x
                          and float(r["bandwidth_bytes_per_cycle"]) == y)
                          for x in xs] for y in ys])
        X, Y = np.meshgrid(xs, ys)
        ax.plot_surface(X, Y, mesh, cmap="viridis", linewidth=.5,
                        edgecolor="#52738C", antialiased=True, alpha=.92)
        ax.scatter([float(r["capacity_bytes"]) / 1048576 for r in sub],
                   [float(r["bandwidth_bytes_per_cycle"]) for r in sub],
                   [float(r["makespan_cycles"]) / 1000 for r in sub],
                   color="#D7793C", s=13, depthshade=False)
        ax.set(xlabel="容量/MiB", ylabel="带宽/B/周期", zlabel="时长/千周期")
        ax.set_title(case, pad=2, fontsize=9)
        ax.view_init(elev=26, azim=-52)
        ax.tick_params(labelsize=6, pad=0)
    fig.suptitle("非官方L2网格响应（高度：千周期）", fontsize=10)
    fig.canvas.draw()
    OUT.mkdir(exist_ok=True)
    pdf = OUT / f"{args.figure}.pdf"
    png = OUT / f"{args.figure}.png"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fig.savefig(pdf, bbox_inches=None)
        fig.savefig(png, dpi=300, bbox_inches=None)
    missing = [str(w.message) for w in caught if "Glyph" in str(w.message)]
    if missing:
        raise RuntimeError(f"Missing glyphs: {missing[:3]}")
    plt.close(fig)
    stats = {
        "figure_id": args.figure, "row_count": len(rows),
        "input": DATA.relative_to(ROOT).as_posix(), "input_sha256": sha(DATA),
        "output_pdf": pdf.relative_to(ROOT).as_posix(),
        "output_png": png.relative_to(ROOT).as_posix(),
        "pdf_sha256": sha(pdf), "png_sha256": sha(png),
        "scientific_observation": "两例九点实际网格，图题明确三维高度量纲；连面不表示额外模拟实验。",
        "status": "rendered_pending_visual_review",
    }
    (OUT / f"{args.figure}.stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"figure_id": args.figure, "pdf_sha256": stats["pdf_sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
