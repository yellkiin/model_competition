# Q3/L2 小批次本轮结果

本报告由保存的真实官方响应、请求、attempts 和资源日志生成；没有调用求解器或评估器。

固定案例：001, 026, 030, 033, 080, 083；Q3/五核，最多 2 workers。每作业 120.0 秒、最多 64 次官方调用，起点和最终同方案 Q2 回放均计入。
本轮总墙钟 139.583 秒。

两臂都是在同一份既有强方案上做局部 Q3 改进，并非完整 SMFB 搜索。本次六图是机制诊断样本，没有运行 100 图；结果不证明全局最优，也不代表总体均值。

| 臂 | 作业 | 起点新回放验证 | 最终同plan配对 | 改善/持平/变差 | 官方调用 | 官方秒数之和 |
|---|---:|---:|---:|---:|---:|---:|
| L2_local_v2 | 6 | 6 | 6 | 2/4/0 | 184 | 143.557 |
| existing_F | 6 | 6 | 6 | 1/5/0 | 145 | 78.941 |

官方秒数是各次评价自身 `eval_seconds` 求和；并行作业的和不等于整轮墙钟。单作业墙钟取 `execution.wall_seconds`，包含读取、构造、评价、保存和配对。

| 图 | 臂 | 状态 | 起点 Q3/Q2 | 最终 Q3/Q2 | Q3下降% | 最终同plan L2比 | hit | Spill | addedCOPY | calls | 墙钟秒 | raw候选Q3 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| case_001 | existing_F | complete | 47502/47502 | 47502/47502 | 0.000 | 1.000000 | 0.000000 | 0 | 4608 | 20 | 2.265 | 47502 |
| case_001 | L2_local_v2 | complete | 47502/47502 | 47502/47502 | 0.000 | 1.000000 | 0.000000 | 0 | 4608 | 20 | 2.260 | 47502 |
| case_026 | existing_F | complete | 23047/25762 | 23047/25762 | 0.000 | 1.117803 | 0.378393 | 0 | 453240 | 9 | 1.254 | 23047 |
| case_026 | L2_local_v2 | complete | 23047/25762 | 23047/25762 | 0.000 | 1.117803 | 0.378393 | 0 | 453240 | 9 | 1.259 | 23047 |
| case_030 | existing_F | complete | 559901/560353 | 559901/560353 | 0.000 | 1.000807 | 0.741581 | 1171456 | 7489536 | 13 | 28.831 | 559901 |
| case_030 | L2_local_v2 | complete | 559901/560353 | 559901/560353 | 0.000 | 1.000807 | 0.741581 | 1171456 | 7489536 | 37 | 80.990 | 559901 |
| case_033 | existing_F | complete | 351503/351503 | 351503/351503 | 0.000 | 1.000000 | 0.483886 | 0 | 8951424 | 27 | 21.074 | 351503 |
| case_033 | L2_local_v2 | complete | 351503/351503 | 351498/351498 | 0.001 | 1.000000 | 0.485321 | 0 | 8951424 | 46 | 37.606 | 351498 |
| case_080 | existing_F | complete | 63001/94963 | 63001/94963 | 0.000 | 1.507325 | 0.503110 | 0 | 3616768 | 26 | 6.516 | 63001 |
| case_080 | L2_local_v2 | complete | 63001/94963 | 63001/94963 | 0.000 | 1.507325 | 0.503110 | 0 | 3616768 | 8 | 2.266 | 63102 |
| case_083 | existing_F | complete | 177330/203523 | 177289/203451 | 0.023 | 1.147567 | 0.575494 | 0 | 5802368 | 50 | 36.600 | 177289 |
| case_083 | L2_local_v2 | complete | 177330/203523 | 177283/203309 | 0.027 | 1.146805 | 0.574816 | 0 | 5802368 | 64 | 47.136 | 177283 |

hit 是官方命中字节率（0..1）。raw 候选列排除种子，只包含搜索时限内真实评价的合法候选；未优于 incumbent 的候选仍报告。缺合法新候选时留空，不把保留种子冒充新方法改善。

## 同方案核对与描述性差分

起点须通过本次 Q3 重新评价，周期等于 prior_makespan，且 attempt plan 与保存种子 JSON 对象相同。起点 Q2 同样检查方案对象与原响应；最终检查 best_plan 与 same_plan_no_l2_plan 对象相等、两份官方响应 status/audit 和 makespan 一致。核查不使用哈希。核对不通过的配对数值不用于收益计算。

| 图 | 臂 | 起点缓存节省周期 | 最终缓存节省周期 | 无L2方案变化周期 | 缓存节省差周期 |
|---|---|---:|---:|---:|---:|
| case_001 | existing_F | 0 | 0 | 0 | 0 |
| case_001 | L2_local_v2 | 0 | 0 | 0 | 0 |
| case_026 | existing_F | 2715 | 2715 | 0 | 0 |
| case_026 | L2_local_v2 | 2715 | 2715 | 0 | 0 |
| case_030 | existing_F | 452 | 452 | 0 | 0 |
| case_030 | L2_local_v2 | 452 | 452 | 0 | 0 |
| case_033 | existing_F | 0 | 0 | 0 | 0 |
| case_033 | L2_local_v2 | 0 | 0 | 5 | 0 |
| case_080 | existing_F | 31962 | 31962 | 0 | 0 |
| case_080 | L2_local_v2 | 31962 | 31962 | 0 | 0 |
| case_083 | existing_F | 26193 | 26162 | 72 | -31 |
| case_083 | L2_local_v2 | 26193 | 26026 | 214 | -167 |

