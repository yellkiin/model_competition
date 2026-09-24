# 数据与来源说明

本包只导出已经结束的本地实验，不调用求解器或官方评估器，不改变原始结果。数值导出保留原精度；CSV 空字段表示缺失，不能按 0 解释。原始 `runs/` 没有提交。

| 文件 | 范围与使用方法 |
|---|---|
| [summary.csv](summary.csv) | 原生 70 行多核 fast/best；原生导出没有失败的 076 Q1 两行，也不含 Q0。 |
| [measured_variants.csv](measured_variants.csv) | 84 行：12 个 Q0 + 72 个多核变体，含失败空记录。`original_singlecore` 只来自本轮 Q0；`source_recipe`、`source_label` 保留候选来源。 |
| [jobs.csv](jobs.csv) | 48 个逻辑作业的原生/核对状态、合法 incumbent、停止原因、官方调用数、超时/剪枝数、整次 solve 时间与请求预算。 |
| [evaluation_attempts.csv](evaluation_attempts.csv) | 234 个候选尝试：191 次官方调用（184 ok、7 timeout）和 43 次未调用官方的 bound_pruned。逐项记录 label、周期、官方内部耗时、调用墙钟、构造耗时与错误。 |
| [cache_pairs.csv](cache_pairs.csv) | 12 个最终 Q3 best_plan 的固定方案 Q2/Q3 回放；`without_cache/with_cache` 是收益比，`same_plan_json_equal` 是本地内容比较结果，非哈希。 |
| [reference_pr16.csv](reference_pr16.csv) | 30 个旧 PR16 首次完整结果参考，按同案例/题问/五核/配置/同一 T1 筛选；旧 120/45/6、新 90/45/8，不是等预算实验。路径为历史来源。 |
| [statistics.json](statistics.json) | 6 组 fast/best 统计、覆盖、Cache 汇总、计时定义、旧参考的 6 项排除原因、问题/下界违反列表。来自本地 analysis.json 的字段投影。 |
| [coverage.json](coverage.json)、[manifest.json](manifest.json)、[run_receipt.json](run_receipt.json) | 原生状态、设置（含当时 config 文本）、机器信息、实际墙钟；原样复制。receipt 不证明方案合法性。 |
| [execution_context.json](execution_context.json)、[summary_structure.json](summary_structure.json) | 当时源码取得方式、解释器/机器/命令，以及 native CSV 缺行与重复统计，原样复制。 |

AM=mean(T1/T)，GM=exp(mean(log(T1/T)))；各问有效 n=10，028/076 当前 T1 缺失不能从旧运行补入。失败的 076 Q1 没有合法周期。合法但无 T1 的多核周期和搬运仍保留。

`summary_structure.json` 原样保留的说明中提到 `analysis.json`，指未提交的本地源分析文件。其失败空记录在本包对应 [measured_variants.csv](measured_variants.csv)，汇总统计和问题列表对应 [statistics.json](statistics.json)；本包不含 `analysis.json`。

`total_solve_seconds`/`solve_seconds` 为整次作业时间；fast/best 共享它，不能再次相加或称为各变体独立耗时。`fast_available_seconds` 含首候选构造、官方验证及 I/O；`variant_solve_seconds` 无法独立辨认时保留空。`official_seconds` 为评估器内部计时，`call_wall_seconds` 含调用开销。并发作业和调用耗时之和不是整轮 645.078 秒墙钟。Q0 请求是 job=122、eval=120 秒；多核为 90/45 秒且最多 8 次调用，Q3 回放计一次。

所有 `result_path`、`raw_file`、`source_raw_path`、`plan_file`、`best_plan`、`replay_plan` 等路径均相对上述本地源运行，不是本包内可访问文件。`old_result` 指向另一旧运行。原始响应不上传，故本包中的 `legal`、`raw_corroborated` 和 plan 相等只是当时本地核对的记录；远端读者应区分报告证据与可自行核验的原始证据。

搬运字节区分 `partition_added_copy_bytes` 与 `spill_added_copy_bytes`；Cache 命中字节率不等于 Makespan 收益。下界字段仅保留原记录，计算松弛的官方语义适用条件未经完整确认，不得将 `instance_ratio_upper` 等直接称作已认证最优性缺口。

[DIAGNOSTICS.md](DIAGNOSTICS.md) 的时间线摘录仅涵盖 003/007/035，不能当全部 12 图的因果证明。012/094 相对旧参考的退步、035 负 Cache 收益和所有超时均保留。12 图已被分析，后续不能再声称是未见测试集。
