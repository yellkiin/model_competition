# A题原文核读卡（10篇）

本卡基于本次资料库的原始PDF，物理页均从PDF第一页起数；期刊/会议印刷页单独指出。核读范围为相关模型、算法段落与列明的关键图式，非逐篇全证明复现。原题和实际执行规则优先于文献模型。

## 直接用于论文的引用分工

- 联合划分、映射与粒度权衡：A49；无环性：A02；共享张量集合表达：A39。
- 张量驻留/换出分析：A16；多初值及局部改进：A42；初始优先级：A01；测量反馈分配搜索资源：A12。
- 补充：A08用于分组与并行性背景，A17用于活跃集/峰值内存背景，A40仅用于缓存亲和的对照，不提供FIFO命中公式。

## 逐篇文献卡

### A49 A Scalable Clustering-Based Task Scheduler for Homogeneous Processors Using DAG Partitioning

- **元数据**：M. Yusuf Özkaya; Anne Benoit; Bora Uçar; Julien Herrmann; Ümit V. Catalyürek；2019 IEEE International Parallel and Distributed Processing Symposium (IPDPS)（2019）；DOI：10.1109/IPDPS.2019.00026；版本：公开全文（出版方/作者/机构来源，保留原版权页）。
- **原文**：`D:\华为杯写作\ORION_Paper_Agent\数据\ORION_论文资料\snapshots\20260925T204725662983Z\literature\调研\A题_文献库\pdf\A49_2019.pdf`；物理页实际阅读：1, 2, 3, 4；实际图像核对：2。
- **关键页观察**：物理页2右栏写明先分K≥p簇再调度簇内各任务，并明确“schedule tasks ... not the clusters”；同页模型规定duplex single-port通信与同处理器通信零代价。
- **可支持主张**：分组可限制共同处理器归属，同时仍进行任务级列表调度；粒度影响通信局部性与并行性。
- **迁移边界**：不能把原文称为原子簇调度；其同核免费通信与端口通信模型不对应第一问同核跨Task DDR、后两问共享带宽及固定等待。最终优劣必须按本题完整执行规则评价。
- **拟放位置**：问题分析的联合决策动机；结构构造与映射。

### A02 Acyclic Partitioning of Large Directed Acyclic Graphs

- **元数据**：Herrmann, J.; Kho, J.; Uçar, B.; Kaya, K.; Çatalyürek, Ü. V.；IEEE/ACM CCGrid（2017）；DOI：10.1109/CCGRID.2017.101；版本：公开全文（出版方/作者/机构来源，保留原版权页）。
- **原文**：`D:\华为杯写作\ORION_Paper_Agent\数据\ORION_论文资料\snapshots\20260925T204725662983Z\literature\调研\A题_文献库\pdf\A02_2017_Acyclic_DAG_Partitioning.pdf`；物理页实际阅读：2, 3, 4；实际图像核对：3。
- **关键页观察**：物理页3右栏Definition 4.3明确粗化后仍须无环；Theorem 1说明收缩边的安全条件与替代路径有关，页上有粗化、初分、反粗化三阶段叙述。
- **可支持主张**：对有向无环图分组时，应保持分组商图无环；多级粗化及反粗化可组织可行分组候选。
- **迁移边界**：原目标为权重平衡下最小割，不包含本题L1/UB瞬时峰值、Pipe与DDR争用；单个子图的局部条件不能替代全部分组和核序的完整可行性检查。
- **拟放位置**：统一模型的无环约束；结构邻域设计。

### A39 Multilevel Acyclic Hypergraph Partitioning

- **元数据**：Merten Popp; Sebastian Schlag; Christian Schulz; Daniel Seemaier；2021 Proceedings of the Workshop on Algorithm Engineering and Experiments (ALENEX), pp. 1-15（2021）；DOI：10.1137/1.9781611976472.1；版本：arXiv预印本（2020），引用对应ALENEX 2021正式论文。
- **原文**：`D:\华为杯写作\ORION_Paper_Agent\数据\ORION_论文资料\snapshots\20260925T204725662983Z\literature\调研\A题_文献库\pdf\A39_2021.pdf`；物理页实际阅读：2, 3, 4, 5；实际图像核对：3, 5。
- **关键页观察**：物理页3定义有向超边的tail/head及商图；式(λ−1)(Π)是跨分区连接度代理。物理页5 §3.2进一步写出多head超边的收缩限制与FixCyclic流程。
- **可支持主张**：共享张量可用生产者tail到多个消费者head的有向超边表达；分组须维护商图无环。
- **迁移边界**：不能把tail/head方向反置；λ−1连接度不是官方COPY字节或Makespan恒等式，也不声称实现原文n-level、FM、memetic全流程。
- **拟放位置**：统一模型张量集合表示；结构候选的数据复用代理。

### A16 Combined Scheduling, Memory Allocation and Tensor Replacement for Minimizing Off-Chip Data Accesses of DNN Accelerators

