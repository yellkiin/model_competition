# Anytime Wu：下一轮本地小批次（v4最终续优化）

分支 `orion/track-anytime-v4-final-20260925` 继承 PR #34 当前全部恢复/结构实验。本次先读 `results/v4_structural_fifo_20260925/REPORT.md`，同时保留 `results/wu_resume_20260925_0900/` 的强种子/失败记录；两套起点不能拼成一个等预算结果。

只研究第三问FIFO合法顺序、三问候选选择/停止及本目录结构触发候选；不改公共solver/campaign、官方图/config/evaluator或其它研究线。

## 已验证 v4 continuation

本次 `--revision v4` 在可追溯v3路径上使用真实 fill/evictor FIFO 候选、结构触发尾核再平衡和近界预算停止。推荐为 **warm continuation**，冷启动保留old对照。

Q3/五核正式seed实测：024 `2227340→2217280`、044 `46827→44768`、083 `181091→180934`、086 `48028→47682`；001/059/084保留seed。最终七个plan均严格同plan重放Q2/no-L2。额外048 cold v4=124681劣于old=117513，但从old incumbent继续15秒得到116941，因此不能删除old冷启动路径。

## 环境与种子

Windows优先已有 `D:\python\python.exe`、Python3.12.x、CPU-only；资源观测需psutil。只核对启动必需项，不做哈希/指纹测试、冒烟、pytest/unittest、全仓审计；官方合法性检查必须保留。本轮Linux实测，未声称Windows已跑。

原输入导出 run **36104651803** / artifact **10850846702**。恢复线 `results/wu_resume_20260925_0900/` 的强种子与本次day01机制种子分开标注来源；未知历史取得成本不填0。

完整仓库已有正式原记录时，从raw_day01或已有next_seed_manifest重新目标q/n官方评估后再作为seed。数值不一致立即停止核查，不能用CSV分数重造plan。

## 推荐下一轮命令

先在完整checkout用正式原记录建立本机seed manifest：

```powershell
& 'D:\python\python.exe' -u -m research_a_orion_track_anytime.prepare --cases 001,024,044,059,083,084,086 --workers 1 --out research_a_orion_track_anytime/results/v4_prepare_local
```

暖启动匹配块：

```powershell
& .\research_a_orion_track_anytime\run_windows.ps1 `
  -Cases '001,024,044,059,083,084,086' -Questions '1,2,3' -Cores '2,5' `
  -Methods 'old,combined' -Modes 'warm' -Revision 'v4' `
  -Seconds 120 -MaxEvaluations 128 -TotalSeconds 2400 -PairSeconds 30 `
  -Workers 'auto' -MaxWorkers 2 `
  -SeedManifest 'research_a_orion_track_anytime/results/v4_prepare_local/seed_manifest.json' `
  -Out 'research_a_orion_track_anytime/results/v4_local_gate'
```

若沿恢复线强种子继续，用其 `revalidate_seeds` / `runner_resume` 流程，但策略改变必须新run_id，且不能把两套起点拼成同一组。

## 验收与分片

Q3所选plan本身必须经原Q2接口做no-L2，不能引用独立Q2最优。同一真实轨迹取30/60/120/300前缀，停止后只持有已有解，不倒填。生成、评估、审计、输出、配对、失败、无收益和资源成本分开记录。

结构候选只由per-core timeline尾差、schedule长度或结构特征触发，禁止添加case ID。任何新增规则先在差图和控制图实测；更差/非法/超时不删除incumbent。启发式停滞与近界停止都不是最优证明。

workers是CPU并发进程数，与NPU核数不同。三台共享同一排序清单，用 `--shards 3 --shard-index 0/1/2` 分片，不各跑完整100图；跨机器wall-clock不直接作算法比较。

最终交付完整代码、真实plan/response/progress、负结果和来源索引；不自动合并、不提交赛事平台。
