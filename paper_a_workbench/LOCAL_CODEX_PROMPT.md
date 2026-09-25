# ORION 论文总控：统一理论、既有研究、本地实验数据

完整读取本文件和当前 Agent 根的 AGENTS.md，再执行 `paper_a_workbench/policies/WRITING_CONSTITUTION.md`。任务是把团队已有方法及真实结果写成学术论文。理论输入、术语规则和数据接入已经在同一流程中，不需要追加另一段提示词。

## 1. 当前项目与干净的生产环境

首次接手时，把 Codex 当前项目目录记为 PROJECT_ROOT，后续切换工作目录不改变它。所有程序缓存、Agent 和论文产物均位于此项目内：

- 仓库缓存：`PROJECT_ROOT/.orion_paper_cache/repository`
- 新论文 Agent：`PROJECT_ROOT/ORION_Paper_Agent`
- 外部实验源：`C:\Users\LEGION\Desktop\数据`，只读；用户另给路径时更新 SESSION 中的 local_data_root。

新环境只安装原 20hw 的共享规范、模板、绘图和材料工具，以及本题六个专题 skills；不导入任何旧论文目录、旧数值或旧完成记录，也不要求本机存在指定编号的旧工作区。

尚未安装时，执行本包 BOOTSTRAP_LOCAL.ps1，以当前 PROJECT_ROOT 为参数。模板优先从当前项目实际目录定位；缺失时从授权仓库恢复共享资源。脚本读取根 AGENTS、原规范和隐藏 .agents 目录的实际文件，不把目录存在视为全部资源可用。

已有本次 Agent 时只读取其 `.orion_paper/SESSION.json`，续接明确的 workspace_root。建立新工作区交给原 workshop.py，编号由该工具分配，不猜编号，不清理用户其他文件。

论文操作以新 Agent 根为工作根，显式读取其 AGENTS 和实际 SKILL.md。仅切换 shell 目录不表示规则已加载；需要新开 Codex 会话时从新 Agent 根启动，先读 SESSION。首次实际启动原工作流时按原入口展示版权与使用说明，正文和匿名图件不包含交互声明。

## 2. GitHub取代码、理论、参考文献与报告；实验大包读本地

以 SESSION 的 repo_cache、agent_root 为准，使用本机已有兼容 Python 3.11+。先读 `paper_a_workbench/SOURCE_PROFILE.json`，执行 discover 和 sync：

```text
python paper_a_workbench/workbench.py discover --repo <SESSION.repo_cache> --ref main --fetch --out <输入区/publication_candidates.json>
python paper_a_workbench/workbench.py sync --repo <SESSION.repo_cache> --profile <本次SOURCE_PROFILE> --home <SESSION.agent_root> --fetch --lfs
python paper_a_workbench/workbench.py scan-local --home <SESSION.agent_root>
```

尖括号是字段说明，执行时由 SESSION 和真实返回值替换。每个可变 Git ref 在一次同步中解析一次，保存完整提交到 SOURCE_LOCK。只读同步不切换研究仓库分支、不运行实验源码。

GitHub侧获取：题目/A题、调研/A题_文献库及A题_文献.json、实际方法源码和完整导入依赖、理论包、发布报告/清单/汇总表。PR #44 已合并；理论源 `theory_pr38_v1` 默认从 main 的 `paper_a_theory` 获取，并冻结本次采用的提交。需要采用开发分支时只调整来源配置的ref。新的理论提交在更新任务中单独采用，不在写作中途漂移。

实验大数据由用户拷贝到桌面数据目录。不得为补齐它们自动下载Release原始分卷、重新上传大包或重新跑百图。先用 scan-local 生成目录/ZIP/连续ZIP分卷清单，读取其中的 manifest、PUBLICATION、HANDOFF、RUN_OUTCOME 等；与仓库报告的实验轮次、分片、方法版本和计时协议对应。

选择明确的一组实验及互不重叠分片。已解包目录直接读；ZIP用 materialize-local 在项目内解开，源包不修改。工具通过连续字节视图读取分卷，不额外拼成第二份大ZIP。若是嵌套包，继续对已解出的包做一次明确选择；7z/rar用已有本地解包工具，登记原包路径与目标。不同轮次、消融、参数研究分别登记，不按每图最小值混成主表。

只有报告没有对应原记录时，先完成理论和已支持的分析，给出具体缺件位置；报告里的最优值不转写成新方案或伪造时间线。原始单核若有超时/历史补证/豁免，依该轮 BASELINE_ACCOUNTING 与实际响应记录处理，分母和样本数明确，不用新回放覆盖历史执行。

## 3. 理论已直接进入六个角色

源同步后执行 `prepare-theory --home <Agent根>`。随后 package-inputs 会强制检查并装入完整理论文件和合并术语表，不再执行来源包的 APPEND_PROMPT、extend_workbench_profile 或独立绑定流程。

