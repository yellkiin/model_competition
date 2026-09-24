# ORION day01 阶段结果交接约定

本文件执行用户 2026-09-24 的新要求：改进阶段结束后立即汇总、发布可复核的阶段结果，同时原进程继续缓存配对与最终验证。不得因为发布而停止、重启或重复启动 campaign。当前只增加交接文档，不修改任何实验 Python、参数、官方输入或评估器。

## 两机共用目录

所有路径相对各自运行包根目录。运行根保持原样：

- 片0：research_a_orion_anytime/runs/team_day01_shard0/auto（奇数50图）。
- 片1：research_a_orion_anytime/runs/team_day01_shard1/auto（偶数50图）。

发布根统一为 research_a_orion_anytime/team_results/day01/shard_N/，N 仅为0或1。首次运行编号始终 day01，不因为发布时间晚、运行更快、换机器或有覆盖重试而改号。

```text
research_a_orion_anytime/team_results/day01/
  shard_0/
    latest.json
    refinement_complete/
      PHASE_STATUS.json
      REPORT.md
      per_case.csv
      report.json
      improvements.csv
      lower_tail.csv
      budget_prefixes.csv
      question_1.svg
      question_2.svg
      question_3.svg
      team_status.json
      research_day_clock.json
      launcher_stdout.txt
      launcher_stderr.txt
      team_day01_shard0_refinement_complete.zip
    final/
      PHASE_STATUS.json
      REPORT.md
      per_case.csv
      report.json
      verification.json
      improvements.csv
      lower_tail.csv
      budget_prefixes.csv
      question_1.svg
      question_2.svg
      question_3.svg
      team_status.json
      research_day_clock.json
      launcher_stdout.txt
      launcher_stderr.txt
      team_day01_shard0_final.zip
  shard_1/
    ...同结构，将包名中的shard0换成shard1...
```

每台只写自己的 shard_N 子树，不能覆盖另一台的结果或 latest.json。已发布的 refinement_complete 保留不变；final 使用新目录。实际文件缺失时如实标记，不能创建假验证或空成绩冒充完成。latest.json 记录 schema_version=1、iteration_id=day01、shard_index、stage、相对本分片根的路径和 published_at_utc，更新前确认上传成功。下一轮必须独立 iteration_id，不能混入 day01。

## 改进结束的触发条件

读取 auto/refinement_policy.json 的 jobs。不能仅凭目录存在或最后一个 summary 出现就发布：campaign 会在 batch 返回后更新每条改进 summary 的阶段时间字段，并检查不能退化。

必须确认本轮计划的改进作业已有终态，并且 auto/pairs 下已经出现 request.json，或 auto/final_index.json 已生成。这说明改进合并已结束、主流程进入后续阶段。若出现 worker 故障或退化异常，则发布失败说明，不能标为阶段完成。不要等待全部配对完成才发布第一版。不得为了产生索引再次启动正式 campaign。

## 不干扰计算的冻结快照

改进快照只包含已经冻结的 coverage、coverage_retry（若有）、refinement，以及已有 campaign.json、capacity_admission.json、refinement_policy.json、gate.json（若有）等元数据。不得把仍在写入的 pairs、临时文件或正在生成的最终报告纳入该快照；本版 pairs 固定为空、缓存对照固定标记 pending。

冻结根放在 runs/team_day01_shardN/snapshots/refinement_complete/auto，位于活动 auto 之外，只复制，不移动或修改活动输出。逐作业目录保留 request、summary、progress、已选方案、官方结果、stderr 和失败证据。原官方图/config/evaluator 不打包，旧 pilot 不混入正式成绩。

复制后的 JSON 中仍含原活动根的绝对路径。必须用现有 research_a_orion_anytime.transfer.rewrite 的相同规则把“原活动 auto 根前缀”改为“冻结 auto 根前缀”；只改 JSON 字符串中的完整根前缀，不做任意字符串替换，跳过 *_plan.json 和 current_plan.json。可以调用现有函数做输出路径重定位，不修改实验 Python 源码，不计算新的哈希/指纹。完成后再生成下面的索引和状态元数据，避免改写来源记录。

在冻结根生成 phase_index.json，保留 campaign.index_write 的既有结构：
- chosen：每项为 key=[case,q,n]、summary=冻结根下对应 summary.json 的绝对路径。
- pairs：本阶段固定 []。
- expected：本片50图全部700个真实主键；每图 (q0,n1)、(q3,n1)，以及 q1/q2/q3 的 n2/n3/n4/n5。不补造 q1/q2 的独立单核作业。
- policy：stage=refinement_complete、iteration_id=day01、shards=2、shard_index=N、原截止与预算、partial_pairs=true。

