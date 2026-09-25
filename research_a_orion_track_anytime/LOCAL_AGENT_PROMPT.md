# Anytime Wu：下一轮本地小批次（2026-09-25恢复交付）

分支 `orion/track-anytime_wu` / PR #34。先读取 `results/wu_resume_20260925_0900/review/REPORT.md`、EVIDENCE_INDEX及原始失败，不覆盖旧实验或其他Agent。只研究第三问FIFO合法顺序、三问候选选择/停止，不改公共solver/campaign、官方图/config/evaluator、结构/内存或Fusion代码。

## 默认版本与边界

默认 `--revision v3`。`v4-window` 完成窗口候选和 `v4-select` 负证据暂停都有明确反例，只是实验选项，不默认合入。v3可运行不等于统一冷启动全面优于旧ORION。024从day01弱种子有改善，但实际强结构种子693470本轮没有再改善，不能称刷新全仓最佳。

FIFO接口：`plugin.propose(g,n,cfg,q,incumbent=None,feedback=None,deadline=None)`；选择器：`selector.select_candidate(candidates,history,remaining_seconds)`。提供完整原官方Q3 response/cache_events，不只是makespan数字。FIFO候选只排序既有子图；不改LRU，不添加sleep/delay，不用命中率代替Makespan。

## 环境、真实种子和重评

Windows优先已有 `D:\python\python.exe`、Python3.12.x、CPU-only；依赖沿用项目环境（资源观测需psutil）。只核对启动必需项，不做哈希/指纹测试、冒烟、pytest/unittest、全仓审计；官方合法性检查必须保留。本轮Linux实测，未声称Windows已跑。

将代码/结果包解压到完整仓库根目录。轻包的 `research_a_orion_track_anytime/results/wu_resume_20260925_0900/review/next_seed_manifest.json` 包含7张Q3五核可用真实种子，每个都有plan/response/progress；024使用已重放的693470计划。其他为可取得原计划的历史解，不是按表格重造；不含无法取得原计划的32870等更强目标。这是有来源的暖启动池，不是免费冷启动，历史池取得总成本unknown。

完整原始包内 `preparation/seed_manifest.json` 重现本轮day01起点，不能与next_seed_manifest混成同组；新runner_resume支持原路径在checkout中重定位，保留原路径作为来源。

缺原始输入时先读tools/A_DATA_ACCESS.md。冻结输入导出run36104651803/artifact10850846702包含7图及原记录、官方代码；源导出不是实验。不要把LFS指针当JSON图。

新机器第一次使用历史计划先重新官方评估（复用已经实测的prepare.fixed，不改变评估规则）：

```powershell
& 'D:\python\python.exe' -u -m research_a_orion_track_anytime.revalidate_seeds --cases 044,083,086 --manifest research_a_orion_track_anytime/results/wu_resume_20260925_0900/review/next_seed_manifest.json --out research_a_orion_track_anytime/results/wu_next_checked
```

该交付辅助入口本身未在Windows执行。重评数值不一致应停止核查，不覆盖历史成绩。若从正式表和raw_day01重新准备，使用prepare_resume；它在所有真实重评完成后才写完整seed_manifest，不能拿partial_seed_manifest启动比较。

## 下一轮先小批次

```powershell
& 'D:\python\python.exe' -u -m research_a_orion_track_anytime.runner_resume --cases 044,083,086 --questions 3 --cores 5 --methods old,combined --modes warm --revision v3 --seconds 60 --max-evaluations 32 --total-seconds 600 --pair-seconds 30 --workers auto --max-workers 2 --seed-manifest research_a_orion_track_anytime/results/wu_next_checked/seed_manifest.json --out research_a_orion_track_anytime/results/wu_next_small
```

输出目录必须全新。run_windows.ps1支持同样参数；auto只在已完成匹配块之间按CPU/RAM/实际RSS及失败调整，匹配块内资源条件不变；workers不是NPU核数。三台共享同一排序清单，用shards=3、shard-index=0/1/2分片，不要三台各跑完整100图。

小批次通过后再扩二核与三问；对应组合必须准备真实种子，轻包next_seed_manifest只含Q3五核，不可冒充二核。正式三问1—5核曲线和Q3同方案对照要求不变。

## 修改与验收

优先研究整体parent改变后相同局部FIFO动作重复无收益的问题。全族3次无收益后暂停、8次后探测在024略好却让044退步，不可永久屏蔽整个族。下一步应区分动作及局部复用环境、保留少量探测，先做小规模FIFO/预算/结合消融；queue不是旧公共ORION。

同一真实轨迹取30/60/120/300前缀，停止后只持有已有解，不倒填。改变预算或策略单列独立run。Q3所选plan本身经原Q2接口做no-L2，不引用独立Q2最优。记录生成、评估、审计、输出、配对、失败、无收益、资源与阶段停止。未知历史池成本不写0；冻结时长的余量只是解释，不是缓存反事实下界。

交付原始plan/response/progress、源码快照、负结果和未启动项，提交可审查PR，不自动合并，不提交赛事平台。
