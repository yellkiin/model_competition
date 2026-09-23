# 中继联合调时 CP-SAT：独立只读审查

日期：2026-09-23。经 `rg` 确认文件名为 `outputs/run_radio_cpsat_retime.py`。对照固定版、runtime `d_radio.py`、`d_schedule.py` 和 `d_model.py`；未修改或重启正在运行的代码。

**结论：有条件通信覆盖、每条固定路线恰选一次、运输与中继各自的机身/能源资源、硬截止均已进入模型。默认固定零软迟到；允许软迟到的变体改变了比较质量口径。发现 horizon 只绑定运输返仓，不能称联合工期硬 cap。没有发现当前有效输入下漏掉被选路线通信义务或遗漏运输资源的错误。**

## 需修正文档口径：horizon 不是联合工期硬上限

位置：第 43–45、89–96、109–113 行。

候选开始范围包含 `hi <= horizon - route.duration`，因此对选中运输路线有 `transport_return <= horizon`。但 `cmax` 上界取所有运输选项和中继会话返回时间的最大值，没有约束 `cmax <= horizon`；`session_pool` 也未排除 `session.returned > horizon`。

所以日志中的 `horizon_s=10800` 是运输选项的返仓上限，并非全体运输+中继均在 10800 s 内返回的保证。若最后选择一个 10800 s 后返仓的中继会话，模型仍可能合法。最小化 cmax 不能替代硬上限。已即时告知主代理和中继负责人；本次不修改运行代码。若研究另要求联合 cap，需新实验显式添加该 cap 并保留原记录。

## 核查项目

| 项目 | 对照代码及结论 |
|---|---|
| 被选运输选项的通信义务 | `demands_for_options()` 为每个 option 建立其轨迹的直连失败需求，owner 是原 options 索引；第 113 行 `sum(z_cover) >= x_owner`。选中 option 时每条需求须有中继，未选中时右端 0。空 covers 会强制该 option 不选，而非静默漏需求。允许中继顺便覆盖未选 option 没有问题，不应强制禁止多余覆盖。 |
| 每路线恰选一开始 | 第 92、97 行以 route.id 聚合并 `add_exactly_one`；固定箱组/访问序不被改变。已知基线的路线 ID 唯一、箱覆盖完整；事后 metrics 再检验未送达/重复箱。某一路线无合法开始选项时 exactly_one 空集正确导致不可行。 |
| 硬截止 | 第 44 行保留 `r.latest`，runtime 的定义是该路线全部硬截止箱 `min(hard_due-delivery_offset)`。故合法 t 不超过任何硬截止的最迟开始，且 t 不早于 r.release。没有通过允许软迟到放松硬截止。 |
| 零软迟到版 | 默认 `hi` 还不超过 `min(due-delivery)`，所以逐箱都不晚于软期限；`soft_tardiness_fixed_s=0` 与实现一致。第 144 行用实际浮点交付重检总加权软迟到 `<=1e-5`。 |
| 允许软迟到版 | `--allow-soft-lateness` 移除上面的软限制，增加第一目标加权软迟到；不再固定基线的 0 迟到。报告须注明此变化，不得与固定零迟到实验称为同质量对照。硬截止仍不变。 |
| 运输机身/电池 | 对每个选项同一个 x 创建 `[start,start+aircraft_hold)`、`[start,start+battery_hold)` 两类 optional intervals，再按机型 count/batteries 分别累计（93–105 行）。prepare、loading 与充电已包含在 runtime route hold，未漏准备或只约束一类资源。 |
| 中继资源 | 同一 z 控制准备开始至 aircraft_end / pack_end 两区间（109–115 行）。官方 departure 是准备开始，真实起飞另外记录；区间沿用原物理 session，不让中继瞬移。 |
| 半开区间与保守取整 | 运输 starts 位于 60 s 网格，转毫秒是精确整数；hold 向上取整至 1 ms，因此比实际 hold 稍保守。中继两类端点原已在 60 s 网格上，转毫秒不改变占用。OR-Tools cumulative 使用半开区间 `[start,end)`。 |
| 资源编号重建 | 选中运输 options 调用 runtime recolor，再 metrics 检查；中继分别按开始时刻、最早空闲原则给机身和能源着色。对于同仓同型可互换资源，该 interval coloring 正确；不允许据此扩展成异地或绑定资源模型。 |
| cmax 绑定 | 每个选中的运输 option、中继 session 都有对应返回下界，未选 option 不施加返回时刻。目标是全部返回，不是电池全部充完；电池充满时刻继续只作为资源占用。 |
| 目标中省略运输能耗 | 路线、箱组、访问序保持固定，运输能耗不随开始时刻变，因此只优化中继能耗等价于总能耗方向。两/三目标按迟到（若启用）、联合返回、中继能耗排列。 |
| 目标阶段保留 | 每阶段结束固定该整数 incumbent 上界；后阶段若 UNKNOWN，保留之前的 best。FEASIBLE 不是证明该阶段最优，故后阶段属于以当前 incumbent 为上限的细化，不是完整词典序最优证明。每阶段有独立 time_limit，累计过程可超过该秒数。 |
| Hints | 每阶段后 clear_hints，再写 x/z 新解，避免固定版扩展到三个阶段时出现重复 hints。初始 hint 只是最近参考开始，不能保证资源/覆盖可行；solver 无义务接受它。 |
| 连续算术事后检查 | 实际 jobs 重算硬迟到、覆盖、重复和资源冲突；固定零软迟到版额外检查软迟到。relay 着色以实际时间检查重叠。CLI 随后计算 10 s 通信细验，但细验非零断联并不会自动禁止写 joint_plan；必须在导出 validation 中核对 joint_valid，不能只读 solver status=feasible。 |

