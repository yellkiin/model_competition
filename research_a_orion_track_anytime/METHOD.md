# Anytime Wu v4 方法

## 1. 不变的官方语义

唯一真分数是原官方 evaluator 的全局 Makespan。Q3 只在 COPY_IN issue 时查 cache，completion 时 fill；hit 不刷新 FIFO。Cache read 与 DDR 是不同带宽池。代码不增加 delay/sleep、不改 op/cycles/tensor、不改 FIFO/LRU 规则。

## 2. FIFO 候选

`plugin.propose(...)` 只重新排列已有同核子图：

- consumer-window：`cold_inflight/evicted_inflight` 后移消费者，`evicted` 前移消费者；
- fill-advance：从真实 event 找到 `earliest_pending_completion` 对应的先前读取，把填充者已有子图前移；
- evictor-delay：从真实 `last_eviction` 找到实际驱逐该 tensor 的 fill，把驱逐者已有子图后移；
- 少量两核联合候选。

优先级只决定评估顺序，不冒充反事实 Makespan。每个方案仍先经 `plan_view`，然后原 evaluator。

## 3. 结构触发候选

`structural.py` 不看 case ID。tail-rebalance 只有在观测最慢核结束差≥1.5% Makespan，且该核 schedule 长度显著高于中位数时才生成；取最晚5个子图×两个较轻核，再按已有 timing proxy 排序。当前分支还保留并行研究中加入的 private-island micro-wave，仍由结构特征触发且最终必须原评估。

结构流不会在一开始抢占短预算：tail类只有在已有真实改善或常规调用达到门槛后进入。024 的真实失败/修复正是这一准入规则依据。

## 4. 预算与停止

- 候选族首评 + 历史官方/proxy 比值的收缩校准；
- 当前机器评估耗时决定是否还能安全准入；外机 wall-clock 不进入当前速度模型；
- incumbent 改善后丢弃其旧 FIFO/结构/局部邻域，重新锚定；
- 全局 lower-bound gap 保留原语义；
- v4 对大图且 `(U-L)/U<=2.05%` 启用 `certified_near_bound_budget_stop`。这是预算策略，不是最优证明。

059 Q3五核因此保留150,524且0次新增评估；Q2也由全局gap直接停止。

## 5. 安全续优化与冷启动

warm 模式从重新验证的 seed 开始，任何新候选变差都不会替换 incumbent。case_048：15秒 cold old=117,513、cold v4=124,681；把old结果作为真实 incumbent 后，15秒 v4 warm=116,941。

因此v4推荐作为已有ORION/其它合法方案之后的 continuation layer，而不是单独替换 cold constructor。

## 6. 实验口径

本轮新增核心门：七图Q3/五核正式seed暖启动；024 v3/v4 20秒同机等预算；024/044/059 Q1/Q2五核10秒门控；048额外cold负结果和warm recovery；最终七个Q3 plan全部严格相同plan重放Q2/no-L2。

此前PR34的 `ci_primary` 已覆盖七图×Q1/Q2/Q3×2/5核×cold/warm×old/combined，本轮不重复那张完整矩阵；v4只补针对已发现失败模式的定向证据。
