你现在负责在这台 Windows 电脑真实运行 A 题 ORION Anytime 的第二分片。不要只给计划；请实际启动、持续读取进程与日志、读取真实结果并汇报。我们共两台机器，本机必须是 Shards=2、ShardIndex=1，负责正式阶段偶数编号 case_002、case_004……case_100。另一台机器负责片 0；不要重复它的正式任务。

使用这次团队运行包：https://github.com/yellkiin/model_competition/raw/refs/heads/codex/orion-team-run-20260924/research_a_orion_anytime/handoff_20260924/orion_team_run_20260924.zip

仓库为私有仓库，下载需要浏览器登录已获得 yellkiin/model_competition 读取权限的 GitHub 账号。未登录或未获权限可能显示404；此时请报告实际情况，让我联系仓库拥有者给予账号读取权限，不要修改仓库可见性。也可打开包文件页后点击下载：https://github.com/yellkiin/model_competition/blob/codex/orion-team-run-20260924/research_a_orion_anytime/handoff_20260924/orion_team_run_20260924.zip

先下载并解压到独立新目录，只用该包内的修复代码。运行包基于 main152e023，已修复四处语句拼接残留和空 inputs.py。不要直接用未修复的旧 main，不要从其他分支混入 Python 文件。包内第一台机器的 pilot 结果只作记录，不能复制其 gate 跳过本机 pilot。

请先读取包内 research_a_orion_anytime/handoff_20260924/README.md，确定解压目录、已有 A 题官方附件目录和 Python。官方完整 A 附件由本机已有文件提供，必要时只解压本机已有的 A题.zip。-Official 必须指向直接包含 code 目录和 data/config.txt、case_*.json 的附件根目录。pilot 也需要部分奇数图，所以准备完整 A 附件。运行包不提供官方图/配置/评估器；当前 inputs 只读现有文件，缺失或 LFS 指针会报错，不会自动恢复输入。不要下载其他题目，不恢复或研究 E 题。已经能确定的路径和环境不要重复询问；缺少实际附件位置或解释器时，只请求确实缺少的信息。

默认使用 D:\python\python.exe，64 位 CPython 3.12.x，CPU-only、标准库，无需 pip 安装依赖。先在运行包根目录执行下面唯一需要的环境探测：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a_orion_anytime\setup_windows.ps1
```

若默认解释器不存在，使用本机已有的符合要求的独立解释器，并向 setup 和启动命令都传入 -Python '实际路径'；不替换其他工作的环境。根据实际 probe 输出选择 Workers：可用内存至少 8 GiB 时可用 2；4–8 GiB 时用 1；低于 4 GiB 拒绝并报告需要释放内存或更换机器。不要运行 smoke、哈希/文件指纹/checksum 测试、pytest、unittest、全仓审计、benchmark 或任何无关前置测试。不要安装 CUDA、torch、WSL 或 Conda。

启动前先检查这个输出目录是否已有本次活动进程，避免重复启动。用新的独立输出目录，不覆盖旧实验。把下例官方附件路径替换为本机真实路径；如果 probe 推荐 2，则使用 -Workers 2：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a_orion_anytime\run_team_shard.ps1 -ShardIndex 1 -Official 'D:\A题附件\通用神经网络处理器下的多核调度问题  附件' -Workers 1
```

启动器默认总片数 2，输出 research_a_orion_anytime\runs\team_day01_shard1。它封装 experiments.ps1 -Stage auto，经 watchdog/campaign 执行本机 pilot→质量门槛→容量准入→正式覆盖→改进→Q3 同方案无 L2 对照。pilot 和容量准入通过后继续正式任务，不用再次询问。不要传 -Gate 来复用其他机器的准入文件，也不要另起 research_day 或 campaign 绕过监督。

预算固定普通作业 30 秒、最多 24 次评估、大图 180 秒、refine 30 秒；覆盖阶段仍按原程序的预算前缀执行。保持图数、1–5 核配置、质量/容量阈值及官方合法性检查。两分片运行不额外做 mechanisms/sensitivity。

