# ASTER-RBC：独立、限时的 A 题构造—改进实现

## 交付状态

这是已进行真实官方实验的候选实现，尚无超过旧论文的同口径证据。PR #13 的初始实现经过两轮六图实验，随后固定第二版运行 100 图。原 120/45 秒预算完成 667/700 个逻辑作业；其余 33 个经用户明确授权，分 360/120 与 600/600 秒两档补齐。跨档共有 700 个完整合法结果，不等于原固定预算全部成功，也不等于每个 fast/components 变体都成功。准确均值、覆盖和限制见 [RESULTS_SUMMARY.md](RESULTS_SUMMARY.md)。

代码由 AI 辅助编写。未运行冒烟、单元测试、文件指纹或环境性能基准；验证来自未修改官方评估器的真实三问算例，完整覆盖、无环、容量和执行检查始终保留。原始方案、官方响应与失败日志仅保留本地 `runs/`，本 PR 只提交代码和精简结果报告。

所有变更仅在 research_a_aster_rbc/。只读复用 research_a.model、research_a.evaluator、research_a.launch.ensure_inputs；不调用旧的 all/dev/main 全量实验，不修改其源码，不复制或修改官方评估器。

## Windows 直接运行

在已包含本 PR 的仓库根目录执行：

```powershell
& 'D:\python\python.exe' -X utf8 -u -m research_a_aster_rbc.run --workers 2 --wall-seconds 1800 --job-seconds 120 --eval-seconds 45 --budget 6
```

或：

```powershell
powershell -ExecutionPolicy Bypass -File .\research_a_aster_rbc\experiments.ps1
```

现有 Python 3.12 环境直接使用；代码采用 Python 3.10+ 和标准库，无 CUDA、Torch、Conda、求解器安装步骤。其他电脑通过 -Python 指定已有兼容解释器。不要先做环境基准、冒烟、哈希、pytest 或全仓审计。官方输入存在就使用，缺失时由现有 A 输入恢复函数补齐；必要时通过 --archive 指定原始 A ZIP，不恢复其他题。

默认在评估前按 JSON 文件大小的六个等距分位选图，覆盖小到大输入；这只是规模分层，不冒称完整结构覆盖。每图含原始单核基准以及 Q1/Q2/Q3 的 2/5 核，合计 42 个作业。每次求解最多 6 次官方调用，Q3 为固定同方案无 Cache 回放保留其中一次。默认总运行窗口 30 分钟、每作业 120 秒、每次评估 45 秒；候选构造也受父进程的作业截止时间约束。停止与报告可能有数秒开销。首次缺失输入的 ZIP/LFS 恢复是同步操作，网络恢复本身不受父进程作业超时保护：输入齐全后才启动 worker；若恢复已耗尽窗口则不再启动实验。

这是限时可行性实验，不是保证 42 个作业全部完成的承诺。没有完成某问或同方案回放，就必须标成未完成。不要暗中补算到全部成功，更不能扩大成 100 图、多种子、全消融。

## 方法

1. 固定输入规则决定保留整弱连通块还是做深度分带；带内连通块没有相互依赖，按 (带, 核) 聚合保持商图无环。
2. 按关键路径优先，对候选核心模拟 Pipe 日历、前驱释放和跨核等待，结合边界通信与静态驻留风险分核。驻留风险不是实际内存峰值。
3. 快速构造只输出一个方案。记录它的独立成绩，再以连通块分配和单核作为小预算参照／回退候选。
4. 定向邻域先加入至多 6 个独立弱连通分量迁移候选，与关键跨核边两端同核化、重核向轻核迁移、同核全局相邻块合并共享原 12 候选上限。分量迁移保留源核非空且不拆散全局独立分量；初始 fast/components 构造不变。代理显式累计 Q2/Q3 跨核等待，并使用现有近似 FIFO/驻留函数。不是重写官方模拟器，不是完整 MILP，也未实现拉格朗日对偶。
5. 原评估成功且目标更优才替换 incumbent。主目标为 Makespan，相同时比较 partition_added_copy_bytes + spill_added_copy_bytes。无法获得合法方案时报告失败，不输出未经验证的“可行兜底”。

构造和局部操作保持的只是表示层偏序；完整覆盖、执行图、Pipe、Spill、容量、缓存等仍由未修改的官方评估链检查。THEORY.md 区分真实可行上界、条件性松弛下界、非严格代理。

## 输出与比较

默认新目录：research_a_aster_rbc/runs/<UTC时间>_<机器>_s<分片>/。

- manifest.json：实际案例、核数、预算、解释器和机器；没有生成文件指纹。
- jobs.json / coverage.json：包含未开始、超时、失败与成功进程，不以进程成功替代官方成功。
- summary.csv：逐例 fast、components、best；原始单核分母、周期、额外搬运、命中率、同方案 Cache 比、整次求解秒数。
- 每个作业：candidate_*.json、official_*.json、best_plan.json、best_official.json、result.json、job.log。

