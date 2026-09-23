"""同源数据绘图、TeX 数表与受控编译。内置版式仅用于演练。"""
from __future__ import annotations

import math
import os
import re
import shutil
import statistics
import subprocess
from pathlib import Path

from .core import Workspace
from .research import eligible_sources


def tex(text: object) -> str:
    mapping = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
               "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
               "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(mapping.get(c, c) for c in str(text))


def metric_rows(ws: Workspace) -> list[dict]:
    value = ws.read("results/metrics.json")
    if value.get("metric") != "RMSE" or value.get("direction") != "min":
        raise ValueError("内置数表器仅支持 RMSE；其他指标需实现独立适配器")
    rows, seen = value.get("rows", []), set()
    if not rows:
        raise ValueError("没有实验结果")
    for r in rows:
        key = (r["model"], r["seed"], r["split"])
        n, sse, rmse = r["n"], r["sse"], r["rmse"]
        if key in seen or type(n) is not int or n <= 0:
            raise ValueError("重复结果或无效分母")
        if not all(math.isfinite(v) for v in (sse, rmse)) or sse < 0:
            raise ValueError("结果包含 NaN/Inf 或负 SSE")
        if not math.isclose(rmse, math.sqrt(sse / n), rel_tol=1e-8, abs_tol=1e-12):
            raise ValueError("RMSE 与 SSE/N 不一致")
        seen.add(key)
    return rows


