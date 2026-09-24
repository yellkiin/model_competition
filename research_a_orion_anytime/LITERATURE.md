# 本轮新增阅读与实际迁移

本轮在既有 A49、A02、A39、A16/COSMA、A42 的基础上，增读以下三篇的相关算法正文。不是声称逐字审阅全部证明/实验，也不是复制作者的性能结论。文献库的编号以调研/A题_文献库为准。

## A08 — IOS: Inter-Operator Scheduler for CNN Acceleration, MLSys 2021

原文：https://proceedings.mlsys.org/paper_files/paper/2021/file/1f8053a67ec8e0b57455713cefdd8218-Paper.pdf

核读PDF第3–7页的阶段分解、动态规划与剪枝，查看算法图。作者把算子并行/组合的序列按阶段优化，使用子问题状态复用。迁移至本题：在最多16个依赖深度箱上做分段DP，产生“阶段内连通块分核”和“同阶段同核合为子图”候选。DP的区间评分包含Pipe工作量、块粒度、边界张量、场景等待。

边界：本题不得重写/融合算子。这里合并的是方案子图，原操作不变。官方执行可以跨阶段重叠，DDR/FIFO又耦合阶段，所以DP只对写出的**可加代理**最优，不认证官方Makespan最优，也不称完整复现IOS。

实现：strategies.stage_candidates；消融no_stage（同时去掉阶段DP）与no_dp（也去掉局部活跃集DP）。

## A17 — Ordering Chaos / SERENITY, MLSys 2020

原文：https://proceedings.mlsys.org/paper_files/paper/2020/hash/79c36fe64e04b80fc44845bb9fe73242-Abstract.html
有效PDF：https://proceedings.mlsys.org/paper_files/paper/2020/file/79c36fe64e04b80fc44845bb9fe73242-Paper.pdf

核读PDF第4–6页：已调度节点集合、就绪节点、内存释放、状态复用，查看DP算法图。迁移：共同拓扑序中至多8个已有子图组成窗口；以已完成子图子集为状态，只扩展局部依赖就绪节点；代价是按容量归一化的活跃张量前沿与工作量乘积之和。

边界：优化的是“活跃前沿面积代理”，不是官方Step2最小Spill或真实内存峰值。没有借用论文的图重写能力，没有改变官方算子内顺序。只允许调整既有子图顺序。论文的内存最优性不迁移到本题。

实现：strategies.memory_window_order；no_dp消融。该消融同时关两类DP，不能从一次消融单独归因给某一篇论文。

## A04 — A Simple and Elegant Mathematical Formulation for the Acyclic DAG Partitioning Problem, 2022

原文：https://arxiv.org/abs/2207.13638 ，PDF https://arxiv.org/pdf/2207.13638

核读模型与上三角商图约束、顺序消除对称性、实验讨论。迁移：用共同拓扑序显式约束可修改区域；相邻子图收缩、拓扑连续窗口的联合分核、可行局部顺序均保持依赖方向。

边界：原文优化带容量的割边目标，并不包含本题固定核内Spill及FIFO事件。没有引入全图ILP或宣称整数最优。6块窗口用宽度12的beam保留若干方案，是受限离散近似搜索，不是MILP的精确求解。

实现：strategies.joint_window、mutations中的adjacent_convex_merge；no_window消融只关联合窗口，不关交换/合并。

## 本轮新增思想与原有机制的关系

原有通信关键路径下界、张量身份计费、驻留风险和FIFO时序代理继续使用。新增的是多阶段/细粒度构造空间、联合窗口、活跃状态DP与逐实例评分校准。评分校准只使用该实例已经完成的官方评估，按候选族actual/proxy中位数缩放，再定期进行族间探索；不跨图训练、不按case文件名设特例。

最终接受标准始终是未改动官方Makespan，平局比较额外搬运。任何文献里的吞吐、峰值内存、BSP代价、割边数都不是本题的正式目标。

## 本轮消融给出的取舍

在002/044的三问五核、每配置30秒/24次上限下，关闭所有分阶段候选使几何平均结果变差；但关闭联合窗口或关闭DP，在本轮小样本里略优于full。主要证据支持分阶段与细粒度构造，不支持“论文组件越多越好”。两个关闭开关仍保留为机制实验，尚未据六格消融宣称对100图普遍更优。具体数值见MEASURED_VALIDATION.md。
