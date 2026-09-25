# 实际阅读、实现与适用边界

先读仓库 `调研/A题_文献库/README.md`、`方法对照与阅读顺序.md`，再按 `调研/A题_文献.json` 找原文。本轮通过既有 GitHub 输入 artifact 将 A39/A16/A17/A18 四篇原始 PDF、官方 DOCX、配置与评估器下载到容器的只读参考目录；读取正文，并查看相关页面。没有将论文、原图或官方代码重复提交到本研究目录。

## 本轮核读与代码对应

|原文|核读位置|落到代码的机制|不可迁移的自由度或保证|
|---|---|---|---|
|A39，Multilevel Acyclic Hypergraph Partitioning，ALENEX 2021|PDF第3–5页，商图定义、§3.1–3.2、多head限制|按张量生产/消费集合计费；fixed-owner band与switch-rank防止跨核离开后重新进入同组；每次收缩检查商图/核序列|tail→head；connectivity的λ−1不是本题COPY计费。没有重做n-level全局划分，也不声称复现论文划分器|
|A16，COSMA，2023|PDF第3–4页§III，create/preserve/spill/retrieve与额外I/O目标|驻留状态用于解释边界改变如何影响官方Spill；参数集合触发分带是候选而非合法性判据|不自由选择Spill/retrieve，不优化连续地址，不改变块内原算子语义；其ILP不是A的精确模型|
|A17，SERENITY，MLSys2020|PDF第4–6页，部分顺序、活跃集合与搜索|在固定合法子图集合上做有限顺序窗口；比较分开的L1/UB前沿峰值|不做graph rewriting，不移植单设备内存最优性或其预算控制器；前沿不等于官方物理峰值|
|A18，HMCOS，DAC2022|PDF第2–4页，stable/transient footprint、层级化及算法1–2；本轮另查看第2页定义|粗细边界分解，考察峰值附近的层级展开，而不是只追求少Task|本题没有给定NAS cell；当前dependency-depth epochs不是完整HMCOS。单设备峰值保证不适用于多核Makespan|

A02 的无环构造思想沿用既有 ORION 实现；本轮重点重读上面四篇，没有声称重新精读资料库全部52篇。I/O下界使用原 `core.bounds` 的必要条件：计算路径、分核算力与强制外部访问；未建立新的红蓝卵石强界，不把允许重算的模型套入本题。

## 从文献机制到真实反例

073 的前轮成功说明 preserve/spill 的交换有用，但不能据此把每张差图都归因于溢出。本轮085五核旧方案和新方案均零Spill。Q2固定核分带16阶段保持所有操作核归属与pre-Spill搬运量不变，却使Makespan从1,346,698降至1,129,936周期；随后张量端点局部迁移再降至1,124,776。这里支持的是合法边界/顺序会改变执行依赖与Pipe重叠，而不是“消除了本来不存在的Spill”。

COSMA的额外字节目标不能直接替代本题Makespan。085 Q2从epoch16继续局部迁移时，COPY不与计算重叠的时间并集从5,933升至6,554周期，Makespan却进一步下降。这一单项诊断也不是应被单调优化的目标。新候选最终只按原官方周期比较，搬运仅作平分次级目标。

`convex_coalesce` 内部用shared touched-tensor字节排序是启发式，之前注释称其为精确收益不准确，已修正。完成候选的pre-Spill读/写总量由完整生产者/消费者集合重新计算。内存窗口只表示组边界前沿，不表示官方插入COPY之后的全物理生存区间。

## 原文与赛题定位

- A39： https://arxiv.org/abs/2002.02962 ，原PDF https://arxiv.org/pdf/2002.02962 。
- COSMA： https://arxiv.org/abs/2311.18246 ，原PDF https://arxiv.org/pdf/2311.18246 。
- SERENITY： https://proceedings.mlsys.org/paper_files/paper/2020/file/79c36fe64e04b80fc44845bb9fe73242-Paper.pdf 。
- HMCOS： https://chengcheng-wan.github.io/paper/22-DAC.pdf ，DOI `10.1145/3489517.3530472`。

本地原文路径为仓库 `调研/A题_文献库/pdf/` 下的对应文件。官方DOCX问题1/2正文明确要求1–5核平均加速比曲线；问题3要求相同核数的no-L2/L2对照。详细规则、精确张量计费公式、停止和时间语义见 [FROZEN_RULES.md](FROZEN_RULES.md)。
