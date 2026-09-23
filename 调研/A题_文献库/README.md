# A题方法文献库

更新：2026-09-23。围绕固定DAG的无环分组、多核映射、子图顺序、共享DDR争用、L1/UB驻留及FIFO L2检索。

**资料库收录 52 篇：原清单 A01–A15 全部保留并下载；新增 37 篇。已取得 41 篇 PDF（约 78.8 MiB），另有 A52 的 IEEE XML 全文，共 42 篇取得全文。** A51 同时保存 PDF 和 XML，不重复计数。

**主代理亲自重筛后，只选5篇主线：A49、A39、A02、A16、A42；另以A01 HEFT作简单基线。** 13条记录增加了亲自核读页码及判断；其余按用途保留为补充、待全文复核或背景。

## 从这里开始

- [主代理5篇主线选择、关键纠正与三问路线](方法对照与阅读顺序.md)
- [逐篇元数据、方法、适用边界和文件路径](../A题_文献.json)
- [BibTeX](references.bib) · [下载记录](download_log.json) · [IEEE检索与全文接口记录](检索与下载说明.md)
- [AI辅助工作记录](AI辅助记录.md)

**P1**：5篇主线及1篇简单基线；**P2**：定向补充或待全文复核；**P3**：背景存档。优先级指对A的可迁移性，不是论文质量排名。逐条角色见主JSON的 `selection_role`。

建议阅读 A49 → A02 → A39 → A16 → A42。A43默认重算、A40周期LRU模型、A31/A32最坏峰值问题已明确降级；本次没有运行A实验，也没有声称成绩提升。

## 分类索引

### 任务列表调度

