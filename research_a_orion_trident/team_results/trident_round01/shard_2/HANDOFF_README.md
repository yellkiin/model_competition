# 本地全量数据包：ORION Trident 1.3 / round01 / shard 2

## 对应实验

- 项目：yellkiin/model_competition 的 ORION Trident trident-1.3，代码 PR #38。
- 冻结源码：489ec93a4c74683679e6a87a0175e4b8a3e3bbe1。
- 本机分片：ShardIndex=2，固定 33 张图；本包不是另外两个分片，也不是此前 ORION Anytime day01 分片 1。
- 本次运行北京时间 2026-09-25 23:35:39 开始，2026-09-26 01:57:03 退出。
- 原批次 460/462 主记录有效，165/165 同方案 no-L2 配对有效；原最终检查 460 主、165 配对全部通过。
- 429/429 非 q0 基线配置全部成功。076/091 原单核基线超时保留；076 另有核验通过的历史官方响应，091 按用户要求不再重算。
- 原报告均值分母为有原批次 T1 的 31 图，不能误写成全部 33 图均值；不得将原 complete=false 改写为完整成功。

## 复制给写作 agent

把同目录 FULL ZIP 复制到目标电脑桌面，再解压到新文件夹。将**实际解压路径**加入写作 agent 提示词。
它可以先读压缩包根的 HANDOFF_README.md，再读 reports/RUN_OUTCOME.md、reports/BASELINE_ACCOUNTING.json。
不要依赖本机 E: 或 C: 绝对路径；请求文件中的原绝对路径仅记录原实验现场，不表示接收电脑已有该路径。
不应从移动后的包恢复求解或重新评估；这里用于分析和写作。

## 包内路径

- reports/：最终报告、论文汇总表、验证记录、基线说明和 GitHub 交付说明。
- research_a_orion_trident/runs/round01/shard_2/：全部主作业、方案、原官方响应、全部候选、30 秒真实轨迹、来源成本、COPY/Spill/cache/Pipe、diagnostics、机制研究、源码快照及错误。
- research_a_orion_trident/runs/assets_shard_2/：本片官方输入、config、原评估器、原题阅读材料、种子/研究资料及输入收据。
- research_a_orion_trident/runs/recovery_20260926/shard_2/：额外补跑现场、真实成本与 091 用户取消证据。
- research_a_orion_trident/runs/retained_reference_20260926/shard_2/：076 历史响应复核、方案/响应和来源说明。
- research_a_orion_trident/runs/local_host2/：本机监督/整理辅助文件与日志，不含凭据或 GitHub CLI 安装包。
- research_a_orion_trident/ 的其他目录：冻结算法、说明文档和随代码提供的证据。

## 边界与说明

保留原固定预算结果、历史复用和用户授权额外补跑三个口径，不合并冒充同一预算实验。
每配置 600 秒是预算上限；不能把早停后持有的轨迹点解释为又计算到了 600 秒。
缓存收益只使用 Q3 选中方案的同方案 no-L2 对照，不用独立优化 Q2/Q3 的差值代替。
官方 Step3 peak 是原报告内存口径，不是独立内存分配重放证明。
已上传的部分 Release 分卷不完整，用户已取消继续上传，不能用于完整恢复。
本地 FULL ZIP 才是这次手动转移的完整包，包含数据和报告；没有官方输入或原始结果再上传的要求。
