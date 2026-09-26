"""Write a schema-v2 draft manifest reflecting the curated, unaudited package.

The original builder intentionally omits draft-question sources and requires
model-selection evidence for complete questions. This manifest records the
real source selection without claiming either gate has passed.
"""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

W = Path(__file__).resolve().parents[2]
S = W / "求解/支撑材料源"
P = W / "提交附件"
F = P / "支撑材料文件"
N = W / "求解/规范化数据"


def rel(path):
    return path.relative_to(W).as_posix()


def item(src, desc, package_path):
    return dict(path=rel(src), description=desc, package_path=package_path)


def copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def main():
    for name in ("问题一", "问题二", "问题三"):
        copy(F / name / "代码环境说明.md", S / "说明源" / f"{name}.md")
    copy(P / "支撑材料说明.md", S / "说明源" / "支撑材料说明.md")
    copy(F / "其他数据" / "来源说明.md", S / "说明源" / "官方来源说明.md")
    copy(F / "其他支撑材料" / "评价规则.md", S / "说明源" / "评价规则.md")
    copy(F / "其他支撑材料" / "已选评价" / "selected_index.csv", S / "说明源" / "selected_index.csv")
    srcdir = F / "问题一" / "源码" / "research_a_orion_trident"
    for source in srcdir.rglob("*"):
        if source.is_file():
            copy(source, S / "方法源码" / "research_a_orion_trident" / source.relative_to(srcdir))
    for source in (F / "其他支撑材料" / "实际执行源码").rglob("*"):
        if source.is_file():
            copy(source, S / "执行源码" / source.relative_to(F / "其他支撑材料" / "实际执行源码"))
    for source in (F / "其他数据" / "官方输入").glob("*"):
        copy(source, S / "官方输入" / source.name)
    for source in (F / "其他数据" / "官方评价代码").glob("*.py"):
        copy(source, S / "官方评价代码" / source.name)

    common_sources = [item(p, "实际方法源码与完整本地依赖", "research_a_orion_trident/" + p.relative_to(S / "方法源码/research_a_orion_trident").as_posix())
                      for p in sorted((S / "方法源码/research_a_orion_trident").rglob("*")) if p.is_file()]
    questions = []
    for q, name in enumerate(("问题一", "问题二", "问题三"), 1):
        questions.append(dict(question_id=f"q{q}", title=name, status="draft",
                              entrypoint=rel(S / "方法源码/research_a_orion_trident/solve.py"),
                              run_command="python 支撑材料文件/其他支撑材料/复现程序/reproduce.py --output 复现输出",
                              source_files=common_sources,
                              run_verification=dict(status="pending", command="原搜索未在独立提交副本重跑；仅提供响应整理入口",
                                                    record_path=rel(S / "BUILD_GATE.md"), verified_at=""),
                              supplementary_materials=[dict(path=rel(N / "combined" / f"appendix_q{q}.csv"),
                                                            material_type="table", description="本问逐例官方评价结果",
                                                            reason="长表用于复核完整逐例结果", package_path=f"逐例结果_问题{q}.csv")],
                              supplementary_materials_note="真实逐例长表，未选择未审核的候选图",
                              environment_doc=rel(S / "说明源" / f"{name}.md"),
                              summary=("完整方法源码、代码环境说明和 " + ("Task/调度" if q == 1 else "跨核交接/DDR" if q == 2 else "L2/FIFO 同方案配对") + "逐例结果表。"),
                              package_command="python 支撑材料文件/其他支撑材料/复现程序/reproduce.py --output 复现输出",
                              depends_on=[] if q == 1 else [f"q{q-1}"]))
    extfiles = [item(p, "官方原始计算图与统一配置", "官方输入/" + p.name)
                for p in sorted((S / "官方输入").glob("*")) if p.is_file()]
    extfiles += [item(p, "题目附件官方评价源代码", "官方评价代码/" + p.name)
                 for p in sorted((S / "官方评价代码").glob("*.py"))]
    additional, official_outputs = [], []
    with (F / "其他支撑材料/已选评价/selected_index.csv").open(encoding="utf-8-sig", newline="") as stream:
        index = list(csv.DictReader(stream))
    for row in index:
        for key in ("main_plan", "paired_plan"):
            if row[key]:
                src = N / row[key]
                additional.append(item(src, "已选完整计划" if key == "main_plan" else "同一完整计划的无 L2 评价输入",
                                       "其他支撑材料/已选评价/" + row[key]))
        for key in ("main_response", "paired_response"):
            if row[key]:
                src = N / row[key]
                official_outputs.append(dict(path=rel(src), description="选定计划的原始官方评价响应",
                                             verification_path=rel(S / "BUILD_GATE.md"), status="pending",
                                             package_path="其他支撑材料/已选评价/" + row[key]))
    additional.append(item(S / "说明源/评价规则.md", "统一官方评价与聚合规则", "其他支撑材料/评价规则.md"))
    for p in sorted((S / "执行源码").rglob("*")):
        if p.is_file():
            additional.append(item(p, "该分片实际执行的完整方法源码快照",
                                   "其他支撑材料/实际执行源码/" + p.relative_to(S / "执行源码").as_posix()))
    additional.append(item(S / "reproduce.py", "从已选官方响应重算数据表和 SVG", "其他支撑材料/复现程序/reproduce.py"))
    additional.append(item(S / "说明源/selected_index.csv", "主配置与同方案配对文件索引",
                           "其他支撑材料/已选评价/selected_index.csv"))
    for p in sorted((F / "其他支撑材料/数据表").glob("*")):
        if p.is_file():
            additional.append(item(N / "combined" / p.name, "从已选官方响应规范化的结果表",
                                   "其他支撑材料/数据表/" + p.name))
    manifest = dict(schema_version="2.0", project_title="通用神经网络处理器下的多核调度问题",
                    package_status="draft", questions=questions,
                    external_data=[dict(data_id="official_a", name=".",
                                        description="100 图、统一配置和题目附件官方评价代码",
                                        source="题目官方附件；按三个原实验分片恢复原件",
                                        accessed_at="2026-09-25", collection_method="从本次原实验输入分片逐例拣选",
                                        license_or_terms="遵守赛事题目附件的使用条件", used_by=["q1", "q2", "q3"],
                                        files=extfiles, collection_scripts=[],
                                        provenance_file=rel(S / "说明源/官方来源说明.md"))],
                    external_data_note="所有计算图来自题目附件，未使用外部训练数据",
                    official_outputs=official_outputs,
                    readme_source=rel(S / "说明源/支撑材料说明.md"), additional_files=additional,
                    category_descriptions={"其他数据": "100 个原始计算图、官方配置、完整官方评价代码及来源说明。",
                                           "其他支撑材料": "1400 个已选主配置和 500 个同方案配对的计划/官方响应、各分片执行源码、数据表及整理复现程序。"})
    (W / "求解/支撑材料清单.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(W / "求解/支撑材料清单.json"), "questions": len(questions),
                      "plans": sum(bool(r[k]) for r in index for k in ("main_plan", "paired_plan")),
                      "official_outputs": len(official_outputs)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
