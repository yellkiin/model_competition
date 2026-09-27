"""Project-local appendix adapter using the original render_appendix_tex function.

The original end-to-end builder requires completed support gates and hashes.
This adapter only renders the actual attachment inventory and selected source
line ranges; it does not issue a PASS or change shared tooling.
"""
from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

W = Path(__file__).resolve().parents[2]
ROOT = W.parents[0]
ORIGINAL = ROOT / "华为杯_论文规范模板/tools/build_appendix.py"
PAPER = W / "论文"
SUPPORT = W / "提交附件/支撑材料文件"
PAIRS = W / "求解/规范化数据/combined/pairs.csv"


def source_segment(question, source, first, last, caption):
    path = SUPPORT / question / "源码/research_a_orion_trident" / source
    if not path.is_file():
        raise FileNotFoundError(path)
    return dict(caption=caption, language="python", firstline=first,
                lastline=last, firstnumber=first,
                paper_relative_path="../提交附件/支撑材料文件/" + question +
                                    "/源码/research_a_orion_trident/" + source)


def num(value):
    return f"{int(value):,}"


def create_pairs_tex():
    with PAIRS.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 500:
        raise ValueError("配对长表需要真实 500 组")
    lines = [
        "% 由 combined/pairs.csv 的 500 组实际同方案官方响应生成；仅显示命中率保留六位小数。",
        r"\Needspace{8\baselineskip}",
        r"\begingroup\normalsize",
        r"\setlength{\tabcolsep}{1.5pt}",
        r"\setlength{\LTleft}{0pt}\setlength{\LTright}{0pt}",
        r"\setlength{\LTcapwidth}{160mm}",
        r"\begin{longtable}{@{}p{12mm}>{\raggedleft\arraybackslash}p{9mm}>{\raggedleft\arraybackslash}p{24mm}>{\raggedleft\arraybackslash}p{24mm}>{\raggedleft\arraybackslash}p{30mm}>{\raggedleft\arraybackslash}p{30mm}>{\raggedleft\arraybackslash}p{23mm}@{}}",
        r"\caption{问题三逐图逐核同方案有无 L2 的官方评价结果}\label{tab:appendix_q3_all_pairs}\\",
        r"\toprule",
        r"算例 & 核数 & \shortstack{无L2\\周期} & \shortstack{有L2\\周期} & \shortstack{无L2额外\\COPY/B} & \shortstack{有L2额外\\COPY/B} & \shortstack{字节\\命中率}\\",
        r"\midrule",
        r"\endfirsthead",
        r"\caption[]{问题三逐图逐核同方案有无L2的官方评价结果（续）}\\",
        r"\toprule",
        r"算例 & 核数 & \shortstack{无L2\\周期} & \shortstack{有L2\\周期} & \shortstack{无L2额外\\COPY/B} & \shortstack{有L2额外\\COPY/B} & \shortstack{字节\\命中率}\\",
        r"\midrule",
        r"\endhead",
        r"\bottomrule",
        r"\endfoot",
    ]
    for row in sorted(rows, key=lambda r: (r["case"], int(r["n"]))):
        case = int(row["case"].split("_")[1])
        lines.append(f"{case:03d} & {int(row['n'])} & {num(row['without_l2'])} & {num(row['with_l2'])} & "
                     f"{num(row['without_l2_added_bytes'])} & {num(row['with_l2_added_bytes'])} & "
                     f"{float(row['hit_rate']):.6f}\\\\")
    lines.extend([r"\end{longtable}", r"\endgroup", ""])
    target = PAPER / "章节内容/数据表/appendix_pairs.tex"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def main():
    spec = importlib.util.spec_from_file_location("original_build_appendix", ORIGINAL)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    inventory = [
        dict(path="问题一", description="完整方法源码、代码环境说明和 Task/调度逐例结果表。"),
        dict(path="问题二", description="完整方法源码、代码环境说明和跨核交接/DDR 逐例结果表。"),
        dict(path="问题三", description="完整方法源码、代码环境说明和 L2/FIFO 同方案配对逐例结果表。"),
        dict(path="其他数据", description="100 个原始计算图、官方配置、完整官方评价代码及来源说明。"),
        dict(path="其他支撑材料", description="1400 个已选主配置和 500 个同方案配对的计划/官方响应、各分片执行源码、数据表及整理复现程序。"),
    ]
    problems = [
        dict(code=[source_segment("问题一", "solve.py", 58, 121, "官方评价与字典序接受"),
                   source_segment("问题一", "sources.py", 43, 49, "初始结构候选构造")]),
        dict(code=[source_segment("问题二", "vendor/orion/core.py", 350, 376, "跨核交接与 DDR 搬运量"),
                   source_segment("问题二", "vendor/orion/core.py", 377, 431, "全局及候选下界")]),
        dict(code=[source_segment("问题三", "fifo.py", 19, 63, "FIFO 事件驱动的候选定位与顺序移动"),
                   source_segment("问题三", "solve.py", 258, 275, "同一完整方案的无 L2 官方配对")]),
    ]
    rendered = module.render_appendix_tex(inventory, problems)
    marker = "\\AppendixEnd\n"
    if not rendered.endswith(marker):
        raise ValueError("原附录生成函数尾部格式变化")
    rendered = rendered[:-len(marker)]
    rendered += "\\AppendixPart{5}{逐例结果与同方案配对}\n"
    rendered += "\\input{章节内容/数据表/appendix_results.tex}\n"
    rendered += "\\input{章节内容/数据表/appendix_pairs.tex}\n"
    rendered += "\\input{章节内容/算法参数.tex}\n"
    rendered += "\\AppendixEnd\n"
    pairs_target = create_pairs_tex()
    target = PAPER / "章节内容/99_附录.generated.tex"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")
    receipt = dict(generator="original build_appendix.render_appendix_tex; project-local adapter",
                   original_generator=str(ORIGINAL), status="generated_not_audited",
                   attachment_rows=len(inventory), question_count=len(problems),
                   code_segments=sum(len(x["code"]) for x in problems),
                   q3_pair_rows=500, appendix_tex=str(target), pair_table_tex=str(pairs_target),
                   source="actual curated package and combined/pairs.csv",
                   note="No full support-package audit, hash pass, or PDF compilation asserted")
    (W / "求解/支撑材料源/APPENDIX_GENERATION_RECORD.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
