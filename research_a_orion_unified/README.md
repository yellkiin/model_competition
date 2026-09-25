# ORION Unified：唯一的新实验入口

当前研究把Fusion SMF2.3与Trident1.3进行同起点、同主机、同时间上限比较，再合并它们实际有用的调度与运行机制。完整对照与结论见 `COMPARISON_REPORT.md`，新实验只按 `PLAN.md` 执行。

旧计划已归档到 `history/orion_plans/`；旧代码/结果原路径保留用于复现。不要在Fusion、Trident和Unified三个目录各自再跑一遍完整100图。

## 开始

在完整仓库根目录，主机0执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a_orion_unified\run_windows.ps1 -ShardIndex 0
```

主机1/2仅改ShardIndex。默认输出 `research_a_orion_unified/runs/unified_round01_shard_N`。已有图、day01 `selected_plans.zip`、配置与解释器直接复用。缺数据时只补本片A输入；可选 `bootstrap.py` 按原始字节取数，但没有必要重复下载已有资料。

每配置总上限600秒，Q3配对在同一进程预算内预留。核心标准库、CPU-only，Windows参考解释器D:\python\python.exe，3.12.x x64。更换解释器用 `-Python`；不要升级其他正在运行任务的环境。

完整三台提示词见 `HOST_0.md`、`HOST_1.md`、`HOST_2.md`。这是研究实现；真实完成量以生成的report.json为准，不以计划写了100图就当已完成。

## 实际单配置

```powershell
& 'D:\python\python.exe' -m research_a_orion_unified.real_run --out 'research_a_orion_unified/runs/local' --cases 044:1:2 044:3:2 --seconds 60
```

这直接处理两项官方图配置，不是合成输入。已有强方案可用 `--seed` 指定（单配置时使用）。批量入口会载入完整好方案库。

## 结果

完成或截止后，用 `publish_results.ps1 -RunRoot <本片目录> -ShardIndex N` 上传本片。主表、完整度与源/时间信息均保存；默认只完整保存种子、当前最好/新候选最好及失败的官方响应，减少无意义磁盘I/O。

报告文件来自 `report/per_case.csv` 和 `report/paper_data/`。集成对照的完整日志与同方案原响应另在本次交付的证据包中。
