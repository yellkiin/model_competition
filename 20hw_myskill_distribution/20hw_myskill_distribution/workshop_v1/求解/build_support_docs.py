"""Write reviewer-facing support descriptions from the current material manifest."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'求解/支撑材料清单.json').read_text(encoding='utf-8'))
for q in manifest['questions']:
    title=q['title']
    text=f'''# {title}代码环境说明

## 环境与安装

正式运行环境使用 Python 3.13.15。独立重放与验证仅使用 Python 标准库；若继续运行绘图及论文构建，可在源码目录按 `python -m pip install -r requirements.txt` 安装随附依赖，锁定版本见 `requirements.lock.txt`。随机种子不适用：当前候选划分、排序和成对统计均为确定性过程。无需 GPU；具体运行时间依图规模而变，未设未经测量的硬件下限。

## 输入与依赖

题目原始100图和固定配置保留在 `../../其他数据/官方输入.zip`；2005份正式候选评估收据、原始响应与方案保留在 `../../其他支撑材料/正式候选评估.zip`。脚本会在本问 `源码/` 下解包并重建原始目录结构。{title}与前问的科学关系见正文；复现入口自身会对三问完整候选重新选择和独立核验。

## 运行方法

工作目录是 `支撑材料文件/{title}/源码/`。按顺序运行：{q['package_command']}。首次运行前，`源码/求解/正式实验/总体摘要.json` 不应存在；在新目录复制提交包后运行即可。若需重新运行，另取一份干净的提交包副本。

## 输出与中间图表

`源码/求解/正式实验/总体摘要.json` 给出三问一至五核的100例正式汇总；`源码/求解/问题一|二|三/结果/逐例官方评估.csv` 与验证JSON记录逐例选择和时间线核验；`源码/求解/正式实验/逐问核验摘要.json` 给出各问所选五百组方案的核验统计。`中间图表/` 收录正文未完整列出的本问候选比较表{('和明确标注为非官方的L2参数网格表' if q['question_id']=='q3' else '')}。

## 使用限制

此入口从封存的正式官方响应重放全部候选的择优和独立时间线核验，并逐份检查响应摘要；它不重新运行全部耗时的官方事件模拟。需要从原始图再次执行完整评估时，使用随附的 `求解/run_official_experiments.py`、候选生成源码和题目未改动的评估源码。非官方L2网格不能计入题定默认配置成绩。
'''
    (ROOT/q['environment_doc']).write_text(text,encoding='utf-8')

rows=[f"| {q['title']} | {q['summary']} |" for q in manifest['questions']]
rows.extend(f"| {name} | {manifest['category_descriptions'][name]} |" for name in ('其他数据','其他支撑材料'))
readme='''# 支撑材料说明

本材料对应《通用神经网络处理器下的多核调度问题》，包含三个问题的源码、环境说明、完整候选评估记录与必要结果表。

| 文件夹名称 | 主要内容 |
|---|---|
'''+ '\n'.join(rows)+'''

## 整体复现顺序

复制完整 `提交附件/` 到新的空目录。各问在本问 `源码/` 目录顺序运行 `python 问题一.py solve` 与 `python 问题一.py validate`（问题二、三依次替换入口名称）。独立重放只依赖 Python 标准库；完整绘图或论文环境可按每问说明安装 `requirements.txt`。运行会在各问源码目录新建 `数据/` 与 `求解/`，不会写回封存的公共归档。三个入口各自从全部正式候选响应重放一至五核结果，彼此独立。

## 数据与最终结果

`其他数据/官方输入.zip` 是题目官方原始图与固定配置，供竞赛评阅复核；未改动内部文件名。`其他支撑材料/正式候选评估.zip` 逐项保留原始官方响应、收据和方案，`问题一|二|三_逐例官方评估.csv` 给出完整正式结果，`总体摘要.json` 与 `统计分析.json` 给出跨问题汇总。六例L2容量—带宽网格是明确标记的非官方机制敏感性实验，不属于题定正式100例成绩。复现过程重算全部候选选择、1500条所选时间线并核对2005份响应摘要；原始官方事件模拟全部结果沿用封存的正式运行记录，未声称在独立复现中再次执行全部官方模拟。
'''
(ROOT/manifest['readme_source']).write_text(readme,encoding='utf-8')
print(ROOT/manifest['readme_source'])
