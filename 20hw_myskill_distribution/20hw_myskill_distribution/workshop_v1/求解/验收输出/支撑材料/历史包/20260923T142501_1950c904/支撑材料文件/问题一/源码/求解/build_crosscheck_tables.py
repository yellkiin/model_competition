"""Create case-level counterexample tables from the current formal CSV evidence."""
from __future__ import annotations

import csv
import hashlib
import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "求解/正式实验/逐例分析.csv"
TRANSFER = ROOT / "求解/图件数据/q2-F03.csv"
CHAPTER = ROOT / "论文/章节内容"
OUT = ROOT / "求解/正式实验/交叉核查.json"


def read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name: str, lines: list[str]) -> None:
    (CHAPTER / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    cases = [r for r in read(CASE) if r["cores"] == "5"]
    transfers = [r for r in read(TRANSFER) if r["cores"] == "5"]
    assert len(cases) == len(transfers) == 100
    by_id = {r["case"]: r for r in cases}
    chosen = [by_id[f"case_{n:03d}"] for n in (83,92,62,63)]
    q1 = [r"\begin{table}[htbp]\centering",
          r"\caption{最大块占比不能单独预测五核收益的四例}\label{tab:q1-counterexamples}",
          r"\small\begin{tabular}{crrrrrc}\toprule",
          r"算例 & 最大块占比 & DAG深度 & 最大层宽 & 新增搬运/MiB & 加速比 & 胜出族 \\ \midrule"]
    for r in chosen:
        q1.append(f'{r["case"].split("_")[-1]} & {float(r["largest_component_fraction"]):.4f} & {r["dag_depth"]} & {r["max_level_width"]} & {int(r["q1_added_copy_bytes"])/2**20:.2f} & {float(r["q1_speedup"]):.4f} & {"分批" if r["q1_candidate"]=="batches800" else "分段" if r["q1_candidate"]=="bands8" else "连通块"} \\\\')
    q1.append(r"\bottomrule\end{tabular}\end{table}")
    save("q1_反例核查.generated.tex", q1)

    groups = defaultdict(list)
    for r in transfers:
        groups[r["candidate"]].append(r)
    q2rows = []
    q2 = [r"\begin{table}[htbp]\centering",
          r"\caption{五核胜出候选族的搬运组成与收益}\label{tab:q2-family-crosscheck}",
          r"\small\begin{tabular}{lrrrrr}\toprule",
          r"候选族 & 例数 & 边界搬运均值/MiB & Spill均值/MiB & Spill例数 & 平均加速比 \\ \midrule"]
    for key, label in (("components","连通块"),("bands8","深度分段"),("batches800","分批")):
        rows = groups[key]
        row = {"candidate": key, "count": len(rows),
               "boundary_mean_mib": statistics.mean(int(r["partition_added_copy_bytes"])/2**20 for r in rows),
               "spill_mean_mib": statistics.mean(int(r["spill_added_copy_bytes"])/2**20 for r in rows),
               "spill_cases": sum(int(r["spill_added_copy_bytes"])>0 for r in rows),
               "speedup_mean": statistics.mean(float(by_id[r["case"]]["q2_speedup"]) for r in rows)}
        q2rows.append(row)
        q2.append(f'{label} & {row["count"]} & {row["boundary_mean_mib"]:.2f} & {row["spill_mean_mib"]:.2f} & {row["spill_cases"]} & {row["speedup_mean"]:.4f} \\\\')
    q2.append(r"\bottomrule\end{tabular}\end{table}")
    save("q2_候选交叉核查.generated.tex", q2)

    bins = [
        ("零命中", lambda x: x == 0),
        (r"$0<H\leq0.20$", lambda x: 0 < x <= .2),
        (r"$0.20<H\leq0.50$", lambda x: .2 < x <= .5),
        ("$H>0.50$", lambda x: x > .5),
    ]
    q3rows = []
    q3 = [r"\begin{table}[htbp]\centering",
          r"\caption{五核命中字节率分层后的同方案收益}\label{tab:q3-hit-crosscheck}",
          r"\small\begin{tabular}{lrrrr}\toprule",
          r"命中字节率范围 & 例数 & Cache比均值 & 严格受益例数 & 最大Cache比 \\ \midrule"]
    for label, pred in bins:
        rows = [r for r in cases if pred(float(r["q3_cache_hit_rate"]))]
        gains = [float(r["q3_cache_gain"]) for r in rows]
        row = {"label": label, "count": len(rows), "gain_mean": statistics.mean(gains),
               "positive": sum(x>1+1e-9 for x in gains), "maximum": max(gains)}
        q3rows.append(row)
        q3.append(f'{label} & {row["count"]} & {row["gain_mean"]:.4f} & {row["positive"]} & {row["maximum"]:.4f} \\\\')
    assert sum(r["count"] for r in q3rows) == 100
    q3.append(r"\bottomrule\end{tabular}\end{table}")
    save("q3_命中交叉核查.generated.tex", q3)
    report = {"input_sha256": {str(p.relative_to(ROOT)).replace("\\","/"): sha(p) for p in (CASE,TRANSFER)},
              "q1_cases": chosen, "q2_candidate_groups": q2rows, "q3_hit_groups": q3rows}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status":"PASS","q1_cases":[r["case"] for r in chosen],
                      "q2_groups":q2rows,"q3_groups":q3rows},ensure_ascii=False))


if __name__ == "__main__":
    main()
