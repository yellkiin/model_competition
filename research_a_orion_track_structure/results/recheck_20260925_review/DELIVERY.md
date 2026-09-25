# 完整交付位置与复核方式

PR #30 接续 #29，不自动合并。CI原始实验run为36085958693；36088539081只是最后的文件发布，不是实验。

## 仓库与会话附件的区别

本仓库的 `../recheck_20260925_run_36085958693/` 保存七图CI分图分阶段的per_case.csv、trajectory.csv、manifest和真实artifact索引。本目录保存中文REPORT、claim_check、计数、只读下界推导与本地123个算法臂的LOCAL_ARMS.json摘要。完整聚合CSV和17张轨迹图在以下会话交付包中，不把尚未上传的本地文件冒称已存在于GitHub。

- `ORION_structure_recheck_20260925_code_reports.zip`：完整结构线代码、文献依据、Windows脚本、LOCAL_AGENT_PROMPT、聚合per_case/trajectory/paired_compare/replay_compare/claim_check、诊断及图表。
- `ORION_structure_recheck_20260925_raw_local.zip`：本地固定原评估、v3同种子实验、v4反例实验、失败修正及各版本源码快照，约73MB。
- `ORION_structure_recheck_20260925_raw_ci.zip`：七个原始CI artifact ZIP和索引，约179MB。

会话附件是真实交付文件，但不是GitHub release/artifact，未给它们编造远端ID。CI七个原始artifact都有真实ID，见EVIDENCE_INDEX，保留期至2026-12-24；长期保存请及时取得副本。

## 还原用于复核的文件布局

代码/报告包和本地原始包均以 `research_a_orion_track_structure/` 为目录前缀，在隔离完整仓库根目录展开；不要覆盖其他正在运行的工作树。CI原始包外层包含 `orion_recheck_XXX_36085958693.zip`，分别展开至：

`research_a_orion_track_structure/results/recheck_20260925_run_36085958693/case_XXX/`

每个case包中有fixed、warm30、cold30_cap8、完成的cold300阶段、source等。源数据导出artifact10843114510含原始day01记录；需要正式种子追溯时只取所需raw_day01记录，不覆盖当前算法源码。

`plot_recheck.py`读取原始all_jobs.json中的已观察合法解事件画阶梯曲线；trajectory.csv提供30/60/120/300的数值前缀。只有代码/报告包时可直接查看已有图；重新绘图需要按上述布局展开原始包。重新导表或绘图都不算新实验。

求解入口依赖冻结仓库中的公共ORION与原官方附件，不在交付包重复分发官方输入或文献PDF。CPU求解部分只依赖标准库；绘图需要已有matplotlib。Windows脚本优先D:\python\python.exe、3.12.x，本轮不是Windows实测。

## 验收边界

399个比较臂不包含未启动的016六个300秒扩展臂。107次固定重放含跨环境重复，不是107个不同plan。127个Q3同方案配对均已实际完成。

最终根目录修正版为v4，CI run执行的是v2b，本地v3/v4分开记录。v4修复064短预算退步但在044产生新退步，不推荐默认替代公共求解器；PR可审查不等于算法全量验收。没有600秒、正式100图1–5核新曲线或足够重复的显著性结论。
