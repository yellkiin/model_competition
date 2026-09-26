# 交付状态

完整源码已重新提交到 PR #59：
https://github.com/yellkiin/model_competition/pull/59

本目录包含 Q3/L2 增量补跑所需的完整源码、三机提示词、Windows入口、结果汇总与本轮实测记录。保留 Trident #38 主体与 Q1/Q2 结果不变，只补 Q3 有 L2；Q3方案改变时才补该方案的同方案 no-L2 对照。

默认策略为 `bank_only`：优先使用两份已发布L2研究中的实际方案库，按当前相同 case/n 的绝对Q3周期筛选；预计改善不足0.1%的配置不新增官方评估。v1强起点方案优先，较差的v2/v3与topo4/shared/stagger不进入默认任务。

本轮已有小样本实测和负例，见 `REVIEW.md` 与 `evidence/local_observations.json`。没有把小样本冒充新的100图结果。三台机器按原Trident #38分片分别执行 HOST_0/1/2。
