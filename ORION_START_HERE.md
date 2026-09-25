# 问题 A：当前实验入口

当前使用 **ORION Unified**：先阅读 `research_a_orion_unified/COMPARISON_REPORT.md` 和 `PLAN.md`，三台分别使用 `HOST_0.md`、`HOST_1.md`、`HOST_2.md`。

默认运行：`powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a_orion_unified\run_windows.ps1 -ShardIndex 0`，其他主机只改分片编号。

Fusion 与 Trident 的旧计划已移入 `history/orion_plans/`。旧代码和结果留在原路径供复现，不作为另一套同时启动的正式计划。不要重新跑三份完整百图。

原题和附件在 `题目/A题/`；文献在 `调研/A题_文献库/`。只更改我方调度方案，不更改原图、配置或官方评估器。
