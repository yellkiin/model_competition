# ORION Anytime Wu — v4

独立方向：真实 FIFO 复用时序 + 候选选择/停止 + 结构触发尾核续优化。只修改 `research_a_orion_track_anytime/`；公共 ORION、原图/config、官方 evaluator 和其它研究线均不改。

## 当前推荐用法

v4 定位为**从已验证 incumbent 继续优化的安全候选池**。候选只有通过未修改官方评估和 audit、且 `(Makespan, added_copy_bytes)` 更优时才替换 incumbent。冷启动仍应保留旧 ORION 对照；case_048 实测表明 v4 冷启动可能更弱，但从旧 incumbent 续优化可恢复并进一步改善。

主要入口：

- `plugin.py`：真实 FIFO consumer/fill/evictor 时序候选；
- `structural.py`：只由结构/真实时间线触发的 tail-rebalance 与 private-island 候选，无 case ID 特判；
- `selector.py` / `adapter.py`：族首评、校准、成本准入、incumbent 改善后刷新邻域、近界预算停止；
- `runner.py`：冷/暖、old/combined、硬截止、Q3严格同方案 no-L2、worker/三机分片；
- `results/v4_structural_fifo_20260925/`：本轮真实结果和最终 plan。

## v4 实测摘要

Q3/五核七图：024 `2,227,340→2,217,280`，044 `46,827→44,768`，083 `181,091→180,934`，086 `48,028→47,682`；001/059/084保留正式 seed。七图 `T1/T5` 均值 `4.22451→4.25020`。七个最终Q3 plan全部完成严格同方案 Q2/no-L2 重放。

024 的20秒 v3/v4等预算是 `2,218,901→2,217,280`。额外图048冷启动 v4 退步 `117,513 vs 124,681`，但从旧解暖启动续优化到 `116,941`；负结果完整保留。

详见 `results/v4_structural_fifo_20260925/REPORT.md`、`METHOD.md`、`LITERATURE.md`。Windows优先 `D:\python\python.exe`，命令见 `LOCAL_AGENT_PROMPT.md`。不需要 pytest/unittest、smoke、hash/fingerprint 或全仓审计；启动必要检查后直接真实官方算例。
