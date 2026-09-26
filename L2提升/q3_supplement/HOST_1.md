# 主机2：Q3有L2增量补跑（Trident #38，分片1）

使用 PR #59 的 `L2提升/q3_supplement`，不要改动仍在运行的旧目录。先读 README.md 和 REVIEW.md。

本轮保持 `research_a_orion_trident` #38 为主体：Q1/Q2旧结果与原始单核分母不重跑、不替换；只补Q3有L2。最新两项L2研究起点不同，不能按“14.8% vs 0.09%”直接比较。默认把portfolio的500份实际方案作为广覆盖候选库，用强起点研究的v1实际好方案补充；同一case/n只看绝对Q3周期。v2/v3以及topo4/shared/stagger不进入默认任务。

先找到本机#38最终FULL包，BaseRoots指向真正选定的final运行根，必须有实际plan；不要只用公开汇总CSV。多个历史目录冲突时显式选择最终版，不按最低数字事后拼表。非标准布局使用 README 中的 `-BaseManifest`。

原题、图、config和官方评估器保持不变。优先使用 `D:\python\python.exe`、Python3.12 x64、CPU-only；不要安装CUDA/PyTorch，不加哈希、冒烟、pytest/unittest或全仓审计前置。官方合法性检查保留。

你负责原 #38 分片1，共 33 张图。运行：

```powershell
.\L2提升\q3_supplement\run_windows.ps1 -ShardIndex 1 -BaseRoots 'D:\本机实际Trident最终根' -Workers 0 -Policy bank_only -Out 'L2提升\q3_supplement\runs\l2_patch01_shard_1'
```

默认规则：
- 只有两份已发布方案库中预计比本机当前同键至少低0.1%的候选，才启动真实Q3重评；其它键直接继承，零新增评估。
- 每个真正启动的补跑最多120秒、8次Q3评估；本机整批4小时绝对截止，不因恢复重置。
- workers=0 使用#38资源准入，自适应多进程，目标留25% CPU/RAM；workers不是题目核数。
- 只有实际达到0.1%改善才替换Q3方案。Q3方案变化才补一次该方案的同方案Q2/no-L2；这是缓存反事实，不是Q2优化。
- 旧方案不变且已有同plan pair就复用。014/n5等旧缺口默认只列pending；只有明确需要时加 `-RepairMissingPairs`。
- 新pair若顺手显示Q2比旧独立Q2好至少3%，只写入迁移候选表，不启动Q2全量搜索。
- 不默认启用 `selective/explore`。本轮044/083/084强图上的扩展分带/weak适配没有新增收益，部分明显更差。只有有明确余量和理由时另开输出目录做小批次。

完成后检查：
`report/q3_overlay.csv`、`changes_only.csv`、`q2_transfer_opportunities.csv`、`attempts.csv`、`time_quality_30s.csv` 和 `report.json`。报告实际处理键、跳过键、改善键、新Q3调用数、新/复用/缺失pair与耗时。没有改善就如实保留原Q3。

发布：

```powershell
.\L2提升\q3_supplement\publish_results.ps1 -ShardIndex 1 -RunRoot 'L2提升\q3_supplement\runs\l2_patch01_shard_1'
```

只发布 `L2提升/q3_supplement/team_results/l2_patch01/shard_1/` 的小报告和changed_plans，完整 evidence.zip 留本地手动交付；不覆盖另外两台、旧Trident结果或赛事平台。返回实际结果PR链接，不自动合并。
