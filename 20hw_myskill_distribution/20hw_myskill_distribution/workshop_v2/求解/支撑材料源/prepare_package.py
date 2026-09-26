"""Curate the selected response archive into the reader-facing support package.

This is a file-selection operation. It never runs the optimizer or evaluator.
"""
from __future__ import annotations

import csv
import json
import shutil
from collections import defaultdict
from pathlib import Path

W = Path(__file__).resolve().parents[2]
P = W.parents[1]
N = W / "求解/规范化数据"
OUT = W / "提交附件"
SUP = OUT / "支撑材料文件"
RAW = P / ".orion_paper_cache/local_raw"
SRC = RAW / "host1/records/research_a_orion_trident/runs/round01/shard_1/source_snapshot"
EXECUTED_SOURCES = {
    "shard0_win_save_1": RAW / "host0/records/run/source_snapshot",
    "shard1_trident_1_3": SRC,
    "shard2_trident_1_3": RAW / "host2/records/research_a_orion_trident/runs/round01/shard_2/source_snapshot",
}
OFFICIAL = {
    "shard0": RAW / "shard0_outer/records/03_inputs/official",
    "shard1": RAW / "host1/records/research_a_orion_trident/runs/assets_shard_1/official",
    "shard2": RAW / "host2/records/research_a_orion_trident/runs/assets_shard_2/official",
}
PUBLIC_FILES = ["main.csv", "pairs.csv", "means.csv", "pair_summary.csv", "anytime.csv",
                "anytime_summary.csv", "graph_features.csv", "cross_question.csv", "source_summary.csv"]