选择规则必须复现当前流程：先 coverage 全部记录；同键 coverage_retry 仅 status=ok 时替换；同键 refinement 仅 status=ok 且 (makespan,added_copy_bytes) 不劣于有效 coverage/retry 种子时替换。失败证据仍保留在快照中。若改进退化、缺少种子或同阶段重复冲突，停止发布成功声明并报告，不能按图择优掩盖异常。不能混入其他运行根、其他源码或其他迭代结果。

在冻结根上使用现有 reporting.collect 生成阶段 per_case.csv/report.json/SVG，verify=False、require_complete=False。这是对已完成、已有官方评估记录的只读汇总；不重新调用官方求解评估，不运行哈希/指纹测试。明确 independent_checks=0 表示本快照尚未执行最终统一验证，不能说“最终验证通过”。原活动流程的官方合法性检查和最终 verify=True 保持不变；它们会照常执行。report.formal_complete 必须保留实际 false，Q3 缺失配对必须保留，不把其解释为700条主记录无效。

使用现有 transfer pack 打包冻结根：
```powershell
& 'D:\python\python.exe' -m research_a_orion_anytime.transfer pack --root 'research_a_orion_anytime\runs\team_day01_shardN\snapshots\refinement_complete\auto' --zip 'research_a_orion_anytime\team_results\day01\shard_N\refinement_complete\team_day01_shardN_refinement_complete.zip'
```
实际执行必须替换 N；解释器使用本机已有运行解释器。包仍保持标准 TRANSFER.json + run/ 格式，接收方用现有 transfer unpack 解压到新空目录，内部引用可重新定位。禁止直接把活动根先复制后 pack 而不修复根前缀，否则接收机的路径仍会指向发送机。

外层 team_status、时钟和日志按同一快照时间复制到发布目录，日志统一命名 launcher_stdout.txt / launcher_stderr.txt；PHASE_STATUS 保留原日志文件名。不得改写活动日志。冻结复制可能需要时间，记录 snapshot_started_at_utc 和 snapshot_finished_at_utc。

## 状态与成绩文件

PHASE_STATUS.json 至少包含：
schema_version=1、iteration_id、shards、shard_index、stage、snapshot_started_at_utc、snapshot_finished_at_utc、source_run_root、snapshot_root、source_revision、algorithm_changed_since_pilot=false、workers、team_deadline_utc、main_deadline_utc、expected_main=700、valid_main、expected_pairs=250、valid_pairs、fully_covered_graphs、refinement_planned、refinement_completed、refinement_failed、historical_failure_count、unresolved_main_keys、hard_timeout_with_valid_count、hard_timeout_without_valid_count、phase_complete、shard_complete、formal_complete、final_verification_complete、cache_comparison_status、original_stdout_name、original_stderr_name。

refinement_complete 时 valid_pairs=0、cache_comparison_status=pending、shard_complete=false、formal_complete=false、final_verification_complete=false，即使主记录700条均有效也不改。stage=final 时按真实报告/验证填写；单片 formal_complete=false 正常，shard_complete 另按50图700主+250同方案对照且无缺失/有效验证确定。字段未知用 null 并说明，不猜测版本或队友状态，不为记录版本计算签名。

per_case.csv 保持现有 reporting.collect 的列名、含义和 UTF-8 BOM 编码，不改 key/q/n，不把派生单核点补成主记录；Q1/Q2单核曲线按原始单核基线定义为1，Q3单核使用实际记录。附加分析放独立CSV：
- improvements.csv：case,q,n,coverage_status,coverage_makespan,selected_status,selected_makespan,coverage_over_selected,relative_makespan_reduction,coverage_added_copy_bytes,selected_added_copy_bytes,refinement_ran,refinement_status,refinement_hard_timeout,coverage_solve_seconds,refinement_solve_seconds,end_to_end_solve_seconds。
- lower_tail.csv：q,n,case,rank_ascending,speedup,makespan,baseline,median_speedup,mean_gap_contribution_vs_median,added_copy_bytes,partition_added_copy_bytes,spill_added_copy_bytes,cache_hit_rate,ops,components,max_component,compute_path,compute_load,compulsory_ddr,global_lower,ratio_upper。只列5核，按 q/speedup/case 排序；贡献为 (本问题5核中位数 - 本图speedup)/本问题有效图数，保留正负号。列出完整50图便于合并分析，不仅上传好图。
- budget_prefixes.csv：case,q,n,stage,cutoff_kind,cutoff_value,best_makespan,has_valid_incumbent。分别记录coverage/refinement；评估前缀3/8/16/24，时间前缀5/10/20/30秒（实际帽以请求文件为准）。没有前缀有效方案时写空，不用最终值倒填。改进继承种子须明确 t=0 已有种子以及是否被包括，不能把coverage耗时算作0。总耗时另外给出首轮失败、重试、改进、配对的实际成本。

