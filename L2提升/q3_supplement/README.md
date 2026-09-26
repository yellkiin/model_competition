# Q3有L2增量补跑：保留Trident #38，只替换真正更好的Q3方案

> 完整源码已重新提交到 PR #59。运行前阅读本目录 README、REVIEW 与对应 HOST 文件。

本目录是结果补丁，不是另一套全问算法。**不启动Q1/Q2搜索、不重跑原始单核分母、不改已有成绩和官方评估器。** 默认比较两项L2研究已经公开的真实方案，对当前本机#38最终Q3结果有足够改善时才调用Q3评估并更新。没有潜在改善的键直接继承旧记录，零新原评估调用。

## 两项研究怎么取舍

- `L2提升/proposals/20260926_workshop_v1_q3_portfolio/`：从早期 components/bands8/batches800 起步，500配置353改善，五核均值3.610380→4.135514。这个14.8358%降时不能直接移植到Trident强起点。例：其083五核185314，弱于强起点研究v1的177259；030为559924，也弱于原Trident559901和v1的558512。
- `L2提升/orion_20260926/`：六张五核强起点上v1固定策略最好，平均降时0.093064%；v2/v3没有超过v1。采用其已经实际保存的v1好方案。昂贵/容易制造Spill的topo4、shared、stagger以及v2/v3不进入默认任务。

**以当前相同case/n的绝对Q3周期筛选，而不是按不同基线的百分比给方法投票。** Portfolio有500个实际计划，覆盖广，作为主要检索库；v1是强起点补充库，同键更好时排在前面。默认不再搜索旧portfolio、不重新跑完整F，更不平均分配两套实验预算。工程阈值 `MinGain=0.001` 表示至少0.1%周期下降才更换方案，可显式调整；不是题面要求。

## 默认流程

1. 读取本机已完成的Trident最终plan、Q3响应及同方案无L2响应；保留原34/33/33分片。
2. 从portfolio的500方案tar.xz与v1的incumbents中读同case/n候选，用已发布Q3周期排出可能有至少0.1%收益的候选。报告值只用于补跑准入，不当作理论下界或新成绩。
3. 没有合格候选：原Q3、原plan、原配对原样继承，标记 `retained_existing`，不重新搜索也不计算无L2。
4. 有候选：优先复用并核对本机完整Q3原响应；缺响应才真实回放旧plan。对候选调用未修改的官方Q3；只有实际改善达到阈值才替换，否则仍用旧plan。
5. 方案改变后只调用一次该方案的Q2/noL2评估，补齐Q3成对数据。这是缓存反事实，不是Q2重新优化。方案未变且旧pair的plan完全相同，则复用旧pair。
6. 新pair恰好比原独立Q2结果好至少3%时列入 `q2_transfer_opportunities.csv`，不自动重跑或替换Q2。

## 三台机器

Python参考 `D:\python\python.exe`、3.12 x64、CPU-only。CPU密集评估使用多进程 workers，并复用#38资源准入，默认目标留25% CPU/RAM余量；workers与题目NPU核数无关。

三台只需要各自原#38最终完整包。BaseRoots应指向真正选定的final运行目录，含 `jobs/case_XXX_q3_nN/{plan.json,result.json.gz,summary.json}` 或 selected/plan.json。不要同时指向历史、候选和多个不同最终版本；冲突时明确选择当前结果，不静默取最低值。

```powershell
.\L2提升\q3_supplement\run_windows.ps1 -ShardIndex 0 -BaseRoots 'D:\实际Trident最终运行目录' -Workers 0
.\L2提升\q3_supplement\run_windows.ps1 -ShardIndex 1 -BaseRoots 'E:\实际Trident最终运行目录' -Workers 0
.\L2提升\q3_supplement\run_windows.ps1 -ShardIndex 2 -BaseRoots 'D:\实际Trident最终运行目录' -Workers 0
```

默认每个实际启动的补跑调用120秒，最多8次Q3评估，本机4小时绝对截止。没有候选的键不占这120秒。可给 `-Seconds 300/600`，但不建议一开始扩大。

## 非标准旧记录

可以提供JSON或CSV显式清单，必需 `case,n,plan`，建议带 `q3_result,old_makespan,no_l2_plan,no_l2_result,reference_t1,old_q2_best`。使用 `-BaseManifest <path>`。汇总CSV不能代替真实plan。

## 可选探索

`-Policy selective` 只增加 weak/FIFO 与 weak/low_footprint 两个便携候选；`-Policy explore` 另加四个pipe/byte分带方案，仅用于小样本研究，非默认。本轮044/083/084强起点实测没有新增收益，部分明显更差，因此正式补跑默认 bank_only。

## 结果与发布

`report/q3_overlay.csv` 保留所有Q3键；`changes_only.csv` 只有真实替换；`attempts.csv` 保存候选结果；`time_quality_30s.csv` 保存30秒前缀；`q2_transfer_opportunities.csv` 只提示现成Q2迁移机会。

```powershell
.\L2提升\q3_supplement\publish_results.ps1 -ShardIndex 0 -RunRoot 'L2提升\q3_supplement\runs\l2_patch01_shard_0'
& 'D:\python\python.exe' -m L2提升.q3_supplement.run collect <片0根> <片1根> <片2根> --out <合并补丁根>
```

发布脚本创建独立结果worktree和PR，只提交小报告及changed_plans；完整 evidence.zip 留本地手动复制。旧Q1/Q2和原报告不动；论文采用补丁时只替换 changes 表对应Q3行及其新的同方案配对。