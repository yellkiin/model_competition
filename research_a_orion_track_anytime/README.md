# ORION Track Anytime：独立 FIFO 时序与有限预算研究

**当前状态：实现草案，真实图实验门未通过。** 当前会话读到了正式 CSV、发布索引、公共接口和官方源代码，但没有将完整原图及 ZIP 中的逐图原始记录导入执行环境。工作期间 PR25 已把原图改为普通 JSON；当前剩余问题是连接器文本到执行环境的传输，而不是最新 main 仍为 LFS 指针。已实际调用运行入口，因原题附件未挂载而退出；官方评估次数为 0。不能把本目录当作已取得性能提升的版本。

全部新增内容位于本目录。没有修改上游 `research_a_orion_anytime`、其他研究线、原图、config 或官方评估器。模块依赖同一仓库已有的上游代码，不能只复制本目录而忽略原项目及真实附件。

## 接口与文件

`plugin.propose(g,n,cfg,q,incumbent=None,feedback=None,deadline=None)` 是 COMMON.md 候选接口，只处理第三问、保持分组及核归属不变，改变每核已有子图的合法顺序。输出 `name/family/plan/proxy/bounds`。所有方案仍必须经过未修改的官方评估及原 audit。

`selector.select_candidate(candidates,history,remaining_seconds)` 返回已有候选索引或 None；不执行评估、不改变候选。`adapter.py` 导入原构造/局部算法，不重写划分或内存修复。`runner.py` 提供父进程硬截止、同机旧新对比、冷/续优化、三机分片及逐轨迹记录。`trace.py`/`diagnose.py` 读取真实缓存事件，并在必要时调用原任务构造函数重建约束，仅作诊断。

`review_records.py` 读取五张正式 CSV 和解包后的 final_index，核对选定案例原记录，提取复用种子。`plot_curves.py` 只对真实 trajectory.csv 画图；没有实测轨迹时拒绝画图。

## 三个版本不是同一次轨迹的不同截断

- `old`：直接调用当前上游 `solver.solve`，strategy=anytime，不是旧 pilot 的 legacy 模式。
- `budget`：惰性取候选、小队列、所有已出现候选族首评、质量历史校准、本机成本准入和停止条件。
- `combined`：budget 加独立 FIFO 窗口候选。

它们分别运行。budget 已改变生成/选择路径，因此不能声称与 old 有相同候选轨迹。当前不提供“只改 FIFO、完全保留旧控制器”的消融，也不据此宣称已分离 FIFO 的净收益。

## 时间与结果口径

父进程覆盖子进程导入、构造、评估和 I/O，保存所有已观察到的可行 incumbent。30/60/120/300 秒切片仅取当时已持有的值；600 秒只在允许的预算内输出。约 0.2 秒轮询造成的是保守的可用时间上界，不把子进程最后结果填到更早时刻。子进程每次完成的 attempt 保留在 progress 中，可追溯每次改善。

续优化显示 seed_solve_seconds、added_solve_seconds、total_solve_seconds；外来种子的早期轨迹未知时留空，绝不把最终种子从 0 秒开始放入端到端曲线。外来种子先在本机用官方函数重评；历史秒数不进入本机成本模型。外来种子成本必须由原记录提供，不能填 0。

第三问同方案无 L2 对照由原 Q2 函数对所选同一 plan 重新执行，评估成本单列。独立优化的 Q2 最优值不会充当对照。默认硬件参数不开放覆盖入口。

## 执行顺序

先阅读 `LOCAL_AGENT_PROMPT.md`，补齐真实原图与原始包，再启动本轮尚未执行的小样本实测。Windows 入口为 `run_small.ps1`，首批默认最多一个外层 worker，以获得清楚的同机时间对照；后续可调 MaxWorkers，由真实 RAM/CPU/作业情况约束。worker 与 NPU 核数是两种参数。

Python 核心依赖为标准库；资源采样可选 psutil，画图可选 matplotlib。Windows 脚本优先 `D:\python\python.exe`，只检查 3.12.x 启动必需项。其他环境由本地 Agent 选择现有解释器或独立环境，不干扰已有实验。

完整证据边界见 `REPORT.md`。本目录不自动扩大到百图，不自动合并 PR，不自动提交本地运行产生的文件。
