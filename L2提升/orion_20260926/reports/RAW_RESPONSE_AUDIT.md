# Q3/L2 已保存原始响应内容核查

只解析既有 JSON/gzip 官方响应、summary 和 plan。没有调用评估器，没有重算合法性，没有修改输入或补造文件。
每项检查已保存 wrapper status/audit、Q3/Q2 语义、周期与 summary/时间线终点一致、配置字段、命中字节率，以及同方案 JSON 对象一致性。

处理状态：完整；501/501 项；耗时 19.828 秒。

| 口径 | 主键 | 解析响应 | 内容核对通过的配对 |
|---|---:|---:|---:|
| 原始三片 | 500 | 998 | 498 |
| 纳入已授权 049/n1 接续 | 500 | 999 | 499 |

049/n1 接续授权选择记录已读且匹配：True。
相对来源：`host1/records/research_a_orion_trident/runs/save_recovery_20260925/shard_1/SELECTED_RECOVERIES.json`。
接续数据：`host1/records/research_a_orion_trident/runs/save_recovery_20260925/shard_1/attempt_001/jobs/case_049_q3_n1`。
原始记录独立保留；最终选择按已明确授权的故障续跑替换唯一键，不按各版本逐例最优混拼。
该接续的早期轨迹不得回填至原轮；JSON 保留完整选择回执与每项相对来源。

## 未通过或缺失项目

- `host0/records/run/jobs/case_014_q3_n5`：summary_pair_not_ok；missing_or_unequal_pair_plan；no-L2:missing_response
- `host1/records/research_a_orion_trident/runs/round01/shard_1/jobs/case_049_q3_n1`：summary_pair_not_ok；missing_or_unequal_pair_plan；no-L2:missing_response

## 最终有来源的有效配对统计

| 核数 | 有效配对 | AM(no-L2/Q3) | 中位数 | 变快/相等/变慢 |
|---|---:|---:|---:|---|
| 1 | 100 | 1.000284452 | 1.000000000 | 28/72/0 |
| 2 | 100 | 1.004676969 | 1.000074680 | 58/42/0 |
| 3 | 100 | 1.015586806 | 1.000929218 | 66/34/0 |
| 4 | 100 | 1.030386322 | 1.001808762 | 71/28/1 |
| 5 | 99 | 1.056110957 | 1.007469632 | 76/23/0 |

注意：这是保存证据的内容一致性核查，不等于重新运行官方合法性检查，也不验证本机各副本逐字相同；未使用哈希或文件指纹。
