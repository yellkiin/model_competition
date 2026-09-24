# 实际阅读与实现边界

先读仓库 `调研/A题_文献库/README.md`、`方法对照与阅读顺序.md`，再核对 `调研/A题_文献.json`。以下原文是方法依据，不是最新 ORION 实验数据，也不把论文效果外推成本题收益。本次没有下载或复制文献到提交目录。

|仓库编号|本次核读原文位置|实际采用|未采用的自由度/保证|
|---|---|---|---|
|A39，Multilevel Acyclic Hypergraph Partitioning，ALENEX 2021|原文 PDF 第3–5页，定义与§3.1–3.2；第5页另作视觉核对|张量生产/消费集合、收缩必须保无环；实施后重新检查商图与核顺序|原文 tail→head；多 head 情况不能套单 head 收缩。没有重做 n-level 全局划分；`lambda-1` 不当 COPY 精确成本|
|A16，COSMA，2023|原文 PDF 第3–4页、§III，状态约束；第3页视觉核对|区分 preserve/spill/retrieve，分析额外 I/O 与驻留的交换|不优化连续地址，不自由决定 Spill，不自由重排块内算子，不把其 ILP 称为本题精确解|
|A17，SERENITY，MLSys 2020|正式 PDF 第4页§3/§3.1及图4–5视觉核对，后续DP段落|已完成集合的重复子问题、局部窗口的峰值 DP|不做 identity graph rewriting，不采用单设备内存最优性保证，也不另写整条预算控制线|
|A18，HMCOS，DAC 2022|作者 PDF 第3页§3.1–3.2文本、第4页算法1–2文本；网页截图未成功，不声称视觉核对|峰值相关分组的局部展开、活跃值及最后一次使用的概念|NAS cell 边界和支配关系分组不是输入自带信息；当前深度分带不是完整复现 HMCOS|
|A02，Acyclic Partitioning of Large DAGs，CCGrid 2017|本地原文模型/无环划分段落|沿用项目既有合法构造与完整结构检查|不重写结构线；顶点权重之和不是 L1/UB 峰值|
|I/O 下界背景|原题共享 DDR 条件与既有 core.bounds 源码|使用已有可证明的必要条件界，明确固定方案界与全局界|没有建立新的红蓝卵石强界，没有把允许重算的模型套入固定图|

## 原文来源

A39：<https://arxiv.org/abs/2002.02962>，PDF <https://arxiv.org/pdf/2002.02962>。

COSMA：<https://arxiv.org/abs/2311.18246>，PDF <https://arxiv.org/pdf/2311.18246>。

SERENITY：<https://proceedings.mlsys.org/paper_files/paper/2020/file/79c36fe64e04b80fc44845bb9fe73242-Paper.pdf>。

HMCOS：<https://chengcheng-wan.github.io/paper/22-DAC.pdf>，DOI `10.1145/3489517.3530472`。

A02：<https://people.bordeaux.inria.fr/julien.herrmann/pub/conf/ccgrid2017.pdf>。

HMCOS 的算法1根据峰值时仍活跃值的定义位置展开相关层级块，再调度；SERENITY 将重复部分调度合并为 DP 子问题。这里的迁移是缩小到已合法子图的局部候选，而非替换官方 Step1/2/3。COSMA 原文显式含创建、保持、换出与取回变量，这些在本题只能用于解释官方产生的流量，不能写成用户可提交的张量置换策略。
