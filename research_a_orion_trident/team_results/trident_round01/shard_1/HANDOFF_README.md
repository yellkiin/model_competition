# 本地完整包：ORION Trident 1.3 / round01 / 主机1 / shard1

包名：`ORION_Trident_trident-1.3_round01_HOST1_shard1_FULL_20260926.zip`。代码PR #38；冻结HEAD `489ec93a4c74683679e6a87a0175e4b8a3e3bbe1`。这是2026-09-25 23:23:23北京时间启动的Trident新实验，不是旧ORION day01，不是主机2或另两片。

把ZIP复制到写作agent电脑桌面，解压到独立目录，再把真实解压路径填入提示词。根目录为research_a_orion_trident。包内请求文件保留原机器绝对路径作为现场证据；接收电脑使用下列相对路径，勿按旧D盘路径启动重算。

- `research_a_orion_trident/team_results/trident_round01/shard_1/`：最终报告、原报告和来源明确的派生汇总；先读RUN_OUTCOME.md和ACCOUNTING.json。
- `research_a_orion_trident/runs/round01/shard_1/`：原462作业、全部候选、真实计划/官方响应、30秒事件、COPY/Spill/cache/Pipe、诊断、机制、报告paper_data、源码快照与失败记录。
- `research_a_orion_trident/runs/save_recovery_20260925/shard_1/`：case049保存错误接续及明确选择映射。
- `research_a_orion_trident/runs/final_collection/shard_1/`：不改原记录的累计恢复轨迹和候选成本补充。
- `research_a_orion_trident/runs/assets_shard_1/`：官方输入、配置、评估器、1400个历史参考plan及研究资料；仅求解本片33图，输入中其他图的历史plan不是新实验结果。
- `research_a_orion_trident/runs/host_control/`：启动记录、stdout/stderr、基线复用策略、补跑与汇总脚本、发布回执。
- 包根其他代码、方法文档、evidence/vendor/publication等：实验方法和来源证据。

写作口径：本轮461/462有效；保存错误接续后165/165同方案配对；用户授权33个历史基线直接复用，覆盖462/462但不声称全部本轮成功。原报告均值32图，derived均值33图。原600秒预算、历史成本和接续累计成本分开；禁止把后来的方案倒填早期轨迹。

建议提示词：数据根目录是【此处填写解压路径】。先读上述HANDOFF_README和RUN_OUTCOME，再用derived表分析；原始证据按包内相对路径定位。只分析和写作，不恢复求解、不修改或补造结果。
