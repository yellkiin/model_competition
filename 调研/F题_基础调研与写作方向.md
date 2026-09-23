# F题：算力约束下大语言模型资源配置——基础调研与写作方向

> 核验日期：2026-09-23。这是资料梳理与备选研究路线，不是可直接提交的竞赛论文。题面明确AI只能辅助概念理解、资料整理与代码调试；核心模型、推导、论证须由参赛队独立完成并核验，论文末尾须披露AI使用。本次没有拟合标度律、求出最优配置或制造预测结果。

## 1. 研究定位与已核实的数据事实

四问连接的是“质量/配比定义—广义损失模型—预算约束优化—能力前沿预测”。适合统计建模、优化和数据工程较强的队伍，无须真正训练大模型。难点在来源可比性和识别条件：给不同文件起同一个Loss或Q列名，不会自动使它们可比较。

本次对解压后的CSV、JSONL和逐任务JSON做了只读统计，详情见 [附件审计](EF_附件审计.json)。

| 数据 | 实际核验 | 研究意义 |
|---|---|---|
| A1/A2/A3质量信号 | 51,230 / 17,523 / 203,752条，总272,505；A2为arxiv、A3为github扩展 | 必须全部处理；不能以抽样分数冒充扩展集结果 |
| RegMix配方表 | 训练512组；1M/60M检验各256组、1B检验64组 | 配比17域，但Loss表只有13个域级目标；用index成对连接 |
| B1 Pythia日志 | 1176条；N、D字段单位为十亿 | 同run检查点相关，随机拆行会造成验证泄漏 |
| B2/B3 | Cerebras日志1029条，来源注明半合成；8份Pythia轨迹为插值 | 必须使用但不能包装成独立真实族外验证 |
| B4/B5、B6–B8 | 57跨族收敛点/44文献点；质量补充360/450/1704点 | 前两者须核对验证语料；后三者为半合成或含外推 |
| C5/C6桥接表 | 43/75条，各仅7条High，其余36/68条Medium | 不能把75条一律当同尺度Loss—能力真实配对 |
| C7架构表 | 45行，上下文取值2048、4096、8192、32768、131072 | 问题3从这些实际取值作外生敏感性分析 |
| C8逐任务结果 | 1863模型目录、1958 JSON，严格解析失败5个 | 记录失败路径并隔离，不能静默修补或当作零分 |

A1的book只有171条，arxiv 1419条，其他域约9640–10000条；域均值与整体均值必须报告加权口径。A2/A3无content，只能在A1原文中人工核验质量解释，再检查结论在扩展信号上的稳定性。扩展与抽样可能重复，应按id审计，分别展示全记录计数、去重后计数和域级结果，不能把重复样本当新增独立证据。

