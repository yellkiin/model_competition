# 结构线安全续优化：本地 Agent 交接

继续 PR #31 的保留好解续优化，不覆盖 PR #30 的冲突分支。分支为 `orion/structure-safe-refine-20260925-0318`，起点 main `996d7d11f10ac44ce65fcd361d5a057a5795c0f9`。开始前核对最新状态和工作目录，不覆盖并行提交或正在执行的实验。

## 当前已完成

七图001/016/024/044/048/059/064，三问，五核，21组配置：11组Makespan下降、10组持平、0退步。42个实际旧/新续优化臂，14个Q3同方案无L2配对全部完成。先行pilot和6个负探针另存，不按跨批次最佳值拼表。044/Q3由46827降至32870；同方案无L2为53161。旧版在044/Q2和059/Q2优于新结构单独结果，最终分别保留44139和149021。不得强制选择新算法。

这是相对于已验证历史主种子的暖启动不退步机制，不是等预算冷启动优势。整个历史方案池取得成本不完整，必须记unknown；只计获胜臂时间是不对的。100图混合均值只替换七图、其余93图保留day01，不是全量新算法重跑，也没有合并内存线。

## 使用哪个种子清单

把本轮代码/方案包叠放到独立的完整仓库副本；官方输入不在交付包中。

**继续优化使用更新后的好解**：
`research_a_orion_track_structure/results/safe_refine_20260925/review/next_seed_manifest.json`

**复现本轮起点才使用旧清单**：
`research_a_orion_track_structure/results/safe_refine_20260925/inputs/seed_manifest.json`

不要用旧清单重新覆盖已取得的32870等新解。两个清单的相对路径以仓库根目录为基准。每个主种子必须先在目标q/n使用未修改的官方评估器重新验证；补空核和跨问题复用也必须目标场景复评，绝不能复制源分数。新清单保留父清单及追加成本谱系，不把未知完整历史成本填0。

若只从仓库day01正式selected_plans.zip生成种子，可用prepare_safe_seeds.py；但该起点不同，不能混称复现本轮历史最优池。

## 下一轮先小批次

Windows优先已有D:\python\python.exe、Python3.12.x、CPU-only。本轮实际是Linux/Python3.13.5，不冒称已做Windows实测。

在仓库根目录执行：

```powershell
& 'D:\python\python.exe' -u -m research_a_orion_track_structure.safe_refine --cases 044,048,059,064 --questions 1,2,3 --cores 5 --methods old,safe --seconds 120 --wall-seconds 900 --max-evaluations 128 --workers auto --seed-manifest research_a_orion_track_structure/results/safe_refine_20260925/review/next_seed_manifest.json --out research_a_orion_track_structure/results/safe_next_small
```

输出必须是新目录。通过后再单列016/024大图实验。run_safe_windows.ps1支持同样参数；三机共享同一完整排序图清单，再用--shards 3和--shard-index 0/1/2分片，不能各跑全部100图。workers是CPU进程数，与NPU核数分开；auto是启动选择并固定比较块，不冒称运行中自适应。

## 研究与验收

只改结构线新增模块，不改公共solver/campaign、图/config/官方评估器或其他研究线。safe_regions.py是未被采用的负候选，不默认接入。024简单细切长链已经实测失败，不能为了并行度忽略中间张量搬运。

保留同一个合法主种子给旧版和安全结构臂。新结构另有冻结备选方案池，必须如实说明不是等信息纯消融。只有完整官方结果合法且(Makespan,额外COPY)字典序更优才替换；失败/超时不能抹掉旧解。保证主要Makespan不退步，不保证所有辅助指标同步改善。

逐臂记录requested_method、actual_route、候选族、耗时及失败；组合择优计入两臂和配对成本。Q3选中方案本身进行无L2对照。30/60/120/300前缀从单一真实轨迹截取，停止后注明持有旧解，不重启各时间点、不倒填最终值。未知历史成本不画虚构端到端冷启动曲线。

只检查启动必需项，直接用真实图，不做哈希/指纹测试、冒烟、pytest/unittest或全仓审计。官方合法性检查不关闭。

按summarize_safe_refine.py汇总每批，读取完整原记录。分别报主种子、旧版续优化、新结构单独结果及最终保底结果。新增收益与此前016/024等累计收益分开。未完成配置/配对明确标记，不因CI成功就称验收通过。

最后提交独立可审查PR、原始方案/响应/失败、连续曲线和交付索引，不自动合并、不提交赛事平台；五核小样本不冒充正式一至五核或100图统一算法结果。
