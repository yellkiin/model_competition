# 两套Agent的选型与本次统一入口

原工作流核对版本为48cedcc9f0053b6afdc7e2db11cc5b45519b8337。本次在#42基础上修补路径与数据接收，并把#44科学母本直接接入，原Agent与理论源文件保持不变。

|职责|原20hw|huaweicup_agent|本Agent的采用方式|
|---|---|---|---|
|工作区|workshop.py创建、文件输入登记、模板只读|init另建contract/inputs/notes/paper|只采用原20hw生产工作流，安装在当前项目子目录|
|正式论文|论文/论文.tex及章节内容|paper/main.tex；内置render用于合成演练|保留原TeX、图件、附录及PDF检查，不运行合成render|
|学术编辑|原八类skills主要覆盖图、摘要与材料|bridge把写作README路由到writer，execute=False|以独立orion-academic-edit显式执行受保护的中文学术编辑|
|理论来源|通用求解到论文|modeler可重新提出候选|团队既有研究是输入；#44提供共同理论、术语与路线，不重新设计求解器|
|结果接收|登记文件后分析|证据依赖管理|本地桌面原包与Git报告对应，选择一个明确主实验集|
|增量更新|add-input及重新审阅|依赖变化检测|同一SESSION更新理论/数据映射及受影响的正文、图表和结论|

## 写作资料的有效用途

bridge.py的writer资料引用来自awesome-ai-research-writing。它产生阅读清单和任务，实际润色由宿主执行。保留准确术语、删无信息修饰、修正指代和减少机械连接的规则；表达清楚时不为换词而改写。

中文Word纯文本输出不用于正式LaTeX编辑。英文阅读翻译中的删除cite/ref/label规则不用于终稿。列表是否保留由算法步骤、约束和阅读逻辑决定。将夸张形容替换成“显著提升”也会改变结论强度，因此本Agent要求改为确切对象、指标与数值，而非增强语气。

编辑前后保留公式、数字、引文、量纲、限定词，并另行审查因果和命题范围。目标是科学含义一致的学术表达，实际AI使用按原流程记录。

## 原生理论而非追加提示词

#44的THEORY、ALGORITHM、TERMS、SOURCE_MAP、PAPER_ROUTE和references进入必需资料源theory_pr38_v1。prepare-theory保留原文，生成兼容#42的GLOSSARY、来源绑定和角色阅读入口。package-inputs将这些文件放进原workshop接收的资料ZIP；bind将理论输入登记到实际工作区。六个角色都先读同一理论，不再执行APPEND_PROMPT或另一套安装器。

#44核读锚点为PR38；最终实验代码由实际PAPER_EXPORT指定。路径变化只改变映射；来源选择、候选和停止规则变化要求更新对应算法表述。有效推导和原题语义优先，实际运行结果决定论文数值。

## 当前项目与本地数据

PROJECT_ROOT就是首次接手的Codex项目。新Agent、缓存和论文产物均在其中。安装只复制共享规则/模板/skills，不导入以前的稿件或完成记录，也不假定某个旧工作区存在。

实验大数据只读用户给出的C:\Users\LEGION\Desktop\数据。GitHub接入源码、理论、题面、文献和已上传报告，不把未上传原件当作空实验或重跑理由。真实检查与执行范围见VALIDATION.md。

## 来源

原20hw的AGENTS、工作区工作流、workshop.py；huaweicup_agent的README、AGENTS、bridge、workflow；awesome-ai-research-writing的中文润色、逻辑与去AI味段；paper_a_theory的科学正文、TERMS和PR42_COMPATIBILITY；用户本次明确的项目根与本地数据路径要求。

上游模板与第三方素材从用户授权本地/仓库恢复，原版权保留。本修补只提交工作台代码、合同、提示词和检查记录。
