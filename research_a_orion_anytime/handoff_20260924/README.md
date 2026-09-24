# ORION Anytime A 题：第二台机器运行说明

请下载本次团队运行包：[直接下载 ZIP](https://github.com/yellkiin/model_competition/raw/refs/heads/codex/orion-team-run-20260924/research_a_orion_anytime/handoff_20260924/orion_team_run_20260924.zip)。也可打开[运行包文件页](https://github.com/yellkiin/model_competition/blob/codex/orion-team-run-20260924/research_a_orion_anytime/handoff_20260924/orion_team_run_20260924.zip)后点击下载。这份包包含本轮修复后的 ORION 代码、团队分片启动器，以及供查看的部分 pilot 结果。请把压缩包解压到一个新目录，例如 `D:\orion_team`，进入其中直接包含 `research_a_orion_anytime` 文件夹的目录后运行命令。

仓库是私有仓库。队友须在浏览器登录已经获得 `yellkiin/model_competition` 读取权限的 GitHub 账号；未登录或未获权限时可能显示 404。请由仓库拥有者给队友的 GitHub 账号开放读取权限，保持仓库私有。团队分支为 `codex/orion-team-run-20260924`，此说明的[在线页面](https://github.com/yellkiin/model_competition/blob/codex/orion-team-run-20260924/research_a_orion_anytime/handoff_20260924/README.md)可用于转发。

请使用本次团队运行包。此前 `main` 提交 `152e023` 中有四处语句拼接残留和一个空的 `inputs.py`；本轮已做必要启动修复，直接下载原 `main` 不能保证得到这份修复代码。包内 pilot 结果属于第一台机器，只作记录，第二台机器仍须自己跑 pilot。

## 1. 准备已有 A 题官方附件

运行包不包含官方图、配置、官方评估器或其他题目附件。请使用自己已有的完整 A 题附件；如只有已有的 `A题.zip`，先解压到独立目录。传给 `-Official` 的目录应直接包含：

```text
实际 A 题附件目录\
  code\                  官方代码目录
  data\
    config.txt
    case_001.json
    ...
    case_100.json
```

第二分片的正式任务是偶数编号的 50 张图，即 `case_002`、`case_004`……`case_100`。pilot 还使用开发图和压力图，所以仍请准备完整 A 附件。当前输入入口只读取现有文件；文件缺失或只有 Git LFS 指针时会报错，不会自动恢复输入。无需下载其他题目，不修改官方文件。

## 2. 探测 Python 和可用内存

默认解释器为 `D:\python\python.exe`，要求 Windows、64 位 CPython 3.12.x，仅使用 CPU 和 Python 标准库。没有此路径时，可使用另一份符合要求的独立解释器，在下面两条命令中都增加 `-Python '实际解释器路径'`。不要替换正在使用的 Python 环境。

在运行包根目录打开 PowerShell，执行唯一需要的环境探测：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a_orion_anytime\setup_windows.ps1
```

按输出的 `recommended_workers` 设置并发：可用内存至少 8 GiB 时可用 `Workers=2`；4–8 GiB 用 `Workers=1`；低于 4 GiB 会拒绝启动，需要释放内存或换机器。这里看的是当时可用内存，不是装机内存容量。不需要安装 CUDA、torch、WSL 或 Conda，不运行额外性能测试。

## 3. 启动第二分片

把以下命令中的官方附件路径替换为本机真实路径。以下使用单 worker；如果上一步推荐 2，则改成 `-Workers 2`：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a_orion_anytime\run_team_shard.ps1 -ShardIndex 1 -Official 'D:\A题附件\通用神经网络处理器下的多核调度问题  附件' -Workers 1
```

总分片数固定为 2，第一台机器运行片 0，队友运行片 1。第一台机器已于北京时间 2026-09-24 14:23 启动片 0，容量准入通过。队友输出默认写入新的 `research_a_orion_anytime\runs\team_day01_shard1`，其中 `auto` 为实际 campaign 结果目录。不要在已有进程运行时重复启动，也不要覆盖旧结果。

启动器封装 `experiments.ps1 -Stage auto`，通过 watchdog 进入 campaign，在本机依次运行 pilot、质量门槛、容量准入，然后自动进入正式覆盖、改进和 Q3 同方案无 L2 对照。pilot 和容量均通过后不需要再次确认。不要传入第一台机器的 `gate.json` 来跳过本机 pilot。

固定默认预算为普通作业 30 秒、最多 24 次评估、大图 180 秒、改进阶段 30 秒。覆盖阶段内部仍按原程序的预算前缀策略执行。不要修改预算、质量/容量门槛、图数或核数来凑完成率。本次两分片只做既定正式流程，不额外运行 mechanisms 或 sensitivity。

两台机器共用绝对截止，重启或换输出目录不会获得新的 12 小时：

| 时间用途 | UTC | 北京时间 |
|---|---|---|
| 主计算停止 | 2026-09-24 16:43:48.3137853 | 2026-09-25 00:43:48.3137853 |
| 团队最终截止 | 2026-09-24 17:43:48.3137853 | 2026-09-25 01:43:48.3137853 |

主计算提前一小时停止，为传回、合并和汇总留时间。启动器保存 `research_day_clock.json` 并监督本次启动的进程树。不要修改日期、关闭截止监督或绕过启动器。计算期间请保持电脑通电、不休眠，并保留 PowerShell 监督进程。

## 4. 看进度与处理拒绝

可以在另一个 PowerShell 窗口读取日志：

```powershell
$S = Get-Content -LiteralPath '.\research_a_orion_anytime\runs\team_day01_shard1\team_status.json' -Raw -Encoding UTF8 | ConvertFrom-Json
Get-Content -LiteralPath $S.stdout -Tail 60 -Wait
```

`team_status.json` 中的 `stdout` 和 `stderr` 指向本次启动日志，文件名形如 `launcher_stdout_yyyyMMdd_HHmmss.txt` 和 `launcher_stderr_yyyyMMdd_HHmmss.txt`。也要查看 `auto` 内实际生成的 `gate.json`、`capacity_admission.json`、`watchdog_status.json`、`formal_status.json`、进度文件、逐作业 summary 和最终报告。日志暂时不刷新不能单独证明程序失败；结合进程和文件更新时间判断。

第一台机器的 pilot 已通过：48 条主记录、18 条同方案缓存对照和 9 条旧方案对照均有效。同预算新旧比的几何平均为 1.1103，三个问题的预算前缀比几何平均分别为 1.2389、1.0850、1.0964。全量单机容量上界为 51,685 秒，超过当时剩余 37,895 秒，因此改为两台机器分片。

按第一台机器的校准，片 0 约需 6 小时 46 分 27 秒，片 1 约需 8 小时 4 分 58 秒。这只是第一台机器的估计，不能当作第二台的完成承诺；第二台机器以自身 pilot 和容量准入结果为准，越晚启动，可用计算时间越少。

如果质量或容量拒绝，请保留失败记录，发回 `team_status.json` 及其中指向的 stdout/stderr 日志、`gate.json`、`capacity_admission.json`、`watchdog_status.json` 和各异常作业中实际存在的 `worker_error.json` / `stderr.txt`。同时提供 Python/平台信息、逻辑 CPU 数、可用内存、实际 Workers 和开始时间。容量不足时要报告实际所需分片数与缺少的机器条件，不降低门槛、不删图、不缩减核数，不自行改变团队分片总数。源码问题先联系协调人；修改 Python 后必须保持两台源码一致，并以新输出目录、同预算重新跑 pilot，不能拼接不同版本成绩。

## 5. 停止后打包并发回

本片完成，或到达主计算停止时间并确认实验进程已退出后，在运行包根目录执行：

```powershell
& 'D:\python\python.exe' -m research_a_orion_anytime.transfer pack --root 'research_a_orion_anytime\runs\team_day01_shard1\auto' --zip 'research_a_orion_anytime\runs\team_day01_shard1_results.zip'
```

如使用其他 Python，替换命令开头的解释器路径。此命令打包 campaign 输出，不包含官方输入。请把生成的 `team_day01_shard1_results.zip` 发回协调人，并一并发回该输出根目录中的 `team_status.json`、`research_day_clock.json` 以及 `team_status.json` 指向的 stdout/stderr 日志；这些外层文件不在上述 `auto` 结果包中。若尚未生成 `auto\campaign.json` 就失败，打包命令会拒绝，此时直接发回已有启动日志和报错即可。

本片完成目标为 **50 图、700 条主记录、250 条 Q3 同方案缓存对照**，且本片预期键无缺失、记录有效。单片报告的 `formal_complete=false` 可以是正常现象，因为它不包含另一片；不能仅凭进程退出或一个状态字段宣布整队完成。整队由协调人收齐两片、合并核对 **100 图、1,400 条主记录、500 条缓存对照** 后确认。未完成就明确写出完成数量、失败和缺失，不报告完整 100 图成绩。

不要运行 smoke、哈希/指纹/checksum 测试、pytest、unittest、全仓审计或 benchmark；保留官方评估和合法性检查；不要自动提交结果到赛事平台或合并 GitHub PR。希望交给本机 AI 执行时，把同目录 `TEAMMATE_PROMPT.md` 的全文发给它即可。


已知恢复限制：请保持监督进程连续运行。现有 formal 入口在恢复时仍按整片全部作业重新做容量准入，尚未扣除已完成记录；因此较晚中断后可能因剩余时间不足而拒绝恢复，即使已有很多结果。若中断，请保留原 Gate 有无、Workers、Official、Out 等参数，先报告协调人；不能承诺任意时点可断点续跑，也不能绕过容量门槛。此限制不影响目前连续运行和首次启动。

## 2026-09-24 快速迭代补充

用户要求改进阶段结束先发阶段结果，同时原进程继续缓存配对和验证。运行中的机器请采用新增的 [统一阶段交接规范](ITERATION_HANDOFF.md) 和 [队友补充提示词](TEAMMATE_ITERATION_PROMPT.md)；无需重新部署或覆盖当前代码。两台发布路径分别为 research_a_orion_anytime/team_results/day01/shard_0 和 shard_1，统一 refinement_complete 与 final 子目录。本补充优先于下文停止后才打包的旧说明；活动auto不能直接全量打包，先按新规范冻结已完成阶段并重定位路径。