起点缓存节省=seedQ2−seedQ3；最终缓存节省=bestQ2−bestQ3；无L2方案变化=seedQ2−bestQ2。恒等式 seedQ3−bestQ3 = (seedQ2−bestQ2) + [(bestQ2−bestQ3)−(seedQ2−seedQ3)] 仅是描述性代数分解。两部分不是独立因果效应：改变方案会同时改变依赖、带宽竞争与缓存访问时序。

## 候选来源与退出原因

| 臂 | 来源 | 调用 | 合法 | 非法/错误 | 显式超时 | 未结束 | 接受 | 严格周期改善 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| L2_local_v2 | l2v2/joint_local | 46 | 46 | 0 | 0 | 0 | 0 | 0 |
| L2_local_v2 | l2v2/local_window | 124 | 124 | 0 | 0 | 0 | 3 | 3 |
| L2_local_v2 | pair | 8 | 8 | 0 | 0 | 0 | 0 | 0 |
| L2_local_v2 | seed | 6 | 6 | 0 | 0 | 0 | 6 | 0 |
| existing_F | fifo/completion_window | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| existing_F | fifo/consumer_window | 72 | 72 | 0 | 0 | 0 | 0 | 0 |
| existing_F | fifo/evictor_delay | 9 | 9 | 0 | 0 | 0 | 0 | 0 |
| existing_F | fifo/fill_advance | 23 | 23 | 0 | 0 | 0 | 1 | 1 |
| existing_F | fifo/joint | 27 | 27 | 0 | 0 | 0 | 0 | 0 |
| existing_F | pair | 7 | 7 | 0 | 0 | 0 | 0 | 0 |
| existing_F | seed | 6 | 6 | 0 | 0 | 0 | 6 | 0 |

seed/pair 单列，接受种子不计为新候选改善；未结束调用不能当成已成功评价。

| 图 | 臂 | 搜索退出判定 | 依据 | 搜索上限秒 | 单项/调用上限 |
|---|---|---|---|---:|---|
| case_001 | existing_F | source_exhausted_or_no_further_improving_epoch | inferred; round1 did not record exact generator exhaustion | 96.0 | 120.0s / 64 |
| case_001 | L2_local_v2 | source_exhausted_or_no_further_improving_epoch | inferred; round1 did not record exact generator exhaustion | 96.0 | 120.0s / 64 |
| case_026 | existing_F | source_exhausted_or_no_further_improving_epoch | inferred; round1 did not record exact generator exhaustion | 96.0 | 120.0s / 64 |
| case_026 | L2_local_v2 | source_exhausted_or_no_further_improving_epoch | inferred; round1 did not record exact generator exhaustion | 96.0 | 120.0s / 64 |
| case_030 | existing_F | source_exhausted_or_no_further_improving_epoch | inferred; round1 did not record exact generator exhaustion | 96.0 | 120.0s / 64 |
| case_030 | L2_local_v2 | source_exhausted_or_no_further_improving_epoch | inferred; round1 did not record exact generator exhaustion | 96.0 | 120.0s / 64 |
| case_033 | existing_F | source_exhausted_or_no_further_improving_epoch | inferred; round1 did not record exact generator exhaustion | 96.0 | 120.0s / 64 |
| case_033 | L2_local_v2 | source_exhausted_or_no_further_improving_epoch | inferred; round1 did not record exact generator exhaustion | 96.0 | 120.0s / 64 |
| case_080 | existing_F | source_exhausted_or_no_further_improving_epoch | inferred; round1 did not record exact generator exhaustion | 96.0 | 120.0s / 64 |
| case_080 | L2_local_v2 | source_exhausted_or_no_further_improving_epoch | inferred; round1 did not record exact generator exhaustion | 96.0 | 120.0s / 64 |
| case_083 | existing_F | source_exhausted_or_no_further_improving_epoch | inferred; round1 did not record exact generator exhaustion | 96.0 | 120.0s / 64 |
| case_083 | L2_local_v2 | call_cap | inferred from recorded calls; one final-pair slot reserved | 96.0 | 120.0s / 64 |

原 runner 若未写精确停止原因，本表明确标注推断：调用达到 calls−1 表示预留最终配对槽后的搜索调用上限；候选完成时刻跨过搜索截止表示时间上限；提前结束且没有触及时限/调用上限表示来源耗尽或无进一步改进的 epoch。不把这种提前停止写成用满 96 秒或 64 次评价。

## 资源与局限

资源来自 resources.jsonl 的现场采点，不是另跑性能基准：

- {"samples": 140, "active_samples": 138, "active_max": 2, "active_mean": 1.9130434782608696, "target_max": 2, "cpu_active_mean": 0.26500126674295726, "cpu_peak": 0.41530054644808745, "available_ram_min_gib": 12.60305404663086}
- 状态分布：{"L2_local_v2": {"complete": 6}, "existing_F": {"complete": 6}}
- 重复 case/arm 键：[]；运行错误条数：0。

cpu_active_mean/cpu_peak 使用 active>0 且 CPU 非空的样本；active_mean 同样只取运行时采点，RAM 是全机可用内存。保存原始 attempts/response/日志，不对未完成结果补造分数。
