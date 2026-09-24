# day01 分片0：用户授权的双 worker 接续

2026-09-24 用户明确要求停止原任务后接续双/三 worker，并接受前后成果拼接。实际选择 2 个 worker。这里的 Python 是独立的接续调度脚本；导入运行工作区中原来的求解器、官方评估入口和报告代码，没有改动原算法文件。

- 原运行根：`D:\桌面\model_competition_orion_anytime\research_a_orion_anytime\runs\team_day01_shard0\auto`，已在北京时间 18:33:36 停止，原结果保留。
- 新运行根：`D:\桌面\model_competition_orion_anytime\research_a_orion_anytime\runs\team_day01_shard0_w2\auto`。
- 切换前保留 700 条有效主记录（含 3 条恢复成功的覆盖重试）和 243 条已完成改进记录。剩余 377 项按原清单接续。
- 原改进预算为普通图 27 秒、大图 54 秒，评估次数上限 256。中断作业扣除已用时间和尝试次数，只续用剩余额度。中断片段保存在 `refinement_interrupted`，最终进度中的时间和序号加上前段偏移；不得再次合计重复的中断片段。
- 重启后的候选生成从保留方案继续，搜索轨迹不保证与无中断运行相同；2 worker 的 CPU 竞争也会影响固定墙钟预算内评估数量。报告必须标明混合执行，不称为纯单 worker 对照。
- 采用原单 worker 预留量计算的改进截止点，保留原 `campaign.deadline_epoch`，主计算仍在 2026-09-24 16:43:48 UTC 停止，团队截止仍为 17:43:48 UTC。
- 新 `continuation_capacity_admission.json` 按剩余改进和全部缓存配对的有限时间帽、2 worker 加验证预留计算，未降低质量门槛或删除图。
- `campaign.identity.args` 保留原配置，新增 `execution_override` 记录实际双 worker 接续。不得使用原 `campaign formal` 入口在此根恢复。
- `phase_index.json` 和 `refinement_complete.json` 只标记改进阶段；缓存对照及官方最终验证完成后才有 `final_index.json` 和 `final_report`。阶段交接仍按原 `team_results/day01/shard_0/refinement_complete/` 与 `final/` 发布。

监督器为 `run_continuation.ps1`，其子进程为 `resume_day01.py`。读取新根 `team_status.json` 指向的 stdout/stderr。原外层 exec 会话已随旧进程结束，不要重复启动它。首次监督器启动因 PowerShell 5 解码无 BOM 中文路径失败，尚未启动求解；修正为 UTF-8 BOM 后启动成功，首次日志保留。

本次只作了 Python/PowerShell 语法解析和真实接续结果检查，没有执行 smoke、pytest、unittest、哈希测试或 benchmark。阶段发布必须包含本目录的脚本和说明以及 `worker_switch.json`、`continuation_*.json`，从而保留执行来源。

## 中断方案保留记录

切换作业 case_043 q3 n3 已用约44.261秒和11次评估，余9.7385秒在新进程初始化时耗尽。接续子段 `deadline_without_incumbent` 失败完整保存在 `resume_attempt_outcome.json` 和 `resume_attempt_progress.json`。`retain_interrupted_incumbent.py` 读取前段已有官方有效结果，将 Makespan 262943 的方案保留为该逻辑作业结果，不新增求解时间。逻辑记录有效不代表接续子段成功，阶段报告须同时披露两者。`interrupted_incumbent_retention.json` 为该处理的证据入口。

## 双 worker 到四 worker：当前作业完成后接续

用户随后明确要求当前正在运行的两项改进作业完成后，后续作业直接使用4 worker。`drain_and_start_w4.ps1` 暂停调度父进程94880以阻止新作业领取，但不暂停两个求解子进程；按各自原27秒预算监督它们结束。case_089 q1 n3 和 q2 n3 均得到有效方案（243614、235137），`finalize_drained_jobs.py` 只读取原官方有效检查点生成终态摘要，没有追加评估。时间分别27.028和27.019秒，包含进程结束观察延迟。旧调度器随后退出。

新的入口为 `run_continuation_w4.ps1` 和 `resume_day01_w4.py`，新根为 `runs/team_day01_shard0_w4/auto`，继承已完成所有结果，仍用原单worker计算的改进截止及同一总截止。旧w2根完整保留。`prior_execution_overrides` 保留早先1到2 worker历史，最新 `execution_override` 为4。本次不另开day02，不调用 parallel_next_20260924 中的下一轮入口。最终报告披露1/2/4 worker混合执行以及第一次切换的失败子段。本次当前作业均完成原预算，无额外中断片段。
