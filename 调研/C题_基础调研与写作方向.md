# C 题：基础调研与写作方向

核查日期：2026-09-23。本文是选题与建模准备，不包含已完成的降噪、分类或认知拟合实验。文献核查层级逐条列出，网页可访问不等于已阅读全文。

## 1. 题目边界与数据现状

本题有三个递进任务：为项目一、二分别设计保留视觉形状信息的降噪方法并拟合三测点响应；建立从视觉刺激到神经群再到头皮观测的生成模型，解释左右三角差异；截取应答前认知信号，建立包含可能记忆作用的宏观模型并验证。疾病是背景，附件没有已核实的诊断标签或病例对照设计，不能把三角识别准确率写成疾病诊断能力。

本地已有四份 MAT。只读 MAT-v5 标签核验结果如下；变量内部事件数、缺失率、幅值单位和时间戳连续性尚未统计。

|文件|原始 data 维度|可见变量|
|---|---:|---|
|VisualCogA_Task-1.mat|10 × 223845|SampleRate、DataLabel、data|
|VisualCogA_Task-2.mat|10 × 230157|同上|
|VisualCogB_Task-1.mat|10 × 223005|同上|
|VisualCogB_Task-2.mat|10 × 228330|同上|

题面规定采样率 256 Hz，通道顺序是 Fz、F3、F4、三个 Decon 通道、ECG、VisCue、TgtAct、TimeStamp。第 1–3 通道是建模输入；第 4–6 通道是机器滤波结果，题面要求避免直接使用；ECG 不是 EOG，不能直接作为眨眼真值。VisCue 的 ±1 表示提示方向，TgtAct 的 ±2 表示点击侧。A/B 文件名不能证明只有两名被试；核实身份前只能称记录组。

开工先构建事件表：以 VisCue 从零进入非零段的起点识别提示，合并持续电平而非把每个非零采样点当试次；在下一提示之前匹配应答，保留错误、超时、重复点击和无应答标志。项目二“形状方向”和“点击空间位置”可能不同，须按实验映射判正确，不能简单用提示符号等于点击符号替代。

## 2. 推荐主线与小问对应

建议题名：**三导联视觉脑电的形态保持去噪、神经群生成模型与认知证据积累分析**。中心论点应是“少通道下可验证的低维机制模型”，避免承诺从三导联重建真实脑区或单神经元分布。

|小问|可靠基线|主路线|必须交付|
|---|---|---|---|
|1：降噪及曲线|温和带通、坏试次标记、稳健事件平均|试次矩阵低秩/稀疏分解＋平滑约束，训练折选择参数|四记录、两方向、三电极曲线与区间；保留率和失真评估|
|2：形成机制、左右区分|ERP 时窗均值/斜率＋收缩 LDA；延迟 VAR|形状输入编码→少量兴奋/抑制神经群→线性观测层|生成曲线、可辨参数区间、方向特征及留出预测|
|3：认知模型|只用提示/任务条件的行为模型|记忆状态＋证据积累，联结 EEG、选择和反应时|正确/错误/超时拟合；外推预测；认知窗口敏感性|

