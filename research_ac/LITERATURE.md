# A / C 文献地图与方法迁移边界

核验日期：2026-09-23。本文件补充而不替换原仓库的文献库；编号供两份深度报告引用。优先使用论文作者版本、期刊/会议官网和作者所属机构记录。下面的“阅读范围”区分摘要、方法段和全文可访问，不将网页访问写成论文复现。代码中的实验是本项目自建反例/原型，未复现这些论文的完整实验。

## A：先解决结构与代价，再考虑复杂搜索

### [A-HYP] 多层无环超图划分——最高优先级

Popp, M.; Schlag, S.; Schulz, C.; Seemaier, D. **Multilevel Acyclic Hypergraph Partitioning**. ALENEX, 2021. DOI: 10.1137/1.9781611976472.1。

来源：[作者版本](https://arxiv.org/abs/2002.02962)、[HTML 方法正文](https://arxiv.org/html/2002.02962v2)、[KIT 会议发表记录](https://publikationen.bibliothek.kit.edu/1000133449)。阅读范围：作者版本的问题定义、无环约束与多层划分思路；发表信息由机构记录交叉核对。

可迁移：把一个张量的生产者与全部消费者表示为一个超边，避免按普通 DAG 每条边重复收费；将商图无环作为划分约束。不可直接迁移：原论文划分目标不包含本题 Step3 生成的 Pipe FIFO、跨核 COPY 及地址复用等待。商图无环不是本题全局可执行性的充分条件。

落地：[a_search.py](a_search.py) 的张量集合计费、保序区间划分和基础合法性；[REPORT_A.md](REPORT_A.md) 第 2–3 节。本次没有移植其完整多层算法。

### [A-HEFT] 列表调度与最早完成时间——基线思想

Topcuoglu, H.; Hariri, S.; Wu, M.-Y. **Performance-effective and low-complexity task scheduling for heterogeneous computing**. IEEE Transactions on Parallel and Distributed Systems, 13(3):260–274, 2002. DOI: 10.1109/71.993206。

来源：[作者所属机构记录](https://openaccess.marmara.edu.tr/entities/publication/feba5344-0457-405a-8cb2-1d26f8963e33)。阅读范围：摘要、书目信息和优先级/插入式处理器选择概要；未宣称重新实现论文全部细节。

可迁移：剩余关键路径优先级，以及选择处理器时考虑负载与数据到达。不可直接迁移：异构处理器上的固定通信代价并不等于本题同构核心、异类 Pipe 与共享 DDR 的联合争用。当前程序是 HEFT 启发的候选生成器，不命名为严格 HEFT 复现；最终以官方模拟器判优。

### [A-MEM] 内存感知、自适应工作流调度——2025 年补充

Kulagina, S.; Benoit, A.; Meyerhenke, H. **Memory-aware Adaptive Scheduling of Scientific Workflows on Heterogeneous Architectures**. 2025；作者版本标注 CCGRID'25。arXiv:2503.22365。

来源：[作者版本与发表备注](https://arxiv.org/abs/2503.22365)。阅读范围：摘要、内存约束/驱逐与自适应重排的方法说明；未进一步核定会议页码或出版 DOI，因此不补写。

可迁移：计算最早完成时间不能忽略输入/输出驻留和驱逐成本；内存状态需要进入候选代价。区别：本题原始 cycles 已给定，论文面对运行时预测偏差的自适应机制并非必要核心。报告提出的 live-byte-time 与峰值联合惩罚是下一步设计，当前代码没有假装已实现完整缓存峰值代理或自适应运行时。

### [A-WELDER] 从张量访存关系出发——解释代价而非改写算子

Shi, Y.; Yang, Z.; Xue, J.; Ma, L.; Xia, Y.; Miao, Z.; Guo, Y.; Yang, F.; Zhou, L. **Welder: Scheduling Deep Learning Memory Access via Tile-graph**. OSDI, 2023:701–718。

来源：[USENIX 原始论文页及官方书目信息](https://www.usenix.org/conference/osdi23/presentation/shi)。阅读范围：官方摘要、方法概要和出版信息；未运行 Welder 或复刻其编译器实验。

可迁移：以张量传递和复用组织代价模型，不把计算图边数当字节流量。不可直接迁移：本题不能借 tile-graph 之名改原图 cycles、tensor size 或原算子语义。适合支撑场景 B 驻留亲和、场景 3 输入复用的设计动机。

### [A-IOS] 算子间动态规划——有条件的精确子问题

Ding, Y.; Zhu, L.; Jia, Z.; Pekhimenko, G.; Han, S. **IOS: Inter-Operator Scheduler for CNN Acceleration**. Proceedings of Machine Learning and Systems, 3, 2021。

来源：[MLSys 官方论文页](https://proceedings.mlsys.org/paper_files/paper/2021/hash/1f8053a67ec8e0b57455713cefdd8218-Abstract.html)。阅读范围：官方摘要及算子间调度的动态规划概要。

可迁移：对小图/窄前沿图构造更精确的局部搜索或 oracle。限制：状态必须充分表示驻留、剩余依赖与共享带宽，否则不同历史不能安全合并为同一 DP 状态。本次只提出“限制模型上的前沿 DP”方向，没有交付一个冒充官方全局最优解的 DP。

### [A-CP] OR-Tools Job Shop——工具文档，不是论文

Google OR-Tools. **The Job Shop Problem**. 官方技术文档，核查于 2026-09-23。

来源：[官方示例与约束说明](https://developers.google.com/optimization/scheduling/job_shop)。阅读范围：interval、precedence、NoOverlap 及 makespan 目标。

用途：制作忽略动态带宽/缓存的限制模型小规模 oracle。必须明确限制模型最优值不自动是官方问题最优值；放松约束所得下界还要证明方向。本次未安装或验证 OR-Tools，故未附一个未经执行的“精确求解”实现。

## C：先纠正观测和验证，再增加神经机制

### [C-UNFOLD] 连续 EEG 的事件重叠校正——最高优先级

Ehinger, B. V.; Dimigen, O. **Unfold: an integrated toolbox for overlap correction, non-linear modeling, and regression-based EEG analysis**. PeerJ, 7:e7838, 2019. DOI: 10.7717/peerj.7838。

来源：[原文开放全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC6815663/)。阅读范围：时展开设计矩阵、重叠校正、非线性协变量以及模型假设相关方法段。

可迁移：在连续记录上同时放入刺激和按钮事件 FIR，条件差异可能来自不同 RT 分布下的运动响应重叠。识别依赖事件间隔变化和足够设计矩阵秩；固定相对时延可能让两个核不可区分，ridge 只能选取正则解。负按钮时滞仅用于回顾性解释，不能拿未来按钮时间定义在线输入。

落地：[c_deconvolve.py](c_deconvolve.py)、[c_models.py](c_models.py) 与 10 个种子的合成重叠实验。本实现是四事件线性 FIR 原型，不是完整 Unfold 非线性工具箱。

### [C-DSS] 任务偏置的源分离——警惕“降噪”目标错位

Särelä, J.; Valpola, H. **Denoising Source Separation**. Journal of Machine Learning Research, 6(9):233–272, 2005。

来源：[JMLR 原始论文页](https://jmlr.org/papers/v6/sarela05a.html)。阅读范围：摘要与去噪偏置的基本思想，未把简化代码标为论文全算法复现。

可迁移：按与任务有关的重复结构而非仅按总方差选择成分。当前代码以训练折条件 ERP 协方差作为偏置，属于 DSS 启发的广义特征值投影。测试折标签绝不能参与空间滤波器生成。本项目反例同时公布 DSS 启发法较好的分类和更差的全波形 MSE，避免单指标挑选。

### [C-XDAWN] 诱发响应增强——与 DSS 形成对照

Rivet, B.; Souloumiac, A.; Attina, V.; Gibert, G. **xDAWN Algorithm to Enhance Evoked Potentials: Application to Brain–Computer Interface**. IEEE Transactions on Biomedical Engineering, 56(8):2035–2043, 2009. DOI: 10.1109/TBME.2009.2012869。

来源：[作者保存的论文 PDF](https://www.gipsa-lab.grenoble-inp.fr/~bertrand.rivet/references/Rivet2009a.pdf)。阅读范围：方法与 Rayleigh 商/广义特征值目标；已核查相关 PDF 页面。论文实验通道配置不同于本题三额区导联。

可迁移：诱发成分与总信号能量的相对优化；与 PCA 的总方差目标形成明确对照。不能将本次训练条件均值投影命名为完整 xDAWN，也不能默认空间秩越低越能保留左右差异。

### [C-EEG2ERP] 少试次 ERP 与不确定性——2025 年补充

Nørskov, A. V.; Jørgensen, K.; Zahid, A. N.; Mørup, M. **Estimating the Event-Related Potential from Few EEG Trials**. Transactions on Machine Learning Research, 2025；作者版本 arXiv:2511.23162。

来源：[作者摘要](https://arxiv.org/abs/2511.23162)、[HTML 正文及 OpenReview 指向](https://arxiv.org/html/2511.23162v1)、[作者机构发表记录](https://orbit.dtu.dk/en/persons/anders-vestergaard-n%C3%B8rskov/)。阅读范围：方法、输入/目标分半及不确定性设计；发表状态由机构记录核对。OpenReview 页面受浏览器验证限制，未读完整审稿讨论。

可迁移：少试次估计的方差、独立分半验证和输入/参考 ERP 不能共享同一批噪声。先移植评价设计，而不是立即训练大网络。预训练通道、参考电极、任务和幅值单位不匹配时，不能假设模型零样本适用于三额区 EEG。本次未训练 EEG2ERP 或下载权重。

### [C-WC] 兴奋—抑制神经群模型——功能性生成模型基础

Wilson, H. R.; Cowan, J. D. **Excitatory and inhibitory interactions in localized populations of model neurons**. Biophysical Journal, 12(1):1–24, 1972. DOI: 10.1016/S0006-3495(72)86068-5。

来源：[原论文索引及摘要](https://pubmed.ncbi.nlm.nih.gov/4332108/)。阅读范围：书目信息、摘要和 E–I 群体建模基础；不声称复现该文的完整非线性分岔分析。

本项目使用稳定线性化 E–I 偏差模型，非解剖真实反演。[REPORT_C.md](REPORT_C.md) 给出的等价参数构造是对本项目模型的推导，不是引用 Wilson–Cowan 原文的结论。三参数加自由观测矩阵时不能将极小误差当作三参数均可辨识；建议固定一个时间常数并做敏感性分析，或报告两个可辨识组合。

### [C-DDM] 广义漂移扩散与完整 RT 似然——认知层基线

Shinn, M.; Lam, N. H.; Murray, J. D. **A flexible framework for simulating and fitting generalized drift-diffusion models**. eLife, 9:e56938, 2020. DOI: 10.7554/eLife.56938。

来源：[原论文](https://elifesciences.org/articles/56938)、[开放全文镜像](https://pmc.ncbi.nlm.nih.gov/articles/PMC7462609/)、[作者机构方法说明](https://medicine.yale.edu/psychiatry/education/programs-and-initiatives/map/support/murray/)。阅读范围：Fokker–Planck 数值求解、时变漂移与选择/反应时联合拟合方法；未运行完整 PyDDM 软件的原文基准。

可迁移：拟合左右选择和完整反应时分布；未响应观测进入生存概率，而非删除。当前自写隐式 birth–death/upwind 求解器是可检查的数值原型，做了概率守恒、对称性及网格细化检查；不宣称已达到 PyDDM 数值精度。缺失目标出现时刻时，提示到点击的模型只能作描述性替代，不能声称估出了真实决策时间。

### [C-MEMORY] 突触工作记忆——用于扩展假设，不是既有发现

Taher, H.; Torcini, A.; Olmi, S. **Exact neural mass model for synaptic-based working memory**. PLOS Computational Biology, 16(12):e1008533, 2020. DOI: 10.1371/journal.pcbi.1008533。

来源：[期刊原文](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1008533)。阅读范围：模型目标、短时突触可塑性和宏观群体描述的方法思路。

启发：记忆不必等价于持续高放电活动，可比较衰减活动状态与慢突触状态。但本题三个测点不直接测量突触变量。本次只交付“常漂移/指数衰减输入”描述性对照；完整突触可塑性模型、跨试次记忆和 EEG–行为层联合拟合仍属后续方向。

### [C-LEAK] EEG 数据泄漏——验证协议文献

Brookshire, G.; Kasper, J.; Blauch, N. M.; Wu, Y. C.; Glatt, R.; Merrill, D. A.; Gerrol, S.; Yoder, K. J.; Quirk, C.; Lucero, C. **Data leakage in deep learning studies of translational EEG**. Frontiers in Neuroscience, 18:1373515, 2024. DOI: 10.3389/fnins.2024.1373515。

来源：[期刊原文](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2024.1373515/full)、[PMC 全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC11099244/)。阅读范围：数据切分与泄漏风险；引用的是同行评审版本，而非早期预印本 DOI。

落地：同一记录/试次不拆散到外层训练与测试；测试标签不参与去噪、标准化、参数选择；没有被试身份映射就只称“跨记录”。文中的临床背景不赋予本题疾病诊断结论。

## 推荐阅读与复现实验顺序

A：先读官方附件 README 和模拟接口，再读 A-HYP、A-HEFT、A-MEM；跑结构测试和一个真实图，再决定要不要引入 A-IOS / A-CP 的复杂搜索。

C：先核对事件表，再读 C-UNFOLD、C-DSS / C-XDAWN、C-LEAK；运行合成反例后接入真实记录。C-WC 与 C-DDM 服务于受约束生成解释，C-EEG2ERP 与 C-MEMORY 是基础路线站稳后的扩展。

所有 DOI/链接指向文献来源，不表示文献中的性能数字已在本题复现。正式论文还应引用实际采用的原始文献，披露 AI 辅助、人工核对和修改记录；不得把本次反例实验数字当作赛事附件成绩。
