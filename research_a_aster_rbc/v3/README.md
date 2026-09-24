# ASTER V3：完整源码与直接 best5 入口

版本：`aster-v3-release-affinity-4.1`。PR #18 已补齐 `quality.py`，不再需要从旧临时包补文件。`quality.py` 是本次根据实际调用接口补写并实跑的新实现；不追认先前未交付模块的测试声明。

只输出 `node_to_subgraph`、`core_schedules`；原图、cycles、size、配置、Step1/2/3 和官方评估函数均不修改。Python 标准库、CPU-only。

## 本轮直接运行

在包含 PR #18 最新提交的仓库根目录执行：

```powershell
& 'D:\python\python.exe' -X utf8 -u -m research_a_aster_rbc.v3.best5 --workers 2 --wall-seconds 900
```

这是固定 **5 核、三问、full/best、最多8次官方调用** 的单轮验证，不另跑 fast、基线算法矩阵、消融、种子或预算网格。`fast` 只记录同一次 full 求解中的首候选，不增加实验作业。每个多核作业90秒、单次评估45秒；Q3把同方案无Cache回放计入8次。原始整图单核分母单独评一次，最多120秒，仍计入总窗口。

默认12图：003/007/012/020/028/035/047/056/065/076/088/094。这些图没有参与本轮构造参数开发，不宣称它们未参与其他 agent 的既往研究。到15分钟窗口就保留完整/partial/失败/未开始状态并汇报，不自动100图或第二轮。

`--official-dir` 可指定包含 `code/`、`data/` 的 A 附件目录。缺少输入只恢复 A 题；不恢复其他题。优先现有 `D:\python\python.exe`，否则用已有 Python 3.10+ 的真实路径，不安装 CUDA、Torch、Conda 或优化器。其他实验占用资源时改 `--workers 1`；本机 workers 不等于模拟核数。

## 算法变化

- 补齐覆盖/唯一分核/商图与核内顺序检查、通信路径下界、评分和有界迁移/合并。官方完整合法性检查保留。
- 移入 FRONTIER 的生产者完成时刻分核与导出释放细化；Q2/Q3 不把整个同核块当作不可提前导出的屏障。
- 共享输入图加入至多96个深度桶上的 Tensor 集合感知 minimax 阶段DP，考虑私有只读工作集风险；有限地比较两种IO权重。DP的精确性仅限其代理。
- 保留 V3 首构造，再比较定向增强候选；只接受真实评估不劣的 incumbent。宽图不因为增加了新机制而强制改用流水。
- 保留未打包的阶段顺序候选，避免同层打包把可提前释放的工作重新捆在一起。
- 新 `best5.py` 与修复后的 `run.py` 正确定位两级上方仓库根目录；PowerShell脚本同样修正路径。

## 运行保护与输出

写入 `research_a_aster_rbc/v3/runs/best5_<time>_<pid>/`。输出包括 manifest、实际request、result、逐次方案/官方响应、summary.csv、coverage.json、REPORT.md、run_receipt.json。

`best5 --resume --out <原目录>` 仅继续未开始的作业，要求版本、协议、配置文本一致；不覆盖既有失败、partial、running或成功目录。用户未明确允许时，不自动续跑。多机使用 `--shards M --shard i`，独立输出、0-based分片，禁止逐例从重复结果中挑最低周期。不同硬件的求解秒数分开报告。

评估进程可被超时终止；Python构造、写盘和收尾不是抢占式操作，实际停止可能略晚于名义窗口。程序不以达到4.5或5倍作为停止条件，也不保证每个图或所有图均达到5倍。

## 证据与边界

本次冻结版本六张真实图、三问五核与原始单核共24作业全部完成，102次官方调用成功，第三问6组同方案回放完整；本机实际146.729秒。六图 best 算术均值为3.963749 / 4.688121 / 4.815077。**六图均值未达5倍，更不是100图成绩。** Windows尚未实机验证。

详见 `LOCAL_MEASURED.md`、`EXPERIMENT_PLAN.md`、`LOCAL_AGENT_PROMPT.md`。原有 `run` 保留可变核数入口供最终题面覆盖；本轮只使用best5快速判断效果，不启动全量。最终仍需补齐题面要求的全部图、核数与Cache参数分析。