完整读取共同输入：THEORY.md、ALGORITHM.md、TERMS.json、SOURCE_MAP.md、PAPER_ROUTE.md、references.bib。阅读顺序和实际路径见 SESSION.theory_binding。六个专题角色均使用同一输入包。

正文起草前，在明确工作区产出：

- THEORY_ALIGNMENT.md：题面、未修改官方语义、实际实现与理论定义/命题逐项对齐。
- TERM_SYMBOL_LEDGER.json：规范词、来源、定义位置、后续使用、数学符号和单位。
- METHOD_TO_CODE.csv：论文机制和实际执行源码的对应；工程字段只留在此表。
- RESULT_BINDING.json：选中的实验轮次、配置、主结果/消融/参数集合与本地包。
- PENDING_EVIDENCE.md：实际待补证据，不在论文正文写成工作日志。

共同路线是“联合决策—统一执行—多邻域迭代改进”：同一方案由子图划分、核心映射、核内子图顺序组成；三问分别特化任务、交接、驻留与FIFO语义；所有候选使用相同总体任务执行时间目标。按理论包组织完整定义、假设、推导、命题、证明和算法流程。标准术语保持原义，不以目录名或内部S/M/F/B字母另造理论体系。

#44的核读锚点是PR38，不自动等于最终实验源码。实际结果来自PR40或后续整合时，对齐真正的algorithm_revision和method_paths，核查候选开放阶段、来源选择、停止阈值、下界、时间预算和配对位置。工程路径变动更新映射；科学行为变动更新对应算法段、条件和证明。原题、有效推导和实际执行证据优先。

TERMS与原GLOSSARY格式不同，prepare-theory会合并成schema=1。正文统一用“总体任务执行时间（Makespan）”，首次定义说明为全部操作完成时刻的最大值；其余同义词在TERM_SYMBOL_LEDGER中选择唯一规范名。原理论术语和定义保留在输入文件，不静默替换来源内容。

## 4. 原工作流输入与实际工作区

执行 package-inputs，使用其真正返回的题面DOCX和资料ZIP，以及 START_COMMAND.json 的参数调用原 workshop.py start。--input传文件，不传目录。工作区建立后执行 bind；工具把理论输入和术语表放入该工作区的 `求解/论文理论/bindings/<快照编号>/`。

大原始包留在本地只读目录，资料ZIP登记其清单。选定实验通过 local-spec 生成带真实本地runs/config_local的接入文件，再运行 intake。输出及派生数据用原 add-input/证据登记规则进入工作区，原始档案与派生结果分开保存。按原工具真实帮助和白名单执行，不虚构新工具名。

已有本次工作区时走 add-input登记新资料，不再次start。正式TeX主源为当前工作区 `论文/论文.tex` 和 `论文/章节内容/*.tex`。源输入和共享模板只读。

## 5. 已有数据的规范化与论文写作

PAPER_EXPORT只选择一个明确主实验。result_delivery为local，result_paths记录GitHub报告位置；runs/config_local记录本地真正原数据。算法目录或结果布局改变时修改method_paths、layout、版本映射，不改写原JSON里的历史路径。

intake读取原summary、完整plan、官方response、progress。核对配置与实际周期、Q3同一完整方案无L2/有L2、真实30秒前缀。Q1/Q2一核点采用题目原始基准约定，逐图求比再算术平均；周期、主机秒数、COPY字节、Spill、字节命中率和同方案缓存比各有定义。seed成本、追加成本与端到端成本按真实记录。数据未齐时产出已有范围的表和待办，继续方法与理论写作；最终全文数字从明确的一份规范化数据生成。

先读题面所有要求；参考文献先README、方法对照、JSON，再按主张读原文与页码。以科学问题组织理论、图件和结果，正文陈述客观方法与结论，不写研发历史、代码字段或防御式套话。术语先定义后使用，上下文一致。润色保留公式、数字、引用、成立条件、量纲和因果强度。

## 6. 可视化、修订和最终交付

按原绘图、机理图、摘要、支撑材料skills执行，先形成Evidence Matrix与图件计划，再读取落盘真实数据画图。最终图和PDF逐页实际查看；模板页数/图数与题面硬要求分开，通过充分论证和非重复科学信息组织篇幅。

lint显式使用本次prepare-theory产生的GLOSSARY，check-edit核对编辑前后保护项；机械检查后做独立语义、理论、数字和引文复核。数据变化时重新生成受影响图表、摘要和结论，不继承过期审核。

完成原工作流的环境、支撑材料、动态附录、图件和PDF检查后finish。保留实际AI使用记录，不代填队员签署，不自动提交赛事。后续改动仍使用同一SESSION与 `ORION_论文更新提示词.md`。

交付本次工作区路径、PDF/TeX、图件和源代码、规范化数据、官方方案/附件、引用与理论记录。所有未知项留在内部待办；正文只使用已获得支持的理论和事实。
