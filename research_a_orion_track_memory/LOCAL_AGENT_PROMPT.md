# 本地Agent：先五核小批次，不复现旧分数

从orion/track-memory取得本轮完整源码；先读FIVECORE_README.md及results/fivecore_final_20260924/REPORT.md。用户明确要求直接信任已发布旧指标，不再运行旧方案复现。新的候选合法性和原评估不能关闭。不要运行hash/fingerprint/checksum、smoke、pytest、unittest或全仓审计。

使用独立工作树，不切换正在实验的目录。Windows先沿用D:\python\python.exe/Python3.12.x/CPU-only；不符合条件由本地Agent显式适配，不自动装CUDA/Conda/PyTorch，不影响旧作业。新运行器不联网、不修改config，不把workers当作NPU核数。

只读官方原路径的数据、原code/config，以及combined_final/per_case.csv、selected_plans.zip。缺图时按tools/A_DATA_ACCESS.md只取当前清单。容器git与授权GitHub Connector是不同能力；源码/输入已在本地就立即执行，不以clone/push失败阻塞研究，不先二次打包整个仓库。

当前八图全三问五核已经实测。下一步先在同小清单补2/3/4核，保持参数一致，分3台时各台传入**同一个排序完整清单**，仅ShardIndex取0/1/2。不得三台各自重复完整100图。保留五核正式表，新增核数不能冒称其旧结果的续跑。

具体命令（先单机小批次；总截止30分钟）：

```powershell
.\research_a_orion_track_memory\run_fivecore_windows.ps1 -Cases 5,51,73,90,92,83 -Questions 1,2,3 -Cores 2,3,4 -Seconds 120 -MaxEvaluations 20 -TotalSeconds 1800 -Workers auto -Out research_a_orion_track_memory\results\small_core_extension
& D:\python\python.exe -m research_a_orion_track_memory.pair_selected --run research_a_orion_track_memory/results/small_core_extension --total-seconds 600 --workers auto
```

需要分片时在同一命令添加-Shards 3 -ShardIndex 0/1/2，并给各机独立Out。运行器接纳由可用RAM、CPU配额和已运行作业RSS决定。停止会保留完成前缀和可信种子；未启动/超时都保留，不继续追加无限预算。五核专用fivecore_report.py不要直接拿来汇总混合核数，逐核取trusted_run生成的COMMON表即可。

只接受Makespan改善的候选，搬运为平分时次目标；Q3同方案noL2/L2比值另报。本轮该比值平均下降，不能说“整体所有指标都变好”，也不应故意恶化noL2对照来放大比例。

如需继续局部修复，用-Proposal local -SeedRun 父run，另给新Out。阶段B的seed成本已包括阶段A原solve+新added，不能清零；生成、评估、输出、失败和配对成本全部保留。不要把跨版本的先后试验拼成单次冷启动或固定策略轨迹。

最终只提交本研究线源码/Markdown/CSV和原响应位置索引，不复制原图或文献，不自动合并。当前分支存在一次性输入传输workflow例外，删除操作被工具安全检查拦截；不绕过，交人工处理。它不调度求解器，不随本目录代码更新自动运行。
