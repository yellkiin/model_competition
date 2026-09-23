"""独立可复现的演练实验；不是任何真实赛题的解答。仅依赖 NumPy。"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np


def evaluate(data_file: Path, output_file: Path) -> dict:
    with data_file.open(encoding="utf-8", newline="") as stream:
        records = list(csv.DictReader(stream))
    rows, selected = [], {}
    for seed in sorted({int(r["seed"]) for r in records}):
        data = [r for r in records if int(r["seed"]) == seed]
        train = [r for r in data if r["split"] == "train"]
        x = np.array([float(r["x"]) for r in train])
        y = np.array([float(r["y"]) for r in train])
        fitted = {degree: np.linalg.lstsq(np.vander(x, degree + 1), y, rcond=None)[0]
                  for degree in (1, 2)}
        validation = {}
        # 先完成验证集选择；测试集不参与模型选择或特征拟合。
        for split in ("validation", "test"):
            samples = [r for r in data if r["split"] == split]
            xx = np.array([float(r["x"]) for r in samples])
            yy = np.array([float(r["y"]) for r in samples])
            for degree, coef in fitted.items():
                residual = np.polyval(coef, xx) - yy
                sse, n = float(residual @ residual), len(yy)
                row = {"model": f"degree_{degree}", "seed": seed, "split": split,
                       "n": n, "sse": sse, "rmse": float(np.sqrt(sse / n))}
                rows.append(row)
                if split == "validation":
                    validation[row["model"]] = row["rmse"]
            if split == "validation":
                selected[str(seed)] = min(validation, key=validation.get)
    result = {"schema_version": 1, "synthetic": True, "metric": "RMSE",
              "unit": "a.u.", "direction": "min", "selection": selected,
              "selection_split": "validation", "rows": rows}
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("用法: python experiment.py input.csv metrics.json")
    evaluate(Path(sys.argv[1]), Path(sys.argv[2]))
