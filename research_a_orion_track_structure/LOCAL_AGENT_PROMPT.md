# 下一轮本地 Agent：只补反例，不扩100图

接续 PR #30、`research_a_orion_track_structure/`。先读 `RECHECK_README.md`、`results/recheck_20260925_review/REPORT.md`、`claim_check.csv` 和 `EVIDENCE_INDEX.json`。#29的数字部分复现，但完整算法不退步没有证明；最终v4在064短预算修复Q2/Q3的同时，使044退步，因此不要将它覆盖公共ORION。

## 当前事实

本轮107次有原始响应的固定方案复评相符；399算法臂、127实际完成的Q3同方案无L2配对。CI v2b、local v3和local v4是不同代码，不能把不同版本最低值拼成“新方法”。016的300秒Q1/Q2扩展在CI因总截止未开始；没有600秒或100图新曲线。

044正确Q2三核45,343在 `selected_plans.zip` 的选中方案对应原始 `refinement/e0074`，不是63,135的 `coverage/e0003`。同方案只补两个空核，目标五核复评仍45,343；这不是冷启动免费收益。v3暖启动先查种子邻域可能挤掉大块重构，016 Q1短预算有退步实例。v4保留DP族代表修复064短Q2/Q3，但044冷Q2=73,395落后old69,095，Q3=68,154落后old49,042。

## 环境与范围

Windows先用已有 `D:\python\python.exe`，Python3.12.x、CPU-only。无解释器时由本地Agent确认适配，不自动安装、不切换其他运行作业目录、不杀其他研究线。只检查启动所需路径和参数，禁止哈希/指纹测试、冒烟、pytest/unittest或全仓审计；原官方合法性检查保留。

只改自己目录，公共solver/campaign、官方图/config/evaluator、其他研究线不改。按实际CPU/内存设置进程workers，它不是NPU核数；同一比较块内资源策略固定，下一块才调整。现有auto仅做启动选择，勿声称动态控制已经完整验证。

## 第一批：先补016首解与真实长轨迹

在干净独立worktree中冻结old/published/final-v4源码。对016 Q1和Q2五核分别单条300秒轨迹、相同机器、三方法；有限候选用完可以停，不能空转伪造搜索。原图大的首评可能慢，预算不足要保留无解/未启动。规划本批总截止2600秒，预留原评估、归档成本。

```powershell
& .\research_a_orion_track_structure\run_recheck_windows.ps1 -Cases '016' -Questions '1,2' -Cores '5' -Methods 'old,published,corrected' -Mode cold_start -Seconds 300 -MaxEvaluations 256 -WallSeconds 2600 -Workers 1 -Out 'research_a_orion_track_structure/results/local_016_long_v4'
```

不是沿用CI已经停掉的30秒轨迹；这是清楚标记的独立长预算运行。30/60/120/300取这条新轨迹的完成前缀。若first-feasible仍失败，先修改结构候选次序/规模，不修改官方评估器来“提速”。不要按case号分支。

## 第二批：044/064/048的候选族消融

先复现原v4反例，再比较“非DP代理前两名”“至少一个DP代表”“已有有效核种子/本次实际求出的有效核候选”等通用构造策略。比较应各有固定源码、同预算，不能给新方法免费最终历史plan。

```powershell
& .\research_a_orion_track_structure\run_recheck_windows.ps1 -Cases '044,048,064,001,059' -Questions '1,2,3' -Cores '2,5' -Methods 'old,published,corrected' -Mode cold_start -Seconds 30 -MaxEvaluations 8 -WallSeconds 2400 -PairSeconds 120 -Workers auto -Out 'research_a_orion_track_structure/results/local_counterexamples_v4'
```

这是小样本复核命令，不是宣告v4通过。Q3一得到最终方案就做该plan的原Q2无L2复评。requested/started/completed/valid分开，超时结果不能补成0或已有旧分数。

## 暖启动与资料路径

暖启动必须先原评估同一目标核数plan，按 `RECHECK_README.md` 的请求格式生成固定复评目录，再传 `-Mode warm_start -SeedRoot ...` 或 `-SeedSpec ...`。正式种子与上轮结构线种子分组；成本未知填unknown，不能省掉取得种子的覆盖/重试/改进成本。混合机器历史成本只用于成本账本，不用来宣称速度优势。

需要重建原始day01选中来源时，可从已有授权GitHub下载run36084731975的 `orion-recheck-sources`（artifact10843114510）到隔离临时目录，只提取所需 `raw_day01/` 记录，不覆盖当前研发代码。该包是源数据导出，不是新实验。算法运行只依赖现有原题附件与自己的模块。

## 交付标准

保留全部原plan/response/progress/summary/失败/源码快照；给新的run_id，不覆盖旧结果。关键不稳定组合做独立重复；归因分成原证据确认、受控实验支持、仍是假设。若某新版本只修复064而破坏044，明确保留反例，不能悄悄用历史最优计划替换输出。

先达到真实小样本可解释、Q3配对完整、对照不失真，再考虑扩大。三机后续只能对同一个排序清单使用Shards=3、ShardIndex=0/1/2，不各跑完整100图。正式1–5核曲线另行验证，不能拿二/五核样本替代。

独立PR，不自动合并，不提交赛事平台。当前任务没有让你编写三研究线最终融合代码。