两项来源风险已经确认：题面将RegMix写成“Xia等、ICML 2024”，原文实际为Qian Liu等、2024预印本/ICLR 2025 [F04](https://openreview.net/pdf?id=5BjQOUXq7i)；《数据说明》部分重复段落声称无需统一指标方向、给出未经复现的R²和最优配置，与题面及统计定义冲突。本报告只采用可核验的数据结构和任务要求，不采用这些现成结论。文档称4个坏JSON，实际严格解析有5个，按磁盘结果留痕。

## 2. 四问的模型与输出对应

| 小问 | 可交付基线 | 主路线建议 | 关键输出 |
|---|---|---|---|
| 一 质量与配比 | 同向化等权Q；17域约束回归 | 分组质量评分+冲突惩罚；对数比正则回归与非线性模型对照 | 272,505条处理日志、域Q对照、冲突案例、13域Loss预测及配比影响 |
| 二 广义标度律 | B1上非线性拟合E+A N^-α+B D^-β | 来源/模型族分层，质量有效数据量与中心化配比项 | 参数区间、跨族/插值/半合成分层验证、边际效用和替代条件 |
| 三 预算优化 | 固定Q、p的N-D优化 | 三种质量成本下联合N、D、Q、p；上下文外生扫描 | 至少三数量级预算最优表、成本份额、敏感性和是否存在结构转移 |
| 四 演进与预测 | 分族能力-规模-时间回归 | 高可比桥接+多任务潜变量/分位数前沿，情景预测 | C8逐任务聚合、贡献分解、12/24个月前沿区间及口径说明 |

建议论文题名：“数据可信度分层下的大语言模型质量—规模替代与资源配置”。主要贡献应是可验证的跨源整合和稳健决策，而非堆叠多个复杂算法。

## 3. 问题一：先定义可比较的Q，再解释配方

质量字段列表中可能是分类logits，而非可以直接求均值的多次评分。应参照数据卡与Meta-rater说明，确认类别次序后用softmax得到概率，再计算归一化期望等级；单元素列表直接取该值，不能用同一函数粗暴平均所有列表 [F05](https://arxiv.org/abs/2504.14194)、[F22](https://huggingface.co/datasets/opendatalab/SlimPajama-Meta-rater/blob/main/README.md)。原始数据卡描述25维，而赛题实际选取22维，以实际字段为准。

先形成“指标—含义—方向—单位—压缩规则”字典：教育价值/可读性为收益型，广告与过度重复为成本型；词长、文本长度、熵等不天然越大越好，若设目标区间，需说明领域依据和敏感性。固定缩放器后对A1–A3使用同一映射，避免各域自行Min-Max抹平差异。

可以把指标分成教育/知识、表达、洁净、重复四组。等组权重与相关性降权作为基线；候选冲突量K_i=Σ_(j,k) w_jk |z_ij−z_ik|只对有可解释可比关系的指标对计算，Q_i=clip(Σ_gω_g q_ig−λK_i,0,1)。冲突不必意味着标注错误，例如有教育价值的技术网页也可能夹带广告。挑选高教育高广告、代码高数值字符等原文案例进行盲评，检查冲突规则是否错误惩罚专业文本。λ必须做敏感性检验，不能用单一任意阈值推出“冲突率为0”。

配比满足Σp_i=1。基线可用去掉一个参考域的正则回归，或对数比表示；零配比用小伪计数并测试其影响，使用Aitchison框架说明闭合效应 [F10](https://academic.oup.com/jrsssb/article/44/2/139/7027742)。主模型可比较低阶交互与RegMix式回归，但保持连续Loss目标，不把它离散成高/低类别逃避误差评价。

对13个验证域分别建模并事先固定总损失权重；17训练域和13评测域并不一一对应。域影响应解释为沿单纯形方向e_i−e_j的替代效应，不能把某一p_i增加、其余不变的偏导当可实施操作。A6–A11用于1M/60M/1B分尺度验证；A12–A15只有估算外推性质，展示排序一致性和不确定性，不能宣称10B/70B真实泛化已经证实。A16的direct/near_direct/inferred映射分别赋予可信度，推荐先完成不含Q的配比模型，再把映射Q作为敏感性扩展。

## 4. 问题二：识别条件比公式复杂度更重要

在B1拟合经典加性幂律应使用约束非线性回归或稳健似然：E低于有效损失下界、A/B/α/β为正；先统一N和D单位。直接对整个L取对数后OLS，不能线性化三个相加项。用不同模型规模留一法、时间前推留出与run级bootstrap检验，避免相邻检查点同时进入训练和验证。跨验证语料的Loss不能直接求平均，需来源截距/尺度项或分别报告。

候选广义形式可研究：
L_s=E_s+A_s N^-α+B_s[D·q(Q)]^-β h(p)，q(Q)>0，h(p)>0。
令q(1)=1、h(p_0)=1，可在“Q=1且p=p_0”的参考状态退化为经典式；仅Q=1并不会消除所有配比差异。q可选Q^κ（避开Q=0），h可由第一问的配比预测相对参考配方构造，并用训练数据控制自由度。第二问只接收第一问的Q、p及汇总不确定性，不重复读取A原始文件。

关键假设是不同实验来源的质量作用和配比作用可迁移。A与B没有共同干预实验；Q效应主要靠B6–B8半合成点支撑，因此无法由现有材料独立识别真实世界“质量提高造成多少能力增益”。应分别给出真实数据基线、加入半合成的条件估计、改变半合成权重/生成假设后的区间。A的相对质量分与B的Q_score也不自动同尺度，须说明锚点或秩校准，并将其视作可变假设。B2用于半合成族外压力测试、B3用于插值轨迹检查；真实跨族证据主要检查B4/B5原始出处。百亿以上B9的元信息可核验，B10预估Loss不能成为真实外推证据。

对于可微候选函数，损失弹性应为ε_N=(N/L)∂L/∂N，ε_Q=(Q/L)∂L/∂Q；单纯ΔL/ΔN不是无量纲弹性。若比较“提高质量ΔQ”和“增加参数”产生同等Loss下降，则局部ΔN_equiv≈(L_Q/L_N)ΔQ；若要求提升质量时保持Loss不变并节省参数，则dN/dQ=−L_Q/L_N。ΔQ=0.1较大时应解有限差分等损失方程，而不是直接沿用微分近似。最优的每FLOP收益还要比较−L_x/C_x，不能仅比较弹性大小。

## 5. 问题三：把成本单位和结构转移定义写清

固定L_ctx及预算C，求min L(N,D,Q,p)，约束为
D{(6+ηL_ctx)N+[g(Q)−g(Q_0)]_+}≤C，p∈Δ^16。
N/D使用参数个数和token个数，表中十亿单位须先还原；g的量纲应与每token FLOPs一致。Q_0来自第一问或明确场景，Q<Q_0意味着免费降低质量而非获得负成本，应说明是否限制Q≥Q_0。

如Loss对D严格下降且没有其他D上限，最优点预算取等号，可消去D=C/{(6+ηL_ctx)N+Δg}，减少搜索维度；有数据供给上限或范围约束时，需重新检查预算是否紧。N/Q用网格加局部优化多起点，p采用单纯形投影或softmax参数化；加入配比变化范围时依据已有配方支持域说明，避免优化器跑到完全未经实验验证的角点。

由题给η=2×10^-4，注意力与基础训练开销比为L_ctx/30000，临界长度严格为30000。C7的五个长度对应约0.0683、0.1365、0.2731、1.0923、4.3691；32768与131072场景不能忽略注意力代理开销。它是赛题给定近似，不应宣称是所有Transformer硬件上精确的FLOPs/KV内存公式。

比较指数、幂函数、对数型三个g，预算至少10^19、10^22、10^24 FLOPs。对数型成本边际递减，可能出现边界最优，应允许数据否定预设的“低预算重规模、高预算重质量”叙述。“结构转移”可定义为活跃约束/非零配比集合发生变化，或最优份额对log C的斜率显著改变；用稠密预算网格和参数bootstrap检查稳定性。平滑份额移动不能一律称为相变，若未检出转移，报告未检出也是合法结论。

## 6. 问题四：把统计分解和因果效应区分开

主样本同时使用榜单C1/C2、扩展时间表C3与Epoch C4；严格连接模型名称、基座、版本、参数和日期，人工复核模糊匹配。区分pretrained与chat/finetuned、密集模型与MoE的总参数/激活参数；“开放权重”和“许可证允许研究复现”分别定义，不把权重开放等同完整开源。时间轴优先用可核验发布日期，提交日期只作替代敏感性分析，避免把旧模型新提交当技术跃迁。

必须从C8做至少一个真正的逐任务聚合，例如同版本BBH子任务按任务等权与按样本数加权分别计算，并与C1汇总差异核对。同模型多JSON按版本/时间规则去重；5个解析失败文件保留失败清单，不把缺失分数置零。HELM和评测工具提供口径参考 [F18](https://arxiv.org/abs/2211.09110)、[F21](https://zenodo.org/records/5371629)。

能力可用固定任务等权指数及潜变量指数交叉验证。Loss—Benchmark先在7条High记录上拟合低自由度单调映射，逐模型留一检验；Medium记录仅作分来源加权敏感性，不以其数量稀释尺度误差。Benchmark可能饱和或受阈值影响，不能用100−Loss直接映射 [F08](https://arxiv.org/abs/2405.10938)、[F17](https://proceedings.neurips.cc/paper_files/paper/2023/hash/adc98a266f45005c403b8311ca7e8bd7-Abstract-Conference.html)。

贡献分解可参考带模型族效应、log算力与时间项的能力模型，再用对称反事实/Shapley分解变化量 [F09](https://arxiv.org/abs/2403.05812)。但时间同时代表数据工程、架构、对齐、评测污染和样本选择；没有可辩护的识别设计，时间系数只能叫“条件非规模残差进步”，不能全称算法因果效应。OpenScholar的优势涉及检索库、检索器、推理反馈和专门任务，不能从8B优于另一模型推断“仅训练数据质量造成” [F19](https://www.nature.com/articles/s41586-025-10072-4)。

预测前沿用高分位数曲线或随机前沿，避免直接对月度最高分拟合后无界外推。以附件数据最后可用日期为预测原点，明确12/24个月对应实际日期；不能默认为从2026年9月预测。设置算力缓增/停滞、非规模进步保持/减速情景，区间同时传播质量映射、标度参数、Loss桥接、族效应和时间趋势误差。用滚动回测检验区间覆盖，能力上限不得突破评分制度上界。

## 7. 写作、图表与72小时行动

正文安排：数据来源与可信度—质量/冲突—配比回归—分层标度律—预算优化—桥接与演进—稳健性及局限。推荐主图为数据来源关系图、域质量与冲突热图、跨规模预测残差、N-Q等损失曲线、资源份额随预算变化图、情景前沿扇形图；主表给出强制数据使用矩阵、参数区间、三预算五上下文三成本比较、贡献分解和滚动回测。

0–12小时完成流式全量处理、坏JSON与重复ID审计；12–24小时做等权Q/配比基线及真实B1经典拟合；24–40小时做分层迁移与半合成敏感性；40–54小时预算扫描、边界和KKT/可行性复核；54–66小时C8聚合、能力桥接、时间回测；66–72小时由队员独立复核推导、补齐AI披露和复现说明。

建议消融至少比较等权/分组Q、无冲突/有冲突、无Q/有Q、只真实/加入半合成、只High/全部桥接、分族/不分族、发布日期/提交日期。若时间有限，优先把这些证据做扎实，不再增加未经验证的复杂模型。

## 8. 已核验文献索引

F01–F10为核心阅读，F11–F22为补充。不同版本按实际年份标注：RegMix区分2024预印本和2025正式会议；The Pile按首个预印本提交日期记2020（arXiv编号为2101.00027）。机器可读元数据和核验层级见 [F题文献JSON](F题_文献.json)。仅阅读摘要的文献不能支持原文未披露的实现细节。

- **F01** Jordan Hoffmann; Sebastian Borgeaud; Arthur Mensch; et al. (2022). [Training Compute-Optimal Large Language Models](https://arxiv.org/abs/2203.15556). NeurIPS；arXiv作者版。DOI: 10.48550/arXiv.2203.15556。用途：问题2–3；经典N-D标度律与固定算力最优分配。证据：论文摘要及出版元数据页面；未通读全文。

- **F02** Jared Kaplan; Sam McCandlish; Tom Henighan; et al. (2020). [Scaling Laws for Neural Language Models](https://arxiv.org/abs/2001.08361). arXiv预印本。DOI: 10.48550/arXiv.2001.08361。用途：问题2；经典标度律的经验边界与估计方法。证据：论文摘要及出版元数据页面；未通读全文。

- **F03** Stella Biderman; Hailey Schoelkopf; Quentin Gregory Anthony; et al. (2023). [Pythia: A Suite for Analyzing Large Language Models Across Training and Scaling](https://proceedings.mlr.press/v202/biderman23a.html). ICML / PMLR 202。用途：问题2；主要真实训练轨迹、同族可比性及训练过程依赖。证据：论文摘要及出版元数据页面；未通读全文。

- **F04** Qian Liu; Xiaosen Zheng; Niklas Muennighoff; Guangtao Zeng; Longxu Dou; Tianyu Pang; Jing Jiang; Min Lin (2025). [RegMix: Data Mixture as Regression for Language Model Pre-training](https://openreview.net/pdf?id=5BjQOUXq7i). ICLR 2025（2024预印本）。用途：问题1–2；附件配方实验来源、小模型配比外推；纠正题面署名与会议信息。证据：作者预印本摘要与ICLR官方PDF首页；未通读全文。

- **F05** Xinlin Zhuang; Jiahui Peng; Ren Ma; Yinfan Wang; Tianyi Bai; Xingjian Wei; Jiantao Qiu; Chi Zhang; Ying Qian; Conghui He (2025). [Meta-rater: A Multi-dimensional Data Selection Method for Pre-training Language Models](https://arxiv.org/abs/2504.14194). arXiv预印本。DOI: 10.48550/arXiv.2504.14194。用途：问题1；多维质量评估来源；原库25维与赛题22维应分开。证据：论文摘要及出版元数据页面；未通读全文。

- **F06** Jiasheng Ye; Peiju Liu; Tianxiang Sun; Yunhua Zhou; Jun Zhan; Xipeng Qiu (2024). [Data Mixing Laws: Optimizing Data Mixtures by Predicting Language Modeling Performance](https://arxiv.org/abs/2403.16952). arXiv预印本；后发表于ICLR 2025。DOI: 10.48550/arXiv.2403.16952。用途：问题1–2；配比到域级Loss映射，嵌套规模与混合规律。证据：论文摘要及出版元数据页面；未通读全文。

- **F07** Sang Michael Xie; Hieu Pham; Xuanyi Dong; et al. (2023). [DoReMi: Optimizing Data Mixtures Speeds Up Language Model Pretraining](https://arxiv.org/abs/2305.10429). NeurIPS；arXiv作者版。DOI: 10.48550/arXiv.2305.10429。用途：问题1、3；域重加权、稳健配比作为扩展路线。证据：论文摘要及出版元数据页面；未通读全文。

- **F08** Yangjun Ruan; Chris J. Maddison; Tatsunori Hashimoto (2024). [Observational Scaling Laws and the Predictability of Language Model Performance](https://arxiv.org/abs/2405.10938). NeurIPS；arXiv作者版。DOI: 10.48550/arXiv.2405.10938。用途：问题4；多模型族能力潜变量与分族效率，不能替代因果识别。证据：论文摘要及出版元数据页面；未通读全文。

- **F09** Anson Ho; Tamay Besiroglu; Ege Erdil; et al. (2024). [Algorithmic progress in language models](https://arxiv.org/abs/2403.05812). arXiv预印本。DOI: 10.48550/arXiv.2403.05812。用途：问题4；规模与算法进步分解，历史样本范围需保留。证据：论文摘要及出版元数据页面；未通读全文。

- **F10** J. Aitchison (1982). [The Statistical Analysis of Compositional Data](https://academic.oup.com/jrsssb/article/44/2/139/7027742). Journal of the Royal Statistical Society: Series B 44(2)。DOI: 10.1111/j.2517-6161.1982.tb01195.x。用途：问题1；17域单纯形、对数比及闭合约束。证据：论文摘要及出版元数据页面；未通读全文。

- **F11** Yasaman Bahri; Ethan Dyer; Jared Kaplan; Jaehoon Lee; Utkarsh Sharma (2024). [Explaining neural scaling laws](https://doi.org/10.1073/pnas.2311878121). PNAS 121(27)。DOI: 10.1073/pnas.2311878121。用途：问题2；经验幂律理论背景，不能把理论指数直接填入附件。证据：论文摘要及出版元数据页面；未通读全文。

- **F12** Niklas Muennighoff; Alexander Rush; Boaz Barak; et al. (2023). [Scaling Data-Constrained Language Models](https://proceedings.neurips.cc/paper_files/paper/2023/hash/9d89448b63ce1e2e8dc7af72c984c196-Abstract-Conference.html). NeurIPS。用途：问题3；独立token与重复训练token区分，数据墙情景。证据：论文摘要及出版元数据页面；未通读全文。

- **F13** Guilherme Penedo; Hynek Kydlíček; Loubna Ben allal; Anton Lozhkov; et al. (2024). [The FineWeb Datasets: Decanting the Web for the Finest Text Data at Scale](https://arxiv.org/abs/2406.17557). NeurIPS Datasets and Benchmarks；arXiv作者版。DOI: 10.48550/arXiv.2406.17557。用途：问题1；教育价值、过滤和质量指标的任务相关性。证据：论文摘要及出版元数据页面；未通读全文。

- **F14** Katherine Lee; Daphne Ippolito; Andrew Nystrom; et al. (2022). [Deduplicating Training Data Makes Language Models Better](https://aclanthology.org/2022.acl-long.577/). ACL。DOI: 10.18653/v1/2022.acl-long.577。用途：问题1、4；重复数据与评测污染、质量不能只看流畅度。证据：论文摘要及出版元数据页面；未通读全文。

- **F15** Nolan Dey; Gurpreet Gosal; Zhiming Chen; et al. (2023). [Cerebras-GPT: Open Compute-Optimal Language Models Trained on the Cerebras Wafer-Scale Cluster](https://arxiv.org/abs/2304.03208). arXiv预印本。DOI: 10.48550/arXiv.2304.03208。用途：问题2；真实模型技术背景；赛题同名轨迹仍为半合成。证据：论文摘要及出版元数据页面；未通读全文。

- **F16** Dirk Groeneveld; Iz Beltagy; Pete Walsh; et al. (2024). [OLMo: Accelerating the Science of Language Models](https://arxiv.org/abs/2402.00838). arXiv作者版。DOI: 10.48550/arXiv.2402.00838。用途：问题2、4；跨族技术差异、开放权重与完整可复现性区别。证据：论文摘要及出版元数据页面；未通读全文。

- **F17** Rylan Schaeffer; Brando Miranda; Sanmi Koyejo (2023). [Are Emergent Abilities of Large Language Models a Mirage?](https://proceedings.neurips.cc/paper_files/paper/2023/hash/adc98a266f45005c403b8311ca7e8bd7-Abstract-Conference.html). NeurIPS。DOI: 10.52202/075280-2425。用途：问题3–4；连续损失、阈值能力与表观突变的区别。证据：论文摘要及出版元数据页面；未通读全文。

- **F18** Percy Liang; Rishi Bommasani; Tony Lee; et al. (2022). [Holistic Evaluation of Language Models](https://arxiv.org/abs/2211.09110). arXiv预印本（后续TMLR版本另核）。DOI: 10.48550/arXiv.2211.09110。用途：问题4；综合能力须固定多任务口径与评测协议。证据：论文摘要及出版元数据页面；未通读全文。

- **F19** Akari Asai; Jacqueline He; Rulin Shao; et al. (2026). [Synthesizing scientific literature with retrieval-augmented language models](https://www.nature.com/articles/s41586-025-10072-4). Nature 650, 857–863。DOI: 10.1038/s41586-025-10072-4。用途：背景、问题4；OpenScholar特定检索增强任务，不能归因为预训练质量单因素。证据：Nature出版页面、摘要及正文相关段落；非全文逐节阅读。

- **F20** Leo Gao; Stella Biderman; Sid Black; et al. (2020). [The Pile: An 800GB Dataset of Diverse Text for Language Modeling](https://arxiv.org/abs/2101.00027). arXiv预印本（首次提交2020-12-31）。DOI: 10.48550/arXiv.2101.00027。用途：问题1–2；原始22子域与赛题17配方域、13损失域区别。证据：论文摘要及出版元数据页面；未通读全文。

- **F21** Leo Gao; Jonathan Tow; Stella Biderman; et al. (2021). [A framework for few-shot language model evaluation](https://zenodo.org/records/5371629). Zenodo v0.0.1 / EleutherAI。DOI: 10.5281/zenodo.5371629。用途：问题4；逐任务指标、few-shot设置及评测版本追踪。证据：官方软件归档/数据卡页面。

- **F22** OpenDataLab (2025). [Annotated SlimPajama Dataset (SlimPajama-Meta-rater)](https://huggingface.co/datasets/opendatalab/SlimPajama-Meta-rater/blob/main/README.md). 官方数据卡。用途：问题1；列表质量信号语义、来源域与附件字段核对。证据：官方软件归档/数据卡页面。
