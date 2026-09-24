# 复制给本地 Agent：ORION Anytime 的完整执行与发布任务

你在Windows本机的yellkiin/model_competition仓库工作。本轮使用完整的`research_a_orion_anytime`代码包，不依赖旧PR#14。请实际执行，不要只重述计划；所有完成、失败与PR地址都必须来自真实输出。

## 一、保护范围与目标

目标是最小化官方Makespan、提高加速比；相同Makespan才比较额外搬运。只改变我方方案、算法与独立输出，不能改题目、100图内容、config、原Step1/2/3和原评估器。不得改FIFO、引入重算/融合算子、使用模拟成绩替代官方结果。保留其他AI工作区、旧结果、本地ZIP及用户改动，不force/reset/clean，不自动merge或上传赛事。

先读本目录README、EXPERIMENT_PLAN和MEASURED_VALIDATION。特别核对SOURCE_MANIFEST：云端完整主pilot与之后的非默认参数/恢复核验修复不是同一哈希，不能复用旧gate启动交付版本的formal；你必须在本机重做pilot。文档里本次云端实测是Linux/CPython3.13.5，不是Windows或100图成绩。源码可用性与GitHub远端是否真正创建PR必须分开。

## 二、放置完整代码并沿用环境

完整包里所有顶层文件都要到位，尤其`core.py, strategies.py, engine.py, solver.py, supervisor.py, campaign.py, reporting.py, watchdog.py, inputs.py, transfer.py, worker.py`。`run.py`是继承的环境探测/旧策略回归支持，不用它启动新版正式批次。

参考解释器是`D:\python\python.exe`、64位Python3.12.5。先运行setup_windows.ps1；合适就直接用，不新建Conda/WSL、不安装CUDA/torch。其他电脑不符合条件时，你自行找现有合适解释器或配置独立的64位3.12.x，再用-Python传入，不修改正在运行实验的环境。本机评估进程Workers与题目NPU核数n是两个参数；Workers=1仍要跑题定1–5核配置。CPU-only；低于8GiB可用内存用1个评估进程，达到8GiB才用2。低于4GiB时按脚本保守拒绝策略处理。

不要重做全仓库审计或其他题恢复。只需要本轮A输入。优先使用现有仓库根目录A题.zip；别处有ZIP则传-Archive；没有才用-RestoreInputs让程序按需拉取A的LFS。不要全量git lfs pull。

## 三、实际启动：总研究日最多12小时

在仓库根目录执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a_orion_anytime\setup_windows.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a_orion_anytime\research_day.ps1 `
  -Workers 2 -Out 'research_a_orion_anytime\runs\day01' -RestoreInputs
```

这条命令先pilot，门槛通过才准入100图，先完成覆盖，再用剩余时间做改进，最后Q3同方案无L2配对和独立核验。主流程最多11小时，剩余时间跑24作业消融与044/083缓存九格的固定方案/重新优化对照。研究日时钟写入文件；同根续跑不能重置截止时刻。监控真实进程与日志，不同时手动启动重复阶段。

默认pilot小作业30秒、评估帽24，大图180秒。先使用已验证默认值；需要研究更宽预算时，在**另一个明确标记的实验目录**使用-Seconds60/-Calls64/-LargeSeconds240/-RefineSeconds45，并仍遵守团队12小时总时钟，不把额外全天实验冒充同一半天。扩大预算不等于更优，按实际轨迹/等预算对照判断。

质量门槛失败：保留gate.json和全部失败记录，停止全量；读matched与prefix比较，定位构造或候选饥饿，不得降低阈值。容量门槛失败：不启动注定超预算的全量，读capacity_admission.json，需要时分片到其他机器。不能删除大图或缩减必需核数来伪造成功。

## 四、多机

各机相同源码/原配置，并有本机pilot时间校准。总分片数相同，索引不同。例如机器0执行-Shards2 -ShardIndex0、机器1执行-Shards2 -ShardIndex1，各自独立Out。分片按案例索引，不人工按成绩选图。不同CPU的求解秒数不直接比较；同机器内用相同worker数的配对结果说明方法收益。

多机不重复做额外消融/网格，合并后在团队截止前集中做。用transfer pack/unpack迁移auto结果根，不直接移动后让JSON中的旧绝对路径失效。汇总用campaign collect --indices全部final_index；必须完整1400主记录与500个Q3同方案对照，冲突重复记录报错，不择优。

## 五、错误与改进的执行规则

异常先看具体job的stderr.txt、worker_error.json、progress.json，使用inspect_results.ps1。路径/编码/进程启动错误只做最小兼容修复；改了Python源码就新目录重做pilot，不能把旧源码记录混入新版本。

超时后已有incumbent仍是有效解，未完成候选不是有效评估；deadline_without_incumbent必须记失败。内存不足先改1进程（新预算/输出策略），不要改变评估算法。完整执行依赖环必须修我方方案；不能屏蔽原校验。低收益图查看真实关键同步、分区/Spill流量、候选族attempts和认证U/L，再决定增加候选或小范围重优化。U/L大只表明证书松，不代表一定有同等幅度可改善。

不要用Q2独立最优结果替代Q3选中方案的无L2配对。网格结果是非官方参数实验，不能混入固定config下100图成绩。所有统计逐例求比再平均。

## 六、真正提交完整PR（用户已要求）

本次云端会话没有GitHub写入动作，不能假装已经新建完整PR。你在本地有合法GitHub授权时，请用本目录publish_pr.ps1实际发布。它新建独立worktree与分支，仅复制本目录源码/文档，显式排除runs/输入/文献，不影响其他AI，不force push，不merge。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a_orion_anytime\publish_pr.ps1 `
  -RepositoryRoot (Get-Location).Path
```

GitHub CLI仅发布需要，运行算法不需要。若gh未安装，配置本机gh；若未登录，请用户在本机交互式gh auth login，绝不索要/打印令牌。分支重名时用新的-Branch和-Worktree，不覆盖旧分支。发布成功后读取命令返回的实际PR URL，并检查文件清单包含完整求解链；不要复用旧#14地址声称完成。无法发布时如实给出分支/提交实际状态，保留完整补丁，不伪造PR编号。

源码PR可以先创建供审查，实验结果不自动上传。真实本地修复经过验证后可提交到该独立分支；不提交官方数据、完整文献、日志大包与其他题文件。

## 七、最终交付给用户

给出真实PR URL或具体发布阻碍、源码版本、解释器/机器/进程数、研究日起止/总壁钟、输出根。读取formal_complete与逐配置缺失清单，报告三问1–5核均值/最差图/新增搬运、Q3同方案缓存比与命中率、各阶段解生成时间和预算收益。对Windows与云端差异如实解释。未完成100图就明确写未完成，不用子集替代。

结果压缩只包含必要方案、响应、CSV、报告和日志；不附官方输入ZIP或文献PDF。特别区分：旧3次策略、本轮限时冷启动、额外30秒续优化、非默认缓存网格，不能跨这些实验手工拼成“统一固定算法的成绩”。

多机统一截止补充：以第一台机器启动时刻确定一个共同UTC截止时刻，所有机器在首次research_day调用传同一个`-DeadlineUtc`字符串。不能在每台机器各自重新算12小时而延长团队总周期。既有research_day_clock的截止时刻不允许重置。
