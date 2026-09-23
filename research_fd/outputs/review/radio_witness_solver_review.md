# 时刻双覆盖候选与连续需求块：独立审查

审查对象是实际执行入口 `outputs/run_radio_cpsat_retime.py` 的 witness 版本，归档副本为 `review/run_radio_cpsat_retime_witness_snapshot.py`，SHA256 `3d0310cab7142094d7e6ee7d8017f09ae0e8e11bff9ca125bfb910a5fab5416f`。没有名为 `run_radio_witness.py` 的执行文件；实际命令可在 `logs/official_radio_repair_witness_coarse.json` 核对。未修改任何求解代码或原结果。

结论：**每条原始采样需求均被保留，块约束是原条件覆盖的保守加强，不是等价变换；未发现本次输入下的站点、option owner 或会话变量索引错位。**

## 实际独立重建检查

使用本次正式输入和 `official_pareto_cpsat/energy_cap_1.json`，按实际命令的 300 s 运输开始网格、2400 s 调时窗口、15000 s 运输 horizon、允许软迟到、60 s 轨迹采样重新生成 options 和 demands，未运行优化器：

- 332 个运输 options，与实跑记录一致。
- 2839 个直连失败需求，拆成 1024 块，与实跑记录一致。
- 对所有块展平原需求索引，恰好等于 `0..2838`，无遗漏、无重复。
- 每个块内的所有 demand.owner 与该块 owner 相同，owner 对应 xx 的原始 option 索引。
- 每个 owner 的需求时间已排序；所有块最大时间跨度不超过 120 s，最大值恰为 120 s。
- `candidates(p,3)` 重新生成的全部 88 个 xyz 与双覆盖诊断 JSON 的 sites 逐值相同。所选 13 个原始索引合法且唯一；输入站点顺序没有变化。

上述机器证据保存在 `radio_witness_block_check.json`。

## 块约束为何不会放松原需求

原单需求约束为 `Σ_{j∈C_d} z_j ≥ x_owner`。新块 B 的候选集为 `C_B=∩_{d∈B} C_d`，约束 `Σ_{j∈C_B} z_j ≥ x_owner`。因为 C_B 是每个 C_d 的子集，新约束在选中 owner 时要求至少一个同一会话覆盖块内所有需求，从而蕴含每一个原单需求约束；未选 owner 时两者都不产生覆盖义务。

若交集为空，代码约束 `0≥x_owner`，正确禁用该 option，并保留 deactivated 计数；没有删除需求后让 option 继续可行。本次日志中因此禁用的 option 数为 0。

新模型会排除原模型中通过不同中继会话接力覆盖同一块的安排，因此是严格可能更强的模型。`sample_step*1.01` 的相邻需求间隔检查不证明连续坏链路；中间即使短暂恢复直连，也可能被归入一个块，这只会增加保守性而不会放松覆盖。块名称应理解为“连续坏链路采样点分组”，不能写为连续时间定理。

## 索引与额外约简

- 新 `by_req` 记录的是重新编号后 pool 的整数索引；block 中交集也是这些整数，再用 `zz[j]` 取变量，三者一致。
- demand.owner 从未被重排；为交集效率对块内需求按覆盖候选数排序，只改变交集遍历顺序，不会改变 owner、xx 映射或覆盖集合。
- site-indices-file 分支优先于 greedy site policy，不会在 13 点上再按原始 88 点索引重复截取。日志 `site_policy=greedy_double` 仍是默认字段，但实际选择依据为非空 `site_indices_file` 与 `retained_site_indices`。
- `Session.site` 是选中 13 点数组的局部索引，恢复原 88 点索引须经过 retained_site_indices；真实 xyz 已直接保存。它不应被无映射地解读为原 88 点索引。当前物理建模使用 xyz，未发现由此产生的计算错位。
- 13 点来自旧 27 趟固定计划的空间双覆盖证人，而此次求解用新 26 趟路线；代码针对新 options 重新生成 covers，因此没有借用旧 covers。旧诊断只作候选筛选，不保证新任务的物理可行性。
- 300 s 运输开始网格也是额外约简；中继资源网格仍为 60 s。细化/扩大模型仍可能存在本次粗模型找不到的解。

`feasibility_seed` 以常数目标求第一可行解，不会绕过硬截止、资源或通信约束。其后清空并重建 hints；若该阶段 UNKNOWN，则不伪造 incumbent，也不进入后续成绩。实际本次 90 s 求可行种子为 UNKNOWN、无 incumbent，是保留下来的有限候选搜索失败。

归档快照放在 review/ 下但内部 OUT 仍按当前文件父目录推导；它是源证据副本，不能直接在 review/ 路径执行。运行日志实际使用 outputs/ 根目录入口，未受该归档路径影响。

## 追加：全部合法需求格末会话长度

随后只读核查 `official_radio_repair_witness_dense_sessions/expanded_session_pool.py`。实际 AST 比较确认该函数相对 runtime 原 session_pool 仅 `ends` 赋值不同，证据为 `radio_dense_sessions_source_check.json`；能耗、覆盖、资源区间及截断判断都未变化。

旧 ends 为少数短时长、2 的幂次和 maxend；新 ends 为该点所有位于 `[lo,maxend)` 的有效需求格 s 对应 `s+1`。对任意原会话，设最后已覆盖的需求格为 q，则新池包含 q+1 结束格，且 `q+1<=原hi<=maxend`。缩去空尾部后 covers 不变、开始不变、返仓和能耗不增；本次充电函数单调，所以返仓加充电的能源端点也不增，机身端点同理。故新池中存在不劣的替代会话，保全原有限采样模型的候选能力，并允许新增中间长度。

这一保证限于当前固定位置、60 s 格点、原始采样需求和单调充电曲线；不能称穷尽连续会话空间。新函数仍有一百万列保护，后端必须检查是否截断。源码的 powers-of-two 注释未更新只是注释滞后，不影响实际新 ends。