生成建模的尺度划分可依据 [C01](https://pubmed.ncbi.nlm.nih.gov/33779888/)，视觉诱发响应参考 [C03](https://pubmed.ncbi.nlm.nih.gov/8452897/)。P300 是任务相关成分，前额观测不能自动命名为中央—顶区 P3b；应优先写“250–500 ms 正向候选成分”，再比较其形态与条件效应。[C04](https://pubmed.ncbi.nlm.nih.gov/17573239/)

## 3. 方法设计与关键假设

### 3.1 将“去干扰”和“保留信息”同时量化

先按连续时间块划分训练与测试，再拟合任何阈值、模板、空间滤波、归一化或降噪超参数。初始候选滤波范围可设 0.1–30 Hz，并将高通 0.1/0.3/0.5 Hz、低通 20/30/40 Hz 作为预先规定的敏感性网格；这只是待验证设置。工频陷波应由频谱判断，不默认所有记录都需要。滤波可能改变潜伏期并把晚期信号扩散至早期，必须保存滤波器响应与边缘裁剪规则。[C05](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2012.00233/full)

以训练试次排列得到矩阵 X，尝试：

```math
min_{L,S} 0.5 ||X-L-S||_F² + λ*||L||_* + λ1||S||_1 + λt||D_t²L||_F² .
```

L 是共享低维响应，S 是稀疏大幅异常，二阶差分惩罚限制曲线粗糙度。关键假设是诱发响应存在跨试次重复性、部分干扰稀疏；持续眼动不一定满足此假设，须用合成污染和人工抽查否证。不能按测试集真实左右标签分别生成模板后再分类。低秩可能抹平真实差异，故比较“不低秩”“不平滑”和不同秩，而不以波形变平滑作为成功标准。

对实际无干净真值的记录，联合报告：异常试次比例、基线噪声、分半波形相关、预定义窗口振幅和潜伏期稳定性、留出方向可分性。另在已知 ERP 模板上注入漂移、眨眼样脉冲和噪声，测信号恢复误差与峰时偏差。真实数据的形状保留只能间接支持，不能报告虚构的真实 SNR 提升。只有三个额区 EEG 时，ICA 成分分离和空间插值缺少足够约束；[C06](https://pubmed.ncbi.nlm.nih.gov/28645840/)、[C13](https://pubmed.ncbi.nlm.nih.gov/31103785/)可启发阈值设计，不宜整套照搬。

### 3.2 神经生成层保持低维、可辨识

生理路径采用“视网膜→LGN→枕叶视觉皮层→高级视觉/额叶网络→头皮混合观测”的简化图。题面中对额叶的直接投射表述应作为简化描述理解，不能省掉视觉皮层后声称建立了解剖真实路径。形状输入可用有向边缘、尖角布局及左右镜像编码；[C08](https://pubmed.ncbi.nlm.nih.gov/25126068/)支持形状特征排列的计算启发，但不是本实验真实神经元位置的测量依据。

取 2–3 个功能群，使用 Wilson–Cowan 方程族：

```math
τE dE/dt = -E + (1-E)σ(wEE E-wEI I + B u(t)),
τI dI/dt = -I + (1-I)σ(wIE E-wII I),
y(t) = H z(t) + b(t) + ε(t).
```

u(t) 为左右形状及任务信息，z 汇集神经群状态或突触响应，H 是三电极的低维混合矩阵。[C02](https://pubmed.ncbi.nlm.nih.gov/4332108/)给出兴奋—抑制建模基础。H 的自由度须受限；对状态尺度设约束，固定部分时间常数并共享左右条件参数，仅让少数输入增益/耦合随条件变化。否则 H 与状态幅值可互相补偿，拟合漂亮却不可辨识。

优化采用多起点有界拟合，损失由波形误差、时频摘要和参数正则组成。展示剖面损失、参数相关性及留出误差；多组参数同样解释数据时报告等价范围。三导联不能唯一定位 LGN、海马或具体神经元分布，模型中的脑区名称是功能假设。用 [C12](https://pubmed.ncbi.nlm.nih.gov/41033379/)启发的延迟 VAR 作更简单对照，若复杂机制模型未改善预测，只讨论解释能力与限制。

### 3.3 认知层纳入错误和删失

离线认知分析可截断到 t_response−100 ms，并做 50/100/150 ms 敏感性；无应答试次不能直接丢弃，按下一事件或任务超时作为右删失。若用于真实在线 BCI，不允许知道未来反应时来定义输入窗口，必须另设固定的刺激锁定窗口；两类结果分别报告。

记忆状态 h 与方向证据 x 的简化方案为：

```math
dh/dt = -h/τh + κ v_visual(t),
dx = [β0 + βv v_visual(t) + βh h(t)]dt + σd dW_t,
choice = first boundary hit at ±a .
```

将神经群生成的视觉摘要用于积累漂移率，并允许项目一/二具有不同起始偏置或记忆耦合。反应时分解为积累时间与非决策时间，不把点击耗时全部解释为认知。[C09](https://pubmed.ncbi.nlm.nih.gov/18085991/)仅提供理论框架；题目目标出现时刻若未单独标记，就不能从提示—应答总时差识别真实决策时长，应估计等待/非决策项或报告区间。

[C11](https://www.nature.com/articles/s41586-024-07309-z)可支持“额叶控制与记忆相互作用”的讨论，其颅内证据不能转化为本数据已观测到海马信号的结论。三通道、短窗及 256 Hz 采样也不足以稳健复刻其高频单细胞机制，PAC 只作为有条件的扩展分析。

## 4. 验证、消融与写作结构

泛化需分层：记录内按连续时间块留出，块间留滤波缓冲；记录间整文件留出；只有身份确认后才称“跨被试验证”。同一试次的所有窗口必须在同一折。测试集不参与时窗选择、模板生成、标准化、过采样和超参数搜索。病例研究若未来扩展，必须按患者分组划分。[C10](https://pubmed.ncbi.nlm.nih.gov/38765672/)

分类报告平衡准确率、宏 F1、ROC-AUC及记录级表现，明确置信区间的重采样单位。候选时窗先定义，探索性的逐时间检验按块/试次有效交换范围置换并校正多重比较；小样本不作人群推断。[C16](https://pubmed.ncbi.nlm.nih.gov/17517438/) 行为层比较选择对数损失、反应时分位数和超时概率，不能只比较平均反应时。必做消融是“无记忆状态”“无左右耦合差异”“原始温和滤波/提出去噪”“经验分类/生成模型”“去除应答附近数据”。

建议正文顺序：数据审计与事件定义→形态保留去噪→生成模型与可辨识性→认知行为联合模型→留出检验和敏感性→适用范围。核心图为实验时序、四记录质量概览、三导联左右响应及区间、生成模型结构、预测混淆矩阵、行为分位数图、参数剖面。仅三个测点不绘制貌似高精度的全脑定位图。

## 5. 48–72 小时执行顺序与备选创新

0–12 小时完成事件核验、身份/单位检查、预处理日志和基线；12–28 小时完成两种降噪及保形评价；28–44 小时完成受限神经群拟合与线性模型比较；44–60 小时完成认知模型、错误和超时处理；60–72 小时冻结测试、完成消融和论文图表。若事件匹配无法可靠恢复，优先完成刺激锁定分析，并说明认知反应时分析不可辨识。

创新优先级：一是将形态保留、方向可分性和生成一致性作为共同选择准则；二是把认知错误与漏答纳入模型；三是用参数剖面展示哪些机制可被三导联区分。EEGNet [C14](https://pubmed.ncbi.nlm.nih.gov/29932424/)仅作补充基线，避免用复杂网络掩盖低样本问题。近期去伪影研究 [C17](https://pubmed.ncbi.nlm.nih.gov/39250958/)提示预处理收益须实测，并不意味着应保留眼动来提高分数。

## 6. 经核查文献

C01–C10 为优先核心，C11–C17 为补充；其中 2024–2025 年文献四篇。以下核查仅保证书目、公开页面内容和用途匹配，不宣称所有全文均已阅读。机器可读记录见 [C题_文献.json](./C题_文献.json)。

- **C01** Katharina Glomb; Joana Cabral; Anna Cattani; Alberto Mazzoni; Ashish Raj; Benedetta Franceschiello (2022). [Computational Models in Electroencephalography](https://pubmed.ncbi.nlm.nih.gov/33779888/). *Brain Topography 35:142–161*. DOI: 10.1007/s10548-021-00828-2。用途：核心；问题2–3：微观、神经群及头皮观测模型的分层框架；限制宏观信号的机制解释。核查：论文摘要页（PubMed及作者机构库）。

- **C02** Hugh R. Wilson; Jack D. Cowan (1972). [Excitatory and inhibitory interactions in localized populations of model neurons](https://pubmed.ncbi.nlm.nih.gov/4332108/). *Biophysical Journal 12(1):1–24*. DOI: 10.1016/S0006-3495(72)86068-5。用途：核心；问题2：低维兴奋—抑制神经群动力学，可作刺激驱动模型。核查：论文摘要页（PubMed）。

- **C03** B. H. Jansen; G. Zouridakis; M. E. Brandt (1993). [A neurophysiologically-based mathematical model of flash visual evoked potentials](https://pubmed.ncbi.nlm.nih.gov/8452897/). *Biological Cybernetics 68(3):275–283*. DOI: 10.1007/BF00224863。用途：核心；问题2：脉冲输入到视觉诱发电位的生理启发建模。核查：论文摘要页（PubMed）。

- **C04** John Polich (2007). [Updating P300: an integrative theory of P3a and P3b](https://pubmed.ncbi.nlm.nih.gov/17573239/). *Clinical Neurophysiology 118(10):2128–2148*. DOI: 10.1016/j.clinph.2007.04.019。用途：核心；问题1–3：P3a/P3b和注意、记忆的联系；前额三电极不等同中央顶区P3b。核查：论文摘要页（PubMed）。

- **C05** Andreas Widmann; Erich Schröger (2012). [Filter effects and filter artifacts in the analysis of electrophysiological data](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2012.00233/full). *Frontiers in Psychology 3:233*. DOI: 10.3389/fpsyg.2012.00233。用途：核心；问题1：滤波形态和潜伏期失真，需报告滤波器及验证边缘效应。核查：论文页面及图注（PubMed/出版社），未通读全文。

- **C06** Mainak Jas; Denis A. Engemann; Yousra Bekhti; Federico Raimondo; Alexandre Gramfort (2017). [Autoreject: Automated artifact rejection for MEG and EEG data](https://pubmed.ncbi.nlm.nih.gov/28645840/). *NeuroImage 159:417–429*. DOI: 10.1016/j.neuroimage.2017.06.030。用途：核心；问题1：训练折内选择坏试次阈值；三通道情况下不照搬多通道空间插值。核查：论文摘要页（PubMed及作者arXiv）。

- **C07** Bertrand Rivet; Antoine Souloumiac; Virginie Attina; Guillaume Gibert (2009). [xDAWN algorithm to enhance evoked potentials: application to brain-computer interface](https://pubmed.ncbi.nlm.nih.gov/19174332/). *IEEE Transactions on Biomedical Engineering 56(8):2035–2043*. DOI: 10.1109/TBME.2009.2012869。用途：核心；问题1–2：ERP空间滤波对照；仅训练数据估计，三通道限制子空间维数。核查：论文摘要页（PubMed）。

- **C08** George Azzopardi; Nicolai Petkov (2014). [Ventral-stream-like shape representation: from pixel intensity values to trainable object-selective COSFIRE models](https://pubmed.ncbi.nlm.nih.gov/25126068/). *Frontiers in Computational Neuroscience 8:80*. DOI: 10.3389/fncom.2014.00080。用途：核心；问题2：边缘排列和形状选择性刺激编码，不作为重建真实神经元分布证据。核查：论文摘要页（PubMed）。

- **C09** Roger Ratcliff; Gail McKoon (2008). [The diffusion decision model: theory and data for two-choice decision tasks](https://pubmed.ncbi.nlm.nih.gov/18085991/). *Neural Computation 20(4):873–922*. DOI: 10.1162/neco.2008.12-06-420。用途：核心；问题3：将行为选择、反应时及错误响应联结为积累至阈值模型。核查：论文摘要页（PubMed）。

- **C10** Geoffrey Brookshire; Jake Kasper; Nicholas M. Blauch; Yunan Charles Wu; Ryan Glatt; David A. Merrill; Spencer Gerrol; Keith J. Yoder; Colin Quirk; Ché Lucero (2024). [Data leakage in deep learning studies of translational EEG](https://pubmed.ncbi.nlm.nih.gov/38765672/). *Frontiers in Neuroscience 18:1373515*. DOI: 10.3389/fnins.2024.1373515。用途：核心；全部问题：避免同被试、同记录相邻片段跨训练测试造成的性能虚高。核查：论文摘要页（PubMed），已打开。

- **C11** Jonathan Daume; Jan Kamiński; Andrea G. P. Schjetnan; Yousef Salimpour; Umais Khan; Michael Kyzar; Chrystal M. Reed; William S. Anderson; Taufik A. Valiante; Adam N. Mamelak; Ueli Rutishauser (2024). [Control of working memory by phase–amplitude coupling of human hippocampal neurons](https://www.nature.com/articles/s41586-024-07309-z). *Nature 629:393–401*. DOI: 10.1038/s41586-024-07309-z。用途：补充；问题3：海马—额叶耦合机制启发；颅内单细胞/LFP证据不能当作三导头皮EEG定位证据。核查：出版社全文页面（核查摘要、主要结果与方法片段，未通读全文）。

- **C12** Mariia Steeghs-Turchina; Ramesh Srinivasan; Paul L. Nunez; Michael D. Nunez (2025). [Slow wave dynamics of scalp EEG can be explained by simple statistical models of long-range connections](https://pubmed.ncbi.nlm.nih.gov/41033379/). *NeuroImage 321:121418*. DOI: 10.1016/j.neuroimage.2025.121418。用途：补充；问题2–3：延迟VAR的低参数宏观基线；原研究静息态不能直接证明任务态认知机制。核查：论文摘要页（PubMed）。

- **C13** Luca Pion-Tonachini; Ken Kreutz-Delgado; Scott Makeig (2019). [ICLabel: An automated electroencephalographic independent component classifier, dataset, and website](https://pubmed.ncbi.nlm.nih.gov/31103785/). *NeuroImage 198:181–197*. DOI: 10.1016/j.neuroimage.2019.05.026。用途：补充；问题1：说明ICA自动成分判别的条件，作为不宜直接套用到3导联的对照。核查：论文摘要页（PubMed）。

- **C14** Vernon J. Lawhern; Amelia J. Solon; Nicholas R. Waytowich; Stephen M. Gordon; Chou P. Hung; Brent J. Lance (2018). [EEGNet: a compact convolutional neural network for EEG-based brain-computer interfaces](https://pubmed.ncbi.nlm.nih.gov/29932424/). *Journal of Neural Engineering 15(5):056013*. DOI: 10.1088/1741-2552/aace8c。用途：补充；问题2：轻量神经网络预测基线，不能替代题目要求的生理计算模型。核查：论文摘要页（PubMed）。

- **C15** Alexandre Gramfort; Martin Luessi; Eric Larson; Denis A. Engemann; Daniel Strohmeier; Christian Brodbeck; Roman Goj; Mainak Jas; Teon Brooks; Lauri Parkkonen; Matti Hämäläinen (2013). [MEG and EEG data analysis with MNE-Python](https://pubmed.ncbi.nlm.nih.gov/24431986/). *Frontiers in Neuroscience 7:267*. DOI: 10.3389/fnins.2013.00267。用途：补充；问题1：事件、分段和滤波的可复现工具链；软件版本需另外固定。核查：论文书目页（PubMed）。

- **C16** Eric Maris; Robert Oostenveld (2007). [Nonparametric statistical testing of EEG- and MEG-data](https://pubmed.ncbi.nlm.nih.gov/17517438/). *Journal of Neuroscience Methods 164(1):177–190*. DOI: 10.1016/j.jneumeth.2007.03.024。用途：补充；问题1–3：多时间点比较的置换检验，须尊重试次/记录的交换性。核查：论文摘要页（PubMed）。

- **C17** Taeho Kang; Yiyu Chen; Christian Wallraven (2024). [I see artifacts: ICA-based EEG artifact removal does not improve deep network decoding across three BCI tasks](https://pubmed.ncbi.nlm.nih.gov/39250958/). *Journal of Neural Engineering 21(6)*. DOI: 10.1088/1741-2552/ad788e。用途：补充；问题1–2：去伪影不保证提升解码，形态保留和泛化须分别评估；非本数据结果。核查：论文摘要页（PubMed）。