|编号|优先级|年份 / 文献|全文|
|---|---|---|---|
|A01|P1|2002 · [Performance-Effective and Low-Complexity Task Scheduling for Heterogeneous Computing](https://openaccess.marmara.edu.tr/entities/publication/feba5344-0457-405a-8cb2-1d26f8963e33)|[PDF](pdf/A01_2002_HEFT_CPOP.pdf) · 15页|

### 无环图与超图划分

|编号|优先级|年份 / 文献|全文|
|---|---|---|---|
|A02|P1|2017 · [Acyclic Partitioning of Large Directed Acyclic Graphs](https://people.bordeaux.inria.fr/julien.herrmann/pub/conf/ccgrid2017.pdf)|[PDF](pdf/A02_2017_Acyclic_DAG_Partitioning.pdf) · 10页|
|A03|P2|2017 · [Graph Partitioning with Acyclicity Constraints](https://arxiv.org/abs/1704.00705)|[PDF](pdf/A03_2017_Acyclicity_Constraints.pdf) · 14页|
|A04|P2|2022 · [A Simple and Elegant Mathematical Formulation for the Acyclic DAG Partitioning Problem](https://arxiv.org/abs/2207.13638)|[PDF](pdf/A04_2022_Acyclic_DAG_MILP.pdf) · 12页|
|A37|P3|2022 · [Graph reductions and partitioning heuristics for multicore DAG scheduling](https://www.sciencedirect.com/science/article/pii/S1383762121002502)|[PDF](pdf/A37_2022.pdf) · 9页|
|A39|P1|2021 · [Multilevel Acyclic Hypergraph Partitioning](https://epubs.siam.org/doi/10.1137/1.9781611976472.1)|[PDF](pdf/A39_2021.pdf) · 20页|

### 访存下界与性能模型

|编号|优先级|年份 / 文献|全文|
|---|---|---|---|
|A05|P2|1981 · [I/O complexity: The red-blue pebble game](https://doi.org/10.1145/800076.802486)|[PDF](pdf/A05_1981_Red_Blue_Pebble.pdf) · 8页|
|A06|P2|2009 · [Roofline: An Insightful Visual Performance Model for Multicore Architectures](https://doi.org/10.1145/1498765.1498785)|[PDF](pdf/A06_2009_Roofline.pdf) · 12页|
|A22|P3|2019 · [Timeloop: A Systematic Approach to DNN Accelerator Evaluation](https://research.nvidia.com/publication/2019-03_timeloop-systematic-approach-dnn-accelerator-evaluation)|[PDF](pdf/A22_2019_Timeloop.pdf) · 12页|
|A23|P3|2021 · [ZigZag: Enlarging Joint Architecture-Mapping Design Space Exploration for DNN Accelerators](https://ieeexplore.ieee.org/document/9360462/)|[PDF](pdf/A23_2020_ZigZag_arXiv.pdf) · 14页|
|A24|P3|2020 · [MAESTRO: A Data-Centric Approach to Understand Reuse, Performance, and Hardware Cost of DNN Mappings](https://research.nvidia.com/publication/2020-04_maestro-data-centric-approach-understand-reuse-performance-and-hardware-cost)|[PDF](pdf/A24_2020_MAESTRO_IEEE_Micro.pdf) · 10页|
|A25|P3|2021 · [Marvel: A Data-Centric Approach for Mapping Deep Learning Operators on Spatial Accelerators](https://doi.org/10.1145/3485137)|[PDF](pdf/A25_2021_Marvel_TACO.pdf) · 26页|

### 编译器与并行搜索背景

|编号|优先级|年份 / 文献|全文|
|---|---|---|---|
|A07|P3|2020 · [Rammer: Enabling Holistic Deep Learning Compiler Optimizations with rTasks](https://www.usenix.org/conference/osdi20/presentation/ma)|[PDF](pdf/A07_2020_Rammer.pdf) · 18页|
|A09|P3|2023 · [Welder: Scheduling Deep Learning Memory Access via Tile-graph](https://www.usenix.org/conference/osdi23/presentation/shi)|[PDF](pdf/A09_2023_Welder.pdf) · 19页|
|A10|P3|2022 · [ROLLER: Fast and Efficient Tensor Compilation for Deep Learning](https://www.usenix.org/conference/osdi22/presentation/zhu)|[PDF](pdf/A10_2022_ROLLER.pdf) · 17页|
|A11|P3|2018 · [TVM: An Automated End-to-End Optimizing Compiler for Deep Learning](https://www.usenix.org/conference/osdi18/presentation/chen)|[PDF](pdf/A11_2018_TVM.pdf) · 17页|
|A12|P3|2020 · [Ansor: Generating High-Performance Tensor Programs for Deep Learning](https://www.usenix.org/conference/osdi20/presentation/zheng)|[PDF](pdf/A12_2020_Ansor.pdf) · 18页|
|A13|P3|2022 · [Alpa: Automating Inter- and Intra-Operator Parallelism for Distributed Deep Learning](https://www.usenix.org/conference/osdi22/presentation/zheng-lianmin)|[PDF](pdf/A13_2022_Alpa.pdf) · 21页|
|A14|P3|2022 · [Unity: Accelerating DNN Training Through Joint Optimization of Algebraic Transformations and Parallelization](https://www.usenix.org/conference/osdi22/presentation/unger)|[PDF](pdf/A14_2022_Unity.pdf) · 19页|
|A15|P3|2019 · [TASO: Optimizing Deep Learning Computation with Automatic Generation of Graph Substitutions](https://catalyst.cs.cmu.edu/projects/taso.html)|[PDF](pdf/A15_2019_TASO.pdf) · 16页|

### 算子分组与多核映射

|编号|优先级|年份 / 文献|全文|
|---|---|---|---|
|A08|P2|2021 · [IOS: Inter-Operator Scheduler for CNN Acceleration](https://proceedings.mlsys.org/paper_files/paper/2021/hash/1f8053a67ec8e0b57455713cefdd8218-Abstract.html)|[PDF](pdf/A08_2021_IOS.pdf) · 14页|
|A21|P2|2023 · [PartitionTuner: An operator scheduler for deep-learning compilers supporting multiple heterogeneous processing units](https://onlinelibrary.wiley.com/doi/10.4218/etrij.2021-0446)|[PDF](pdf/A21_2023_PartitionTuner.pdf) · 11页|
|A44|P2|2026 · [Peak-memory-aware partitioning and scheduling for multi-tenant DNN model inference](https://www.sciencedirect.com/science/article/pii/S1383762126000147)|尚未取得|
|A48|P3|2024 · [Scaling Deep Learning Computation over the Inter-core Connected Intelligence Processor with T10](https://doi.org/10.1145/3694715.3695955)|[PDF](pdf/A48_2024_T10.pdf) · 17页|
|A49|P1|2019 · [A Scalable Clustering-Based Task Scheduler for Homogeneous Processors Using DAG Partitioning](https://ieeexplore.ieee.org/document/8820781/)|[PDF](pdf/A49_2019.pdf) · 11页|
|A50|P2|2020 · [Efficient Scheduling of Irregular Network Structures on CNN Accelerators](https://ieeexplore.ieee.org/document/9211523/)|尚未取得|

### 内存约束与活跃张量

|编号|优先级|年份 / 文献|全文|
|---|---|---|---|
|A16|P1|2023 · [Combined Scheduling, Memory Allocation and Tensor Replacement for Minimizing Off-Chip Data Accesses of DNN Accelerators](https://arxiv.org/abs/2311.18246)|[PDF](pdf/A16_2023_COSMA.pdf) · 8页|
|A17|P2|2020 · [Ordering Chaos: Memory-Aware Scheduling of Irregularly Wired Neural Networks for Edge Devices](https://proceedings.mlsys.org/paper_files/paper/2020/hash/79c36fe64e04b80fc44845bb9fe73242-Abstract.html)|[PDF](pdf/A17_2020_SERENITY.pdf) · 14页|
|A18|P2|2022 · [Hierarchical Memory-Constrained Operator Scheduling of Neural Architecture Search Networks](https://doi.org/10.1145/3489517.3530472)|[PDF](pdf/A18_2022_HMCOS.pdf) · 6页|
|A19|P3|2023 · [ROAM: memory-efficient large DNN training via optimized operator ordering and memory layout](https://arxiv.org/abs/2310.19295)|[PDF](pdf/A19_2023_ROAM.pdf) · 14页|
|A20|P3|2024 · [MoteNN: Memory Optimization via Fine-grained Scheduling for Deep Neural Networks on Tiny Devices](https://doi.org/10.1145/3649329.3655922)|[PDF](pdf/A20_2024_MoteNN.pdf) · 6页|
|A26|P3|2023 · [MODeL: Memory Optimizations for Deep Learning](https://proceedings.mlr.press/v202/steiner23a.html)|[PDF](pdf/A26_2023_MODeL.pdf) · 15页|
|A31|P2|2018 · [Parallel Scheduling of DAGs under Memory Constraints](https://inria.hal.science/hal-01828312/)|[PDF](pdf/A31_2018.pdf) · 10页|
|A32|P2|2020 · [Revisiting dynamic DAG scheduling under memory constraints for shared-memory platforms](https://doi.org/10.1109/IPDPSW50202.2020.00102)|[PDF](pdf/A32_2020.pdf) · 10页|
|A43|P2|2025 · [Multiprocessor Scheduling with Memory Constraints: Fundamental Properties and Finding Optimal Solutions](https://arxiv.org/abs/2507.17411)|[PDF](pdf/A43_2025.pdf) · 18页|
|A45|P2|2025 · [Parallel Scheduling of Task Graphs with Minimal Memory Requirements](https://ieeexplore.ieee.org/document/11078551/)|尚未取得|
|A46|P2|2023 · [Memory-aware Scheduling for Complex Wired Networks with Iterative Graph Optimization](https://arxiv.org/abs/2308.13898)|[PDF](pdf/A46_2023.pdf) · 9页|
|A47|P2|2026 · [Minimizing memory in parallel task graph scheduling: Focusing on average consumption](https://www.sciencedirect.com/science/article/abs/pii/S0743731526000778)|尚未取得|

### 换入换出与重算背景

|编号|优先级|年份 / 文献|全文|
|---|---|---|---|
|A27|P3|2016 · [vDNN: Virtualized Deep Neural Networks for Scalable, Memory-Efficient Neural Network Design](https://arxiv.org/abs/1602.08124)|[PDF](pdf/A27_2016_vDNN.pdf) · 13页|
|A28|P3|2020 · [SwapAdvisor: Pushing Deep Learning Beyond the GPU Memory Limit via Smart Swapping](https://doi.org/10.1145/3373376.3378530)|[PDF](pdf/A28_2020_SwapAdvisor.pdf) · 15页|
|A29|P3|2020 · [Capuchin: Tensor-based GPU Memory Management for Deep Learning](https://doi.org/10.1145/3373376.3378505)|尚未取得|

### 通信争用与精确调度

|编号|优先级|年份 / 文献|全文|
|---|---|---|---|
|A30|P2|2005 · [Communication contention in task scheduling](https://researchportal.ulisboa.pt/en/publications/communication-contention-in-task-scheduling/)|尚未取得|
|A33|P2|2007 · [A Decomposition-based Constraint Optimization Approach for Statically Scheduling Task Graphs with Communication Delays to Multiprocessors](https://doi.org/10.1109/DATE.2007.364567)|[PDF](pdf/A33_2007.pdf) · 6页|
|A34|P2|2018 · [Satisfiability modulo theory (SMT) formulation for optimal scheduling of task graphs with communication delay](https://www.sciencedirect.com/science/article/pii/S0305054817302186)|尚未取得|
|A35|P2|2020 · [Contention-aware optimal scheduling of real-time precedence-constrained task graphs on heterogeneous distributed systems](https://www.sciencedirect.com/science/article/pii/S1383762119305132)|尚未取得|
|A36|P2|2022 · [Contention Cognizant Scheduling of Task Graphs on Shared Bus-Based Heterogeneous Platforms](https://doi.org/10.1109/TCAD.2021.3059569)|尚未取得|
|A38|P2|2021 · [HMDS: A Makespan Minimizing DAG Scheduler for Heterogeneous Distributed Systems](https://doi.org/10.1145/3477037)|尚未取得|
|A41|P2|2025 · [DAG Scheduling in the BSP Model](https://arxiv.org/abs/2303.05989)|[PDF](pdf/A41_2025.pdf) · 30页|
|A42|P1|2024 · [Efficient Multi-Processor Scheduling in Increasingly Realistic Models](https://doi.org/10.1145/3626183.3659972)|[PDF](pdf/A42_2024.pdf) · 24页|

### 缓存亲和与共享输入

|编号|优先级|年份 / 文献|全文|
|---|---|---|---|
|A40|P3|2025 · [A cache-aware DAG scheduling method on multicores: Exploiting node affinity and deferred executions](https://www.sciencedirect.com/science/article/pii/S138376212500044X)|[PDF](pdf/A40_2025.pdf) · 15页|

### 通信与存储联合分配

|编号|优先级|年份 / 文献|全文|
|---|---|---|---|
|A51|P3|2019 · [Dynamic Data Allocation and Task Scheduling on Multiprocessor Systems With NVM-Based SPM](https://ieeexplore.ieee.org/document/8579198/)|[PDF](pdf/A51_2019.pdf) · 12页|
|A52|P3|2025 · [Dynamic Cluster Selection DAG Scheduling for Clustered Many-Core Processor Considering Inter-Cluster Communication](https://ieeexplore.ieee.org/document/11098909/)|[XML全文](fulltext/A52_11098909.xml)|

## 版本与引用注意

- 主索引的题名、作者、年份、DOI以标注的发表版本为准；下载的是作者稿/预印本时单列 `pdf_version`，不能用PDF页数冒充正式页码。
- A23：下载的是2020 ZigZag预印本，其题名不同于2021 IEEE TC文章；两个题名单独记录。
- A24：使用 IEEE Micro 2020 正式PDF；A25使用ACM TACO正式PDF，未将九作者预印本误标为六作者期刊版。
- A26：MODeL是ICML/PMLR 2023，OLLA的arXiv DOI只在关联版本中列出。
- A36正式卷期是2022（在线发表2021）；A41、A42、A43的长预印本与会议版本分开记录。
- A44 Quilt只核对出版方摘要与Highlights；其实现细节尚待全文确认。A50核对IEEE卷39(11)、2020年、3408–3419页。

## 尚未取得全文

|编号|题名|本次访问情况|
|---|---|---|
|A29|[Capuchin: Tensor-based GPU Memory Management for Deep Learning](https://doi.org/10.1145/3373376.3378505)|作者站TLS失败，HTTP副本502；未找到可访问的作者镜像。|
|A30|[Communication contention in task scheduling](https://researchportal.ulisboa.pt/en/publications/communication-contention-in-task-scheduling/)|旧机构链接失效；CiteSeerX/公开下载端点404或418。|
|A34|[Satisfiability modulo theory (SMT) formulation for optimal scheduling of task graphs with communication delay](https://www.sciencedirect.com/science/article/pii/S0305054817302186)|出版方PDF403；保留DOI和作者公开记录。|
|A35|[Contention-aware optimal scheduling of real-time precedence-constrained task graphs on heterogeneous distributed systems](https://www.sciencedirect.com/science/article/pii/S1383762119305132)|出版方PDF403；作者主页仅列引用。|
|A36|[Contention Cognizant Scheduling of Task Graphs on Shared Bus-Based Heterogeneous Platforms](https://doi.org/10.1109/TCAD.2021.3059569)|IEEE API命中LOCKED；未发现可直接下载的作者稿。|
|A38|[HMDS: A Makespan Minimizing DAG Scheduler for Heterogeneous Distributed Systems](https://doi.org/10.1145/3477037)|ACM PDF403；作者页面提供DOI，未发现公开稿。|
|A44|[Peak-memory-aware partitioning and scheduling for multi-tenant DNN model inference](https://www.sciencedirect.com/science/article/pii/S1383762126000147)|出版方PDF403；只有摘要/Highlights和机构元数据。|
|A45|[Parallel Scheduling of Task Graphs with Minimal Memory Requirements](https://ieeexplore.ieee.org/document/11078551/)|HAL返回验证页面，未取得PDF。|
|A47|[Minimizing memory in parallel task graph scheduling: Focusing on average consumption](https://www.sciencedirect.com/science/article/abs/pii/S0743731526000778)|HAL返回验证页面；SSRN PDF403。|
|A50|[Efficient Scheduling of Irregular Network Structures on CNN Accelerators](https://ieeexplore.ieee.org/document/9211523/)|IEEE API命中LOCKED；尚未发现可信公开PDF。|

下载器拒收HTML登录页、验证码页和损坏PDF；保留失败状态与来源，不把检索命中算作全文。论文保留原版权与许可，本文献目录不改变论文的使用条款。

## 复现公开PDF下载

环境：Python 3、`requests`、`PyMuPDF`。在仓库根目录运行：

```powershell
& D:\python\python.exe "调研/A题_文献库/download_papers.py" "调研/A题_文献.json" --workers 4
```

已有PDF会复用并保留来源；失败条目可补充 `pdf_urls` 后重试。IEEE脚本只从环境变量 `IEEE_API_KEY` 读取凭据，仓库不保存密钥。
