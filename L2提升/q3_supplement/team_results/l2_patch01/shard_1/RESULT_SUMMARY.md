# Q3 有 L2 增量补跑：Trident #38 分片 1

本轮只更新原 Trident #38 分片 1 的 Q3 方案。PR #59 的 `bank_only` 程序从已发布的 500 份真实方案中筛选同图同核数、预计至少降低 0.1% 周期的键，再使用未修改的官方评估器逐项核实；Q1/Q2 独立搜索、原图、题定配置和原始单核分母均未重跑。六份本地强起点 v1 方案的键均不属于本分片，本轮 24 个新评估方案全部来自 portfolio 归档。

| 指标 | 实际结果 |
|---|---:|
| 图 / Q3 键 | 33 / 165 |
| 新方案经官方评估并更换 | 24 键，涉及 14 图 |
| 继承旧合法方案 | 141 键 |
| 新 Q3 官方评估 | 24 次 |
| 新方案同计划 Q2/no-L2 对照 | 24 次 |
| 原计划同计划对照复用 | 141 次 |
| 缺失方案 / 配对 / 本地错误 | 0 / 0 / 0 |
| Q2 迁移候选，仅列出、未执行 Q2 搜索 | 9 键 |
| 执行墙钟 / 最大实际并发 workers | 约 81.35 秒 / 8 |

旧输入取自本机保存的分片 1 最终 FULL 原始作业和响应；`case_049_q3_n1` 按最终选择回执采用其完成的 recovery 版本及同方案对照，没有在历史目录中逐图挑最低值。新方案只有 `(Makespan, added COPY)` 优于旧解且通过官方合法性检查后才替换。24 项都达到本轮门槛，141 项仍保留原方案。另行试过的三个键、六次 `selective` Q3 评估均比旧解差，不混入本次固定 `bank_only` 主结果。

| 核数 | 有原单核分母的图数 | 旧 Q3 平均加速比 | 更新后 Q3 平均加速比 | 更换键数（含缺分母图） |
|---:|---:|---:|---:|---:|
| 1 | 32 | 1.127845 | 1.128912 | 1 |
| 2 | 32 | 2.166294 | 2.173303 | 5 |
| 3 | 32 | 3.043075 | 3.059559 | 4 |
| 4 | 32 | 3.801118 | 3.825208 | 7 |
| 5 | 32 | 4.545460 | 4.605856 | 7 |

`case_072` 缺少原始整图单核分母，因此其五个核数均不参与加速比均值；Q3 周期及同方案配对仍保留在覆盖表。最大逐键降时为 `case_003/n5`：194,971 → 142,684 周期，降低 26.818%。24 个更换键的降时均值为 4.076%，中位数 1.481%。这些是相对本机最终旧方案的同键比较，不代表三片合并或完整 100 图收益。

165 个 Q3 方案都有精确同方案 Q2/no-L2 对照。按 `no-L2 Makespan / Q3 Makespan` 计算，全部 165 项的算术均值为 1.02443，24 个新方案为 1.00792；新方案组与继承组不是同一批图，不能用两组均值差归因于算法对 L2 的作用。9 个 Q2 迁移机会仅供以后独立验证，未改动旧 Q2 方案和成绩。

运行使用 Python 3.12.8 x64、CPU-only、`-Workers 0` 自适应资源准入，最大实际同时 8 个 workers；4 小时绝对截止沿用本轮最初的时钟，没有重置。核心参数为 `-ShardIndex 1 -BaseManifest <selected final Trident manifest> -Official <unchanged A attachment> -Policy bank_only -Seconds 120 -Hours 4 -MinGain 0.001`。本次没有启动其他分片或全量搜索。

[`report/q3_overlay.csv`](report/q3_overlay.csv) 给出 165 键最终覆盖、来源、周期、COPY、Spill、Cache 和同方案收益；[`report/changes_only.csv`](report/changes_only.csv) 与 [`changed_plans/`](changed_plans/) 对应 24 项真实更换；[`report/attempts.csv`](report/attempts.csv) 和 [`report/time_quality_30s.csv`](report/time_quality_30s.csv) 保留新调用和保存时刻轨迹；[`report/q2_transfer_opportunities.csv`](report/q2_transfer_opportunities.csv) 只列迁移候选。本地 `evidence.zip` 保留全部原始计划、官方响应、来源和错误轨迹，未自动上传。