- **元数据**：Yi Li; Aarti Gupta; Sharad Malik；arXiv preprint arXiv:2311.18246（2023）；DOI：10.48550/arXiv.2311.18246；版本：arXiv预印本。
- **原文**：`D:\华为杯写作\ORION_Paper_Agent\数据\ORION_论文资料\snapshots\20260925T204725662983Z\literature\调研\A题_文献库\pdf\A16_2023_COSMA.pdf`；物理页实际阅读：1, 2, 3, 4；实际图像核对：4。
- **关键页观察**：物理页4式(9)约束地址与大小不超内存预算，式(10)约束驻留张量地址互不重叠，式(12)最小化Spill/Retrieve字节；同页区分固定调度的内存子问题。
- **可支持主张**：张量创建、驻留、换出、取回的状态及额外片外访问可解释分组/顺序引起的存储压力。
- **迁移边界**：原文允许联合选算子顺序、张量置换及连续地址；本题这些由固定执行规则确定，且容量按缓冲实例/虚拟字节计。只迁移状态分析与候选评分思想，不套原ILP最优性。
- **拟放位置**：执行模型的L1/UB驻留及Spill；驻留相关邻域。

### A42 Efficient Multi-Processor Scheduling in Increasingly Realistic Models

- **元数据**：Pál András Papp; Georg Anegg; Aikaterini Karanasiou; Albert-Jan N. Yzelman；Proceedings of the 36th ACM Symposium on Parallelism in Algorithms and Architectures (SPAA 2024), pp. 463-474（2024）；DOI：10.1145/3626183.3659972；版本：作者公开预印本（24页），引用对应SPAA 2024会议版。
- **原文**：`D:\华为杯写作\ORION_Paper_Agent\数据\ORION_论文资料\snapshots\20260925T204725662983Z\literature\调研\A题_文献库\pdf\A42_2024.pdf`；物理页实际阅读：3, 4, 5, 6；实际图像核对：5。
- **关键页观察**：物理页5 §4.3从已可行BSP调度出发，尝试节点跨处理器或邻近超步的小步迁移并只接受合法且低成本方案；§4.4另有全局/局部ILP，不应混入本文已实现机制。
- **可支持主张**：多初值和可行解上的局部迁移为有限预算改进提供通用搜索框架。
- **迁移边界**：BSP将计算与通信按超步计费，NUMA/通信计划也是其决策；本题有重叠的离散事件与固定通信规则。不能继承其BSP代价、ILP最优性或论文实验收益。
- **拟放位置**：多邻域迭代改进总流程与可行性接受规则。

### A01 Performance-Effective and Low-Complexity Task Scheduling for Heterogeneous Computing

- **元数据**：Topcuoglu, H.; Hariri, S.; Wu, M.-Y.；IEEE TPDS 13(3):260–274（2002）；DOI：10.1109/71.993206；版本：作者机构保存的正式发表PDF；文字编码异常，已视觉核对首页。
- **原文**：`D:\华为杯写作\ORION_Paper_Agent\数据\ORION_论文资料\snapshots\20260925T204725662983Z\literature\调研\A题_文献库\pdf\A01_2002_HEFT_CPOP.pdf`；物理页实际阅读：4, 5, 6；实际图像核对：5。
- **关键页观察**：物理页5（期刊印刷页264）图2确为HEFT伪代码：先按上行rank排序，再对每个处理器计算插入式EFT并选最早完成者；同页式(8)给平均计算/通信代价递归rank。
- **可支持主张**：DAG任务的关键性排序与最早完成时刻映射可作为初始构造思路。
- **迁移边界**：原文面向异构处理器、边通信代价和任务级列表调度；本题是同构核、双Pipe、共享DDR与固定Task语义，rank/EFT只作候选代理，不能称复现完整HEFT或用其EFT替代官方执行周期。
- **拟放位置**：方法章初始方案与基础候选；文献综述中一句说明经典列表调度。

### A12 Ansor: Generating High-Performance Tensor Programs for Deep Learning

- **元数据**：Zheng, L.; Jia, C.; Sun, M.; Wu, Z.; et al.；USENIX OSDI:863–879（2020）；DOI：无/未标；版本：公开全文（出版方/作者/机构来源，保留原版权页）。
- **原文**：`D:\华为杯写作\ORION_Paper_Agent\数据\ORION_论文资料\snapshots\20260925T204725662983Z\literature\调研\A题_文献库\pdf\A12_2020_Ansor.pdf`；物理页实际阅读：7, 8, 9, 10；实际图像核对：9, 10。
- **关键页观察**：物理页9 §5.2明确用实测程序更新学习成本模型；物理页10（印刷871）§6将调优时间分配给子图任务，表2展示端到端目标，并说明先round-robin暖启再依据收益选择。
- **可支持主张**：有限搜索资源可依据已观测收益分配，完整测量用于校准候选评价。
- **迁移边界**：Ansor的task是调优任务而非本题执行Task；其程序重写、tiling、GBDT成本模型和梯度式时间分配未在本题实施。仅引用测量反馈的设计思想，本文来源优先级式是自定义启发式。
- **拟放位置**：候选来源选择与搜索预算分配；避免把代理分数写成执行结果。

