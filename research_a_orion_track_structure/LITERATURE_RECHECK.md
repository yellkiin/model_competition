# 结构线独立复核：实际阅读的原文与迁移边界

本轮读取了仓库文献库 README、方法对照与阅读顺序和 A题_文献.json；以下页码均为本地 PDF 页码，而非期刊印刷页码。只声称阅读列出的模型/算法段落，不声称复现论文全部实验。

|文献|实际阅读位置|采用/不采用|
|---|---|---|
|A02，Herrmann 等，Acyclic Partitioning of Large Directed Acyclic Graphs，CCGrid 2017|PDF第2–5页，定义2.2，§IV-A收缩及定理1，§IV-B/C初始划分/细化|采纳收缩必须保留商图无环的原则。单入单出链是更保守的收缩特例；不同深度区间之间只能向前连边。没有实现该文完整多层匹配/FM分区器。最小割不是本题官方Makespan。|
|A01，Topcuoglu 等，Performance-Effective and Low-Complexity Task Scheduling for Heterogeneous Computing，IEEE TPDS 2002|PDF第5页（印刷页264），§4.1–4.2、图2；文本编码不正常，使用页面图像阅读|原HEFT使用含平均通信代价的上行rank及插入空闲槽的EFT。仓库map_groups不是完整HEFT：它使用本题的分组/每Pipe负载代理，不实现原算法的异构插槽搜索。本文只称rank/EFT风格映射。|
|A08，Ding 等，IOS: Inter-Operator Scheduler for CNN Acceleration，MLSys 2021|PDF第4–5页，阶段定义、cost[S]递推、Algorithm 1|采纳阶段组合不能只逐层贪心的思想。原文枚举合法ending子集并在硬件测量stage_latency，还可合并算子；本题不允许改写算子。原ORION的stage_dp和本轮保留该候选，不等于实现IOS。宽度转折分组也是自己的有限启发式。|
|A49，Herrmann 等，A Scalable Clustering-Based Task Scheduler for Homogeneous Processors Using DAG Partitioning，IPDPS 2019|PDF第3–4页，§III模型、§IV算法、Algorithm 1、§IV-B|借鉴无环分组与核映射粒度的权衡。原文仍在任务级调度并约束同簇同处理器，使用duplex single-port通信；不能称为把簇当原子Task，也不能替代本题共享DDR。|
|A42，Papp 等，Efficient Multi-Processor Scheduling in Increasingly Realistic Models，SPAA 2024|PDF第4–5页，§3 BSP模型、§4.2初始化、§4.3局部搜索、§4.4局部ILP|借鉴从有效种子做有界局部重分配。原文的superstep和通信阶段不可直接当A的Pipe时序；本轮未引入其BSP计分或ILP精确求解器。|
|A33，A Decomposition-based Constraint Optimization Approach for Statically Scheduling Task Graphs with Communication Delays to Multiprocessors，DATE 2007|PDF第2–3页，§2、§4及Algorithm 1、master/subproblem变量|原文是SAT master加图论子问题，学习环/关键路径约束，并可在其模型上证明最优。本轮没有SAT或约束学习；仅将候选构造和官方复评分开，不足以称为该文的分解式约束优化。将上一轮过于宽泛的文献关联收紧为“阅读后未移植”。|

原文位置使用仓库 `调研/A题_文献.json` 中相应 local_pdf、url 和 DOI；未下载或改写任何官方输入来匹配论文模型。A39在本輪只复核方法索引，没有重新精读其证明，因此不把“重新阅读A39全文”列为本轮贡献。

## 这轮真正实现的修正

新增独立候选模块 `plugin_recheck.propose`，保留COMMON签名。它保留原结构线无环非均匀分组和链映射，在短算子图上保留原ORION阶段DP候选，并给有效核数候选目标核数复评。短算子判据只是一条可否被反例推翻的代理策略，不是性能保证，不含case编号分支。

Q1先评估同阶段同核打包方案，改变的是Task边界，不是改官方FIFO；局部迁移仍仅改变官方允许的两项方案字段。保留旧阶段DP后064 Q1五核的首次八次评估实测得到12273；此前未补该候选的失败修正仍为17055，两者原记录都保留。

后续v3仅补充warm启动时立刻生成种子邻域，避免所有构造都未改善时从不尝试种子邻域。此改动独立留源代码快照和本地同机warm复核；不能把v2b的warm数据改名成v3实测。

v4进一步在短算子图中固定保留一个DP族代表，避免纯代理前两名排挤它。它在064短Q2/Q3复测恢复到旧版水平，但在044恶化，报告保留该反例。这是有限结构候选覆盖策略，不是实现全局预算控制器或完整论文算法。