fast 与 components 恰为同一 JSON 时复用该次真实评估，记录 alias，不增加评估调用。best 是小预算组合的结果，不冒称纯构造器。solve_seconds 是整个作业耗时，不能冒称每个 variant 的独立计时；各次官方调用 seconds 另存 evaluations。

超时被强制结束时 result.json 可能仍写 running，但父进程 jobs.json 明确记录超时，已经保存的合法 incumbent 仍有效。--resume 仅补尚未有结果且没有请求/日志/错误轨迹的作业；若首个检查点前已有失败轨迹，则拒绝同目录重跑，要求在新目录定向补跑，不覆盖已有失败或部分轨迹；需要重跑失败病例时指定新目录和 --cases，不能把不同版本的最好结果拼成一次固定算法。

只对同案例、同核数、同小问、同配置的旧结果作配对。旧论文的三个五核平均值 3.5093、3.5456、3.6104 是上传草稿摘要中的报告值，不是本 PR 已复核的成绩；小样本均值不能与其全 100 图均值直接比较。缺逐例旧方案/结果时明确说明。Q3 Cache 比必须来自同一个 best_plan.json 在 Q2 和 Q3 的回放，不能直接用分别优化的两问结果相除。

## 多机与恢复

同样六图的两台机器可分别加 --shards 2 --shard 0 和 --shards 2 --shard 1；分片按案例分，每张图的单核与三问都留在同台。不要并发写同一输出目录。合并 CSV 前检查案例/小问/核数/variant 重复、缺项和参数一致性即可，不做哈希任务；不同硬件的求解秒数分别报告。

内存不足先 --workers 1，不修改题定缓存容量。运行异常只修本目录兼容性代码；把错误与修复记入结果旁的说明。效果差先看 fast 对 components 的逐例结果、通信路径、Spill、缓存回放，再考虑一次有限修订。不得修改官方逻辑来提升分数。

## 独立输入、续跑与失败补跑

`--input-root <已有仓库根目录>` 可只读复用另一工作目录的 A 输入、题定配置和官方代码。它不改变 ASTER 代码目录。设置 `PYTHONDONTWRITEBYTECODE=1` 可以避免在复用目录写入字节码。

`--continue-from <已结束目录>` 在新目录引用原已启动作业的结果，只执行 `not_started`；原图集合、核数、每项预算、实现、机器、解释器和输入路径必须一致。它不会恢复已超时作业，也不会把休眠时间静默兑换成新预算。`--wall-seconds` 是操作者为本次续跑明确给出的窗口。

`--only-job-ids <JSON文件>` 接受唯一作业 ID 的非空列表，例如 `case_014_q1_n2`；每项在独立新目录尝试一次，不与 `--continue-from`、`--resume` 或分片混用。可配 `--baseline-from <已结束目录>`，只复用同图/配置/官方代码路径且有原始官方响应支持的合法 Q0 分母，不导入旧多核成绩。失败、超时和部分完成必须保留；放宽预算需要明确授权，不自动重试。

Windows 运行期间采用进程范围的临时防空闲睡眠，退出恢复原请求状态，不改全局电源计划。检查点原子替换遇到 WinError 5/32/33 时，只短暂重试文件操作（累计最多 0.75 秒），不重做官方调用。

## 已保存结果的离线报告

下面仅读取已有结果，不启动求解或官方评估。`$AsterRun` 指本包 `runs/` 下已经结束的某轮目录：

```powershell
& 'D:\python\python.exe' -X utf8 -m research_a_aster_rbc.analyze_results $AsterRun
& 'D:\python\python.exe' -X utf8 -m research_a_aster_rbc.performance_summary $AsterRun
```

`analyze_results` 写出 `analysis.json`、`coverage_detailed.json`、`evaluation_times.csv` 和 `REPORT.md`，根据官方证据区分完整、部分、失败和超时，并复核 Q3 同方案回放；可通过 `--command`、`--interpreter`、`--note` 记录实际执行信息。`performance_summary` 在最终分析上分开统计构造器、增强和 Cache；`progress` 只读取已结束作业用于进度统计；`compare_rounds` 比较同一案例/配置的两轮结果。

`write_experiment_report` 是本次已授权 700 个正式逻辑作业、33 项补跑以及可选 18 项十分钟补跑的历史汇总工具，要求对应目录和最终分析齐备，并非任意规模实验的通用合并器。它保留各档成绩，按阶段/案例/问题/核数/变体检查重复与缺项，不生成混合预算的最低周期成绩。所有生成报告及原始大批数据都保留在本地。
