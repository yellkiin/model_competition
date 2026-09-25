# ORION论文理论输入包

本包把PR #38实际实现整理为可供全文写作采用的统一模型、术语、方法路线和证据接口。它是论文的理论输入，不是新的求解器，也不是另一套通用写作Agent。

**统一主线：子图划分、核心映射和核内顺序的联合决策，在同一执行模型下由多类邻域共同改进。三问通过Task组织、跨核交接和FIFO状态的不同规定加以特化。**

## 版本与隔离

- 理论锚点：PR38 `489ec93a4c74683679e6a87a0175e4b8a3e3bbe1`，`research_a_orion_trident/`。
- 本包版本：`orion-pr38-theory-v1` / `1.0.0`，独立PR #44。
- 本包分支：`docs/orion-pr38-theory-v1-20260926`。
- 独立目录：`paper_a_theory/`；不修改`paper_a_workbench/`、原始写作Agent、实验代码与结果。
- PR42已完成并合并；核对版本为`eb2bb14d67a8d2770e276b77411f779f43f94b49`。接入优先读`PR42_COMPATIBILITY.md`，使用它实际的SOURCE_PROFILE、sync与package-inputs接口。本理论PR无需先合并。
- PR40或后续整合可改变实现根目录和结果根目录；绑定实际运行版本后重新核对语义，不靠目录名判断方法相同。

题目、原始执行规则和可核对的源码事实优先于本包解释。包内若有错误应修订理论，不得为保持措辞而改写原始数据或夸大已执行机制。

## 阅读与文件分工

| 文件 | 用途 | 面向 |
|---|---|---|
| `THEORY.md` | 统一方案、三问语义、资源/缓存执行、目标、下界与性质、指标 | 模型与正文写作 |
| `ALGORITHM.md` | 真实的共同方案更新、多邻域、成本选择与停止流程 | 算法章节与流程图 |
| `TERMS.json` | 全篇术语、符号、定义、内部实现词到学术表述的映射 | 所有写作/数据/绘图角色 |
| `SOURCE_MAP.md` | 原题章节、代码调用链、已读原文段落、迁移边界 | 内部核对与增量更新 |
| `references.bib` | 与文献库编号对应的书目 | 参考文献管理 |
| `PAPER_ROUTE.md` | 章节主线、必需图表、证据集合、未来变化处理 | 论文主Agent及更新角色 |
| `PR42_COMPATIBILITY.md` | 优先追加到PR42启动提示词后的原生接入要求 | 零上下文本地Codex |
| `extend_workbench_profile.py` | 新增固定版本理论源，保留已选算法和正式结果配置 | PR42资料入口 |
| `APPEND_PROMPT.md` | 完整理论、证据与写作补充；包含其他Agent可用的通用接入 | 理论对齐及通用后备入口 |
| `BINDING.template.json`、`bind_theory.py` | 给其他工作流建立独立理论输入和版本绑定，不写原目录 | 通用接入 |
| `check_binding.py`、`check_workbench_compat.py` | 接入边界及真实PR42资料打包接口检查 | 工程验证，不执行研究算法 |
| `MANIFEST.json` | 完整文件清单、阅读次序、版本锚点与数据要求 | 机器读取 |

科学内容阅读顺序：README → THEORY → ALGORITHM → TERMS → SOURCE_MAP → PAPER_ROUTE → references。接入先读PR42_COMPATIBILITY。内部源码、绑定与检查文件不直接进入论文正文；正文沿已定义的数学和学术术语写作。

## PR42原生接入：推荐路径

由原启动提示词确定真实Agent根、资料缓存和本次工作区，保留`workshop_v1`。从理论分支单独读取本目录，记录实际取得的commit。

```text
python <理论目录>/extend_workbench_profile.py --profile <当前实际SOURCE_PROFILE> --theory-commit <理论包commit> --out <新的SOURCE_PROFILE.with_theory.json>
python <home>/paper_a_workbench/workbench.py sync --repo <repo> --profile <新配置> --home <home> --fetch --lfs
python <home>/paper_a_workbench/workbench.py package-inputs --home <home> --snapshot <sync实际返回的快照>
```

理论文件进入快照和资料ZIP中的`theory_pr38_v1/paper_a_theory/`。用原工作流返回的DOCX与ZIP文件启动新工作区；已有本次工作区则按原add-input接口登记增量资料。具体操作见PR42_COMPATIBILITY，既不猜workshop编号，也不把目录当作--input文件。

理论源与正式结果选择独立：新配置保留原active_publication、method_selection和已有sources。TERMS与PR42的GLOSSARY格式不同，应生成新的工作区合并表，不能直接互换。成稿统一用题面术语“总体任务执行时间（Makespan）”，首次说明它等于所有操作完成时刻的最大值。

## 其他Agent的通用接入

复制BINDING模板为本次新配置，填入真实路径后执行：

```text
python <理论目录>/bind_theory.py --spec <已填写配置JSON> --package-commit <理论包commit>
```

输出到新的`<workspace>/theory_input/orion-pr38-theory-v1/<binding_id>/`，包含THEORY_HANDOFF、THEORY_BINDING、原绑定输入及package目录。已有同名绑定不覆盖；不修改AGENTS、模板、实验或Git分支。Git模式仅比较列出的入口文本与声明commit，后续还需完整依赖和语义核对。原生PR42快照无需强行使用此后备脚本。

## 数据未到齐时

先写模型、性质、算法与方法性摘要草案，并建立数据和图表脚本。最终实验集合、实际算法版本、原plan与原response绑定之后，再填写定量结论。理论包没有新增成绩或实验曲线。

只更新结果时不必重写数学框架；更新算法策略时修改伪代码与相应实验定义；改变决策权限或执行语义时重新审查受影响的定义和证明。

## 数学解释的几个边界

商图无环不是完整执行可行性的全部条件；计费按张量与Task/核语义而非简单割边数；缓存候选只改核内顺序，结构/驻留候选不一定只改变一个变量；当前解单调保持相对于给定可行起点成立；停滞与下界精度停止分别解释。

第三问的额外COPY字节、DDR实际服务量和命中率是不同指标。时间—质量曲线按结果实际可用时刻记录。具体阈值、源码变量和跨版本历史留在内部绑定中，不充当论文主线。

## 本次工作范围

本次完成原题、文献、指定源码核对及理论文件编写，未运行新的NPU调度实验。导出包中的BINDING_CHECK.json和PR42_COMPAT_CHECK.json记录真实接入检查；其范围是文件、版本和资料路由，不是最终论文数学正确性、全文质量或Windows完整安装验收。原论文PDF、模板与字体不随本包再分发。
