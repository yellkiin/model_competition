"""从规范化 CSV 重建正文统计表和逐例附录表。"""

from __future__ import annotations

import csv
from pathlib import Path
from statistics import mean, median


WORKSHOP = Path(__file__).resolve().parent.parent
DATA = WORKSHOP / "求解" / "规范化数据" / "combined"
OUTPUT = WORKSHOP / "论文" / "章节内容" / "数据表"


def rows(name: str) -> list[dict[str, str]]:
    with (DATA / name).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write(name: str, body: str) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(body.rstrip() + "\n", encoding="utf-8")


def dec(value: str | float) -> str:
    return f"{float(value):.4f}"


def integer(value: str) -> str:
    return f"{int(float(value)):,}"


def means_table(question: int, means: list[dict[str, str]]) -> str:
    selected = sorted((r for r in means if int(r["q"]) == question), key=lambda r: int(r["n"]))
    lines = [
        "% 由求解/规范化数据/combined/means.csv 生成；逐图加速比的算术平均。",
        r"\begin{table}[htbp]",
        rf"\caption{{问题{['一', '二', '三'][question - 1]}各核数逐图加速比统计}}\label{{tab:q{question}_mean}}",
        r"\centering\normalsize",
        r"\setlength{\tabcolsep}{5pt}",
        r"\begin{tabular}{rrrrrr}",
        r"\toprule",
        r"核心数 & 样本数 & 平均加速比 & 中位加速比 & 最小加速比 & 最大加速比 \\",
        r"\midrule",
    ]
    for r in selected:
        lines.append(
            f'{int(r["n"])} & {int(r["count"])} & {dec(r["mean_speedup"])} & '
            f'{dec(r["median_speedup"])} & {dec(r["min_speedup"])} & '
            f'{dec(r["max_speedup"])} ' + r"\\"
        )
    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]
    return "\n".join(lines)


def pairs_table(pairs: list[dict[str, str]]) -> str:
    groups: dict[int, list[dict[str, str]]] = {n: [] for n in range(1, 6)}
    for r in pairs:
        if r["same_plan"].lower() != "true" or not r["with_l2"] or not r["without_l2"]:
            continue
        n = int(r["n"])
        if n in groups and int(r["with_l2"]) > 0 and int(r["without_l2"]) > 0:
            groups[n].append(r)
    lines = [
        "% 由同一方案的有/无 L2 双响应计算；比值为无 L2 周期/有 L2 周期。",
        r"\begin{table}[htbp]",
        r"\caption{第三问同一方案有无 L2 的周期配对统计}\label{tab:q3_pairs}",
        r"\centering\normalsize",
        r"\setlength{\tabcolsep}{4pt}",
        
        r"\begin{tabular}{rrrrrrrr}",
        r"\toprule",
        r"核数 & 配对数 & \shortstack{平均\\周期比} & \shortstack{中位\\周期比} & 改善 & 相同 & 退化 & \shortstack{平均字节\\命中率} \\",
        r"\midrule",
    ]
    for n, group in groups.items():
        if not group:
            continue
        ratios = [int(r["without_l2"]) / int(r["with_l2"]) for r in group]
        hits = [float(r["hit_rate"]) for r in group if r["hit_rate"]]
        better = sum(int(r["without_l2"]) > int(r["with_l2"]) for r in group)
        equal = sum(int(r["without_l2"]) == int(r["with_l2"]) for r in group)
        worse = len(group) - better - equal
        lines.append(
            f"{n} & {len(group)} & {dec(mean(ratios))} & {dec(median(ratios))} & "
            f"{better} & {equal} & {worse} & {dec(mean(hits)) if hits else '—'} " + r"\\"
        )
    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        
        r"\end{table}",
    ]
    return "\n".join(lines)


def appendix_table(question: int, ns: tuple[int, ...], values: dict[tuple[str, int], dict[str, str]]) -> str:
    cases = sorted({case for case, _ in values})
    suffix = "、".join(str(n) for n in ns)
    title = "一二三"[question - 1]
    right_cycle = r">{\raggedleft\arraybackslash}p{28mm}"
    right_bytes = r">{\raggedleft\arraybackslash}p{39mm}"
    colspec = r"@{}p{15mm}" + (right_cycle + right_bytes) * len(ns) + r"@{}"
    headings = ["算例"]
    for n in ns:
        headings += [rf"\shortstack{{{n} 核\\周期}}", rf"\shortstack{{{n} 核额外\\COPY/B}}"]
    lines = [
        "% 周期为总体任务执行时间；字节为额外 COPY。q1/q2 单核使用题设约定的原始整图响应。",
        r"\begingroup\normalsize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\setlength{\LTleft}{\fill}\setlength{\LTright}{\fill}",
        r"\setlength{\LTcapwidth}{160mm}",
        rf"\begin{{longtable}}{{{colspec}}}",
        rf"\caption{{问题{title}逐例结果：{suffix} 核}}\label{{tab:appendix_q{question}_n{''.join(map(str, ns))}}}\\",
        r"\toprule",
        " & ".join(headings) + r"\\",
        r"\midrule",
        r"\endfirsthead",
        rf"\caption[]{{问题{title}逐例结果：{suffix} 核（续）}}\\",
        r"\toprule",
        " & ".join(headings) + r"\\",
        r"\midrule",
        r"\endhead",
        r"\bottomrule",
        r"\endfoot",
    ]
    for case in cases:
        # This final block otherwise reaches the ordinary page builder after
        # longtable has finished, dropping its continuation header in this template.
        # Keep the actual page boundary inside longtable instead.
        if question == 3 and ns == (1, 2) and case == "case_098":
            lines.append(r"\noalign{\penalty-10000}")
        cells = [case.removeprefix("case_")]
        for n in ns:
            r = values.get((case, n))
            cells += [integer(r["makespan"]), integer(r["added_copy_bytes"])] if r else ["—", "—"]
        # Keep the last three rows together, including at a longtable chunk boundary.
        ending = r"\\*" if case in cases[-3:-1] else r"\\"
        lines.append(" & ".join(cells) + ending)
    lines += [r"\end{longtable}", r"\endgroup"]
    return "\n".join(lines)


def appendix() -> str:
    sections = [
        "% 可选附录长表；每表最多两个核数，表宽不超过 160 mm。",
        "% 问题一、二的 1 核行从规范化 appendix_q1/q2.csv 中题设单核约定读取，不由多核公式回填。",
    ]
    for q in range(1, 4):
        values = {(r["case"], int(r["n"])): r for r in rows(f"appendix_q{q}.csv") if r["status"] == "ok"}
        for ns in ((1, 2), (3, 4), (5,)):
            sections.append(appendix_table(q, ns, values))
    return "\n\n".join(sections)


def main() -> None:
    means = rows("means.csv")
    for q in range(1, 4):
        write(f"q{q}_means.tex", means_table(q, means))
    write("q3_pairs.tex", pairs_table(rows("pairs.csv")))
    write("appendix_results.tex", appendix())
    for name in ("q1_means.tex", "q2_means.tex", "q3_means.tex", "q3_pairs.tex", "appendix_results.tex"):
        print(OUTPUT / name)


if __name__ == "__main__":
    main()
