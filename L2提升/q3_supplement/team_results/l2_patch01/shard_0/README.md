# Q3 L2补丁 l2_patch01：主机1执行分片0

本结果由 PR #59 完整源码（18b60bfd0a34a99dbcfa68edfca0c7d7b84142bd）在 Windows、D:\python\python.exe、CPU-only 实际执行。主体仍为 Trident #38；Q1/Q2旧结果及原始单核分母保持不变。

34张图、170个Q3键全部处理。37键在两份已发布真实方案库中有至少0.1%的潜在收益并实际补跑，37键均改善；133键直接继承。新增Q3原评估37次、新增同方案Q2/noL2评估37次、复用原配对133项，最终配对170/170。没有缺失键、失败或超时。启动到退出102.559秒，退出码0。

默认 bank_only，每个启动键120秒、最多8次Q3调用，整轮4小时绝对截止，自动workers目标保留25%CPU/RAM。不启动Q1/Q2搜索、全量Q3搜索或selective/explore。新noL2只是所选Q3方案的缓存反事实，不能用于宣称独立Q2优化。6项Q2迁移机会仅列于report/q2_transfer_opportunities.csv，未改Q2。

旧记录来自已补齐的最终round01_savefix分片0Release，通过有界范围下载，仅提取最终jobs内Q3计划/响应/summary和同方案文件。没有将不同历史目录按最低成绩拼接。014/n5已发布的缺失项原配对补算文件也已找到并作为旧输入；本轮未启用RepairMissingPairs，014/n5新方案的noL2是本轮随实际改善正常新增的配对。

- report/q3_overlay.csv：170键最终覆盖表。
- report/changes_only.csv与changed_plans/：37键真实改善及其计划，论文只替换这些Q3行和新配对。
- report/attempts.csv：旧响应复用及37次真实候选评估。
- report/time_quality_30s.csv：真实保存时间的30秒前缀；held_after_stop明确表示停止后保持。
- report/curves.csv：保留原单核分母的34图Q3均值，各核有效数均为34。
- report/SOURCE_SELECTION.json、EXECUTION_FACTS.json：来源、预算及实际调用计数。
- PUBLICATION.json：改善计划清单。

完整evidence.zip仅保留本地手动交付，包含原Q3输入/配对、014既有配对来源、运行记录、实际新响应、候选库、官方输入及源码快照。未自动上传原档或赛事平台，不自动merge。本机指定发布脚本已完成导出，但缺少gh命令；报告分支推送和结果PR使用既有Git授权及GitHub连接器完成。
