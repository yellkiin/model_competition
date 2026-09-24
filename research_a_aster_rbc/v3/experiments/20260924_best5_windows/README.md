> 这是用户授权发布的实验记录包。运行源码固定为 [PR #18 的 cd24013](https://github.com/yellkiin/model_competition/tree/cd24013cb8dfc29d847df5c4caea5222923402a7/research_a_aster_rbc/v3)，不是本记录 PR 的 Git 基底。原始方案、官方响应、时间线与失败日志仅保留在源运行 `best5_20260924T095317_031044_61144`，未随 PR 上传。合法性、同方案 JSON 相等和零证据问题是本地核对结论；仅凭本包不能重新验证原始响应或重建完整时间线。本机绝对路径和命令是历史记录，其他机器必须调整输入路径。

# PR #18 单轮实测结论

本轮实际运行 **645.078 秒（10 分 45.078 秒）**，程序提前正常结束，未续跑、未补齐、未扩大 100 图或开始第二轮。三问有效样本均值均未达到 4.5 或 5 倍。

版本 `aster-v3-release-affinity-4.1`；PR 当前源码提交 `cd24013cb8dfc29d847df5c4caea5222923402a7`。默认 12 图、三问、5 核、full/best，fast 取同一次 full 的首候选，未另跑。

## 加速比与覆盖

加速比为本轮原始整图单核 T1 / 本轮合法 best 周期；仅 10 图有有效分母，未删除低分图或借用旧分母。

| 小问 | AM | GM | 中位数 | 最低值 | >5 倍 | 有效 n/计划 |
|---|---:|---:|---:|---:|---:|---:|
| Q1 | 3.191400 | 2.838940 | 3.004376 | 1.341165 | 1 | 10/12 |
| Q2 | 3.330496 | 3.063566 | 3.032015 | 1.855384 | 1 | 10/12 |
| Q3 | 3.360775 | 3.093592 | 3.054405 | 1.855242 | 1 | 10/12 |

三个小问超过 5 倍的均仅 case_007：5.101017× / 5.138552× / 5.138552×；不能写成平均超过 5 倍。

| 范围 | 计划 | complete | partial | failed | not_started | running |
|---|---:|---:|---:|---:|---:|---:|
| Q0 | 12 | 10 | 0 | 2 | 0 | 0 |
| Q1 | 12 | 11 | 0 | 1 | 0 | 0 |
| Q2 | 12 | 12 | 0 | 0 | 0 | 0 |
| Q3 | 12 | 12 | 0 | 0 | 0 | 0 |

合计 48 项全尝试，45 complete、3 failed；部分完成、未开始、遗留 running 均 0。失败为 028/076 原图单核官方评估达到 120 秒上限，以及 076 Q1 两次官方评估耗尽 90 秒作业窗口。028 三问、076 Q2/Q3 周期保留，但缺 T1 的加速比空白；076 Q1 无合法方案，周期也空白。没有运行兼容性错误，未修改实验实现。

官方实际调用 **191 次 = 184 ok + 7 timeout**；另 43 个 bound_pruned 候选未作为官方调用。官方调用墙钟累计 1150.938 秒、各作业 solve 累计 1252.269 秒，均是并发累计，不是整轮墙钟，也不是各 variant 的独立求解时间。逐例额外搬运/Spill、求解秒数、逐次官方耗时见详细报告和 派生表（见 EVIDENCE.md）。

## 实测改善与低尾

相同案例、5 核、小问、题定配置和 T1 下，旧 PR16 首次完整结果可作 10 图逐例参考：003/007/047/056/065 三问均更快；035 的 Q2/Q3 更快、Q1 持平；088 的 Q1 更快而 Q2/Q3 更慢；020 持平；012/094 三问更慢。旧预算为 120 秒/job、45 秒/call、6 calls，新为 90/45/8，故只作已测结果参考，不作等预算因果结论。

低尾仍明显：Q1 的 047 仅 1.341165×，035/056/088 约 1.73–1.85×；Q2/Q3 的 035 最低约 1.855×。012/094 的相对回退也需保留，不能将旧版本更好周期拼进本轮。

官方时序的局部证据：003 的多配方 best 改善伴随更均衡的计算负载，同时 Task 和搬运反而增加；007 保持计算负载均衡、缩短主要计算 Pipe 的非执行区间，Q2/Q3 却增加 2,150,400 字节 Spill；035 的主核结束显著晚于其他核。这些支持进一步检查负载分配、Task 边界、重复读取、释放时序与驻留代价，尚不足以作完整因果归因，不能默认增加搜索预算。详见 [DIAGNOSTICS.md](DIAGNOSTICS.md)。

## 同方案 Cache 与证据范围

最终相同 best_plan 的无 Cache Q2 / 有 Cache Q3 回放 **12/12 完整**，周期比 GM=1.018897；8 有收益、3 持平、1 略退。035 为同方案 Q2=91400、Q3=91401，虽有约 2.08% 命中字节率仍多 1 周期。此比值未使用分别优化的 Q2/Q3 最好方案。

原始官方响应核对问题和 bound_violation 均 0；下界仍有语义适用条件，未称认证最优性缺口。没有新 100 图结果，**本轮不能声称整体超过旧论文或 PR16**。原生 summary.csv 有 70 条多核变体记录，缺 076 Q1 的 fast/best 两行；派生表（见 EVIDENCE.md） 显式保留其空记录。重复为 0，详见 [summary_structure.json](summary_structure.json)。

## 实际执行与本地文件

解释器：`C:\Program Files\Python312\python.exe`（Python 3.12.8）。机器 `Nuggets`，13th Gen Intel(R) Core(TM) i7-13650HX，20 逻辑处理器，RAM 31.81 GiB。workers=2 为本机并发；题目模拟为 5 核。

实际工作目录：`C:\Users\LEGION\Documents\ChatGPT\华为杯\model_competition_aster_v3_pr18`。输出目录：`C:\Users\LEGION\Documents\ChatGPT\华为杯\model_competition_aster_v3_pr18\research_a_aster_rbc\v3\runs\best5_20260924T095317_031044_61144`。

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
& 'C:\Program Files\Python312\python.exe' -X utf8 -u -m research_a_aster_rbc.v3.best5 --workers 2 --wall-seconds 900 --official-dir 'C:\Users\LEGION\Documents\ChatGPT\华为杯\model_competition\题目\A题\通用神经网络处理器下的多核调度问题  附件'
```

源码取得：Git 网络连接未能完成，通过 GitHub 连接器一次取得指定 PR 提交下完整 23 个 V3 文件（包含 quality.py），未使用缺文件旧版本或替代模块。独立稀疏 worktree 的 Git 基底为缓存 4012819，只用于隔离；实际 V3 源码来源是上面的 cd24013。官方附件只读复用，未改原图、cycles、size、配置或 Step1/2/3。完整来源见 [execution_context.json](execution_context.json)。

[summary.csv](summary.csv) · [coverage.json](coverage.json) · [manifest.json](manifest.json) · [run_receipt.json](run_receipt.json) · [详细实测报告](MEASURED_REPORT.md) · [派生表与字段说明](EVIDENCE.md)

全部方案、原始官方响应和失败轨迹保留本地。没有冒烟、pytest/unittest、哈希/文件指纹、全仓审计、环境性能基准或额外实验；实验结束时未提交；此记录包随后依用户明确授权发布 PR，仍未合并或上传赛事平台。

## 阅读入口

- [派生表、字段和证据边界](EVIDENCE.md)
- [下一步研究提示词](NEXT_STEP_PROMPT.md)：只做文献、语义与方案设计，不自动执行新实验。
