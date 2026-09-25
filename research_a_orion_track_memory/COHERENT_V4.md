# memory-coherent-4.4：结构感知驻留波前与可组合候选

本版是在 memory-frozen-3.0 之后的增量候选源。目标不是替换完整 ORION，而是修复 v3 已暴露的两类内存/边界局部最小：

1. 大量互不相连的小计算组件被全图深度分带后同时“打开”，导致 L1/UB 活跃张量峰值和 Spill 暴涨；
2. 一般连通图中，单条边迁移无法跨过生产者/消费者集合的联合代价，需要以完整 Tensor 端点集合为单位提出迁移。

公共入口 plugin_adaptive_v4.py 继续遵循 PR #24 的 COMMON：propose(g, n, cfg, q, incumbent=None, feedback=None, deadline=None)。

插件不执行官方评估、不改 FIFO/Spill、原图、Tensor、cycles、配置或公共 solver.py/campaign.py。宿主决定候选选择、预算和验收；只有未修改官方评估返回的 (Makespan, added_copy_bytes) 改善才替换 incumbent。

## 1. 图结构特判：private-island micro-wave

这是对 084 反例的修正，按结构触发，不看 case 编号。

触发特征：
- 计算弱连通分量数至少 8；
- 至少 75% 的原计算操作属于大小不超过 32 的小分量；
- 跨分量共享的外部输入 Tensor 字节不足私有输入的 10%。

满足这些特征时，默认禁止全图深度分带。Q2/Q3 可以把一个弱连通分量整体迁到一个核，再按 Pipe 负载做确定性的整分量负载均衡。不同弱连通分量之间没有原计算依赖，因此整体迁核不会制造跨分量数据环。

随后按每个分量的 L1/UB 活跃区间代理估计批宽，提出 1.0/1.5/2.0/2.5 倍包络候选；每个批次再按组件内部拓扑深度切成 2/3 个阶段。批内先执行所有组件的早阶段，再执行后阶段：

- 比“全局按深度打开全部组件”显著减少同时活跃组件；
- 比“一个组件完全跑完才开始下一个”保留更多 Cube/Vector 重叠。

代理峰值只用于候选批宽，不是容量证明。最终容量、Spill 与 Makespan 完全由官方 Step2/Step3 决定。Q1 默认不做整组件迁核，因为同核跨 Task 仍有边界复制与等待，之前实测没有证明收益。

## 2. 一般图：固定核分带 + Tensor 交易

非 private-island 图继续保留 v3 已验证的固定核深度分带：操作核归属不变，按 depth-band / switch-rank / core 重新打包。switch-rank 对同一 band 内每条跨核依赖严格增加，避免 owner re-entry 形成环；每个候选仍调用 plan_view 做完整商图/核顺序检查。

Tensor 交易不逐边计费。一个 Tensor 的生产者/消费者 Task 集合先形成端点集合，再在原数据依赖商图上求有限逻辑凸包；候选最多移动一个完整 hull 到已有端点核。默认 max_hull_groups=10，不会把整张大图改成新全局划分器。

Q1 另外可以提出 producer_downset_split：若某个跨核 Tensor 在一个很长 Task 中很早产生，则把其生产者以及该 Task 内必须的祖先组成一个前缀 Task，尝试让数据更早释放。它不插 delay，也不改 Tensor，只改变 Task 边界。

## 3. 与其他研究线组合

推荐用 plugin_adaptive_v4.make_proposer(Options(...)) 构造候选源。如果结构线已经提供核迁移，可设 allow_core_migration=False，只保留 Task 边界、固定核驻留候选。

插件没有全局缓存、进程、文件输出或预算控制，多个 proposer 可以并列放入同一个候选池。candidate_advice 只给外部候选池一个 private-island 活跃前沿扩大的警告；它不是可行性证书，高峰值候选仍可能通过合法 Spill 获胜。

## 4. 文献依据与迁移边界

本版除了原 A16/A17/A18/A39，又重点读取了文献库中与 084 问题更相关的工作：

- A08 IOS：其核心观察是“全部 ready 操作立即并发”可能造成资源竞争和后续低利用率。对应本版的“有限批次 + 批内阶段交错”。没有移植算子融合，也没有把其设备调度 DP 当成本题多 Pipe 的保证。
- A31 Parallel Scheduling of DAGs under Memory Constraints：提供并行展开宽度与活跃内存峰值之间的分析视角。这里不向原 DAG 写虚拟约束边，也不以逐边内存代替 Tensor 集合与官方峰值。
- A46 Iterative Graph Optimization：隔离/祖先/后继子图的局部变换视角启发有限逻辑凸包。这里只重新组合官方允许的两个方案字段，不融合算子或改变图语义。
- A39：继续作为有向端点集合与无环收缩的理论背景；论文 hyperedge connectivity 不是本题 COPY 精确成本。
- A16 COSMA / A17 SERENITY / A18 HMCOS：继续用于驻留状态、活跃集/局部顺序、峰值相关层级拆解；不移植自由 Spill、graph rewriting 或单内存模型的最优性结论。

## 5. 实测边界

本版结果见 results/coherent_v4_20260925/。主要实测是 warm-start 局部修复，不是同预算全100图冷启动替代实验。父方案采用已保存的 frozen-v3/day01 可行解，旧指标按用户要求直接信任，只评估新增候选。

最重要反例已经被规则吸收：084 Q2 原方案 391,700 周期、零 Spill；v3 全局深度分带产生约 39.9 MB Spill 并恶化到 1,305,922。v4 的容量受控 micro-wave 最终取得 285,686 周期，约下降 27.1%，且最终方案只有少量 Spill。说明目标应是“控制驻留峰值同时保留计算重叠”，而不是单调追求零 Spill。
