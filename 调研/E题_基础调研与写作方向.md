# E题：复杂场景下多模态情感预测——基础调研与写作方向

> 核验日期：2026-09-23。本文是选题与研究准备材料，不是完成后的竞赛论文；下面的模型组合、图表和验证均为待实施方案，不包含虚构的性能结果。书目以出版机构、作者预印本或官方项目页核验，未把摘要阅读标为全文阅读。

## 1. 题目究竟要求完成什么

本题的重点依次是“特征可追溯—局部缺失鲁棒性—解释可复核”。问题1处理附件1的全部100条原视频；问题2、3必须使用附件2训练集学习参数、验证集选超参数；附件3、4只用于最后推理。外部情感数据不能用于训练、微调、阈值优化或结果统计，开源预训练特征提取器可以使用并须注明版本。原始MOSEI文献 [E01](https://aclanthology.org/P18-1208/) 提供研究背景，不能用其完整数据集的规模和性能替代本题子集。

本次对解压目录和对齐PKL进行只读核验：

| 附件 | 实际内容与研究边界 |
|---|---|
| 1 | 100个MP4和1个标注XLSX；题面给定37个video_id、时长2.648–34.567秒；100条必须完整保留 |
| 2 | aligned_50.pkl、unaligned_50.pkl及label.xlsx；已核实对齐版本train/valid/test为3395/728/727，总4850条 |
| 3 | 全60个PKL已展开核验：对齐/未对齐各30条，每文件1条；两套字段存在明显差异，见下文 |
| 4 | 对齐/未对齐各20个PKL和20个MP4；同一内容的不同特征版本不能算独立样本 |
| 对齐特征 | text为N×50×768，audio为N×50×74，vision为N×50×35；text_bert是N×3×50整数输入，不能算第四模态 |

对齐版本三个划分之间，完整id及按`$_$`拆出的video_id交集均为0；这尚不能证明说话人完全独立。未直接提供说话人身份时，应明确“已检查视频级重叠，人物级泄漏尚不能彻底排除”。已逐类核实0/1/2对应负/零/正连续标签；训练集计数为967/758/1670。审计见 [特征结构记录](E_特征结构审计.json) 和 [附件记录](EF_附件审计.json)。

**实际接口与题面概述不同：** 附件3对齐版本只有test下的audio、vision和text_bert，没有预计算text和id；未对齐版本只有audio、vision和raw_text，没有text、text_bert或有效长度字段。因此建议主线选对齐版本，在附件2、3、4统一从text_bert编码文本，样本编号保留原文件名。必须先打通专项接口再训练；不能训练只接受768维text的模型后假定测试特征自然存在。未对齐版本须额外核对文本缺失表达方式与长度规则，暂作备选。

## 2. 小问—模型—交付物

| 小问 | 最小可行基线 | 建议主路线 | 必交输出 |
|---|---|---|---|
| 1 特征/对齐 | BERT文本、声学低层特征、OpenFace视觉；词区间池化 | 统一毫秒时间轴，词元—单词—时间段映射，三类掩码与异常日志 | 全100条特征、索引、有效长度、时间戳、汇总表和典型样本 |
| 2 局部缺失 | 对齐版本、统一text_bert编码、掩码均值池化+小MLP | 小型时序编码+可靠性门控+连续块遮挡训练；必要时加入完整教师一致性 | 极性、强度CSV，缺失类型/位置/长度实验与误差分析 |
| 3 解释 | 逐模态遮挡对预测的影响 | 三模态Shapley+每一模态内积分梯度/片段删除，回看原素材 | 极性、强度、主模态、三模态作用程度、三模态各自关键片段和解释卡 |

第一问推荐优先保证时序可核验，不追求叠加多个大型编码器。文本用提供的转写，MFA获得词时间戳 [E07](https://www.isca-archive.org/interspeech_2017/mcauliffe17_interspeech.html)；声学记录采样率、帧长/步长、响度及韵律；视觉保存帧时间、AU、头姿和检测置信度。eGeMAPS与OpenFace可作为可解释特征参考，但不能声称它们天然等于附件2的74维/35维，题面已明确74维不作逐维物理假定。

设第k个词覆盖区间I_k=[a_k,b_k]，某模态第j帧覆盖J_j；用重叠时长w_kj=|I_k∩J_j|作加权池化：x̄_k=Σ_j w_kj x_j/Σ_j w_kj。分母为0时记录无观测掩码，而非悄悄填成有效零特征。子词合并、静音、超50词截断、帧率变动、未检出人脸均写清规则；保存未截断长度和截断覆盖率。至少抽查开头、结尾及语义转折处的同步误差。

## 3. 优先完成的论文主线

建议题名：“基于连续缺失增强与分层证据归因的多模态情感预测”。它可以把三问串成同一套数据规范与验证框架，避免三种互不兼容的大网络。

**问题2的核心改动应针对连续局部缺失。** 整模态缺失论文可以提供蒸馏或表示约束，但直接复现其测试协议不能回答本题。MissModal、P-RMF与CMAD分别支持表示一致性、代理模态和教师学生路线 [E03](https://aclanthology.org/2023.tacl-1.94/)、[E04](https://aclanthology.org/2025.acl-long.1075/)、[E05](https://openaccess.thecvf.com/content/ICCV2025/html/Zhuang_CMAD_Correlation-Aware_and_Modalities-Aware_Distillation_for_Multimodal_Sentiment_Analysis_with_ICCV_2025_paper.html)。比赛时间内先实现其中一个思想。

定义有效掩码P_mt、缺失掩码M_mt与观测掩码O_mt=P_mt(1−M_mt)。P区分填充；M区分真实局部缺失；全零连续段只是检测候选，须结合有效长度和特征规范排除填充/合法零值。输入编码器显式拼接O与相对时间。每个模态池化得到h_m，门控权重g_m=softmax(s(h_m,r_m))，r_m包含可观测比例及连续缺失长度，再融合z=Σg_mh_m。应阻断缺失位置的注意力，并处理所有位置不可用时的回退路径。

训练损失可比较“Huber回归+三分类交叉熵”与其增加一致性项的版本：
L=L_reg+λ_c L_CE+λ_d||z_complete−z_masked||²。
三分类头单独预测中性，回归限制至[-3,3]；若使用回归阈值划分三类，阈值只能在验证集确定，真实标签0仍只属于中性。主实验保持模型规模和优化预算相近。完整输入教师只读取训练样本，专项测试标签和真实完整缺失段均不可进入训练。

文本编码前须识别text_bert中实际缺失与padding规则，并在编码后继续屏蔽原本缺失的位置，避免Transformer利用上下文产生非零向量后被误认为真实观测。若不同版本保留的raw_text更完整，也不能跨版本拼接恢复被屏蔽信息。文本编码器、词表与词元编号必须一致；可用冻结BERT缓存所有合法输入特征，或以仅在训练集学习的小型词嵌入作轻量基线。两者都应在训练和专项测试保持同一接口。

**问题3采用“模态层—时间层”两级解释。** 仅有门控权重或注意力热图不能证明解释忠实 [E10](https://aclanthology.org/N19-1357/)。三模态只有8种子集，可在明确遮挡基线后计算模态Shapley贡献；分别解释回归输出和预测类别logit，保留带符号贡献，另输出归一化绝对贡献作为“作用程度”。同一模态对正向和负向贡献不可混在一张无符号图中。

在文本、语音、视觉三个模态内分别计算积分梯度 [E08](https://proceedings.mlr.press/v70/sundararajan17a.html) 并聚合成连续证据段，输出各自的关键文本、音频时段和视觉帧段；即使作用较弱，也应保留该模态的证据及贡献值，不能只解释主模态。主模态再提供更细的局部重要性可视化。用删除各模态高贡献片段后输出变化、只保留证据段后的预测变化验证解释。遮挡产生分布外输入时，采用训练期同样使用的掩码标记/模态基线，同时测试均值基线的敏感性，避免把遮挡伪影当成重要性。

附件4的抽查PKL提供特征及文本但无直接逐词时间戳；“第17个位置”不能自动换算为“视频第17/50处”。需要对配套视频和文本重新建立时间映射，核验词元化、截断和原特征组织；映射未能唯一确认时，明确报告位置区间与定位误差，不能生成伪精确秒数。问题1建立的映射规范可在这里复用。

## 4. 验证、消融与创新边界

固定官方划分，训练集内拟合标准化参数；验证集选择结构与阈值，附件2测试集在方案冻结后作独立复核，附件3、4无标签不能报告真实准确率。建议3个随机种子，并按video_id分组bootstrap构建区间，避免把同视频片段当独立重复。

| 对照维度 | 实验设计 | 解释目的 |
|---|---|---|
| 模态 | T/A/V、两两组合、三模态 | 判断提升是否只是文本独占 |
| 缺失 | 单/双模态局部缺失；0%、10%、30%、50%有效时长 | 画MAE和macro-F1退化曲线 |
| 位置/长度 | 开头/中部/末尾；等缺失率但短碎片/长连续块 | 区分缺失总量与连续结构效应 |
| 组件 | 去门控、去连续块增强、去一致性项 | 证明主创新独立贡献 |
| 解释 | 重要片段/随机片段/低贡献片段删除；参数随机化 | 检验忠实性而非热图美观 |
| 资源 | 参数量、特征耗时、推理耗时、保存大小 | 证明方案可复现并满足附件限制 |

分类同时报告Accuracy、macro-F1、各类召回率与混淆矩阵；回归报告MAE、Pearson及按真实极性分层误差；Pearson在预测常数时应标为未定义。公平性优先检查视频质量、片长、缺失率、情感类别等已知组；没有可靠人口属性标注，不能从外貌猜测性别/族裔再声称完成群体公平评估。英语视频语境与人群局限要诚实保留。

创新备选仅挑一个：质量/不确定性门控、连续缺失位置鲁棒性正则、归因一致性约束。复杂扩散补全、多个大型预训练模型联合微调风险较大，在4850条子集上必须先证明收益。MISA、MulT与低秩融合适合做结构对照 [E02](https://aclanthology.org/P19-1656/)、[E12](https://aclanthology.org/P18-1209/)、[E13](https://arxiv.org/abs/2005.03545)。

## 5. 写作与72小时安排

正文依次安排：题意/符号—数据及泄漏审计—特征提取和时间对齐—缺失预测—分层解释—实验/消融—局限和复现。主图建议为全流程图、单样本三模态时间轴、缺失类型×缺失率热图、预测误差分布、三模态贡献图、证据删除曲线；主表包括100条特征全量汇总、模型资源与性能、消融、两专项输出字段表。

0–12小时完成数据接口、掩码和5条视频全链路；12–24小时完成100条提取及轻量基线；24–42小时完成一个主模型和预注册缺失网格；42–56小时做消融和解释；56–72小时冻结参数、专项推理、核查CSV覆盖率和打包复现。时间不足时优先保全100条特征与规范输出，减少网络分支。

官方提交附件上限50MB，而本地原始包约4GB，两者用途不同。可考虑冻结编码器、缓存压缩特征、保存小型融合模型；先估算文件体积，再检查所需权重是否真的齐全，不能用下载大模型的说明替代题目要求的核心参数。所有参赛文件匿名，原始赛题数据保持本地完整；仓库中的文献和调研不等同于最终参赛附件。

## 6. 已核验文献索引

核心阅读E01–E10，补充阅读E11–E20；“用途”为本题建议，并非原文已验证本题数据有效。2025年的P-RMF、CMAD、EMOE补足近期研究。正文没有直接采用尚未逐条核实的题面2026文献。机器可读记录含DOI、核验层级与日期，见 [E题文献JSON](E题_文献.json)。

- **E01** AmirAli Bagher Zadeh; Paul Pu Liang; Soujanya Poria; Erik Cambria; Louis-Philippe Morency (2018). [Multimodal Language Analysis in the Wild: CMU-MOSEI Dataset and Interpretable Dynamic Fusion Graph](https://aclanthology.org/P18-1208/). ACL。DOI: 10.18653/v1/P18-1208。用途：问题1–3；原始数据定义与动态融合图，赛题子集不可等同完整MOSEI。证据：论文摘要/出版元数据页面；未通读全文。

- **E02** Yao-Hung Hubert Tsai; Shaojie Bai; Paul Pu Liang; et al. (2019). [Multimodal Transformer for Unaligned Multimodal Language Sequences](https://aclanthology.org/P19-1656/). ACL。DOI: 10.18653/v1/P19-1656。用途：问题1–2；跨模态注意力与非对齐时序对照。证据：论文摘要/出版元数据页面；未通读全文。

- **E03** Ronghao Lin; Haifeng Hu (2023). [MissModal: Increasing Robustness to Missing Modality in Multimodal Sentiment Analysis](https://aclanthology.org/2023.tacl-1.94/). TACL。DOI: 10.1162/tacl_a_00628。用途：问题2；完整/缺失表示一致性，需改为连续局部缺失。证据：论文摘要/出版元数据页面；未通读全文。

- **E04** Aoqiang Zhu; Min Hu; Xiaohua Wang; Jiaoyun Yang; Yiming Tang; Ning An (2025). [Proxy-Driven Robust Multimodal Sentiment Analysis with Incomplete Data](https://aclanthology.org/2025.acl-long.1075/). ACL。DOI: 10.18653/v1/2025.acl-long.1075。用途：问题2；代理模态、缺失不确定性与随机不完整序列。证据：论文摘要/出版元数据页面；未通读全文。

- **E05** Yan Zhuang; Minhao Liu; Wei Bai; et al. (2025). [CMAD: Correlation-Aware and Modalities-Aware Distillation for Multimodal Sentiment Analysis with Missing Modalities](https://openaccess.thecvf.com/content/ICCV2025/html/Zhuang_CMAD_Correlation-Aware_and_Modalities-Aware_Distillation_for_Multimodal_Sentiment_Analysis_with_ICCV_2025_paper.html). ICCV。用途：问题2；完整教师和缺失学生蒸馏；与局部时间缺失区别。证据：论文摘要/出版元数据页面；未通读全文。

- **E06** Yiyang Fang; Wenke Huang; Guancheng Wan; Kehua Su; Mang Ye (2025). [EMOE: Modality-Specific Enhanced Dynamic Emotion Experts](https://openaccess.thecvf.com/content/CVPR2025/html/Fang_EMOE_Modality-Specific_Enhanced_Dynamic_Emotion_Experts_CVPR_2025_paper.html). CVPR。用途：问题2–3；动态模态权重，权重本身不构成忠实解释。证据：论文摘要/出版元数据页面；未通读全文。

- **E07** Michael McAuliffe; Michaela Socolof; Sarah Mihuc; Michael Wagner; Morgan Sonderegger (2017). [Montreal Forced Aligner: Trainable Text-Speech Alignment Using Kaldi](https://www.isca-archive.org/interspeech_2017/mcauliffe17_interspeech.html). Interspeech。DOI: 10.21437/Interspeech.2017-1386。用途：问题1、3；逐词时间戳及回看原素材。证据：论文摘要/出版元数据页面；未通读全文。

- **E08** Mukund Sundararajan; Ankur Taly; Qiqi Yan (2017). [Axiomatic Attribution for Deep Networks](https://proceedings.mlr.press/v70/sundararajan17a.html). ICML / PMLR 70。用途：问题3；积分梯度定位连续特征中的局部贡献。证据：论文摘要/出版元数据页面；未通读全文。

- **E09** Scott M. Lundberg; Su-In Lee (2017). [A Unified Approach to Interpreting Model Predictions](https://proceedings.neurips.cc/paper/2017/hash/8a20a8621978632d76c43dfd28b67767-Abstract.html). NeurIPS。用途：问题3；三模态作为三个参与者进行Shapley归因。证据：论文摘要/出版元数据页面；未通读全文。

- **E10** Sarthak Jain; Byron C. Wallace (2019). [Attention is not Explanation](https://aclanthology.org/N19-1357/). NAACL。DOI: 10.18653/v1/N19-1357。用途：问题3；注意力热图需以删除/保留实验验证忠实性。证据：论文摘要/出版元数据页面；未通读全文。

- **E11** Amir Zadeh; Minghai Chen; Soujanya Poria; Erik Cambria; Louis-Philippe Morency (2017). [Tensor Fusion Network for Multimodal Sentiment Analysis](https://aclanthology.org/D17-1115/). EMNLP。DOI: 10.18653/v1/D17-1115。用途：问题2；高阶交互参考与模型复杂度对照。证据：论文摘要/出版元数据页面；未通读全文。

- **E12** Zhun Liu; Ying Shen; Varun Bharadhwaj Lakshminarasimhan; et al. (2018). [Efficient Low-rank Multimodal Fusion With Modality-Specific Factors](https://aclanthology.org/P18-1209/). ACL。DOI: 10.18653/v1/P18-1209。用途：问题2；适合小样本及50MB限制的低秩融合基线。证据：论文摘要/出版元数据页面；未通读全文。

- **E13** Devamanyu Hazarika; Roger Zimmermann; Soujanya Poria (2020). [MISA: Modality-Invariant and -Specific Representations for Multimodal Sentiment Analysis](https://arxiv.org/abs/2005.03545). ACM Multimedia；arXiv作者版。DOI: 10.48550/arXiv.2005.03545。用途：问题2；共享/私有表示，作为备选消融路线。证据：论文摘要/出版元数据页面；未通读全文。

- **E14** Jacob Devlin; Ming-Wei Chang; Kenton Lee; Kristina Toutanova (2019). [BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding](https://aclanthology.org/N19-1423/). NAACL。DOI: 10.18653/v1/N19-1423。用途：问题1；文本特征与词元掩码；不将text_bert误算第四模态。证据：论文摘要/出版元数据页面；未通读全文。

- **E15** Florian Eyben; Klaus R. Scherer; Björn W. Schuller; et al. (2016). [The Geneva Minimalistic Acoustic Parameter Set (GeMAPS) for Voice Research and Affective Computing](https://ieeexplore.ieee.org/document/7160715/). IEEE Transactions on Affective Computing 7(2)。DOI: 10.1109/TAFFC.2015.2457417。用途：问题1；可解释韵律特征；不可将eGeMAPS维度强说为附件74维。证据：IEEE官方检索摘要及期卷/DOI元数据；直接打开受访问验证限制。

- **E16** Tadas Baltrušaitis; Amir Zadeh; Yao Chong Lim; Louis-Philippe Morency (2018). [OpenFace 2.0: Facial Behavior Analysis Toolkit](https://github.com/TadasBaltrusaitis/OpenFace). IEEE FG；作者项目页。DOI: 10.1109/FG.2018.00019。用途：问题1；AU、头姿、视线特征和人脸检测置信度。证据：作者官方项目页面及其引用信息；出版页受访问验证限制，未通读全文。

- **E17** Alexei Baevski; Henry Zhou; Abdelrahman Mohamed; Michael Auli (2020). [wav2vec 2.0: A Framework for Self-Supervised Learning of Speech Representations](https://arxiv.org/abs/2006.11477). NeurIPS；arXiv作者版。DOI: 10.48550/arXiv.2006.11477。用途：问题1；冻结语音编码器备选，非必须的大模型路线。证据：论文摘要/出版元数据页面；未通读全文。

- **E18** Julius Adebayo; Justin Gilmer; Michael Muelly; Ian Goodfellow; Moritz Hardt; Been Kim (2018). [Sanity Checks for Saliency Maps](https://arxiv.org/abs/1810.03292). NeurIPS；arXiv作者版。DOI: 10.48550/arXiv.1810.03292。用途：问题3；随机化参数与解释稳定性检查。证据：论文摘要/出版元数据页面；未通读全文。

- **E19** Paul Pu Liang; Yiwei Lyu; Xiang Fan; et al. (2021). [MultiBench: Multiscale Benchmarks for Multimodal Representation Learning](https://arxiv.org/abs/2107.07502). NeurIPS Datasets and Benchmarks；arXiv作者版。DOI: 10.48550/arXiv.2107.07502。用途：问题2；借用鲁棒性与复杂度评价协议，禁止导入额外情感训练数据。证据：论文摘要/出版元数据页面；未通读全文。

- **E20** CMU MultiComp Lab (2026). [CMU-MultimodalSDK](https://github.com/CMU-MultiComp-Lab/CMU-MultimodalSDK). 官方仓库（核验年，持续更新）。用途：问题1；时间区间与对齐数据结构参考，不能替换赛题样本。证据：官方仓库README页面。
