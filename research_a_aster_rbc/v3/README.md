# ASTER V3：分支链—阶段 DP—驻留阶段流水线

本目录是 A 题的新候选实现，与 PR #16 的旧 ASTER 保持隔离。只读取原题输入并调用**未修改的官方函数**，不改原图、不改 cycles/size/config/Step1/2/3；只输出题定的 `node_to_subgraph` 与 `core_schedules`。Python 标准库、CPU-only。

> 交付状态：GitHub 写入 `quality.py` 被工具拦截，当前 PR 是缺该模块的草稿，不能直接运行。对话提供的 `ASTER_V3_full_source.zip` 包含完整实测源码；先在独立 worktree 补齐该目录，再按下文执行。见 `DELIVERY_STATUS.md`。

## 直接执行

在仓库根目录、Windows PowerShell：

```powershell
& 'D:\python\python.exe' -X utf8 -u -m research_a_aster_rbc.v3.run --workers 2 --wall-seconds 1800 --job-seconds 90 --eval-seconds 45 --budget 8
```

默认 7 个开发/机制案例 001、002、016、044、059、071、083，三问五核，以及每图原始整图单核。`budget=8` 是每个调度作业的**全部官方调用上限**，Q3 包含最终同方案 Q2 回放；原始单核是单独作业。默认 3% 计算松弛 gap 停止条件只依赖输入/当前方案，不按文件名调参。`--mode fast` 单独运行构造主体；构造失败时仍允许必要回退，报告不会把回退伪称首构造成功。

缺失输入/LFS 指针时给出具体路径后停止。由本地 agent 从原始 A ZIP 或仅 A 目录的 LFS 恢复；不要恢复其他题，也不要运行旧 `research_a.launch all`。`--official-dir` 可显式指定包含 `code/` 和 `data/` 的 A 附件目录。本机缺少 D 盘解释器时使用已有 Python 3.10+ 的真实路径；无需 CUDA、Torch、Conda、MILP 求解器。

内存或 CPU 正被别的实验使用时 `--workers 1`。workers 是运行电脑的评估进程数，不是模拟 NPU 的核心数。两个核心数不能混淆。

## 本轮变化

* 大弱连通块不再直接视作串行：收缩单入单出的分支链，再收缩低成本凸汇合区，最后分核/同层打包。它能暴露反复 fork/join 的并行性。
* 小/中图在固定深度轴上做有限阶段 DP。最优性**仅针对该加性代理和固定轴**；真实全局时间不等于各阶段时间之和。
* 共享输入密集的深层多分量图使用阶段固定核心、分量微批次、阶段内细粒度子图优先级；还考虑少用部分核心减少重复读取。空核心列表是原接口允许的，不改变题设核数。
* 原函数在隔离子进程中常驻调用，避免每次解析图与启动 CLI；超时终止的是评估子进程，不修改评估函数。保留官方内部所有合法性检查，但不做独立冒烟、哈希或全仓审计。
* 先保留首构造的真实成绩，再比较少数结构候选和定向邻域。仅在没有合法方案时才尝试昂贵的单核兜底，不再每作业必评串行方案。

从 ORION 借鉴的是阶段/局部窗口思想、先保存 incumbent、分离构造与评估成本；不接入其哈希、独立审计、64 次搜索或默认续跑流程。本代码没有直接调用 ORION 的搜索器。

## 输出与时间边界

默认写入 `research_a_aster_rbc/runs/v3_<time>_<pid>/`，包含 manifest、逐作业 request/result、逐次原方案、原始官方响应 `.json.gz`、best_plan、CSV、覆盖记录和报告。未达预算上限不一定是错误：候选耗尽或达到计算下界的允许误差时会提前停止。

每次官方调用有硬超时；构造步骤、落盘和汇总不是抢占式操作，实际总停止可能比名义墙钟多几秒。首次输入恢复不是自动计分步骤。本轮上限不是“保证所有实例均完成”，缺项必须保留。

`--resume --out <原目录>` 只继续**从未开始的作业**，要求参数/配置文本/版本一致。已有成功、失败、超时、partial 目录一律不覆盖、不重跑。运行中断遗留 `running` 也不悄悄重新计时；修复/重试必须用新目录并明确另一个协议。新文件夹不能与旧成绩逐例取历史最小值混合。

多机使用 `--shards M --shard i`（i 从 0 开始），各机独立输出。汇总各分片的 CSV 时按 case/question/cores/variant 检查重复与缺项；不同硬件的求解秒数分开报告，不做文件哈希任务。

## 指标与未完成部分

正式速度是逐例 `T_original_singlecore / T_official` 再算术平均，另报几何平均和有效计数。`fast_available_seconds` 是首构造通过评估后可用的时刻；`total_solve_seconds` 是整个求解成本，不能给每个 variant 都冒称相同独立耗时。Q3 Cache 收益用**完全同一 best_plan**分别在 Q2/Q3 回放，不拿两问各自最好时间相除。

开发案例上的成绩不是全 100 图成绩，也不是留出验证。没有跑完全部题定核数、配置和 Cache 对照，就不能把 `formal_complete=false` 改成 true。目标 4.5× 不是停止条件，更不是可以通过删案例/改分母来完成的承诺。

方法/理论见 `METHOD_AND_BOUNDS.md`，52 条文献复筛见 `LITERATURE_COVERAGE.md`，实际结果见 `LOCAL_MEASURED.md`，后续交给本地 agent 的限时协议见 `LOCAL_AGENT_PROMPT.md`。
