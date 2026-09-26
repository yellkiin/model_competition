"""Recompute public tables and a compact SVG from the selected official responses.

This entry reads only the submitted package. It never invokes a search or evaluator.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def official(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        value = json.load(stream)
    return value.get("official_result", value)


def write_csv(path, data, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data)


def draw_svg(path, values):
    width, height = 760, 350
    labels = [f"Q{q} / {n} cores" for q in (1, 2, 3) for n in (2, 3, 4, 5)]
    numbers = [values.get((q, n), 0.0) for q in (1, 2, 3) for n in (2, 3, 4, 5)]
    maximum = max(numbers) * 1.08 if numbers else 1
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             '<text x="30" y="28" font-size="17" font-family="sans-serif">Mean per-case speedup from official responses</text>',
             '<line x1="55" y1="300" x2="735" y2="300" stroke="#333"/>']
    for index, (label, number) in enumerate(zip(labels, numbers)):
        x = 62 + index * 55
        bar = 230 * number / maximum
        parts.append(f'<rect x="{x}" y="{300-bar:.2f}" width="34" height="{bar:.2f}" fill="#287aa4"/>')
        parts.append(f'<text x="{x+17}" y="{294-bar:.2f}" text-anchor="middle" font-size="10" font-family="sans-serif">{number:.2f}</text>')
        parts.append(f'<text x="{x+17}" y="318" text-anchor="middle" font-size="8" font-family="sans-serif">{label}</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--output", type=Path, default=Path("复现输出"))
    args = parser.parse_args()
    root = args.package_root.resolve() / "支撑材料文件" / "其他支撑材料"
    index = rows(root / "已选评价" / "selected_index.csv")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    main_rows, pair_rows = [], []
    for item in index:
        raw = official(root / "已选评价" / item["main_response"])
        movement = raw.get("data_movement_bytes") or {}
        q, n = int(item["q"]), int(item["n"])
        entry = dict(case=item["case"], q=q, n=n, makespan=raw["makespan"],
                     added_copy_bytes=movement.get("added_copy_bytes"),
                     spill_added_copy_bytes=movement.get("spill_added_copy_bytes"),
                     cache_hit_rate=(raw.get("cache_stats") or {}).get("hit_rate"))
        if item["paired_response"]:
            other = official(root / "已选评价" / item["paired_response"])
            pair_rows.append(dict(case=item["case"], n=n,
                                  with_l2=raw["makespan"], without_l2=other["makespan"],
                                  cache_speedup=other["makespan"] / raw["makespan"],
                                  same_plan=True))
            entry["no_l2_makespan"] = other["makespan"]
            entry["cache_speedup"] = other["makespan"] / raw["makespan"]
        main_rows.append(entry)
    baseline = {row["case"]: row["makespan"] for row in main_rows if row["q"] == 0}
    grouped = defaultdict(list)
    for row in main_rows:
        row["baseline"] = baseline[row["case"]]
        row["speedup"] = row["baseline"] / row["makespan"]
        if row["q"]:
            grouped[(row["q"], row["n"])].append(row["speedup"])
    main_rows.sort(key=lambda r: (r["case"], r["q"], r["n"]))
    pair_rows.sort(key=lambda r: (r["case"], r["n"]))
    write_csv(out / "recomputed_main.csv", main_rows,
              ["case", "q", "n", "makespan", "added_copy_bytes", "spill_added_copy_bytes",
               "cache_hit_rate", "no_l2_makespan", "cache_speedup", "baseline", "speedup"])
    write_csv(out / "recomputed_pairs.csv", pair_rows,
              ["case", "n", "with_l2", "without_l2", "cache_speedup", "same_plan"])
    means = [dict(q=q, n=n, count=len(grouped[(q, n)]), mean_speedup=mean(grouped[(q, n)]))
             for q in (1, 2, 3) for n in (2, 3, 4, 5)]
    write_csv(out / "recomputed_means.csv", means, ["q", "n", "count", "mean_speedup"])
    draw_svg(out / "mean_speedup.svg", {(r["q"], r["n"]): r["mean_speedup"] for r in means})
    reference = {(r["case"], int(r["q"]), int(r["n"])): r
                 for r in rows(root / "数据表" / "main.csv")}
    discrepancies = []
    for row in main_rows:
        key = (row["case"], row["q"], row["n"])
        old = reference.get(key)
        if old is None or int(old["makespan"]) != row["makespan"]:
            discrepancies.append({"key": key, "field": "makespan"})
        elif old.get("added_copy_bytes") and int(old["added_copy_bytes"]) != row["added_copy_bytes"]:
            discrepancies.append({"key": key, "field": "added_copy_bytes"})
    pair_ref = {(r["case"], int(r["n"])): r for r in rows(root / "数据表" / "pairs.csv")}
    for row in pair_rows:
        key = (row["case"], row["n"])
        old = pair_ref.get(key)
        if old is None or int(old["with_l2"]) != row["with_l2"] or int(old["without_l2"]) != row["without_l2"]:
            discrepancies.append({"key": key, "field": "pair_makespan"})
    report = dict(main_configurations=len(main_rows), paired_configurations=len(pair_rows),
                  baseline_cases=len(baseline), comparison_mismatches=discrepancies,
                  source="selected official evaluation responses")
    (out / "reproduction_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "comparison_mismatches"}, ensure_ascii=False))
    if discrepancies:
        raise SystemExit(f"{len(discrepancies)} reference values differ; inspect reproduction_report.json")


if __name__ == "__main__":
    main()
