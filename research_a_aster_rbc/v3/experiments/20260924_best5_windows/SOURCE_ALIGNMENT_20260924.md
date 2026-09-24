# 原始来源、固定源码定位与案头验证记录

日期2026-09-24。这里没有新增官方实验；网页查询、源码阅读、派生表算术重算均不能替代原始响应验证。

## 1. 固定来源

实验：[PR20 head 25efe96](https://github.com/yellkiin/model_competition/tree/25efe96e85aa1daff9a751af3c4fad454d106ccb/research_a_aster_rbc/v3/experiments/20260924_best5_windows)。读取时确认该PR已合并，但实际阅读仍显式使用其head。

实现：[cd24013的v3](https://github.com/yellkiin/model_competition/tree/cd24013cb8dfc29d847df5c4caea5222923402a7/research_a_aster_rbc/v3)。发布新设计所用main之后可能前移，不能据此更换实现基线。

已读记录：README、EVIDENCE、MEASURED_REPORT、DIAGNOSTICS、NEXT_STEP_PROMPT，及statistics.json、measured_variants.csv、jobs.csv、evaluation_attempts.csv、cache_pairs.csv、reference_pr16.csv、manifest.json、coverage.json、run_receipt.json。长表分段读取到尾部。没有拿历史绝对路径当成可访问的原文件。

## 2. 原始论文：确切使用内容

以下“页”指PDF页序，不是出版社连续页码。A39的出版年2021与预印本初次提交2020分开。各论文仅阅读与本次设计相关的正文；没有执行其软件或复现其结果。

### L1 / A49

M. Yusuf Özkaya、Anne Benoit、Bora Uçar、Julien Herrmann、Ümit V. Çatalyürek，2019。
**A Scalable Clustering-Based Task Scheduler for Homogeneous Processors Using DAG Partitioning**，IPDPS。
[作者原始PDF](https://people.bordeaux.inria.fr/julien.herrmann/pub/conf/ipdps2019.pdf)。使用PDF第1–4页，§III–IV及Algorithm 1。

论文先无环分簇，再作任务级列表调度，约束同簇同处理器；不是把整个簇作为不可分割的大任务。通信采用duplex single-port，单处理器可并行计算、发送一项、接收一项；同处理器任务间通信不收费。

迁移：M1保留细单元，M2以依赖释放选择边界。本题一个核心有多个Pipe、DDR跨核共享，且Q1同核跨Task仍搬运，不能照搬通信日历或原性能数字。

### L2 / A02

Julien Herrmann、Jonathan Kho、Bora Uçar、Kamer Kaya、Ümit V. Çatalyürek，2017。
**Acyclic Partitioning of Large Directed Acyclic Graphs**，CCGrid。
[作者原始PDF](https://people.bordeaux.inria.fr/julien.herrmann/pub/conf/ccgrid2017.pdf)。使用PDF第1–4页，Definition 2.2、§IV及合并条件。

采用粗化、初划分、反粗化细化，并维护无环。原文受限分区权重与cut目标不是本题私有存储峰值和Makespan。M1借鉴可逆粒度，但使用更保守的拓扑前缀和公共顺序相邻合并；其合法性是本文单独推导，不冒称复现原算法。

### L3 / A39

Merten Popp、Sebastian Schlag、Christian Schulz、Daniel Seemaier，ALENEX 2021；预印本2020。
**Multilevel Acyclic Hypergraph Partitioning**。
[原始预印本PDF](https://arxiv.org/pdf/2002.02962)、[正式出版记录](https://epubs.siam.org/doi/10.1137/1.9781611976472.1)。使用PDF第2–5页，§2–3。

有向超边由tail指向head；论文主要实现针对单head，讨论了多head收缩限制，目标使用connectivity。Tensor用集合表达复用有价值，但一生产者多消费者通常对应单tail多heads；本题COPY还区分读、写、图输入与最终输出，不能把(lambda−1)*size直接当作精确流量。

原始PDF文字成功读取；该PDF网页截图请求出现cache miss，本次不据其未取得的图片或实验表格推导结论。

### L4 / A16

Yi Li、Aarti Gupta、Sharad Malik，2023。
**Combined Scheduling, Memory Allocation and Tensor Replacement for Minimizing Off-Chip Data Accesses of DNN Accelerators**（COSMA）。
[作者预印本全文](https://arxiv.org/html/2311.18246v1)。使用§III-A至III-F，特别是四种Tensor状态、式(9)–(12)和目标的范围。

联合调度、连续地址分配与替换，以额外片外访存字节为目标。它不是固定Step1/2/3、多核公平共享带宽下的Makespan最优解。本题可以借鉴生命周期/替换状态来评分合法方案，不能直接控制地址、Spill指令或删除有利流水的Spill。

### L5 / A42

Pál András Papp、Georg Anegg、Aikaterini Karanasiou、Albert-Jan N. Yzelman，2024。
**Efficient Multi-Processor Scheduling in Increasingly Realistic Models**，SPAA。
[原始全文](https://arxiv.org/html/2404.15246v1)、[正式出版记录](https://doi.org/10.1145/3626183.3659972)。使用§3.2–3.5、§4.3–4.4、附录A.3–A.4。

BSP将计算与通信分阶段，总成本由各superstep相加；论文还把局部计算映射、通信时机及局部ILP分开优化。迁移的是受影响局部和可用通信窗口，不是BSP总成本公式、五分钟/三十分钟预算，也不是论文中的数倍指标。

### L6 / Python官方文档

[Python 3.12 subprocess](https://docs.python.org/3.12/library/subprocess.html#subprocess.Popen.communicate)、[time.perf_counter](https://docs.python.org/3.12/library/time.html#time.perf_counter)。只用于说明外部等待时限/墙钟不等于模拟完成周期，以及等待超时后需要显式清理进程；不作为某次076超时的性能原因证据。

## 3. 固定源码与官方语义位置

以下源码链接全部固定cd24013。行号用于导航，不把源码行号混为connector的引用行号。

|编号|定位|核对内容|
|---|---|---|
|C1|[components.py L9–53](https://github.com/yellkiin/model_competition/blob/cd24013cb8dfc29d847df5c4caea5222923402a7/research_a_aster_rbc/v3/components.py#L9-L53)|vector-LPT默认traffic_weight=0；locality_waves按wave/core聚合；wave不改变component_owners|
|C2|[policy.py](https://github.com/yellkiin/model_competition/blob/cd24013cb8dfc29d847df5c4caea5222923402a7/research_a_aster_rbc/v3/policy.py)|profile、_base_recipes、recipes、build；独立结构分支只有component/wave；Q1不注入新增release/affinity候选|
|C3|[quality.py L14–186](https://github.com/yellkiin/model_competition/blob/cd24013cb8dfc29d847df5c4caea5222923402a7/research_a_aster_rbc/v3/quality.py#L14-L186)|view与条件性下界分离；neighbors从L126开始；无细单元迁移/拆分/交换，incumbent未用，score未排序|
|C4|[enhancements.py](https://github.com/yellkiin/model_competition/blob/cd24013cb8dfc29d847df5c4caea5222923402a7/research_a_aster_rbc/v3/enhancements.py)|export_split、release_frontier、affinity_pipeline；end来自构造日历；工作集为静态惩罚|
|C5|[job.py L27–96](https://github.com/yellkiin/model_competition/blob/cd24013cb8dfc29d847df5c4caea5222923402a7/research_a_aster_rbc/v3/job.py#L27-L96)|build前检查search_deadline，evaluate入口仅检查最终deadline；Q3 timeout下限0.01；先构造后邻域|
|C6|[stages.py L21–68](https://github.com/yellkiin/model_competition/blob/cd24013cb8dfc29d847df5c4caea5222923402a7/research_a_aster_rbc/v3/stages.py#L21-L68)|16桶DP枚举区间；区间成本相加；精确性仅限该代理|
|C7|[model.py L87–141](https://github.com/yellkiin/model_competition/blob/cd24013cb8dfc29d847df5c4caea5222923402a7/research_a_aster_rbc/v3/model.py#L87-L141)|retained_pred、每Pipe总工作及lower_bound；wcc每次扫描全g.order，不能忽略重复调用成本|

官方附件根目录：[`题目/A题/通用神经网络处理器下的多核调度问题  附件`](https://github.com/yellkiin/model_competition/tree/cd24013cb8dfc29d847df5c4caea5222923402a7/题目/A题/通用神经网络处理器下的多核调度问题%20%20附件)。

|编号|文件/函数/行号|语义与设计边界|
|---|---|---|
|S1|docs/多核并行模拟执行算法.md §2–6|Q1 Task门控，Q2/3每核合Task；4 Pipe；DDR公平共享；Cache独立读池|
|S2|code/multicore_cut_evaluate_problem_1.py L70–198 `_build_scene_a_tasks`|每Task输入/输出边界，DDR→UB，Step1/2/3，原始/边界/Spill字节分解|
|S3|code/multicore_cut_evaluate_problem_2.py L43–59 `_prioritize_task_seq`；L135–270 `_build_scene_b_tasks`|图输入按消费核；跨核按源核→目标核对；src后生产子图/dst早消费子图；保留同核优先级|
|S4|code/schedule_step3.py L74–84 `_op_duration`，L125–180容量额度与L459起发射逻辑|普通操作max(1,cycles)；可拆字节额度与复用依赖不是COSMA连续地址；不把序列中静态活跃字节当最终时间线|
|S5|code/multicore_cut_evaluate_problem_3.py L398–442、L493–580|逻辑Tensor查询、发射时判hit、完成尝试插入、不刷新FIFO；外部500等待；两池与发射顺序|

官方资料包仅作便于逐行阅读的本地副本；上述主要Task、COPY、Cache逻辑通过固定提交connector回读对照。局部文档的“步骤1/2/3”编号不能替代多核题三问的实际Task语义。

## 4. 算术与逻辑交叉验证：没有新增运行分数

1. 转录远端 `measured_variants.csv` 的12图fast/best和本轮T1字段，重算逐例比例、AM/GM：均与statistics一致。转录错误风险不能由原始响应校验排除，因此只称派生字段交叉核对。
2. 回退以周期增加计算：012 Q1/Q2为(15706/13005−1)*100%=20.768935%；094 Q1/Q2=5.049608%，Q3=5.509826%。这些是旧参考对新结果，不是同预算因果实验。
3. 003 Q1周期减少38.585542%；partition字节增加78.420164%；最忙核M工作下降39.060273%。三者同时成立，不允许用“减少搬运”统一解释。
4. directed净增益只相对于同次最好构造：035的127/120周期及088的33/472/150周期，不相对于fast。这五项加其余30个因子1，GM=1.0002326002；即约0.02326%的时长比增益，不是整套候选选优只有这个收益。
5. cache_pairs12组包含035的91400/91401<1。028/076即使缺原始T1，仍能记录其同方案Cache比，因为这个分母不是Q0。
6. “整块移不动，但其中独立单元能移”用6+4对2的简化解析例说明邻域局限；没有调用仿真器，不能视为正式案例复现。
7. Q3 build结束后跨search_deadline但未跨deadline的代码路径确实存在；028的0.031秒调用支持追查该路径，但没有绝对事件记录，不宣称已经完整复现超时成因。

## 5. 待补的来源而不是待填的结论

必须向本地读取原有012/094旧新方案及对应工作量，才能判定回退是否主要由分量分核改变；需要035原始图与主核依赖，才能区分隐藏并行与真正串行；需要028/076日志/已有剖析才能定位评估墙钟。源文件未保存或不在机器上就写缺失。本轮不执行求解器来补证据，也不借旧分母填入本轮均值。
