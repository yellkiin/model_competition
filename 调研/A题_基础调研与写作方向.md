# A题：通用神经网络处理器下的多核调度问题

调研日期：2026-09-23。本文是建模与写作准备，不包含已完成的调度实验或性能结论。题面、附件 README、固定配置已核对；文献核验深度见文末及 JSON。

## 1. 题意与材料现状

题目要求联合决定“操作如何分组、子图分到哪个核、同核按何顺序执行”，最终由官方评估器重建搬运、处理缓存换入换出并进行带宽争用仿真。材料含 **100 个正式 JSON 计算图**、统一 config.txt、三个问题评估脚本、单核基准、三个核内调度步骤和说明文档。随机 stub 仅演示格式，不能作为唯一性能基线。

决策只覆盖非 COPY_IN/COPY_OUT 的核内操作；不能修改原始计算图的 cycles、size 或官方评估过程。输出必须覆盖所有计算操作且每个子图恰好分配一次。输入图有向无环，并不自动保证合并后的子图商图无环；商图合法也不自动保证加入同核顺序、Pipe FIFO、跨核同步和内存复用依赖后无等待环。[A02–A04](https://arxiv.org/abs/2207.13638)

已核对的固定参数：L1=524288 B、UB=131072 B，DDR 总带宽=60 B/cycle；场景 A 跨核/同核 Task 等待为1000/100 cycle；场景 B 跨核 COPY 延迟500 cycle；L2=1048576 B、独立带宽250 B/cycle，采用只读 FIFO Cache。正文“1 MB”应按配置的1048576字节实现。尤其不能把 DDR=60 分别分配给每个核心。

| 小问 | 实质差异 | 推荐模型与求解 | 必须输出 |
|---|---|---|---|
| 1：场景 A | 每子图一个 Task，同核跨子图也清空缓存并经 DDR | 无环聚类、缓存峰值估计、关键路径列表调度、官方仿真筛选 | 1～5核平均加速比；全部用例 Makespan/额外搬运；Python脚本 |
| 2：场景 B | 每核心全部子图构成一个 Task，同核可驻留，跨核有搬运与同步 | 张量亲和分核、驻留区间估计、合法局部迁移与顺序优化 | 同上，并说明缓存溢出与跨核流量的取舍 |
| 3：B+L2 | 共享输入可能命中只读 FIFO；L2与DDR独立 | 共享输入分组、复用距离与带宽时间线感知调度 | 同核数有/无L2对比、两种加速比定义、命中率和额外搬运 |

## 2. 核心建模：以真实评估器为准的约束搜索

设分区为 $\mathcal P=\{P_1,\ldots,P_m\}$，核映射为 $a(P_i)$，核内子图顺序为 $\pi_k$。主目标是
```math
\min_{\mathcal P,a,\pi} T_{\rm official}(\mathcal P,a,\pi).
```
采用“先 Makespan、后额外搬运量”的字典序比较；如用加权目标探索候选，应先归一化，最后仍按官方主指标选择。设置总搜索时间/评估次数预算，使算法时间也能复现。

用 Op 依赖图计算关键路径，但保留 Tensor 表计算搬运。一个张量被多个消费者使用时，不能把每条依赖边简单计为一次读写；应按**生产 Task、消费 Task 集合和张量身份**去重，最终让官方构图统计。场景 A 关注跨子图共享，场景 B 关注跨核共享，场景3还关注共享输入的访问时间。

驻留估计按生产结束到最后消费者完成定义：
```math
M_{k,p}(\tau)=\sum_{t:\,\mathrm{pos}(t)=p}s_t
\,\mathbf1[t\text{ 在核 }k\text{ 的时刻 }\tau\text{ 驻留}],\quad p\in\{L1,UB\}.
```
L1与UB各自检查，不能只检查二者总和。此式是搜索代理；官方 Step2/Step3 的 spill、地址额度复用以及新增依赖才决定最终执行行为。红蓝 pebble 模型说明有限高速存储与数据移动的关系，但不直接给出本题全部用例的精确最优值。[A05](https://doi.org/10.1145/800076.802486)

对一个已构造方案，可用计算关键路径、各计算 Pipe 总工作量除以核数、实际 DDR 字节数/60、实际 L2 命中字节数/250 的最大值做**解释性下界**。其中实际字节数依赖方案；它不是所有可行划分共用的全局下界。这里的 cycles 也不是 FLOPs，Roofline 只能借用“识别计算或带宽瓶颈”的方法。[A06](https://doi.org/10.1145/1498765.1498785)

## 3. 可落地算法路线

**可复现基线。** 第一组是官方整图单核基准。第二组按确定性拓扑序切成固定大小的连续块，再以最早完成时间分核。第三组是每操作一个子图的细粒度方案，用来展示过度切分的代价，不预设其速度必定最差。HEFT 可作优先级基线，但同构核、异类 Pipe 和共享 DDR 都需要适配；不能直接复制其点对点定长通信假设。[A01](https://openaccess.marmara.edu.tr/entities/publication/feba5344-0457-405a-8cb2-1d26f8963e33)

**主路线：无环多尺度聚类＋列表调度＋仿真局部改进。**

1. 为每张图提取规模、拓扑层宽、关键路径、Cube/Vector周期占比、张量大小、扇出以及共享输入集合。按规模和计算/带宽特征选择几个候选块粒度，不逐图手工写特例。
2. 从拓扑连续块或单点开始，按“减少边界字节、共享输入复用、Pipe互补”给合并打分；缓存压力和损失的并行度作为惩罚。每次合并后校验商图无环，或采用天然保序的连续区间分区作为稳妥起点。
3. 按估计剩余关键路径排序就绪子图，尝试各核心，使用核负载、数据就绪、DDR拥塞和驻留峰值预测完成时间。场景 A 的同核映射不能获得跨 Task 缓存复用优惠。
4. 场景 B 优先尝试把生产者与高字节消费者放在同核，同时限制长生命周期张量的占用。保留Cube/Vector互补子图的候选，使通信减少不以严重流水线失衡为代价。[A07](https://www.usenix.org/conference/osdi20/presentation/ma)
5. 用代理模型筛掉明显劣解，只把前若干候选送官方评估器。采用合并、拆分、迁移、交换无依赖相邻子图等邻域，记录每次真实评估结果；搜索预算耗尽时输出当前最优合法方案。相同候选以规范化分区/分核签名缓存，避免重复昂贵仿真。

**问题3扩展。** 给共享 DDR 输入建立消费者集合，估计下一次复用间隔与FIFO驻留机会，鼓励共享输入消费者在时间上接近。并发过强仍可能占满L2带宽，FIFO命中也不是LRU复用距离公式；应直接复用官方访问轨迹验证。L2只能服务官方定义的可缓存只读输入，不能把所有跨核中间结果都视为命中。Welder 的张量级访存视角适合构造代理代价。[A09](https://www.usenix.org/conference/osdi23/presentation/shi)

**创新备选。** 若主路线已稳定，可加入受限宽度束搜索、分层候选预算分配或代理模型排序；IOS、ROLLER、Ansor分别提供动态规划、快速构造和搜索预算的参考。[A08](https://proceedings.mlsys.org/paper_files/paper/2021/hash/1f8053a67ec8e0b57455713cefdd8218-Abstract.html) [A10](https://www.usenix.org/conference/osdi22/presentation/zhu) [A12](https://www.usenix.org/conference/osdi20/presentation/zheng) 只有少量评估样本时，不建议把深度强化学习作为主方案。Alpa、Unity、TASO用于理解联合优化，不授权本题改写原算子或数据语义。

## 4. 实验、消融与论文证据

正式实验应覆盖100图、2～5核、三个场景，使用相同固定配置、相同搜索预算和记录的随机种子。单核分母按官方定义计算一次并保存。正文明确“先算各用例加速比，再取平均”，同时报告几何均值、中位数和最差值作补充，不能把“平均时间的比值”冒充平均加速比。问题3同时报告相对单核加速比与同核数无L2/有L2之比。

必须检查方案覆盖、商图无环、全局等待环、每条Pipe顺序、官方内存峰值以及评估异常；失败用例不可静默删去。评价算法开销时报告墙钟时间、正式评估次数、规模随节点数变化的趋势。以小型链、菱形、多分支共享输入图解释机制；这些用于逻辑验证，不替代正式测试。

建议消融：去掉通信权重、去掉缓存压力、去掉Cube/Vector互补、去掉真实评估局部搜索、去掉L2访问亲和。每次只改一项，配对比较每张图的性能变化。对差例绘制Perfetto时间线，区分关键路径阻塞、DDR争用、spill增加和同步等待，形成有解释的结论。合并后性能变差属于合理可能性，不能假设合并总有正收益。

## 5. 写作方向与执行安排

推荐题名：**共享带宽与缓存驻留约束下的NPU无环切图和联合调度**。主线突出“一套联合搜索框架，逐步加入Task通信差异和L2复用”，贡献应是可验证的特定改进，不宣称全局最优。

论文结构：问题与硬件语义；相关工作；符号和约束；场景A算法；场景B驻留感知扩展；L2调度扩展；实验与消融；边界与复杂度；结论。关键图表包括三场景通信示意、分组前后DAG、1～5核加速比、额外流量与spill分解、命中率与加速比散点、关键用例Pipe时间线、搜索时间曲线。附录放逐例结果和复现命令，程序参数、配置哈希与原始图哈希一并记录。

48～72小时安排：0～8小时跑通合法性和单核基准；8～24小时完成基线与场景A；24～40小时加入B驻留代理与局部搜索；40～52小时加入L2；52～64小时跑全量与消融；最后核对分母、失败记录、图表和代码。若时间紧，保留朴素可靠基线与两个解释清楚的改进，优先完成全部用例。

主要风险是评估开销过大、代理模型误判和合法性不足。应先审官方模拟器，再决定优化变量。当前调研未运行全部调度实验，因此不提供“提升百分比”等结果。论文如采用本调研或AI辅助代码，应按题面/赛事规范披露工具、输入任务、人工核验与后续修改。

## 6. 核验文献与阅读顺序

A01～A10为核心，A11～A15为补充。2022～2023年的A04、A09、A10、A13、A14补充近年方法。下表只概括可迁移思路；预印本明确标注，不等同同行评审结论。核验日期均为2026-09-23，未声称通读所有全文。

|编号|文献（作者，年份，出处）|本题用途|核验证据|
|---|---|---|---|
|A01|[Performance-Effective and Low-Complexity Task Scheduling for Heterogeneous Computing](https://openaccess.marmara.edu.tr/entities/publication/feba5344-0457-405a-8cb2-1d26f8963e33)；Topcuoglu, H.; Hariri, S.; Wu, M.-Y.；2002；IEEE TPDS 13(3):260–274|问题1/2：HEFT上行优先级和最早完成时间基线；须改写同构核与共享带宽代价。|作者机构论文摘要页；作者信息同时核对论文首页|
|A02|[Acyclic Partitioning of Large Directed Acyclic Graphs](https://people.bordeaux.inria.fr/julien.herrmann/pub/conf/ccgrid2017.pdf)；Herrmann, J.; Kho, J.; Uçar, B.; Kaya, K.; Çatalyürek, Ü. V.；2017；IEEE/ACM CCGrid|问题1/2：无环粗化、初分和细化；解释普通无向切图为什么可能不合法。|作者公开PDF首页、摘要和引言（非全文精读）|
|A03|[Graph Partitioning with Acyclicity Constraints](https://arxiv.org/abs/1704.00705)；Moreira, O.; Popp, M.; Schulz, C.；2017；arXiv:1704.00705（预印本）|问题1/2：带无环约束的图划分启发式，设计局部移点的合法性检查。|作者预印本摘要页|
|A04|[A Simple and Elegant Mathematical Formulation for the Acyclic DAG Partitioning Problem](https://arxiv.org/abs/2207.13638)；Özkaya, M. Y.; Çatalyürek, Ü. V.；2022；arXiv:2207.13638（预印本）|问题1/2：小规模整数规划对照及分区商图无环的数学表达；不能直接代替本题仿真目标。|作者预印本摘要页|
|A05|[I/O complexity: The red-blue pebble game](https://doi.org/10.1145/800076.802486)；Hong, J.-W.; Kung, H. T.；1981；ACM STOC:326–333|问题1–3：缓存容量与数据移动的理论关系，给通信优化提供解释。|ACM论文摘要页|
|A06|[Roofline: An Insightful Visual Performance Model for Multicore Architectures](https://doi.org/10.1145/1498765.1498785)；Williams, S.; Waterman, A.; Patterson, D.；2009；Communications of the ACM 52(4):65–76|问题1–3：以计算/内存下界解释扩核饱和；本题cycles不能擅自等同FLOPs。|作者机构技术报告摘要和正文片段、期刊版本首页|
|A07|[Rammer: Enabling Holistic Deep Learning Compiler Optimizations with rTasks](https://www.usenix.org/conference/osdi20/presentation/ma)；Ma, L.; Xie, Z.; Yang, Z.; Xue, J.; et al.；2020；USENIX OSDI|问题1/2：跨算子与算子内并行的统一调度思想，启发Cube/Vector互补。|会议论文页面与PDF摘要|
|A08|[IOS: Inter-Operator Scheduler for CNN Acceleration](https://proceedings.mlsys.org/paper_files/paper/2021/hash/1f8053a67ec8e0b57455713cefdd8218-Abstract.html)；Ding, Y.; Zhu, L.; Jia, Z.; Pekhimenko, G.; Han, S.；2021；Proceedings of Machine Learning and Systems 3|问题1/2：动态规划选择算子分组/并行方案，可借鉴拓扑窗口搜索。|会议论文摘要页|
|A09|[Welder: Scheduling Deep Learning Memory Access via Tile-graph](https://www.usenix.org/conference/osdi23/presentation/shi)；Shi, Y.; Yang, Z.; Xue, J.; Ma, L.; et al.；2023；USENIX OSDI:701–718|问题2/3：分块数据复用与分层访存代价，设计张量级共享输入亲和度。|会议论文摘要页|
|A10|[ROLLER: Fast and Efficient Tensor Compilation for Deep Learning](https://www.usenix.org/conference/osdi22/presentation/zhu)；Zhu, H.; Wu, R.; Diao, Y.; Ke, S.; et al.；2022；USENIX OSDI:233–248|问题1–3：快速构造候选、微型性能模型；本题不重新生成算子内核。|会议论文摘要页|
|A11|[TVM: An Automated End-to-End Optimizing Compiler for Deep Learning](https://www.usenix.org/conference/osdi18/presentation/chen)；Chen, T.; Moreau, T.; Jiang, Z.; Zheng, L.; et al.；2018；USENIX OSDI:578–594|背景与实现组织：图层/算子层优化分离、成本模型搜索。|会议论文摘要页|
|A12|[Ansor: Generating High-Performance Tensor Programs for Deep Learning](https://www.usenix.org/conference/osdi20/presentation/zheng)；Zheng, L.; Jia, C.; Sun, M.; Wu, Z.; et al.；2020；USENIX OSDI:863–879|问题1–3：分层候选和进化搜索预算分配；仅借鉴搜索机制。|会议论文摘要页|
|A13|[Alpa: Automating Inter- and Intra-Operator Parallelism for Distributed Deep Learning](https://www.usenix.org/conference/osdi22/presentation/zheng-lianmin)；Zheng, L.; Li, Z.; Zhang, H.; Zhuang, Y.; et al.；2022；USENIX OSDI:559–578|问题1/2：划分与映射的分层优化；GPU集群通信结论不可照搬NPU共享DDR。|会议论文摘要页|
|A14|[Unity: Accelerating DNN Training Through Joint Optimization of Algebraic Transformations and Parallelization](https://www.usenix.org/conference/osdi22/presentation/unger)；Unger, C.; Jia, Z.; Wu, W.; Lin, S.; et al.；2022；USENIX OSDI:267–284|问题1–3：联合搜索的研究背景；本题仅改变分组与调度，不改变计算语义。|会议论文摘要页|
|A15|[TASO: Optimizing Deep Learning Computation with Automated Generation of Graph Substitutions](https://catalyst.cs.cmu.edu/projects/taso.html)；Jia, Z.; Padon, O.; Thomas, J.; Warszawski, T.; Zaharia, M.; Aiken, A.；2019；ACM SOSP|创新备选：受约束图变换的正确性意识；仅使用合法合并/拆分/迁移，不做代数替换。|作者研究组项目页及论文出版信息|

完整可机读元数据见 [A题_文献.json](A题_文献.json)。DOI缺省表示本次未确认DOI，稳定论文URL仍可用于溯源。