def table(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def copy(src, dst):
    if not src.is_file():
        raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main():
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError("提交附件目录已有内容；请先由负责人处理旧包，不自动覆盖或删除")
    for name in ("问题一", "问题二", "问题三"):
        (SUP / name / "源码").mkdir(parents=True, exist_ok=True)
        (SUP / name / "中间图表").mkdir(parents=True, exist_ok=True)
    for name in ("其他数据", "其他支撑材料"):
        (SUP / name).mkdir(parents=True, exist_ok=True)

    source_files = [p for p in SRC.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    for name in ("问题一", "问题二", "问题三"):
        for src in source_files:
            copy(src, SUP / name / "源码" / "research_a_orion_trident" / src.relative_to(SRC))
    for label, directory in EXECUTED_SOURCES.items():
        for src in directory.rglob("*"):
            if src.is_file() and "__pycache__" not in src.parts:
                copy(src, SUP / "其他支撑材料" / "实际执行源码" / label / src.relative_to(directory))

    official_code = OFFICIAL["shard1"] / "code"
    for src in official_code.glob("*.py"):
        copy(src, SUP / "其他数据" / "官方评价代码" / src.name)
    copy(OFFICIAL["shard1"] / "data/config.txt", SUP / "其他数据" / "官方输入" / "config.txt")

    main_rows = table(N / "combined/main.csv")
    pair_rows = table(N / "combined/pairs.csv")
    cases = {row["case"]: row["shard"] for row in main_rows if row["q"] == "0"}
    for case, shard in sorted(cases.items()):
        copy(OFFICIAL[shard] / "data" / f"{case}.json",
             SUP / "其他数据" / "官方输入" / f"{case}.json")

    pair_by_key = {(row["case"], int(row["n"])): row for row in pair_rows}
    index, provenance = [], []
    for row in main_rows:
        case, q, n = row["case"], int(row["q"]), int(row["n"])
        entry = dict(case=case, q=q, n=n, main_plan="", main_response="",
                     paired_plan="", paired_response="")
        for source_key, dest_key in (("plan", "main_plan"), ("response", "main_response")):
            rel = row[source_key].replace("\\", "/")
            if not rel:
                raise ValueError(f"缺少选定 {source_key}: {case} q{q} n{n}")
            copy(N / rel, SUP / "其他支撑材料" / "已选评价" / rel)
            entry[dest_key] = rel
            provenance.append(dict(case=case, q=q, n=n, role=source_key, selected_source=str(N / rel)))
        if q == 3:
            pair = pair_by_key[(case, n)]
            for source_key, dest_key in (("no_l2_plan", "paired_plan"),
                                         ("no_l2_response", "paired_response")):
                rel = pair[source_key].replace("\\", "/")
                if not rel:
                    raise ValueError(f"缺少配对 {source_key}: {case} n{n}")
                copy(N / rel, SUP / "其他支撑材料" / "已选评价" / rel)
                entry[dest_key] = rel
                provenance.append(dict(case=case, q=q, n=n, role=source_key, selected_source=str(N / rel)))
        index.append(entry)
    idx_path = SUP / "其他支撑材料" / "已选评价" / "selected_index.csv"
    with idx_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(index[0]))
        writer.writeheader()
        writer.writerows(index)

    for name in PUBLIC_FILES:
        src = N / "combined" / name
        if src.is_file():
            copy(src, SUP / "其他支撑材料" / "数据表" / name)
    copy(N / "combined/SUMMARY.json", SUP / "其他支撑材料" / "数据表" / "SUMMARY.json")
    for q, name in enumerate(("问题一", "问题二", "问题三"), 1):
        copy(N / "combined" / f"appendix_q{q}.csv",
             SUP / name / "中间图表" / f"逐例结果_问题{q}.csv")
    copy(Path(__file__).with_name("reproduce.py"),
         SUP / "其他支撑材料" / "复现程序" / "reproduce.py")

    for q, name in enumerate(("问题一", "问题二", "问题三"), 1):
        extra = ("Task 分组、单核对照与多核调度" if q == 1 else
                 "跨核交接与 DDR 数据搬运" if q == 2 else
                 "固定 Spill/Pipe、L2 驻留和 FIFO 语义")
        env = f"""# {name}代码环境说明\n\n## 环境与安装\n\n原实验源码使用 Python 3.12；本包的响应重算程序只依赖 Python 3.10 及以上的标准库，无需安装第三方包。原官方评价源码与配置位于 `../../其他数据/`，完整方法源码位于本目录 `源码/research_a_orion_trident/`。\n\n## 输入与依赖\n\n输入为 `../../其他数据/官方输入/` 中的 100 个原图和 `config.txt`。本问研究 {extra}；完整方法源码含公共模块与 vendor 依赖。选定计划与对应官方评价响应位于 `../../其他支撑材料/已选评价/`，逐项路径见 `selected_index.csv`。原实验搜索有运行预算和候选状态；本包默认不重新运行百图搜索。\n\n## 运行方法\n\n从提交附件目录执行：`python 支撑材料文件/其他支撑材料/复现程序/reproduce.py --output 复现输出`。该命令读取实际官方响应，重算逐例指标、聚合表和一张 SVG 图。原方法求解主入口为 `源码/research_a_orion_trident/solve.py`，需原实验 request 与运行环境；本包提供已选完整计划供审核，不将整理命令冒充重新求解。\n\n## 输出与中间图表\n\n本问较长逐例结果在 `中间图表/逐例结果_问题{q}.csv`；复现输出 `recomputed_main.csv`、`recomputed_pairs.csv`、`recomputed_means.csv`、`mean_speedup.svg` 与 `reproduction_report.json`。重算基于全部已选官方响应。\n\n## 使用边界\n\n计量单位为官方评价周期；性能比以每图单核原整图结果为分母。不同分片来自实际多主机记录，本说明不归并为单台机器。随机种子和本地预算属于原求解记录，整理命令不使用随机数。\n"""
        write(SUP / name / "代码环境说明.md", env)

    write(SUP / "其他数据" / "来源说明.md",
          "# 官方输入与评价代码来源\n\n本目录收录题目提供的 100 个原始计算图、统一 config.txt 和完整官方评价 Python 代码。图按原实验三个不相交分片拣选；程序保持官方原件。竞赛题目及附件的使用边界以赛事规定为准。运行公开整理程序只读取这些已提交文件和已选官方响应；未重新执行评价器。\n")
    write(SUP / "其他支撑材料" / "评价规则.md",
          "# 统一评价规则\n\n问题零单核基准使用原整图、单核官方入口。问题一至三的每个已选完整计划对应官方返回的总体任务执行时间（Makespan）和搬运量。问题三的无 L2 数值是在同一完整计划上按问题二场景重评，不改变映射、顺序或搬运安排。逐图加速比为该图单核 Makespan 除以当前配置 Makespan，聚合均值是逐图比值的算术平均。所有时间数值的单位均为官方评价周期。三项后补官方评价用于填齐响应，不回填原搜索时钟或 30 秒轨迹。不同分片保留各自真实来源，不假定为同一物理主机。`实际执行源码/` 保留三个分片各自的完整代码快照，问题目录中的方法源码为 shard1 快照；shard0 执行版本为 trident-1.3-win-save.1。\n")
    description = [
        ("问题一", "完整方法源码、代码环境说明和 Task/调度逐例结果表。"),
        ("问题二", "完整方法源码、代码环境说明和跨核交接/DDR 逐例结果表。"),
        ("问题三", "完整方法源码、代码环境说明和 L2/FIFO 同方案配对逐例结果表。"),
        ("其他数据", "100 个原始计算图、官方配置、完整官方评价代码及来源说明。"),
        ("其他支撑材料", "1400 个已选主配置和 500 个同方案配对的计划/官方响应、各分片执行源码、数据表及整理复现程序。"),
    ]
    text = "# 支撑材料说明\n\n本材料对应通用神经网络处理器下的多核调度问题，共三问。\n\n| 文件夹名称 | 主要内容 |\n|---|---|\n"
    text += "".join(f"| {name} | {desc} |\n" for name, desc in description)
    text += """\n## 整体复现顺序\n\n使用 Python 3.10 及以上版本。从本说明所在的提交附件目录执行：\n\n```text\npython 支撑材料文件/其他支撑材料/复现程序/reproduce.py --output 复现输出\n```\n\n整理程序从 `其他支撑材料/已选评价/selected_index.csv` 找到每项已选计划与官方响应，读取响应重算逐例指标、同方案配对、均值及 SVG 图，并与附带主表的关键整数逐项比较。它不运行百图搜索。\n\n## 数据与最终结果\n\n原始 100 图、config.txt 和官方评价源码位于 `支撑材料文件/其他数据/`。最终的逐例主表、配对表和聚合表位于 `支撑材料文件/其他支撑材料/数据表/`；完整已选计划与官方响应位于 `已选评价/`，三个分片的实际执行源码快照位于 `实际执行源码/`。三个逐问中间图表为按问题展开的逐例长表。官方评价的时间单位为周期；原实验涉及不同分片与主机，本包按统一评价规则汇总结果，不对物理运行环境作单机断言。\n"""
    write(OUT / "支撑材料说明.md", text)
    internal = W / "求解/支撑材料源"
    (internal / "PUBLIC_SELECTION_PROVENANCE.json").write_text(json.dumps({
        "selection": "exactly 1400 selected main rows and 500 same-plan pairs from final combined CSV",
        "source_index": str(N / "combined/SOURCE_INDEX.json"),
        "later_official_recalculations": str(W / "求解/补算/pr38_missing_20260926/RECALCULATION_MANIFEST.json"),
        "official_graph_roots": {k: str(v) for k, v in OFFICIAL.items()},
        "method_source_snapshot": str(SRC),
        "executed_source_snapshots": {k: str(v) for k, v in EXECUTED_SOURCES.items()},
        "entries": provenance,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"package": str(OUT), "graphs": len(cases), "main": len(main_rows),
                      "pairs": len(pair_rows), "method_source_files_each_question": len(source_files)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
