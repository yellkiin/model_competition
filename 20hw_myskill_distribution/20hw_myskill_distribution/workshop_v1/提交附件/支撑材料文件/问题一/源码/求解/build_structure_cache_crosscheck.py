"""Cross-check official five-core Cache results against the predeclared graph bins."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "求解/正式实验/逐例分析.csv"
ROWS = [r for r in csv.DictReader(SOURCE.open(encoding="utf-8-sig", newline=""))
        if int(r["cores"]) == 5]
assert len(ROWS) == 100 and len({r["case"] for r in ROWS}) == 100
BINS = [
    (r"$f\leq0.05$", lambda f: f <= .05),
    (r"$0.05<f\leq0.20$", lambda f: .05 < f <= .20),
    (r"$0.20<f\leq0.60$", lambda f: .20 < f <= .60),
    (r"$f>0.60$", lambda f: f > .60),
]
out = []
for label, predicate in BINS:
    rows = [r for r in ROWS if predicate(float(r["largest_component_fraction"]))]
    out.append({
        "bin": label, "cases": len(rows),
        "mean_hit_rate": mean(float(r["q3_cache_hit_rate"]) for r in rows),
        "mean_matched_gain": mean(float(r["q3_cache_gain"]) for r in rows),
        "strict_gain_cases": sum(float(r["q3_cache_gain"]) > 1 for r in rows),
        "max_matched_gain": max(float(r["q3_cache_gain"]) for r in rows),
    })
assert sum(r["cases"] for r in out) == 100
assert sum(r["strict_gain_cases"] for r in out) == 58
assert abs(sum(r["cases"] * r["mean_matched_gain"] for r in out) / 100 - 1.02595684) < 1e-6
result = {
    "source": SOURCE.relative_to(ROOT).as_posix(),
    "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    "statistical_unit": "one official case at five cores, using the same q3 plan with and without L2",
    "bin_definition": "The four largest-component-fraction bins were also used in q1 structure analysis; no threshold was tuned on Cache outcomes.",
    "rows": out,
}
target = ROOT / "求解/正式实验/结构与缓存交叉核查.json"
target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = [
    r"\begin{table}[htbp]\centering",
    r"\caption{五核图结构分组下的同方案Cache收益}\label{tab:q3-structure-cache}",
    r"\small",
    r"\begin{tabular}{c r r r r}",
    r"\toprule",
    r"最大连通块占比 & 案例数 & 平均命中字节率 & 平均收益比 & 严格受益数 \\",
    r"\midrule",
]
for row in out:
    hit = f"{row['mean_hit_rate']:.2%}".replace("%", r"\%")
    lines.append(f"{row['bin']} & {row['cases']} & {hit} & "
                 f"{row['mean_matched_gain']:.4f} & {row['strict_gain_cases']} " + r"\\")
lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
(ROOT / "论文/章节内容/q3_结构缓存交叉核查.generated.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(target)
