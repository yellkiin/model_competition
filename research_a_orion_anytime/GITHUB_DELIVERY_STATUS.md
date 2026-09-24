# GitHub交付状态

2026-09-24，本目录已按用户授权提交到独立分支 `feat/a-orion-anytime-20260924`。提交范围仅为 `research_a_orion_anytime/` 源码、Windows入口、实验控制、理论与说明文档；不提交官方数据、生成实验结果、文献PDF或其他AI目录。

旧 PR #14 是上一轮不完整的 `research_a_orion_frontier` 草稿，不代表本轮实现。本轮 ORION Anytime 使用独立分支和完整 PR #15：https://github.com/yellkiin/model_competition/pull/15 。

本地 Agent 直接使用该 PR/分支运行实验，不重复创建新 PR，不 force push，不自动 merge。Windows 实测和完整100图结果仍应来自本地真实运行，不能因为代码已提交就写成实验已完成。

用户明确要求：本轮本地执行不做冒烟测试、不做哈希/文件指纹测试；只做启动所需最小环境检查和真实官方算例。官方评估器内部的覆盖、无环、容量和执行合法性检查必须保留。
