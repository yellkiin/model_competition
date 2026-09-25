# 结构线独立复核入口（PR #30）

这不是公共 ORION 的默认替代版本。原 `plugin.py/worker.py/run.py` 留作已发布版本，修正版独立入口是 `plugin_recheck.propose` 和 `recheck_run`。报告按 v2b、v3、v4 分组；某个版本的实验不能改名为另一个版本。

先读 `results/recheck_20260925_review/REPORT.md` 和该目录的 `claim_check.csv`，不要只看获胜例或 CI 绿色状态。新结果保留退步、无收益、超时和未启动。

## 最小真实图运行

在完整仓库根目录、已有解释器上执行：

```powershell
& 'D:\python\python.exe' -X utf8 -u -m research_a_orion_track_structure.recheck_run --cases 064 --questions 1,2,3 --cores 2,5 --methods old,published,corrected --mode cold_start --seconds 30 --max-evaluations 8 --workers 1 --wall-seconds 900 --pair-seconds 120 --out research_a_orion_track_structure/results/local_064_recheck
```

也可调用 `run_recheck_windows.ps1`；它只检查启动必需的解释器版本和参数，不安装环境、不做哈希/冒烟/测试框架检查。Python 求解核心仅用标准库。当前官网附件相对路径在 `recheck_evidence.OFF` 中；不修改原官方数据。移植其他目录时应在独立输入适配层改变路径，不修改图内容。

## 固定方案重放与暖启动

创建请求 JSON，例如（路径用实际存在的位置）：

```json
{"case":"044","q":2,"n":5,"source_n":3,"label":"044_final_n3_padded_n5","out":"research_a_orion_track_structure/results/local_fixed/044_final_n3_padded_n5"}
```

```powershell
& 'D:\python\python.exe' -X utf8 -m research_a_orion_track_structure.recheck_evidence path/to/request.json
```

默认正式方案解析器要求 `combined_final/selected_plans.zip` 与原始 day01 解包记录。它按选中方案内容和正式表匹配，不按第一个文件名取种子。原记录在导出包中的布局为 `raw_day01/shard_0/run/...`、`raw_day01/shard_1/run/...`。本地原始记录路径不同应先整理只读输入副本；已有 plan 也可以通过请求的 `plan_file` 指定并明确 provenance。没有这些证据时不能伪造正式种子成本。

先完成固定复评，再让 `--seed-root` 指向含 `formal_XXX_qQ_nN/summary.json,plan.json,official_response.json.gz` 的目录。所有算法使用相同新复评的种子。使用 `--seed-spec` JSON 可以给 `044_q2_n5` 指定三核补空核后的复评目录。报告分别列历史种子成本、新验证成本、追加成本和混合机器的端到端账本；混合机器账本不用于宣称速度优势。

## 时间与并发

`--seconds 300` 是一条连续轨迹的最大预算；前缀从父进程在截止前实际观察到的可行解导出。`--max-evaluations` 同样是停止条件；很多真实图会提前耗尽有限候选。因此 60/120/300 行并不自动说明一直搜索到这些时刻。`not_started` 与 `stopped_carry_forward` 分开。

`workers=auto` 根据启动时 CPU 配额/可用内存选择最多两个并发比较块，每个块内的方法顺序交替且串行。它不是动态负载预测器；本轮公平对照保持比较块策略不变，没有据此宣称求解器速度提高。内存不足应在下一比较块减少 workers，不杀停其他研究线。

Q3 的选中方案立即调用原 Q2 做同方案无 L2 对照。预算不足保留未启动/超时，不计为完成；配对秒数另列并计入运行总墙钟。

## 复核与绘图

`summarize_recheck.py` 从已落盘的原始表按版本/机器/阶段/冷暖/种子配对，不运行算法；重新导出报表不能称为重新实测。图表可使用 `plot_recheck.py`（需要已有 matplotlib），曲线值只来自 `trajectory.csv`。

`--shards 3 --shard-index 0/1/2` 对同一排序清单分片。现在不默认扩100图，2/5核样本也不替代正式三问1–5核曲线。
