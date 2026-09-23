# 华为杯整合 Agent

本入口属于 **yellkiin/model_competition**。整合现有三套资料：MathModelAgent 的阶段交接、HWB Skills 的读题与模型适配检查、awesome-ai-research-writing 的表达与图表说明；Python 工作台负责可复现计算、科学绘图、LaTeX 和证据审核。

## 从仓库根目录使用

```bash
python -m pip install -r "各种建模agent/华为杯整合Agent/huaweicup_agent/requirements.txt"
python tools/huaweicup.py assets orchestrator --check
python tools/huaweicup.py papers --year 2023 --problem A
python tools/huaweicup.py demo /tmp/huaweicup-demo
# 已安装 XeLaTeX 中文环境时，加 --compile；不要覆盖已有工作区。
python tools/huaweicup.py init /path/to/work --mode competition
python tools/huaweicup.py prompt /path/to/work orchestrator
```

Windows 示例工作区可用 `C:/work/huaweicup-demo`。完整命令和边界见 [工作台说明](huaweicup_agent/README.md)、[执行协议](huaweicup_agent/AGENTS.md)、[调研与吸收决策](huaweicup_agent/docs/research.md)、[迁移验证](huaweicup_agent/docs/migration.md)。

## 团队调用文本

> 先读本入口和执行协议，读取完整题面、附件说明与现有调研。用 assets 获取当阶段参考指南，用 papers 查已下载参考论文。先逐问区分固定条件、变量和约束，建立跨问依赖；提出可行基线和机制驱动候选，写实验方案后再计算。所有图、表、数字和正文绑定真实来源；审稿与反例复核后由队员决定定稿。

八角色为 orchestrator、researcher、modeler、coder、visualizer、writer、reviewer、redteam。角色路由只提供阅读入口，不会自动运行第三方后端；也不需要为了离线演练填模型密钥。

## 论文原文

论文只保存于已有 HWB 索引的 [近期论文原文](../hwb-math-modeling-skills/数模资料/优秀论文索引/近期论文原文/README.md)，不在本目录另存一套。12 篇均为 2023 年索引收录论文，A/C 各 4 篇，B/D/E/F 各 1 篇。103 条 2023—2025 年索引均保留下载状态；2024/2025 全文未取得，不冒称齐全或已精读。

## 测试

```bash
cd "各种建模agent/华为杯整合Agent"
python -m unittest discover -s huaweicup_agent/tests -v
```

宿主仍须真正完成文献阅读、建模推导和代码执行。工具通过不代表数学正确，演练不是参赛解答。当年正式模板与 AI 规则以组委会文件及队员核对为准。