def render(ws: Workspace) -> None:
    ws.require_fresh(["results/metrics.json"])
    if not ws.read("results/metrics.json").get("synthetic"):
        raise ValueError("内置正文仅用于 synthetic 演练；真实赛题请使用 plot 与写作角色")
    generator = "code/workbench_publication.py"
    shutil.copyfile(Path(__file__), ws.path(generator))
    rows = [r for r in metric_rows(ws) if r["split"] == "test"]
    groups = {name: [r for r in rows if r["model"] == name]
              for name in sorted({r["model"] for r in rows})}
    if not groups:
        raise ValueError("没有测试集结果")
    populations = [{(r["seed"], r["n"]) for r in group} for group in groups.values()]
    if any(p != populations[0] for p in populations):
        raise ValueError("模型比较不是相同种子/分母的配对")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = list(groups)
    means = [statistics.mean(r["rmse"] for r in groups[name]) for name in names]
    stds = [statistics.stdev(r["rmse"] for r in groups[name]) if len(groups[name]) > 1 else 0
            for name in names]
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    ax.errorbar(range(len(names)), means, yerr=stds, fmt="o", capsize=5)
    ax.set_xticks(range(len(names)), names)
    ax.set_ylabel("Test RMSE (a.u.); mean +/- sample SD")
    ax.set_xlabel("Model; all prespecified repetitions included")
    ax.set_ylim(bottom=0)
    ax.set_xlim(-0.5, max(0.5, len(names) - 0.5))
    fig.tight_layout()
    for ext in ("pdf", "png"):
        name = f"figures/comparison.{ext}"
        fig.savefig(ws.path(name), dpi=200)
        ws.record(name, ["results/metrics.json", generator], "figure")
    plt.close(fig)
    lines = [r"\begin{tabular}{lrrr}", r"\toprule",
             r"模型 & 重复数 & RMSE 均值 & 样本标准差 \\", r"\midrule"]
    for name, mean, sd in zip(names, means, stds):
        lines.append(f"{tex(name)} & {len(groups[name])} & {mean:.6f} & {sd:.6f}" + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    ws.path("paper/table.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    ws.record("paper/table.tex", ["results/metrics.json", generator], "table")
    sources = eligible_sources(ws)
    bibliography = [r"\begin{thebibliography}{99}"]
    bibtex = []
    for source in sources:
        key = source["id"]
        bibliography.append(r"\bibitem{" + key + "}" + tex(source["title"]) + ". " + tex(source["url"]))
        bibtex.append("@misc{" + key + ",\n  title={" + tex(source["title"]) + "},\n  note={" + tex(source["url"]) + "}\n}")
    bibliography.append(r"\end{thebibliography}")
    ws.path("paper/references.tex").write_text("\n".join(bibliography) if sources else "% No verified references\n", encoding="utf-8")
    ws.path("paper/references.bib").write_text("\n\n".join(bibtex) + "\n", encoding="utf-8")
    for name in ("paper/references.tex", "paper/references.bib"):
        ws.record(name, ["sources.json"], "references")
    citations = ", ".join(r"\cite{" + s["id"] + "}" for s in sources)
    document = r"""\documentclass[UTF8,fontset=fandol,11pt]{ctexart}
\usepackage[a4paper,margin=25mm]{geometry}
\usepackage{amsmath,booktabs,graphicx,hyperref,float}
\title{建模整合工具链演练：数值、图表与论文的一致性}
\author{}\date{}
\begin{document}\pagestyle{plain}\maketitle
\begin{abstract}
本文是工具链演练稿，不是华为杯赛题解答，也不是官方竞赛模板。
比较结果由固定划分的数据计算，表格与图件来自同一结果文件。
自动化校验只能检查所实现的结构与数值条件，不能替代人工科学审稿。
\end{abstract}
\section{实验设置与方法}
内置演练采用合成回归数据，比较一次与二次多项式最小二乘模型。
所有模型只在训练集拟合，通过验证集选择阶数，测试集仅用于最终评价。
种子及数据划分记录于原始 CSV；各方法使用相同评价样本。
二次项移除构成结构消融，不是针对真实竞赛提出的新算法。
\section{评价口径}
\[\mathrm{RMSE}=\sqrt{\frac{\mathrm{SSE}}{N}},\qquad
\mathrm{SSE}=\sum_{i=1}^{N}(\widehat y_i-y_i)^2.\]
先计算每次运行的 RMSE，再对预设重复等权汇总。误差条表示样本标准差，
不是置信区间，也不表示统计显著性。单位为任意单位（a.u.）。
\section{同源结果}
\begin{center}\input{paper/table.tex}\end{center}
\begin{figure}[H]\centering
\includegraphics[width=.82\textwidth]{figures/comparison.pdf}
\caption{测试误差比较。所有预设重复均纳入统计。}\end{figure}
\section{局限与人工复核}
合成数据来自预设生成机制，本例不能证明模型在实际赛题中的优越性。
正式论文须重新建立题目模型、完成敏感性与稳健性分析，并按当年官方模板排版。
本稿保留草稿标记，禁止直接作为参赛作品上传。
\section{参考资料入口}
""" + ("经阅读定位的资料：" + citations + "。\n" if sources else "本演练没有引入外部文献结论。\n")
    document += r"\input{paper/references.tex}" + "\n" + r"\end{document}" + "\n"
    if not ws.read("results/metrics.json").get("synthetic"):
        raise ValueError("内置正文仅用于 synthetic 演练；真实赛题请按角色协议另写正文")
    ws.path("paper/draft.tex").write_text(document, encoding="utf-8")
    ws.record("paper/draft.tex", ["paper/table.tex", "figures/comparison.pdf", "paper/references.tex"], "tex")


def compile_tex(ws: Workspace, source: str, trusted: bool = False) -> str:
    if not trusted:
        raise ValueError("请先审查 TeX 并显式提供 --trusted-tex；编译器不是安全沙箱")
    path = ws.path(source)
    if path.suffix != ".tex" or not re.fullmatch(r"[A-Za-z0-9_-]+", path.stem):
        raise ValueError("TeX 主文件名必须为 ASCII 字母/数字/下划线/短横线")
    if not shutil.which("xelatex"):
        raise RuntimeError("缺少 XeLaTeX；请安装 TeX Live 的中文支持")
    ws.require_fresh([source])
    pdf = f"build/{path.stem}.pdf"
    ws.path(pdf).unlink(missing_ok=True)
    command = ["xelatex", "-no-shell-escape", "-halt-on-error", "-interaction=nonstopmode",
               "-recorder", "-output-directory=build", source]
    env = dict(os.environ, openin_any="p", openout_any="p")
    for iteration in range(3):
        process = subprocess.run(command, cwd=ws.root, env=env, capture_output=True, timeout=60)
        ws.path("build/compile.stdout").write_bytes(process.stdout + process.stderr)
        if process.returncode:
            ws.path(pdf).unlink(missing_ok=True)
            raise RuntimeError("XeLaTeX 失败；见 build/compile.stdout")
        aux = ws.path(f"build/{path.stem}.aux")
        if iteration == 0 and aux.exists() and r"\bibdata" in aux.read_text(errors="replace"):
            if not shutil.which("bibtex"):
                ws.path(pdf).unlink(missing_ok=True)
                raise RuntimeError("需要 BibTeX，但当前未安装")
            bibliography = subprocess.run(["bibtex", f"build/{path.stem}"], cwd=ws.root,
                                          env=env, capture_output=True, timeout=30)
            ws.path("build/bibtex.stdout").write_bytes(bibliography.stdout + bibliography.stderr)
            if bibliography.returncode:
                ws.path(pdf).unlink(missing_ok=True)
                raise RuntimeError("BibTeX 失败；见 build/bibtex.stdout")
    log = ws.path(f"build/{path.stem}.log").read_text(encoding="utf-8", errors="replace")
    if re.search(r"(?:Citation|Reference).+undefined|There were undefined references", log):
        ws.path(pdf).unlink(missing_ok=True)
        raise ValueError("仍有未解析引用；不登记为已编译产物")
    # TeX recorder 捕获实际本地输入，避免漏登记手写 input/graphics/bib。
    dependencies = {source}
    fls = ws.path(f"build/{path.stem}.fls").read_text(errors="replace")
    for line in fls.splitlines():
        if not line.startswith("INPUT "):
            continue
        target = (ws.root / line[6:]).resolve()
        if target.is_relative_to(ws.root) and target.is_file():
            name = target.relative_to(ws.root).as_posix()
            if not name.startswith("build/"):
                dependencies.add(name)
    # BibTeX 的 bib 文件不一定出现在 XeLaTeX 的 recorder 中。
    for target in ws.root.rglob("*.bib"):
        dependencies.add(target.relative_to(ws.root).as_posix())
    ws.record(pdf, sorted(dependencies), "pdf")
    ws.record(f"build/{path.stem}.log", sorted(dependencies), "compile_log")
    return pdf
