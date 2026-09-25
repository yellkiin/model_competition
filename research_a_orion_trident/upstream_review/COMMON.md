# 三条研究线的最小共用约定

本轮按优化机制分工，不把“研究方向编号”误当作原奇偶数据分片编号。三台都先看100图汇总及自己要研究图的两片原记录；可以共享少量对照图，但不要三份相同算法各跑一遍100图。

|方向|独立目录|分支|负责模块|
|---|---|---|---|
|结构|research_a_orion_track_structure/|orion/track-structure|结构构造、关键路径分核、有效核数、结构邻域|
|内存|research_a_orion_track_memory/|orion/track-memory|边界通信、Task合并、张量驻留与Spill修复|
|Anytime|research_a_orion_track_anytime/|orion/track-anytime|FIFO顺序候选、候选选择、时间分配与停止|

## 可组合的候选接口

每条线提供 `plugin.py`，实现下面的生成器。它是本轮新增接口约定；当前ORION主程序并没有自动加载这些插件，独立实验适配器应放本条线目录。

```python
propose(g, n, cfg, q, incumbent=None, feedback=None, deadline=None)
```

`g/cfg` 沿用现有core.Graph/Config，`incumbent` 为 `None` 或含 `plan`、`official_result` 的字典，`feedback` 为已完成尝试记录列表，`deadline` 为当前进程 `time.monotonic()` 的绝对截止或 `None`。不修改传入图、配置和已有方案，不跨进程复用monotonic绝对值。

逐个返回兼容现有候选池的字典：`name, family, plan, proxy, bounds`。`family` 使用各自前缀 `structure/`、`memory/`、`anytime/`。`plan` 只含官方 `node_to_subgraph/core_schedules`，元数据放外层。`proxy` 是含 `score` 的代理字典；`bounds` 沿用可信界，拿不准的新增项不得标为已证明下界。先做现有结构检查，再由运行器调用未修改的原评估器；插件内部不私自把代理当正式分数。

第三条线另可提供 `select_candidate(candidates, history, remaining_seconds)`，只返回现有候选索引或 `None`（建议停止），不隐藏地改方案/执行评估。三条线均可提出额外接口，但必须写清，不能把公共模块改成三个互不兼容版本。需要公共挂钩时只在本目录给适配器和说明，暂不同时修改现有 solver.py/campaign.py；本轮不写最终汇总代码。

## 最小统一结果

各线 `results/<run_id>/` 内保留：

- `per_case.csv`：case,q,n,method,run_id,mode,status,baseline,old_makespan,new_makespan,old_added_copy_bytes,new_added_copy_bytes,seed_solve_seconds,added_solve_seconds,total_solve_seconds,construction_seconds,evaluations,lower,no_l2_makespan,cache_hit_rate,plan_file,result_file。
- `trajectory.csv`：case,q,n,method,run_id,mode,phase,elapsed_seconds,total_elapsed_seconds,best_makespan,baseline,speedup,added_copy_bytes,evaluations,has_valid_incumbent。
- `REPORT.md`：真实数据、归因依据、改了什么、好坏例、时间曲线、未解决问题；`LOCAL_AGENT_PROMPT.md` 与 `run_windows.ps1` 写明下一轮本地命令。

mode区分cold_start与warm_start。从已有解续跑时，追加时间0可以有种子，但种子成本必须另列；端到端时间要包括实际取得该种子的覆盖、重试和改进成本，不把day01整天其他图的成本均摊进来。无有效解填空，零值不是缺失。参数曲线从同一固定策略轨迹取已完成前缀，超过实际停止时间只延续已有解并注明已停止，不能外推。预算变更会改变算法路径时，另列独立运行，不混称同一条轨迹。

主要目标为官方Makespan，额外搬运等指标不隐藏。原评估、失败修复和输出成本都算时间；Q3同方案无L2对照成本单列并计入实验总成本。较大原响应包可用仓库现有上传方式并附位置索引，不重复提交官方输入或文献。相同机器和并发条件下比较旧新算法；混合worker结果记录实际政策，不据此宣称求解器更快。

## 本地与范围

运行器支持图清单、q/n、时间预算、workers自动调整、输出目录及shards/shard-index。研究时各跑自己的小清单；以后要分配数据到三台时才使用shards=3，按同一个排序后完整图清单分片。不要默认启动三份全量百图。普通图最多300秒、困难图必要时600秒作为首轮建议，不是题面硬上限；设置本轮总截止，先小批次再扩大。

不运行哈希/指纹测试、冒烟、pytest/unittest、全仓审计；启动必需检查之外直接用真实图。原官方覆盖、无环、容量、Pipe/FIFO和执行检查不能关闭。各自只提交本条线目录，保留旧day01和其他AI结果，不自动合并PR或提交赛事平台。
