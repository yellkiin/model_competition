# PR42原生接入补充（可直接追加到本地总控提示词末尾）

本补充应在正文写作之前执行。先读完原总控提示词与本补充，再安排步骤。

## 1. 已核对的实际接口

PR #42已经合并，核对版本为`eb2bb14d67a8d2770e276b77411f779f43f94b49`。实际接口是：

`SOURCE_PROFILE.json → workbench.py sync → SOURCE_LOCK.json → package-inputs → 原workshop.py start或add-input → 正文工作区`。

本理论包位于仓库`yellkiin/model_competition`的独立PR #44：

- 分支：`docs/orion-pr38-theory-v1-20260926`
- 目录：`paper_a_theory/`

它不要求#44先合并，也不需要修改#42的代码。获取方式参见本目录`APPEND_PROMPT.md`的A节：新建独立只读检出，只拉本目录，并记录取得的完整commit。下述原生路径优先于通用APPEND_PROMPT的B节绑定方式；其余理论、证据和写作要求全部保留。

## 2. 把理论加入原资料清单，而不是散放旁边

沿用原提示词解析出的真实Agent根目录、Git资料缓存与Python解释器。已有Agent时读取`<home>/.orion_paper/SESSION.json`，不得重新安装，也不得猜测工作区编号。默认值可能是`E:\ORION_Paper_Agent`与`E:\orion_paper_repo`，但以本地真实配置为准。

找出本次正在使用的SOURCE_PROFILE；如果已经通过adopt-export生成正式配置，应使用那份新配置，不退回初始模板。

在新文件中增加理论源：

```text
python <理论检出>/paper_a_theory/extend_workbench_profile.py --profile <本次实际SOURCE_PROFILE> --theory-commit <刚取得的理论包commit> --out <新的本地SOURCE_PROFILE.with_theory.json>
```

脚本完整保留原sources、active_publication、method_selection及其他字段，只追加：

```json
{"id":"theory_pr38_v1","ref":"<固定理论包commit>","paths":["paper_a_theory"],"required":true,"text_only":true,"role":"mandatory theory input before manuscript drafting; not a result publication"}
```

原文件不覆盖。若同名理论源已存在且配置不同，先在新配置中明确处理版本差异；不同时激活互相矛盾的两份理论母本。未来再次adopt-export时，也确认理论源仍在最终使用的sources中。

随后使用#42真实命令：

```text
python <home>/paper_a_workbench/workbench.py sync --repo <repo> --profile <新的本地SOURCE_PROFILE.with_theory.json> --home <home> --fetch --lfs
```

从命令返回值及`<home>/.orion_paper/latest_snapshot.json`读取实际快照。按已核对的sync实现，本包进入：

`<home>/数据/ORION_论文资料/snapshots/<snapshot_id>/theory_pr38_v1/paper_a_theory/`

检查SOURCE_LOCK里该源所有必需文件为present，且revision为选定的理论包commit。检查完整THEORY、ALGORITHM、TERMS、SOURCE_MAP和PAPER_ROUTE都存在，不只看目录是否建立。

## 3. 纳入原workshop的文件输入

对含理论源的新快照执行：

```text
python <home>/paper_a_workbench/workbench.py package-inputs --home <home> --snapshot <实际新快照绝对路径>
```

#42的package-inputs会把整个快照加入资料ZIP，因此THEORY等文件随原题DOCX和其他资料一并成为原工作流的输入。检查返回的ZIP内确实存在`theory_pr38_v1/paper_a_theory/THEORY.md`。这里只使用命令实际返回的文件路径，不把目录传给workshop.py的--input。

- 尚未建立本次论文工作区：执行原提示词的版权/使用说明步骤；使用START_COMMAND.json中的实际参数启动原workshop，再按其返回workspace_root执行#42的bind。
- 已有本次论文工作区：不得再start。读取原workshop.py的add-input帮助及工作流规范，用返回的资料文件和明确reason登记增量输入；保留旧快照和旧稿。

原生路径下无需再强行运行通用bind_theory.py。应根据SESSION与SOURCE_LOCK在本次工作区的工作记录中新增THEORY_BINDING.json，记录理论包commit、实际输入位置、当前实现版本、结果绑定和语义核对状态。换用其他Agent时才使用通用绑定脚本。

## 4. 实际驱动写作角色

让#42的以下六个角色均读取新输入：证据整理、理论核对、论文写作、学术编辑、增量修订、独立审阅。其实际skill分别是orion-evidence-curator、orion-theory-review、orion-paper-writer、orion-academic-edit、orion-change-integrator和orion-paper-review。

正文起草前按APPEND_PROMPT的C节产出THEORY_ALIGNMENT、TERM_SYMBOL_LEDGER、METHOD_TO_CODE、RESULT_BINDING及PENDING_EVIDENCE。把本包作为policies/THEORY_BLUEPRINT.md的详化理论依据，而非另立一套模型。逐章采用“联合决策—统一执行—多邻域迭代改进”的路线；三问仅对Task、交接和缓存语义作特化。

科学事实优先：以原题、实际执行版本及可复核推导校正本包。实际结果若来自#40或未来整合，更新方法映射和必要伪代码；不要把#38目录名固定成不可迁移的接口。

## 5. 术语表兼容，不把不同JSON格式直接混用

本包TERMS.json采用zh/en/symbol/definition/source；#42的GLOSSARY.json使用term/english/unit/source/avoid_aliases等字段。不要直接把TERMS.json作为workbench lint的--glossary参数。

在工作区生成一份合并后的、符合#42 schema=1的术语表，保留原表不改。先做语义归并再转换字段，补充首次定义章节与数学符号表。题目用“总体任务执行时间”，本包的“最大完成时间”表示同一个Makespan；成稿优先统一为“总体任务执行时间（Makespan）”，在必要的首次数学定义处说明其为所有操作完成时刻的最大值。其他同义词也只选定一个正文名称。

将该合并表显式传给#42的lint，仍由语义审阅角色检查定义和上下文。正文不保留工程变量、PR历史或防御式套话；标准术语、成立条件、数学符号和真实负结果不因润色而改变。

## 6. 数据未来到达时

理论源是必需方法输入，不是active_publication，不能覆盖正式实验选择。最终结果仍由#42的PAPER_EXPORT、adopt-export、intake和final-ready流程管理。更新时依据PAPER_ROUTE第7节处理：只迁目录则更新映射；新结果则重算图表；策略改变则同步方法章；执行语义改变则重审模型与证明。

接入完成后，报告实际理论输入ZIP、工作区登记位置、理论包与实现commit，以及对齐和数据状态。先做能独立于数据完成的理论稿，等真实结果完成后再定稿摘要和结论。此任务不重新跑百图，不改实验结果，不自动合并PR。
