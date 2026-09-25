# 主机3：ORION Unified，分片2

你在yellkiin/model_competition最新统一计划分支。先读ORION_START_HERE.md及本目录COMPARISON_REPORT.md、PLAN.md。Fusion/Trident旧计划已移到history/orion_plans；不要启动它们各自的完整100图实验，也不要在另一台正在跑的工作区改文件。

实际使用统一的S/M/F＋持久B基础路径，保持官方图/config/评估器不变。原题与数据在题目/A题同名附件，文献在调研/A题_文献库。Windows优先已有D:\python\python.exe，Python3.12.x x64、CPU-only；缺环境由本机Agent适配，别升级正在跑的环境。

取得完整100图day01参考表和selected_plans.zip。本入口自动恢复已有真实强种子；其余可用真实好方案通过-ExtraPlans传入。只有报告分数没有plan的不能冒充种子。每个起点在目标q/n重新原评估，原基准不换。

你负责分片2，与另两台使用同一数据清单、源码和预算。不要哈希/冒烟/单元或全仓审计前置；保留原评估合法性检查。先两个本轮未验证的真实键，通过后继续本片。每配置600秒包含读图/回放/构造/原评估/保存/Q3同方案无L2，30秒采点；自动workers按CPU和RAM75%目标准入。批次12小时截止，恢复不能重新获得完整时间。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a_orion_unified\run_windows.ps1 -ShardIndex 2 -Out 'research_a_orion_unified\runs\unified_round01_shard_2'
```

结果不佳先查实际候选和阶段；SM/SF/MF三选二仍不明才单模块。诊断表单列，不把它们事后最小值冒充一次固定策略。只保留起点不算新模块改善，要同时报raw候选质量。发生保存错误先保留完整检查点和错误，再判断是否继续；不得删失败装作完成。

完成或截止后执行：

```powershell
.\research_a_orion_unified\publish_results.ps1 -RunRoot 'research_a_orion_unified\runs\unified_round01_shard_2' -ShardIndex 2
```

只发布到research_a_orion_unified/team_results/unified_round01/shard_2/；提交独立分片PR，不覆盖他机、不自动合并。附实际有效/缺失数量、逐例指标、每30秒曲线、优化来源/阶段、原plan/response和论文数据，返回真实PR链接。完整度要求全队1400主+500精确同方案对照。