### A08 IOS: Inter-Operator Scheduler for CNN Acceleration

- **元数据**：Ding, Y.; Zhu, L.; Jia, Z.; Pekhimenko, G.; Han, S.；Proceedings of Machine Learning and Systems 3（2021）；DOI：无/未标；版本：公开全文（出版方/作者/机构来源，保留原版权页）。
- **原文**：`D:\华为杯写作\ORION_Paper_Agent\数据\ORION_论文资料\snapshots\20260925T204725662983Z\literature\调研\A题_文献库\pdf\A08_2021_IOS.pdf`；物理页实际阅读：1, 3, 4, 5；实际图像核对：4。
- **关键页观察**：物理页4图3显示先做算子合并的stage，再在另一stage并行两个组；图4以ending集合递归分解，正文式Q={(S_i,T_i)}定义stage及其并行策略。
- **可支持主张**：算子分组粒度与组间并行度相互作用，阶段化分组可提供调度候选组织思路。
- **迁移边界**：IOS的stage全序、算子合并/改写及单GPU profile代价不符合本题可提交变量；不可直接采用其动态规划最优性或把stage叫本题Task。
- **拟放位置**：相关工作中分组与并行性权衡；结构候选动机。

### A17 Ordering Chaos: Memory-Aware Scheduling of Irregularly Wired Neural Networks for Edge Devices

- **元数据**：Byung Hoon Ahn; Jinwon Lee; Jamie Menjay Lin; Hsin-Pai Cheng; Jilei Hou; Hadi Esmaeilzadeh；Proceedings of Machine Learning and Systems 2 (MLSys 2020)（2020）；DOI：无/未标；版本：正式发表PDF或作者公开稿。
- **原文**：`D:\华为杯写作\ORION_Paper_Agent\数据\ORION_论文资料\snapshots\20260925T204725662983Z\literature\调研\A题_文献库\pdf\A17_2020_SERENITY.pdf`；物理页实际阅读：1, 3, 4, 5；实际图像核对：4。
- **关键页观察**：物理页4图4完整显示图重写、软预算、动态规划调度；图5展示零入度集合的记忆化搜索，正文目标为最小峰值activation内存。
- **可支持主张**：合法拓扑顺序改变活跃张量集合与峰值存储占用，活跃集可指导顺序候选。
- **迁移边界**：原文研究边缘设备单图算子顺序及峰值内存，还允许图重写；本题原算子图不可改、核内只能重排子图、主目标是Makespan，Spill由固定规则生成。
- **拟放位置**：驻留相关候选的活跃集分析；存储与顺序耦合的相关工作。

### A40 A cache-aware DAG scheduling method on multicores: Exploiting node affinity and deferred executions

- **元数据**：Huixuan Yi; Yuanhai Zhang; Zhiyang Lin; Haoran Chen; Yiyang Gao; Xiaotian Dai; Shuai Zhao；Journal of Systems Architecture 161:103372（2025）；DOI：10.1016/j.sysarc.2025.103372；版本：White Rose机构仓储作者稿。
- **原文**：`D:\华为杯写作\ORION_Paper_Agent\数据\ORION_论文资料\snapshots\20260925T204725662983Z\literature\调研\A题_文献库\pdf\A40_2025.pdf`；物理页实际阅读：1, 4, 5, 6；实际图像核对：4, 5。
- **关键页观察**：物理页4图2及文字明确每核L1、簇共享L2、包容式缓存和LRU替换；物理页5图3/式(1)的Cache Reuse Profile基于同一周期DAG节点连续释放间的复用距离。
- **可支持主张**：缓存亲和与节点执行时序可影响DAG调度效果，可作为寻找复用机会的背景。
- **迁移边界**：本题一次图执行、COPY_IN发射查找且完成填充、共享只读FIFO（命中不刷新）；原文LRU复用距离与延后执行策略不能直接预测FIFO命中或充当第三问算法。
- **拟放位置**：第三问相关工作及FIFO机制差异；不作为FIFO命中率公式来源。

## 写作时特别保留的边界

1. A39的tail→head表示生产者到消费者；λ−1是分区代理，不是官方COPY计费。
2. A49的聚类约束同核归属，实际仍调度任务；本题Task边界及共享带宽按官方模型。
3. A16、A17的自由顺序/地址/图改写超出本题权限；只取驻留与活跃集解释。
4. A40为LRU周期作业，第三问FIFO须由题面及官方事件轨迹独立定义；不可借其CRP曲线宣称FIFO收益。
5. A12的task为调优任务，与本题执行Task不是同一概念；未实现其GBDT或梯度分配。

PDF文字抽取用于定位；上述列明的物理页另经渲染图像实际查看。未运行论文实验，也未从文献推定本题收益。