时间单位秒，Makespan沿用官方单位，DDR/Spill字节。失败、缺失和零值与 null 区分。P10 统一采用对排序样本在位置 (N-1)*0.1 的线性插值；median为通常中位数。不给未完成配对填零命中率或伪造缓存收益。

## REPORT.md 要回答的问题

1. 明确50图分片/阶段快照、主和缓存覆盖数、是否最终验证；列三问1–5核逐图 T1/Tk 的算术平均，同时给有效样本数。另列5核中位数、P10、最差值/图、低于1倍的图数和缺失。禁止用平均T1除平均Tk代替。
2. 列明coverage到selected的改善/持平/退化/缺失数量，逐图改善比和代表性好图。基线重试补齐与算法收益分开；同图同核同问题同预算才比较，不拿异机求解秒数直接证明算法更快。
3. “为什么好/差”必须引用实际case、Makespan、负载/路径/通信下界、分量数量、DDR、Spill、命中率或已保存官方结果中的证据。将测量事实、瓶颈推断、需要后续验证的假设分开。候选下界与全局下界不要混用；U/L不是承诺可提升倍数。
4. “为什么均值上不去”列最低10%（50图为5图）的具体case和对均值的贡献，并与中位数/其他45图均值并列。排查串行关键路径、负载不均、通信复制、Spill与内存峰值、缓存复用少、搜索预算花在无收益候选等。不能看见超时就说失败，也不能把触帽本身当作改善证据。图多/算子多不自动等于瓶颈。
5. Q3缓存因果比只能使用同一选中方案的Q2无L2与Q3有L2。refinement_complete阶段注明pending，仅可描述Q3实测命中率与总表现；不能拿独立优化Q2/Q3的差值证明缓存收益。final阶段补齐同方案比、命中率、低收益/负收益图及原因。
6. 给出阶段实际求解秒数、预算前缀、收益随预算变化和下一轮最多3项有证据的参数/策略建议，注明预期作用、风险及验证方式。不为了快迭代现场改预算、降门槛、删图或缩核，不修改当前运行Python。下一算法版本须两机协调同源、新根同预算pilot，绝不混入day01。
7. 原失败和未完成如实保留；不声称全局最优，不用分片结果冒充100图。

## final 与团队合并

原本机流程继续 pairs 和最终验证。完成后在 final/ 发布完整 transfer 包、原有 final_report 的CSV/JSON/SVG/verification、补全上述诊断，不覆盖 refinement_complete。最终包内保留原 final_index.json；不要把 phase_index.json 重命名成 final_index.json。中断/截止则明确未完成，按实际文件发布 final 状态，不能制造成功标记。

两片最终均完整后，协调人用现有 transfer unpack 分别解到新根，再用 campaign collect 合并各自 final_index.json，核对1400主+500同方案对照。冲突重复报错，不能择优消解。阶段包只能用于提前分析和下一轮建议，不当作已完成的正式合并输入。

## GitHub 发布

协调机获用户明确授权，将片0阶段/最终结果发布到私有 yellkiin/model_competition 分支 codex/orion-team-run-20260924 的上述 team_results/day01/shard_0 路径。只提交本次文档和对应发布产物，不提交活动 runs、不打包官方输入、不自动merge或上传赛事平台。发布后读取远端文件确认存在并记录commit，再更新对应latest.json，不重复发同阶段。

队友默认只制作片1同结构的文件并回传给用户/协调机，由协调机统一发布；本提示词不要求队友自行push共用分支。若用户另行明确授权队友发布，也只能写 shard_1，保留其他改动并处理普通分支快进冲突，禁止force push。GitHub单文件限制或传输失败应报告，不通过删掉坏图/失败记录缩包；必要时分卷并在manifest列全，维持完整交接内容。

主计算截止仍为2026-09-24T16:43:48.3137853+00:00，团队最终截止仍为2026-09-24T17:43:48.3137853+00:00。阶段发布不重置窗口，不延误继续计算。保持每5分钟真实进度更新。
