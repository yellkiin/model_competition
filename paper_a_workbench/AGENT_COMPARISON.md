# 两套 Agent 的核对与本次选型

核对提交：`48cedcc9f0053b6afdc7e2db11cc5b45519b8337`。这是对工作流、实现和写作约束的审查，不用示例论文的奖项或AI检测分数作效果依据。

## 实际差异

|项目|原20hw生产工作流|huaweicup_agent整合版|本次处理|
|---|---|---|---|
|工作区|原workshop.py分配workshop_vN、登记文件输入、共享模板只读|init生成contract/inputs/notes/paper等另一套目录|保留20hw作为唯一生产引擎，新根与旧根分离|
|正式主源|论文/论文.tex及章节内容/*.tex|宿主编辑paper/main.tex；内置render用于synthetic演练|沿用原正式TeX合同，不运行demo/render|
|图件|8个实际同端skills，结果图/机理/流程/综合图与终稿检查|内置line/scatter/bar，其他由宿主扩展|保留原绘图skills，新增数据/主张接口|
|学术写作资料|8个已列出的skills中没有单独中文humanizer|bridge.py把awesome-ai-research-writing/README.md列为writer参考，execute=False、host_must_read|新增显式可发现的中文LaTeX学术编辑skill|
|研究阶段|完整求解到论文|modeler要求新三候选、coder有训练/验证/测试描述|论文任务直接消费已有ORION研究，不被泛化流程触发重建算法|
|更新|原add-input/adopt-resources/finish可登记和重审|按输入/产物依赖识别过期记录|增加来源快照差分与论文主张依赖，不自动把新路径视为新理论|

## “去 AI 味”的适用内容与修正

整合版 `bridge.py:GUIDES['writer']` 的第一项是 `各种建模agent/awesome-ai-research-writing/README.md`，它返回引用清单而非执行润色。`workflow.py:task_prompt` 写角色任务文件，真正阅读和编辑由宿主完成。这解释了为什么“目录里有该资料”与“写论文时已经实际应用”不是同一件事。

已核读该README的中文表达润色、逻辑检查、英文/中文去AI味段。可保留的规则是标准术语不乱换、删无信息修饰、修正指代、减少机械连接、表达准确时不强改。以下内容需按本题覆盖：

1. 中文Word规则的纯文本输出不适用于LaTeX正式主源；本次保留数学、引用、label/ref、必要结构。
2. 英文去AI味全面禁止列表会误伤算法步骤与约束列举；按科学组织是否必要决定。
3. 上游示例把“令人惊叹的能力”改成“显著的性能提升”，可能无依据地增强结论；本次改为具体对象、指标和幅度，无检验就不增加统计含义。
4. 英文翻译阅读模式删除cite/ref/label，其用途是帮助读原文，不用于终稿编辑。
5. 不能用零修改或token检查通过替代科学审阅；每次编辑还核对因果、量词、作用范围和成立条件。

因此新Agent不是追求“识别器测不出AI”，而是**事实、公式和术语保持下的学术编辑**。队伍按实际使用记录完成规定披露。

## 有效性检查

本次实际使用已有011完整作业记录检验资料接入：14主记录与5个精确同方案配对；改根目录和字段布局后值不变；重复配置、不同真实方案配对会定位错误。中文编辑示例保持公式和引文，另把公式分母及引文故意改动后的副本用于验证告警；这只是编辑接口检查，没有改动原论文或原实验。

本次文本导出未包含隐藏的原 `.agents` 资产，本地probe正确报告缺失，未把导出包标成完整可运行模板。完整原模板由本机已有授权目录复制，或者由template-source恢复所需共享资源；安装后必须读实际skills资产并完成原工作流。新六个skills的输入/输出与执行位置均在SKILL.md中明确。

检查记录见 `review/VALIDATION.json` 与 `VALIDATION.md`。结果支持本次数据适配与机械编辑保护的功能；中文终稿质量仍需对实际论文全文、图件和PDF审阅。当前实验未最终发布，完成稿质量不在本次已执行范围。

## 可复核来源

- `20hw_myskill_distribution/20hw_myskill_distribution/AGENTS.md`、`华为杯_求解规范/工作区工作流.md`、`tools/workshop.py`。
- `各种建模agent/华为杯整合Agent/huaweicup_agent/{README.md,AGENTS.md,bridge.py,workflow.py,publication.py,audit.py,visuals.py}`。
- `各种建模agent/awesome-ai-research-writing/README.md` 的中文润色/逻辑/去AI味段。
- 用户提供的 `ORION_Anytime_论文生成提示词.md` 和本地目录截图：只作迁移设计依据，不继续固定旧day01为新论文最终结果。

上游模板、第三方skills及字体不随本PR重发。已有版权声明保留在新的授权本地副本中；本PR只提交新增的工作台代码、提示词、适配合同及本次检查记录。
