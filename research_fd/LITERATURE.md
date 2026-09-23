# F / D 原始文献与方法地图

核查日期：2026-09-23。以下为针对当前方案选读的16组原始论文和官方资料，**不是穷尽检索或系统综述**。区分摘要核验、正文选段、官方文档；可访问全文不等于通读全文。2025年的新方向已纳入，但不声称覆盖截至日期的所有最新论文。

报告中的代数不可辨识反例、边际条件和通信区间上界是本轮对候选模型的分析，不冒充原论文结论。所有引用均用于解释方法来源或边界；来源模型的参数和实证成绩不直接移植到赛题。

## F：质量、混合、标度和预测

### R01 — Chinchilla：固定算力下的规模/数据基线

Jordan Hoffmann, Sebastian Borgeaud, Arthur Mensch, et al. (2022). **Training Compute-Optimal Large Language Models**. [作者原始页面](https://arxiv.org/abs/2203.15556)。

阅读范围：论文摘要及元数据；经典加性N-D形式另在R04正文§2交叉核对。借鉴固定预算下联合考虑参数量和训练token量，而不是只增大模型。原型用 `E+A N^-α+B D^-β` 作可检验基线，并独立推导解析最优作单位校核。

局限：该经验形式及原系数不是对所有架构、语料、训练阶段通用的定律；本代码使用十亿单位，不能直接抄计数单位下的A/B。实现位置：`Law`、`fit_law`、`analytic_optimum`。

### R02 — RegMix：小规模配比预测与跨规模排序

Qian Liu, Xiaosen Zheng, Niklas Muennighoff, Guangtao Zeng, Longxu Dou, Tianyu Pang, Jing Jiang, Min Lin. **RegMix: Data Mixture as Regression for Language Model Pre-training**. 2024年首个预印本，2025年v2。[作者正文v2](https://arxiv.org/html/2407.01492v2)。

阅读范围：§3.1—3.4、§4.1—4.2及局限段落。借鉴代理模型配方实验、回归预测、多候选配比筛选，以及跨规模排名稳定性的检验。研究包含ridge和LightGBM路线，但本提交只实现线性/CLR ridge及验证入口，**不声称完整复现作者方法**。

局限：排名迁移不等于绝对Loss可直接跨尺度比较；供给充足假设不自动适合强筛选和有限独立数据。应对附件1M/60M/1B配对配方实际验证，不把估算10B/70B标签作为真实证据。题面作者/会议信息的历史纠正见原调研；本轮以可访问的作者v2为阅读依据。

### R03 — Data Mixing Laws：配比到域Loss的函数形式

Jiasheng Ye, Peiju Liu, Tianxiang Sun, Yunhua Zhou, Jun Zhan, Xipeng Qiu (2024). **Data Mixing Laws: Optimizing Data Mixtures by Predicting Language Modeling Performance**. [作者正文v2](https://arxiv.org/html/2403.16952v2)。

阅读范围：§3.2—3.3，尤其Eq.7指数混合形式与Eq.8聚合。启发为逐验证域建模再固定聚合权重，而非把17个训练域和13个评测域误认为一一对应。

本轮分析：因Σp=1，指数参数可整体平移并由乘法系数吸收；应以域替代系数差或明确参考系解释。这个等价变换是本轮校核，非宣称原文已给出同一批评。局限：即使拟合优良，未受控的质量与配比也不因此具备独立因果意义。

### R04 — 数据受限标度：重复token的边际价值

Niklas Muennighoff, Alexander Rush, Boaz Barak, et al. (2023). **Scaling Data-Constrained Language Models**. [作者正文v3](https://arxiv.org/html/2305.16264v3)。

阅读范围：§2、§3/3.1的Eq.5与Eq.6，以及§5—6讨论。Eq.5将首轮独立数据与后续重复的饱和贡献区分；Eq.6另有有效参数量形式。`effective_tokens`借用**有效数据项**，本提交没有实现有效参数饱和，也不描述严重过拟合引起的Loss上升。

局限：重复饱和参数需要重新估计/扫描，不能把某一研究拟合值视为跨场景常数。质量过滤导致 `U(Q)` 缩减是本轮提出的额外假设，不能说是该论文对本附件的实证结论。

### R05 — Observational Scaling Laws：多任务能力与模型族

Yangjun Ruan, Chris J. Maddison, Tatsunori Hashimoto (2024). **Observational Scaling Laws and the Predictability of Language Model Performance**. [作者正文v3](https://arxiv.org/html/2405.10938v3)。

阅读范围：方法部分及附录B.3，核查PCA、缺失处理和训练集内拟合预处理的原则。可用于“多任务低维能力—族内规模关系—未见模型预测”的设计。

局限：观察相关不等于数据质量因果贡献；任务协议变化、base/instruct混合及日期泄漏会使外推失真。该方向仅进入F报告的第四问设计，**未实现C8聚合、PCA能力模型或时间预测**。

### R06 — 2025联合配比标度：最优配比未必与预算无关

Mustafa Shukor, Louis Bethune, Dan Busbridge, David Grangier, Enrico Fini, Alaaeldin El-Nouby, Pierre Ablin (2025). **Scaling Laws for Optimal Data Mixtures**. [作者正文v1](https://arxiv.org/html/2507.09404v1)。

阅读范围：§2.2，比较加性形式Eq.4与配比影响规模/数据项的联合形式Eq.5。它为“配比效应是否随N/D变化”提供可检验的对照模型，适合与R02的排序迁移假设并列讨论，而非二选一当定理。

局限：小维度域实验不自动支持17域高自由度拟合；更多交互参数更容易不可辨识。建议先低阶、正则化的规模交互消融；本提交没有实现该论文的完整联合估计。

### R07 — Meta-rater与官方数据卡：必须分清每种列表

Xinlin Zhuang, Jiahui Peng, Ren Ma, et al. (2025). **Meta-rater: A Multi-dimensional Data Selection Method for Pre-training Language Models**. [作者摘要与元数据](https://arxiv.org/abs/2504.14194)。OpenDataLab官方 [SlimPajama-Meta-rater数据卡](https://huggingface.co/datasets/opendatalab/SlimPajama-Meta-rater/blob/main/README.md)。

阅读范围：论文摘要；数据卡字段定义、类别和例子。数据卡包含单元素分数、二分类logits、有序类别logits，也存在把不同维度放入同一列表的字段；不能以“所有列表都是logits”或“所有列表求平均”代替字段级解析。

重要区分：数据卡部分字段建议argmax；报告提出softmax期望等级是便于连续建模的**候选替代**，不是作者统一要求，也不意味着概率已经校准。只有确认类别顺序与语义才适用，应与argmax版比较。原数据卡25维与题目选择的22维需逐字段对照。全量评分未实现。

### R08 — DoReMi：域重加权的替代思路

Sang Michael Xie, Hieu Pham, Xuanyi Dong, et al. (2023). **DoReMi: Optimizing Data Mixtures Speeds Up Language Model Pretraining**. [作者摘要与元数据](https://arxiv.org/abs/2305.10429)。

阅读范围：摘要，未通读训练算法。用于讨论基于域表现重加权与直接配比回归的区别；不从摘要推断具体超参数、损失实现或当前附件收益。当前无DoReMi训练代码，也不需要为了运行本原型占用GPU。

### R09 — Pythia：开放训练轨迹的来源背景

Stella Biderman, Hailey Schoelkopf, Quentin Gregory Anthony, et al. (2023). **Pythia: A Suite for Analyzing Large Language Models Across Training and Scaling**. ICML, PMLR 202. [正式会议页面](https://proceedings.mlr.press/v202/biderman23a.html)。

阅读范围：正式摘要与元数据。其同族训练轨迹适合讨论规模与训练进展，但论文存在不证明附件中每个同名CSV字段都源自原始训练日志。当前B1前34行的run_id逐行唯一，必须另核其语义，不按名字把它当轨迹簇ID。

## D：路由、通信与调度

### R10 — 无人机路由中的载荷与多架次复用

Kevin Dorling, Jordan Heinrichs, Geoffrey G. Messier, Sebastian Magierowski. **Vehicle Routing Problems for Drone Delivery**. 2016预印本；IEEE Transactions on Systems, Man, and Cybernetics: Systems, 47(1), 70–85, 2017. [作者原始页面](https://arxiv.org/abs/1608.02305)。

阅读范围：摘要与出版元数据。借鉴把能量、载荷、机队复用共同纳入路线规划，而不是只优化平面总距离。原题的航程、爬升、库存与交付规则仍须采用题给口径；当前能耗内核不是该论文完整复现，也不是已核验的官方箱集合解。

### R11 — 旋翼通信的飞行/悬停耦合

Yong Zeng, Jie Xu, Rui Zhang (2018预印本). **Energy Minimization for Wireless Communication with Rotary-Wing UAV**. [作者原始页面](https://arxiv.org/abs/1804.02238)。

阅读范围：摘要与元数据。用于启发分开处理移动、悬停位置及服务时间，再协调能源。没有从摘要直接移植推进功率公式；题给中继能源组件、最高AGL、建链和回传约束必须单独落实。

### R12 — ALNS：可行解上的破坏/修复

Stefan Ropke, David Pisinger (2006). **An Adaptive Large Neighborhood Search Heuristic for the Pickup and Delivery Problem with Time Windows**. Transportation Science, 40(4), 455–472. DOI: 10.1287/trsc.1050.0135. [出版社页面](https://pubsonline.informs.org/doi/10.1287/trsc.1050.0135)。

阅读范围：出版社摘要与元数据。可作为运输方案破坏/修复、自适应选择算子的来源。本轮提出的电池/通信修复需自行实现；未通读算法实现，不宣称已复现原作者参数或性能。

局限：启发式找不到插入位置，不证明选择组合全局不可行；不能据此删除其他时刻可能可行的路线。本提交尚无完整ALNS求解器。

### R13 — ITU-R P.525-5：自由空间衰减和单位

International Telecommunication Union (11/2024). **Recommendation ITU-R P.525-5: Calculation of free-space attenuation**. [官方PDF](https://www.itu.int/dms_pubrec/itu-r/rec/p/R-REC-P.525-5-202411-I!!PDF-E.pdf)。

阅读范围：标准Eq.6所在页，已查看PDF截图（文件第5页、正文页码3）。原文为 `L_bf=32.4+20log10(f)+20log10(d)`，f单位MHz、d单位km。

代码沿既有调研采用32.45，差0.05dB，正式求解应统一题面常数。标准的自由空间衰减不等于山区传播全模型；遮挡额外10dB来自既有调研转述的赛题代理，非ITU对所有遮挡的保证。双向门槛、最坏罚和区间距离上界组合是本轮方法推导。

### R14 — 逻辑Benders：分配与调度分解

John N. Hooker (2007). **Planning and Scheduling by Logic-Based Benders Decomposition**. Operations Research, 55(3), 588–602. DOI: 10.1287/opre.1060.0371. [出版社页面](https://pubsonline.informs.org/doi/10.1287/opre.1060.0371)。

阅读范围：出版社摘要及元数据，确认MILP分配/CP调度分解思路，未逐条复现原论文割。对应本题可研究路线选择主问题、资源和中继时间子问题。

局限：本轮关于“只有证实不可行才能添加相应全局no-good割”的提醒是算法正确性要求，不是已经实现的有效割族。候选路线池不完整时，池内最优不等于全问题最优。

### R15 — OR-Tools区间调度官方文档

Google OR-Tools. **The Job Shop Problem**. [官方教程](https://developers.google.com/optimization/scheduling/job_shop)。在线软件文档，查阅于2026-09-23，不按固定论文年份引用。

阅读范围：区间、先后、NoOverlap的建模与示例。可用来承载实体机、电池等兼容资源的时间约束，但换电、充电、机型和通信规则不会自动存在于标准job-shop示例。本提交没有OR-Tools依赖或完整CP-SAT模型。

## 数值实现

### R16 — SciPy稳健非线性最小二乘

SciPy官方文档. **scipy.optimize.least_squares**. [在线API文档](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html)。查阅于2026-09-23。

阅读范围：bounds、loss、f_scale、收敛返回和Jacobian参数说明；在线文档版本可能随更新改变。实际测试版本为SciPy 1.17.0，见environment.txt，不把网页版本当测试环境。

soft-L1和多起点用于减少异常残差/初值影响，但数值收敛不证明参数可识别或外推可信。雅可比条件数是坐标相关诊断，不能代替组间验证、参数剖面或来源审计。

## 选读顺序

F先读R02/R03/R04正文相应小节，再对照R06提出跨规模交互检验，R05用于最后一问；R07数据卡应在任何Q构造之前读。D先固定R13单位与题面口径，再读R10/R11建立耦合问题意识，R12/R14用于选择求解策略。

摘要级条目只支持方法背景；需要实际移植算法时，应继续阅读原文对应方法与实现。未读到的细节不从二手概述补成“原文结论”。
