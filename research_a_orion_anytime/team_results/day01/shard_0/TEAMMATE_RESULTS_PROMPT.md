# 给队友机器 Agent 的结果交接提示词

继续你现有的 ORION day01 分片1（偶数编号50图）。本提示词用于统一结果格式，不要求停止你正在运行的作业，也不要求重启或更改worker。先读取已有进程、输出根和你自己的真实进度；不要猜测本机或另一片进度。

协调机片0已经完成700主记录、250同方案缓存对照、700最终验证。片0发布于私有 yellkiin/model_competition 的 codex/orion-team-run-20260924 分支，路径 research_a_orion_anytime/team_results/day01/shard_0/。你只制作对应 shard_1/，iteration_id仍为day01，原图编号不重新编号。

请以仓库 research_a_orion_anytime/handoff_20260924/ITERATION_HANDOFF.md 和 TEAMMATE_ITERATION_PROMPT.md 为共同格式协议，按片0的PHASE_STATUS和CSV字段交接。改进完成且pairs已有request（或final_index存在）后，复制已完成coverage、coverage_retry、refinement及元数据到活动根外的独立快照，使用原transfer.rewrite重定位。阶段包的pairs为空、final_verification_complete=false、formal_complete=false，phase_index不能冒充final_index。保留现有计算继续配对和验证。若已全部完成，仍分别保存阶段快照与final最终结果。

发布相对路径固定为：

research_a_orion_anytime/team_results/day01/shard_1/refinement_complete/
research_a_orion_anytime/team_results/day01/shard_1/final/

每版包括PHASE_STATUS.json、REPORT.md、原per_case.csv/report.json/question_1.svg/question_2.svg/question_3.svg，以及同列同含义的improvements.csv、lower_tail.csv、budget_prefixes.csv、team_status.json、research_day_clock.json、stdout/stderr和标准transfer ZIP。final另保留verification.json和包内原final_index.json。命名team_day01_shard1_refinement_complete.zip与team_day01_shard1_final.zip。

如果包超过单文件限制，可以像片0按90MiB顺序分卷，附TRANSFER_PARTS.json和重组脚本；重组后必须仍是原TRANSFER.json + run/格式，不能删掉坏图、失败或中断记录以缩包。片0的reassemble_transfer.py可以按清单复用，清单原包名改为shard1。

报告先逐图算T1/Tk再取50图算术平均；三问1–5核、5核中位/P10/最差/缺失、DDR/Spill、最低5图对均值的贡献都要列全。缓存因果比必须是同一选中方案Q2无L2 / Q3有L2，不拿独立优化Q2/Q3差值代替。解释好图、差图和预算收益时区分测量事实与假设。保留全部失败与触帽有效方案，不能挑选最优重复记录。

如果你也发生过用户授权的worker迁移，请附你自己的切换记录、外部接续脚本和前后来源；继承记录只算一次，保留原已用秒数/评估次数，不能增加逻辑作业预算。片0经历1→2→4，不代表你的机器也应修改并发。原算法变更必须另根、同预算pilot并协调同源，不混入day01。

主计算硬截止仍为2026-09-24T16:43:48.3137853+00:00，团队截止17:43:48.3137853+00:00（北京时间次日00:43:48和01:43:48）；还要遵守你manifest中的更早截止。禁止smoke、哈希/文件指纹/checksum测试、pytest、unittest、全仓审计、benchmark，不改官方图/config/评估器或合法性检查。

请把完整shard_1结果目录/分卷回传用户或协调机，并告知真实活动状态、最终验证是否完成及缺失项。默认由协调机统一上传，你不需要自行push共用分支。不要自动merge或上传赛事平台。单片700+250是50图完成；协调机在新根分别unpack两片final并collect，1400主+500同方案对照且最终验证完整才称100图完成。

协调机更新：本次队友分片已通过GitHub回传并完成团队统一验证；上述提示保留作格式约定，不需要重复上传或重启day01。完整团队报告位于 ../combined_final/REPORT.md。下一轮仍须用户授权与两机协调。
