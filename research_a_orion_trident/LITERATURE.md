# 本轮阅读与方法依据

本轮研究已从仓库取得文献库README、方法对照、文献JSON及相关原文。此文件记录已完成研究的来源和方法映射；本次GitHub发布不新增论文复现或性能实验。

## A12 Ansor（OSDI 2020），§5–6

原文：https://www.usenix.org/system/files/osdi20-zheng.pdf

迁移完整候选、代价反馈与多任务预算思想：候选族先获得机会，再按实际全局收益/成本分配；相互竞争来源需保留代表，避免不完整代理提前删除有用区域。Trident的来源首评、近期收益/中位成本、8次未访问保护和三次冷覆盖是本题实现，不是Ansor梯度调度逐行复现。

不迁移张量程序改写、循环tile或kernel编译。本题共享DDR下的Makespan不是各子图独立耗时加权和。

## A16 COSMA（arXiv:2311.18246），§III

原文：https://arxiv.org/html/2311.18246v1

迁移create/preserve/spill/retrieve与生命周期分类，帮助M控制同时打开的组件数、解释额外COPY。原模型每离散步一个operator，允许地址布局和换入换出决策；本题固定Step1/2/3，只在合法分组、归核和子图序内提出候选。少访存字节不保证Makespan更短，本轮084不同核数负结果显示了该区别。

## A39 Multilevel Acyclic Hypergraph Partitioning（ALENEX 2021）

原文：https://arxiv.org/pdf/2002.02962

有向超边/无环收缩表达共享张量端点；一生产者多消费者不按独立边重复估价。S/M的事务和分组仍经完整官方合法性检查。Connectivity只作提案依据，不是COPY次数或完成周期。

## A42 Efficient Multi-Processor Scheduling in Increasingly Realistic Models（SPAA 2024）

原文：https://arxiv.org/html/2404.15246v1

迁移多个初始区域、有限移动、联合窗口与反馈迭代。Trident把局部搜索绑定实际父epoch，全局构造独立保存，避免继续评价旧窗口或误删未评全局构造。BSP/NUMA中的分阶段通信目标不替代共享带宽/流水事件模型。

## FIFO与CADE背景

A40的周期任务和LRU只作亲和/时序对照，不移植周期热态、LRU刷新或主动delay。实际规则取自原`multicore_cut_evaluate_problem_3.py`：发射查找、完成尝试填充、仍驻留条目不刷新FIFO。

## 独立增量

三线构造算子来源记录在SOURCE_MANIFEST，私有组件微波次不重复认领。Trident增量包括共同父方案快照、全局流跨epoch保留、M参数游标保留、按实际工作量引入F、共同成本选择、011实测推动的冷覆盖、时间帽内配对与余额内消融，以及可恢复/分片/导出的完整控制流程。