## 与固定版的差异、精度和删列范围

固定版全部通信需求必须覆盖。调时版必须、也确实采用 `x_owner` 条件右端，避免替所有未选开始时刻提供中继。固定版无需再建运输资源；调时版新增两类运输累计资源及每路线恰一约束，是必要差异。

新 `dominant()` 第 28–34 行比较实际 CP 模型采用的整数系数：资源端点毫秒、向上取整返回毫秒、能耗 `1e-9 kWh`。此前固定版浮点容差跨取整边界的问题在此版本已修复。相同 covers 加资源区间包含，且两目标整数系数不增，足以安全删除当前整数有限模型中的被支配列；不能推广为所有连续位置/采样下的支配关系。

运输迟到系数是每条路线的加权迟到总和先向上取整到 1 ms 再求和。因此有 N 条被选路线时，整数目标相对实际加权秒总量的保守误差小于 N×0.001 s（精确整数边界浮点误差另计）；这不是每箱 1 ms。后阶段固定整数迟到上界，不等同于无误差地固定连续实数迟到。实际报告应采用 metrics 重算值，并保留目标单位。

`greedy_double`/`greedy_quad` 是额外的启发式空间候选约简：在所有选项需求并集上重复做贪心集合覆盖，不能保证保留原 88 点池的时间/资源可行性。它没有改变链路预算，但可能丢失不同时间下需要的候选点。`pool_truncated=false` 只表示在约简后的站点与有限会话生成器中没有截断列；不能据此宣称全站点模型已完整求解。不可行或 UNKNOWN 都不构成原全候选问题不可行的证明。记录 original_sites、retained_site_indices、site_policy 是正确做法。

## 非当前运行阻断的输入边界

当所有 routes 都没有可用开始选项，且 session_pool 也为空，第 89 行 `max([])` 会抛出异常，不能输出结构化 no_start_options；只有部分路线无 options 时则由 exactly_one 空集给出不可行。当前运行日志显示 848/1630 个 options，不触发此边界。

函数假定 reference_jobs/horizon 存在，且路线 ID 与 reference 一致；当前 CLI 满足该前提。若作为通用 API 暴露，应在入口先验证，而不是让 KeyError/TypeError 代替诊断。此处不是本轮有效输入下的缺陷结论。

## 审查版本

- `run_radio_cpsat_retime.py` SHA256：`15b256fb679850728793733c8b3b3b09bd4dce79486be5d44149542e2a87fe56`
- runtime `d_schedule.py` SHA256：`c3d11ed2efe530d7eae32487900661f4abd9a33157a2bd00649cca58cfad9328`

本审查没有补填未结束后端的成绩，也没有把代码约束存在等同于已取得可行联合计划。
