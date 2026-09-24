# ORION Memory：局部边界与驻留修复

实现位于独立目录，导入现有 `research_a_orion_anytime`，不修改公共 solver/campaign、官方输入/config/评估器或其他研究线。`plugin.py` 实现 COMMON.md 的 `propose(...)` 接口；这是可组合的候选模块，不是三线最终求解器。

**本轮实测不支持用它替换完整 Anytime。** 六图暖启动严格对照 5 胜/15 平/16 负；冷启动 34 对中 1 胜/8 平/25 负。保留局部机制收益和全部负面记录，尚未通过原定 005/051/073/090/092 优先样本门槛，不扩大到 100 图。

## 文件

`plugin.py` 是纯候选生成器；`run.py` 是旧/新、冷/暖启动独立适配器；`analyze.py` 从原响应读 COPY 排队、计算重叠和张量集合变化；`complete_pending.py` 仅在新总截止下补充从未启动的作业；`plot_curves.py` 画实际保存的阶梯曲线。求解只需 Python 标准库，绘图才需现有 Matplotlib。

方法与文献见 `METHOD.md`、`LITERATURE.md`。实测、失败、证据范围见 `results/memory_v13_six_graphs/REPORT.md`。完整原响应包位置和目录见同目录 `EVIDENCE_INDEX.json`。Windows 后续定向命令见 `LOCAL_AGENT_PROMPT.md`。

## 启动

在仓库根目录，先准备目标原图以及完整的官方附件 `code/`、原 `config.txt`。PR25 已合并；旧工作树仍可只取得 `codex/a-data-plain-json-20260924` 的所需输入而保留研发分支。路径“问题”和“附件”之间有两个空格。大文件使用官方 `tools/restore_a_inputs.py` 还原，不手抄 base64，不将截断内容当成图。

```text
python -m research_a_orion_track_memory.run --cases 5 51 73 90 92 83 --questions 1 2 3 --cores 2 5 --seconds 300 --max-evaluations 24 --total-seconds 3600 --workers auto --modes warm_start --seed-index memory_day01_seeds.json --out research_a_orion_track_memory/results/priority_warm_local
```

这是**下一轮本地命令，不是本轮已运行记录**。`memory_day01_seeds.json` 必须指向两片 final 原包中实际选中、未修改的作业和原配置，列出覆盖、失败重试、续优化完整种子成本。只有原响应与当前官方重评的 Makespan、搬运分解一致才接收；不要把汇总表上的分数当成一个方案。

所有方法支持 `--cases`、`--questions`、`--cores`、`--seconds`、`--workers auto`、`--shards` 和 `--shard-index`。使用三机时三台给出相同排序后完整小清单，分别 index=0/1/2；不要三份各跑完整百图。Q1/Q2 的一核是固定原始基准，Q3 一核仍可优化并配对；正式后续 1–5 核曲线要求未取消。

## 实测环境与范围

本次实际为 Linux / CPython 3.13.5 / CPU-only；主对照请求 workers=2，同机 4 核 CPU 配额、4 GiB 内存。交付适配器另在真实 044 上运行固定原始一核、外部种子、auto workers，28 条主记录与 10 条配对均有效；**不是 Windows 3.12 实测**。

主实验 `memory-1.3` + 当时 `adapter-1.3`，144 条方案有效、48 条同方案无 L2 有效。主 CSV 后用 1.4 汇总器重导出，原表保留；不得把重导出叫作以新适配器重跑。1.4 补记进程启动偏移、种子重评时间、正式一核语义、外部种子及从未启动作业恢复。

本地 ORION 依赖由连接器所读源码函数体暂存，注释/文档字符串有缩减，并非字节一致的 Git checkout；双方使用同一依赖副本，官方评估器由原附件完整取得且未修改。PR 中不提交该依赖副本。目标图与 day01 原包的完整传输尚缺，所以不能声称已重放 092 的获胜候选。详见证据索引。
