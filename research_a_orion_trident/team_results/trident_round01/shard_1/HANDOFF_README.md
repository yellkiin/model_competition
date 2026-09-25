# 写作入口：ORION Trident 1.3／round01／主机1／shard1

完整包名：`ORION_Trident_trident-1.3_round01_HOST1_shard1_FULL_20260926.zip`。本实验为2026年9月25日启动的Trident新实验，固定33张图；不对应旧day01，也不对应另外两台主机。

将ZIP复制到目标电脑桌面并解压。把实际解压目录下的`research_a_orion_trident`路径填入写作agent提示词。

## 统一最终结果

先读`team_results/trident_round01/shard_1/RUN_OUTCOME.md`。主结果462项，同方案noL2配对165项。统一33图均值位于`derived/mean_speedup_1_to_5_cores.csv`，最终逐配置指标位于`derived/per_case_final.csv`。5核均值为Q1=3.8320×、Q2=4.3975×、Q3=4.5597×。

## 包内完整材料

- `team_results/trident_round01/shard_1/`：统一最终报告与汇总表，默认写作入口。
- `runs/round01/shard_1/`：全部主作业、候选、真实计划和官方响应、30秒轨迹、COPY/Spill/cache/Pipe、诊断、机制研究、paper_data和源码快照。
- `runs/save_recovery_20260925/shard_1/`：保存错误接续的原始证据和来源映射。
- `runs/final_collection/shard_1/`：累计成本、轨迹和来源追溯材料。历史整理版本仅供追溯，正文使用上述统一最终表。
- `runs/assets_shard_1/`：本片官方输入、配置、评估器、历史参考方案和研究资料。
- `runs/host_control/`：启动记录、日志、整理与补跑脚本、发布回执。
- 其他目录：冻结代码、方法文档、vendor和研究证据。

请求文件中的旧绝对路径是原实验现场记录。换电脑后按包内相对路径找数据，不按旧D盘路径恢复求解。

建议提示词：数据根目录为【填写实际解压路径】。请先读HANDOFF_README.md和team_results/trident_round01/shard_1/RUN_OUTCOME.md，以derived中的统一33图最终结果作为正文数据。机制归因使用同方案配对与诊断证据，不把独立Q2/Q3均值差直接解释为缓存收益。
