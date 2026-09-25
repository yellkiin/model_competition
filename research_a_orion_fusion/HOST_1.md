# 主机2：ORION Fusion分片1

你在 yellkiin/model_competition 的问题A仓库。先取得本次ORION Fusion完整PR，使用 research_a_orion_fusion，不切换或改动其他机器正在运行的目录。先阅读README.md、REVIEW.md、FIFO_INTERFACE.md；现阶段启用结构S+内存M，FIFO研究分支及_wu尚未整合，不把它们当已验证第三组件。

题目与原配置/评估代码在“题目/A题/通用神经网络处理器下的多核调度问题  附件”；文献在“调研/A题_文献库/”。现有ORION在research_a_orion_anytime，两个完成研究目录是research_a_orion_track_structure和research_a_orion_track_memory。新宿主导入它们，只在允许的两个方案字段上组合优化，不改原图、Tensor、cycles、config或官方Spill/FIFO。

取得day01完整combined_final表、selected_plans.zip及两条研究线已经能读取的真实更好方案。若某报告只有数值缺plan，按publication清单查归档；暂时拿不到就保留published_target_gap，不造种子。真实更好方案统一导出qN/nN/case_NNN_multicore_res.json并用-ExtraPlans传入，程序会重新官方评估并保留更好解。不要只拿自己原来的50图准备分片；三台须用同一完整100图清单，按manifest分成34/33/33图，不按旧奇偶分片重复跑。

优先D:\python\python.exe、Python3.12.x x64、CPU-only。不匹配时由你配置独立解释器并传-Python，不更换旧进程环境。不做哈希、冒烟、单元/pytest、全仓审计或环境跑分，检查启动必需项后直接跑真实图。官方合法性与最终时间线检查保留。workers=0自动，目标CPU/RAM留25%余量；不手动塞满全部核，也不结束其他程序。实际resources.jsonl记录峰值和调度，若存在压力先调整workers。

执行下面属于本机的命令。默认小图追加120秒、大图300秒，先2个未在本轮测过的真实组合键，然后通过才接着运行本片全部三问与核数，先行结果复用。已有输出同参数可恢复，不重置截止；不同参数或FIFO版本开新目录。三机需要同一个全局时限时共同传入-DeadlineUtc。本轮建议不超过8小时，阶段预留给Q3配对和诊断。缺图只补本片A输入，不下载其他题。

每个候选原评估后才更新最好方案；旧好解作为候选保留。不能因为单个候选或小样本局部变差否定整个优化。出现raw候选整体不佳、或低于真实已发布目标时，查看diagnostic_queue.json：当前SM按需运行S、M；F真正接入之后才三选二，必要时三选一。不得默认启动完整百图消融，也不把诊断的事后最优悄悄混入固定组合主表。明确更好的方案可供下一轮续优化。

记录实际best-so-far随时间的变化，区别本轮追加、种子取得成本和本地总成本；不能倒填早期，没有完整历史成本就留空。所有失败、超时和无收益记录保留。三个小问输出都要齐，Q3对最终方案做同方案无L2比较。核数指题目NPU核数，与CPU workers不同。

结束后执行本机的export命令，确认报告、所有选中方案和官方结果都在本机独立发布目录。把本机报告、精简逐例表、资源/时间曲线及原始证据包提交独立PR或按现有仓库大附件方式发布，README写明包地址。不能覆盖day01、另一台结果或改公共求解器。只回报实际完成和缺失键；不要把单片说成100图全部完成。我们之后统一收取三片并检查1400主+500配对。

本机运行：
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a_orion_fusion\run_windows.ps1 -ShardIndex 1 -Out research_a_orion_fusion\runs\round01_shard_1
```

本机发布：
```powershell
& 'D:\python\python.exe' -m research_a_orion_fusion.export_results --root research_a_orion_fusion\runs\round01_shard_1 --out research_a_orion_fusion\team_results\round01\shard_1 --include-all-candidates
```

结果分支使用 `results/orion-fusion-round01-shard-1`，只提交 `research_a_orion_fusion/team_results/round01/shard_1/`。若更换了解释器，运行和发布都使用同一个实际路径。
