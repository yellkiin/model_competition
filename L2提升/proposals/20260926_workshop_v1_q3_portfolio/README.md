# 基于早期 workshop_v1 的问题三组合优化与 L2 分析

本目录保存 2026-09-26 完成的一轮问题三实验：在官方计算图、评估器和硬件参数不变的条件下，扩展通用切图、分核与缓存相关候选，通过官方评估择优，并保留原问题三方案作为回退。

**本轮起点是早期 `workshop_v1` 的 `components / bands8 / batches800` 候选组合。仓库已有 `orion_20260926` 的 Unified/Trident 成果，其起点与本轮不同。这里的改善幅度不能与 Trident 强起点上的改善幅度直接混比，也不构成优于 Trident 的结论。** 如需比较，应在相同输入、官方参数、核数、基线、评分口径和搜索预算下重放双方方案。

本轮保留问题一、问题二原方案与成绩，未修改原论文 PDF。新增成果作为独立提案发布到 `L2提升/proposals/20260926_workshop_v1_q3_portfolio/`。

## 结果与统计口径

题给 100 个图，各 1—5 核，共 **500 个配置：353 个严格改善，0 个退步**。五核结果如下：

| 指标 | 早期 workshop_v1 基线 | 本轮方案 |
| --- | ---: | ---: |
| 相对原单核参考的平均加速比 | 3.610380 | 4.135514 |
| 五核严格改善配置 | — | 76 / 100 |
| 五核问题三执行时间的逐例平均降幅 | — | 14.8358% |
| 同方案开启 L2 的逐例平均时间收益 | 约 2.1410% | 3.0149% |

这些数值区分了两个问题：

- **算法整体收益**：固定官方 L2 配置，比较旧方案和新方案的总执行时间；五核逐例平均降时 **14.8358%**，包含切分、分核、私有缓存压力和访存时序变化的共同影响。
- **缓存自身收益**：固定同一方案，分别运行无 L2 与有 L2 的评估；在旧、新方案上的五核逐例平均时间收益分别约为 **2.1410%** 和 **3.0149%**。不能把整体算法收益全部归为 L2 硬件收益，也不能将上述两个百分比直接相加。

平均加速比逐例计算 `原单核参考时间 / 问题三时间` 后取算术平均；原单核分母保持不变。平均降时逐例计算 `1 - 新时间 / 旧时间` 后取平均，不是平均加速比的倒数。有限候选搜索没有证明全局最优。

逐例结果与审计依据：

- [完整分析与改进报告](./问题三_L2分析与算法改进报告.md)
- [选中方案的 500 配置 CSV](./selected_results.csv) / [JSON](./selected_results.json)
- [各问原成绩与新问题三成绩对照](./all_questions_comparison.csv)
- [总体统计](./summary.json)、[收益分布](./gain_distribution.json)、[最终审计](./final_audit.json)
- [代表算例的改善机制](./代表算例改进机制.md)、[机制数据](./representative_mechanisms.json)
- [L2 理论边界与原方案诊断](./analysis_potential/结论.md)、[五核逐例诊断](./analysis_potential/five_core_potential.csv)
- [独立统计核查](./analysis_potential/final_statistics_check.json)、[统计结论复核](./final_statistics_review.md)
- [500 个计划的清单及 SHA-256](./plan_archive_manifest.json)

审计记录验证了清单中的 3661 个受保护文件未变，覆盖原 Q1/Q2 已选计划、结果及求解源码；这不是整个仓库所有文件的哈希审计。官方参数保持 DDR 60 B/cycle、L2 250 B/cycle、L2 容量 1 MiB、L1 512 KiB、UB 128 KiB、跨核释放延迟 500 cycle。

## 发布内容与复现边界

本目录保留成果原文件名、`analysis_potential/` 子目录、Markdown 报告、CSV/JSON 数据、全部 Python 源文件，以及 [问题三优化计划 500 组 tar.xz 归档](./问题三_优化计划_500组.tar.xz)。tar.xz 归档 内的计划布局为：

```text
n1/case_001_multicore_res.json
...
n5/case_100_multicore_res.json
```

tar.xz 归档 包含每个算例、每种核数的最终问题三计划，合计 500 个。**本次不发布 `evaluations/` 中全部候选的完整原始时间线。** 报告和历史 JSON 中出现的本机绝对路径仅用于记录来源，读者不需要访问作者电脑。历史记录中的部分工作区相对路径也不直接指向当前提案目录；请按下文恢复目录层级，并以发布的 tar.xz 归档、CSV、JSON 和清单定位成果。

发布代码保留原始字节，因此仍依赖原项目目录结构。仓库已有的工作区位置为：

[`20hw_myskill_distribution/20hw_myskill_distribution/workshop_v1`](../../../20hw_myskill_distribution/20hw_myskill_distribution/workshop_v1)

使用前需具备以下依赖：

- 工作区的 `数据/原始/A题官方附件/code/`、`data/config.txt` 和待运行计算图；
- 工作区的 `求解/solve_components.py`、`solve_bands.py`、`solve_batches.py`、`verify_official_results.py`；
- 将本目录的 Python 文件复制到该工作区的 `求解/q3_l2_optimization_20260926/`，保留 `analysis_potential/` 的相对层级；
- 可运行本项目代码的 Python；本轮通用入口实测使用 Python 3.12，入口及候选代码使用标准库。

