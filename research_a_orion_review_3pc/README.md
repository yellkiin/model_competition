# ORION：三机独立诊断与优化任务

本目录是下一轮研究的交接材料，不是新算法成绩，也不修改现有求解器。

给三台聊天端分别复制：
- [机器一：结构与关键路径](A_STRUCTURE.md)
- [机器二：DDR与驻留](B_MEMORY.md)
- [机器三：FIFO与Anytime](C_ANYTIME.md)

[COMMON.md](COMMON.md)规定最小候选接口和结果字段，便于后续合并；不包含最终汇总代码。[DATA_REVIEW.md](DATA_REVIEW.md)区分已读原记录、计算推论和待做反事实。[observed_examples.csv](observed_examples.csv)是从最新逐例表摘出的定向证据，不是完整100图数据。

当前数据入口：`research_a_orion_anytime/team_results/day01/latest.json`；完整汇总位于`combined_final/`，原奇数/偶数50图分别保留在`shard_0/final/`、`shard_1/final/`。更新时先查发布索引，不用旧阶段快照替代最终记录。请保留所有旧实验。
