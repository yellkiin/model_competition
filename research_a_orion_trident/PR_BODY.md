## 范围

只新增 `research_a_orion_trident/`，与并行 PR #37 的 `research_a_orion_fusion/` 分开。Trident 将结构 S、内存 M、FIFO/预算 F 接入同一个 incumbent 搜索；不修改原图、config、官方评估器、公共 ORION solver/campaign 或其他研究线。

## 独立审查与整合修正

- S：链/转折/有效核数、局部迁移和窗口。
- M：coherent-v4 的受控微波次、固定核复用分带、Tensor 端点与 producer release。
- F：官方 issue-time lookup / completion-time fill / FIFO eviction 事件候选，并吸收 PR #36 修复的候选保留/排序经验。
- 三源共享同一个已通过官方评估的 incumbent；局部流绑定父 epoch，全局构造流保留游标。
- B 基础覆盖始终存在，避免多来源竞争把已有有效搜索路径挤掉。
- 候选只在未修改官方 evaluator 下改善 (Makespan, added COPY) 时替换 incumbent。

## 本地真实小样本

保存 32 个主实验、17 个精确同方案 Q3/Q2 配对和 1200 次返回 ok 的主官方评估。16 次被接受的 FIFO 变换均核对 mapping/owner 不变。

第一组尚未被前序整合重复覆盖的新核数组合：
- 024 Q2/n2：2,555,343 → **1,334,769**。
- 044 Q1/n4：71,861 → **59,761**。
- 059 Q2/n3：250,929 → **250,622**。
- 083 Q3/n4：229,284 → **224,192**；独立续段继续到 **216,836**。
- 086 Q3/n2：74,136 → **71,128**。
- 084 Q3/n3 保留 458,172；Q2/n2 保留 686,336。

新图 011 完成 14 主配置 + 5 个同方案配对，并对 Q3/n5 依次做 SM/SF/MF，再 S/M/F。结果定位到短预算下的来源竞争；增加受时间约束的基础覆盖后，完整 SMF 从 41,849 改到 40,801，但仍保留正式旧 40,077 作为生产 incumbent。

所有小样本、负结果、轨迹与源码版本分开记账，不跨版本拼成统一成绩。

## 三机正式计划

固定代码分支：`integration/orion-trident-publish-20260925`。三台必须记录并使用同一 HEAD。

- HOST 0：34 图，476 主配置，170 个 Q3/no-L2 配对。
- HOST 1：33 图，462 主配置，165 个配对。
- HOST 2：33 图，462 主配置，165 个配对。

每个配置=(graph,q,n)最多 600 秒，包含启动、解析、种子回放、构造、官方评估、保存和 Q3 精确同方案配对。每 30 秒记录当时已保存的最好合法方案、来源、阶段、调用数和已用时间。外层 workers 自适应到约 75% CPU/RAM 使用目标，NPU 核数与 worker 数完全分离。

若主结果低于已有强 incumbent，诊断按 Q3: SM/SF/MF → 必要时 S/M/F；Q1/Q2: S/M。诊断只使用该配置剩余预算，结果另存 diagnostics，不偷偷把六条臂的最好值拼入固定 SMF 主表。

最终要求 1400 主配置 + 500 个精确同方案 Q3/no-L2 对照，并输出论文所需逐图表、1–5 核均值/分位数、30 秒 anytime 曲线、COPY/Spill/hit、Pipe 利用率、图特征和候选成本/收益。

## 三机提示词与入口

- `HOST_0.md`
- `HOST_1.md`
- `HOST_2.md`
- `PROMPTS.md`
- `run_windows.ps1`
- `publish_results.ps1`

不运行 smoke、pytest/unittest、哈希/指纹或全仓 benchmark；只做启动必要检查与真实官方算例。结果分片各开独立结果 PR，不自动合并。

