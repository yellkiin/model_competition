# 零上下文本地 Codex：从这里开始

任务：采用团队已经完成的方法和最终正式实验写A题论文。先准备统一理论与写作工作区；最终结果到位后补齐结果、图件、摘要、附件。不是再次自动设计或训练一个新模型。

代码交付：GitHub PR #42，分支 `docs/orion-paper-workbench-20260926`，新增目录 `paper_a_workbench/`。它和算法运行目录分离。原题、参考文献及实验来源通过 SOURCE_PROFILE / PAPER_EXPORT 配置，不绑定最终算法目录名称。

## 第一次接手

1. 先定位本机已有模板的真实AGENTS.md：默认 `E:\20hw_myskill_distribution\AGENTS.md`；若解压多了一层，检查 `E:\20hw_myskill_distribution\20hw_myskill_distribution\AGENTS.md`。保留现有workshop_v1、原数据、共享规范，不切换正在跑实验的仓库分支。
2. 在新的专用缓存 `E:\orion_paper_repo` 获取本PR。使用现有授权：

```powershell
# 仅在 E:\orion_paper_repo 尚不存在时执行clone。
gh repo clone yellkiin/model_competition E:\orion_paper_repo -- --filter=blob:none --no-checkout
git -C E:\orion_paper_repo fetch origin docs/orion-paper-workbench-20260926
git -C E:\orion_paper_repo sparse-checkout set --cone paper_a_workbench
git -C E:\orion_paper_repo checkout --detach FETCH_HEAD
```

已有专用缓存时读取状态并复用；有未保存修改就另建缓存，不做reset --hard。准备阶段读取main的最新资料，sync会固定一次实际提交。

3. 完整读取本目录README、AGENT_COMPARISON、写作宪章、LOCAL_CODEX_PROMPT。按本机实际解释器和模板路径运行：

```powershell
& E:\orion_paper_repo\paper_a_workbench\BOOTSTRAP_LOCAL.ps1 -Repo E:\orion_paper_repo -Template E:\20hw_myskill_distribution -Home E:\ORION_Paper_Agent -Python D:\python\python.exe
```

模板路径多一层时调整-Template；已有合适Python时调整-Python。新根存在且有SESSION时按记录续接，不重复安装。脚本不会开始正式工作区；原版权声明及共享规范保留。

4. 从 `E:\ORION_Paper_Agent` 开启后续Codex上下文，完整执行：

`E:\ORION_Paper_Agent\ORION_论文总控提示词.md`

先读取所有规则，实际核对输入，按原workshop入口创建新工作区，普通文件和科学技术选择自主完成。最终数据未出时先做理论工作稿、来源卡、术语/符号表、方法—实现对应和图件计划。新实验数字、结果图、摘要结论等到明确正式发布后从原记录生成。

## 后续有实验或方法更新

完整执行：

`E:\ORION_Paper_Agent\ORION_论文更新提示词.md`

它读取本次SESSION绑定的工作区，发现新发布候选，固定新来源，比较真实代码/协议/结果变化，沿论文依赖只改受影响部分。最终算法目录改变只更新PAPER_EXPORT映射；数学行为改变则同步定义/命题/推导。通过原add-input登记资料，结束后重新审阅PDF与finish。不会自动重跑整套优化、强推代码或上传赛事。

## 本次用户写作要求

术语有来源、先定义后使用、全文一致；三问用统一决策和目标组织理论。正文只写方法、理论、实验设计和客观结果，不写代码字段、PR历史、交接/审计话术或无关内容。不用“不声称”等防御式套话；成立条件正面表述。润色不改数字、公式、引用、量纲、因果强度或科学范围。按照题目要求给完整结果，再补充有真实证据支持的必要机理和验证。
