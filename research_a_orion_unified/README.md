# ORION Unified：唯一的新实验入口

当前研究把Fusion SMF2.3与Trident1.3进行同起点、同主机、同时间上限比较，再合并它们实际有用的调度与运行机制。完整对照见 `COMPARISON_REPORT.md`，最后完成的Linux/Windows实测和交付状态见 **`LATEST_VALIDATION.md`**，新实验只按 `PLAN.md` 执行。

旧计划已归档到 `history/orion_plans/`；旧代码/结果原路径保留用于复现。不要在Fusion、Trident和Unified三个目录各自再跑一遍完整100图。

## 本轮已取得的证据

同条件5配置×3算法的15份选中结果、9个Q3同方案对照均已核验。Unified相对Fusion两胜两平一负，相对Trident一胜四平；不是所有图都优于两种旧算法。另3个Linux冷启动配置含Q3同次配对完成。Windows Server 2025 / Python3.12.5也已实际运行044 Q1/Q3二核，两配置与同方案无L2对照完成，原响应再次核验通过。新百图与用户三台电脑尚未完成。

## 开始

在完整仓库根目录，主机0执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a_orion_unified\run_windows.ps1 -ShardIndex 0
```

主机1/2仅改ShardIndex。默认输出 `research_a_orion_unified/runs/unified_round01_shard_N`。已有图、day01 `selected_plans.zip`、配置与解释器直接复用。缺数据时只补本片A输入；可选 `bootstrap.py` 按原始字节取数，但没有必要重复下载已有资料。

每配置总上限600秒，Q3配对在同一进程预算内预留。核心标准库、CPU-only，Windows参考解释器D:\python\python.exe，3.12.x x64。更换解释器用 `-Python`；不要升级其他正在运行任务的环境。

完整三台提示词见 `HOST_0.md`、`HOST_1.md`、`HOST_2.md`。当前已验证过的配置不需要作为新计划的强制重复项；批量执行按尚未验证的真实键开始。

## 实际单配置

```powershell
& 'D:\python\python.exe' -m research_a_orion_unified.real_run --out 'research_a_orion_unified/runs/local' --cases 044:1:2 044:3:2 --seconds 60
```

这直接处理两项官方图配置，不是合成输入。已有强方案可用 `--seed` 指定（单配置时使用）。批量入口会载入完整好方案库。该命令仅供针对性复现，不要求三台先重复本轮已经完成的044测试。

## 结果

完成或截止后，用 `publish_results.ps1 -RunRoot <本片目录> -ShardIndex N` 上传本片。主表、完整度与源/时间信息均保存；默认只完整保存种子、当前最好/新候选最好及失败的官方响应，减少无意义磁盘I/O。

报告文件来自 `report/per_case.csv` 和 `report/paper_data/`。集成对照的完整日志与同方案原响应另在本次交付的证据包中。Windows运行索引为36173491379，结果artifact10880628491；详见 `evidence/windows_real.json`。