**通用入口与历史批量实验的依赖不同：** `solve_q3_optimized.py` 只需要图、官方代码/配置、上述旧求解器，以及一个明确提供的可行基线计划。它可以使用本次 tar.xz 归档 中的计划，不依赖早期全部候选档案。`optimize_q3.py`、批量审计和旧成绩重建还需要 `求解/正式实验/` 中的原逐例表、候选计划、评估 receipt、压缩时间线等。仓库里的这些旧候选档案是否齐全尚未确认，因此不能把本发布目录描述为完整历史实验的一键复现包；发现缺档时应补齐相应原记录，或通过官方评估重新生成，不能用汇总表代替原始执行证据。

## 安装位置、计划解压与通用入口

以下 PowerShell 示例从仓库根目录执行，所有路径均相对当前克隆，无需作者本机盘符。输出单独放在 `求解/q3_l2_replay_20260926/`。若该输出目录已经存在，请换一个新名称，避免覆盖先前复现结果。

```powershell
$repoRoot = (Get-Location).Path
$proposalRoot = Join-Path $repoRoot 'L2提升/proposals/20260926_workshop_v1_q3_portfolio'
$workshopRoot = Join-Path $repoRoot '20hw_myskill_distribution/20hw_myskill_distribution/workshop_v1'
$solverRoot = Join-Path $workshopRoot '求解/q3_l2_optimization_20260926'
$replayRoot = Join-Path $workshopRoot '求解/q3_l2_replay_20260926'

New-Item -ItemType Directory -Path $solverRoot -Force | Out-Null
Get-ChildItem -LiteralPath $proposalRoot -Filter '*.py' -File | Copy-Item -Destination $solverRoot
Copy-Item -LiteralPath (Join-Path $proposalRoot 'analysis_potential') -Destination $solverRoot -Recurse -Force
New-Item -ItemType Directory -Path $replayRoot | Out-Null
python -m tarfile -e (Join-Path $proposalRoot '问题三_优化计划_500组.tar.xz') `
  (Join-Path $replayRoot 'published_plans')
```

先重放 tar.xz 归档 中的一个已发布方案，验证本地依赖与官方执行。`--max-candidates 0` 只验证并导出所给基线，不重新搜索：

```powershell
python -X utf8 -B (Join-Path $solverRoot 'solve_q3_optimized.py') `
  (Join-Path $workshopRoot '数据/原始/A题官方附件/data/case_044.json') -n 5 `
  --baseline-plan (Join-Path $replayRoot 'published_plans/n5/case_044_multicore_res.json') `
  --max-candidates 0 `
  -o (Join-Path $replayRoot 'verified_case044_n5/plan.json')
```

再对任意可行基线尝试通用候选改进，输出到另一目录：

```powershell
python -X utf8 -B (Join-Path $solverRoot 'solve_q3_optimized.py') `
  (Join-Path $workshopRoot '数据/原始/A题官方附件/data/case_044.json') -n 5 `
  --baseline-plan (Join-Path $replayRoot 'published_plans/n5/case_044_multicore_res.json') `
  --families 'original,band,cache,refine' `
  --budget-seconds 300 --timeout-seconds 30 --baseline-timeout-seconds 120 --max-candidates 24 `
  -o (Join-Path $replayRoot 'search_case044_n5/plan.json')
```

以上示例以**本轮已优化方案**作为基线，结果可能不再改善；它用于重放和继续搜索，不会重现相对早期旧方案的 14.8358% 平均降幅。要复核旧到新的降幅，必须补齐并使用同一个早期基线集合，遵循前述统计口径。

通用入口先重放基线并进行独立检查。候选失败、超时或成绩更差时保留已验证 incumbent，按 `(总周期数, 新增搬运字节数)` 选择，完全持平时保留原方案。默认总搜索预算 300 秒不含基线验证，候选生成和评价分别受单项超时与剩余总预算约束。基线无法核验时返回 `BASELINE_UNVERIFIED`，不发布未经验证的计划。输出包含计划、`.receipt.json` 和独立运行子目录；更详细参数见 [通用 Q3 改进器说明](./README_通用Q3改进器.md)。

## 对原成果的影响

本轮只提交新的问题三方案和分析材料，原 Q1/Q2 方案与成绩保持原样，原论文 PDF 尚未更新。新问题三计划在其他题目场景下的成绩没有相同的不退步保证，因此不要直接替换原 Q1/Q2 提交计划。论文后续采用本轮结果时，需要同步更新问题三正文、图表、摘要与相应支撑材料，并继续区分算法整体收益和同方案的纯 L2 收益。

## 发布校验与来源

[发布清单](./PUBLICATION_MANIFEST.json)记录原文件与发布副本的 SHA-256；源码、CSV/JSON 结果及归档内的所有成员保留原始字节，Markdown 仅增加发布说明及修正链接。[数据位置索引](./DATA_INDEX.md)说明外部依赖和未随包提交的历史时间线。发布不重新执行原全量实验，上传前只进行归档与内容核查。

AI 辅助记录：本轮使用 Codex 协助阅读题面与源码、提出候选、运行官方评估、复核统计和整理报告；所有成绩来自题给评估器，保留原始审计回执及源码哈希。

发布归档采用 Python 标准库支持的 tar.xz，将原 ZIP 的同一批 503 个成员（500 计划和 3 份清单/指标文件）重新压缩；已逐文件验证内容完全相同。历史审计中记录的 ZIP 哈希仍对应原执行机 ZIP；本次发布归档的哈希另列于发布清单。此变更只为适配上传接口，不改变计划或成绩。

[依赖哈希核查](./dependency_hash_check.json)覆盖 116 个仓库依赖：15 个与实测文件字节相同；100 个图和原逐例 CSV 仅有 CRLF/LF 换行差异，JSON/CSV 内容相同。通用入口可使用仓库文件；复核历史保护快照的原始字节 SHA 时须恢复相应原换行格式，不能将换行变化误判为算法或图内容改变。