统一团队截止是 2026-09-24T17:43:48.3137853+00:00，即北京时间 2026-09-25 01:43:48.3137853。主计算固定提前一小时停止：2026-09-24T16:43:48.3137853+00:00，即北京时间 2026-09-25 00:43:48.3137853，预留结果回传和合并时间。新启动、新输出目录或重试都不得重置此窗口。保留启动器写出的 research_day_clock.json 和绝对截止监督；监督只作用于本次启动的进程树。保持机器通电、不休眠，不关闭监督进程。

第一台机器已有真实 pilot：48 主记录、18 缓存对照、9 旧方案对照均有效，质量门槛通过。但 Workers=1 的全量容量上界 51,685 秒（约14.36小时）超过当时剩余约10.53小时，因此采用两片。第一台已于北京时间2026-09-24 14:23启动片0，容量准入通过。按第一台校准，片0约6小时46分27秒，片1约8小时4分58秒；这是第一台机器的估计，不能直接当作本机容量结论。本机一定要实际跑 pilot。若本机容量拒绝，报告真实上界、剩余秒数、所需分片数、实际机器信息，并请求团队协调缺失机器，不修改阈值、删图、缩核或自行改分片总数。

运行后持续检查实际进程和以下文件：输出根 team_status.json、research_day_clock.json，以及 team_status.json 的 stdout/stderr 字段指向的本次启动日志（文件名形如 launcher_stdout_yyyyMMdd_HHmmss.txt 和 launcher_stderr_yyyyMMdd_HHmmss.txt）；auto 下 campaign.json、gate.json、capacity_admission.json、watchdog_status.json、formal_status.json、实际生成的 progress/summary 和报告；异常时读取各作业中实际存在的 worker_error.json、stderr.txt。不要只报告启动成功就结束。状态不变时保持安静，在 pilot 通过、质量/容量失败、重要故障、需要用户动作、本片完成或到达停止时间时汇报真实信息。程序可能正在长作业中，不能只凭日志暂时不刷新就判定卡死。

不要修改官方图、config、评估器或合法性检查，不动其他实验，不自动提交 GitHub、不合并 PR、不上传赛事平台。保留 AI 辅助和实际运行记录。出现 Python 源码问题时先把具体报错发给协调人，由团队统一版本；任何必要 Python 修复都必须只发生在 research_a_orion_anytime 内，修改后用新输出目录、同预算重新跑本机 pilot，旧失败保留，不能混不同源码的成绩。

本片结束后，核对正式 50 图预期 **700 条主记录和250条Q3同方案缓存对照** 的有效数、失败数和缺失键。单片报告 formal_complete=false 可能正常，整队100图尚需另一片合并；不能把单片或 pilot 称为完整100图。报告本片图数、主/缓存记录数、失败、Makespan/DDR/Spill、阶段求解秒数和预算，注明这是分片结果。未完成明确写未完成。

本片完成，或到达主计算停止时间并确认实验进程退出后，在运行包根目录打包实际 campaign 输出：

```powershell
& 'D:\python\python.exe' -m research_a_orion_anytime.transfer pack --root 'research_a_orion_anytime\runs\team_day01_shard1\auto' --zip 'research_a_orion_anytime\runs\team_day01_shard1_results.zip'
```

如果使用其他 Python，请替换命令开头路径。这个包不含官方输入；不要另打包官方附件。把生成的 ZIP 交给我发送协调人，同时提供输出根的 team_status.json、research_day_clock.json 及 team_status.json 指向的 stdout/stderr 日志；这些文件在 auto 外，需要一并回传。若连 auto/campaign.json 都没有生成，则保留并发回已有日志与报错，不伪造结果包。

异常需回传 team_status.json 及其中指向的 stdout/stderr 日志、gate.json、capacity_admission.json、watchdog_status.json 和各异常作业中实际存在的 worker_error.json/stderr.txt，以及 Python/平台、CPU数、可用内存、Workers、开始时间。正常完成也须及时回传，协调人在统一截止前汇总两片的1,400主记录和500缓存对照，再确认正式100图是否完整。


已知恢复限制：请保持监督进程连续运行。现有 formal 入口在恢复时仍按整片全部作业重新做容量准入，尚未扣除已完成记录；因此较晚中断后可能因剩余时间不足而拒绝恢复，即使已有很多结果。若中断，请保留原 Gate 有无、Workers、Official、Out 等参数，先报告协调人；不能承诺任意时点可断点续跑，也不能绕过容量门槛。此限制不影响目前连续运行和首次启动。
