# 华为杯论文生成与验收工具

共享运行的命令变量 `$templateRoot`、`$workspaceRoot`、`$runtime`、`$python` 按模板 `华为杯_求解规范/工作区工作流.md` 的“命令变量”设置。工具从共享模板读取，子进程 cwd 为工作区；本题路径相对工作区，skill 内部引用相对本 SKILL.md。

新建论文运行先按[工作区工作流](../华为杯_求解规范/工作区工作流.md)创建或明确恢复 `workshop_vN`，不等待视觉计划。两份总控、两套 skill 和两套规范从 `template_root` 共享只读；题目副本、数据、求解、论文、图库、附件及运行缓存属于 `workspace_root`。外层题目/数据保留投放用途。会话从模板根启动，工具通过 `workshop.py run` 显式选择工作区；下文科学路径相对工作区、共享路径相对模板，不可在 workshop 直接拼接不存在的规范/skill 副本。旧独立项目命令仅用于明确 legacy 模式，不自动迁移历史研究。详细路径、编号、只读和实际运行规则以上述工作区工作流为准。

结构图与逐问主要综合图执行 `华为杯_求解规范/结构图工作流.md`；每问综合图为必需，规划、逐问与入文通过现有工具接入审计。

候选转正文采用 `candidate_figures.py select-paper` 派生正文视觉计划，复用候选ID和资产路径。新增项目在render/paper审计中核验候选覆盖和选图一致性；原有图数、流程图及页数门禁保持。候选通过render不代表通过paper；交付同时提供 `待选图库/index.html`，细则见绘图规范第14节和候选图工作流。

材料规划、每问完成、材料修改、最终打包、附件表生成和交付验收时，必须读取 `.agents/skills/gmcm-supporting-materials/SKILL.md`（另一运行时读取其同名副本）。该 skill 是支撑材料目录、材料取舍、说明文件和附件表展示的唯一详细规则；本规范保留阶段门禁。构建、逐问/final 审计、独立目录复现和受影响论文页面检查通过后才可交付。


当前交付规则：摘要800--1600个可见字符、正文不少于35页；正文每问4–6张独立科学图外另有1张主要综合图，排除主要综合图后全文至少16张。摘要、目录、附录不计正文。每个问题章节在 manifest 声明 `abstract_type`，按需声明 `abstract_result_mode` 和 `depends_on_previous`，词组与例外见 [摘要题型规则](摘要题型规则.md)。新增字段只记录类型及验证方式，不保存正文内容。

本目录提供 LaTeX-first 论文生产链和可选 Word 派生链：

1. `tools/build_latex.py`：根据 TeX-only manifest 生成唯一主入口 `论文/论文.tex`，章节通过 `\input{}` 组合，并在最终模式刷新动态附录、复制且实际调用统一 `附录模板.tex`；
2. `tools/audit_abstract.py`：在生成前检查摘要逐问题闭环/真实递进、四类短加粗、结构化结果/正文绑定、关键词唯一和局限/未来工作/内部交付禁写；`build_latex.py`、`build_docx.py`、`audit_tex.py` 会复用该门禁；
3. `tools/audit_tex.py`：检查 `.tex` 输入链、三级目录命令/顺序及编译后的 `.toc`、Markdown 残留、环境/花括号、图片、匿名、标签/引用、Unicode 数学字符和显式斜体；
4. `gmcmthesis.cls`、`gmcm-layout.sty`：统一章节字重/起页、上标引用和图表短标题物理宽度；`build_latex.py` 生成匿名入口，保持 A4、四边 25 mm、摘要起始页码 1、小四宋体、无页眉和居中页脚；封面单独调用不可随意改动的 `gmcm-title.sty`；
5. `tools/audit_paper.py`：检查最终 PDF 页数、摘要/正文边界、关键词标签唯一、摘要 1–2 页及单页摘要填充度、参考文献/附录边界和各章页数；
6. `tools/build_docx.py`：从同一批 `.tex` 章节生成可选 DOCX 派生物，明确拒绝 Markdown 和旧 inline content 字段；
7. `tools/audit_docx.py`、`tools/render_word.vbs`：审计动态 TOC 字段、标题大纲级别、格式和可选 Word 派生输出的渲染；
8. `tools/build_appendix.py`：在最终 `提交附件` 完成后扫描真实目录，交叉校验论文/支撑材料的问题数，筛选每问关键代码并生成 `求解/附录清单.json` 与 `论文/章节内容/99_附录.generated.tex`；
9. `tools/audit_appendix.py`：核对附件库存、连续编号、问题数、源码哈希、提交快照和统一 minted 模板；
10. `agent_manifest.schema.json`：TeX-only 智能体输入协议，关键词为 3–5 个且不得重复；附录不再作为手写 chapter role；
11. `tools/audit_citations.py`及`reference_evidence.py`：生成前检查至少十条普通正文实引、唯一末尾AI工具披露、来源元数据与用途证据，最终 PDF 再查完整上标方括号、多篇/范围、实际数量、链接及印出的书目核心字段；`collect_reference_source.py`只采集待审来源。详细契约见章节规范“参考文献”和`参考文献证据.schema.json`。

固定结构及页数限制的唯一详细规则见章节规范第 3.2 节。`paper_contract.py` 被生成器和 TeX 审计共同调用；`audit_pdf_layout.py` 被最终 `audit_paper.py` 强制调用，核对实际 PDF 的标题、字重、起页、目录文字/页码/链接以及图表标题实际行数和字号。没有可验证 PDF 源、manifest 或物理测量时不能通过。`\GMCMFigureNote{}` 与 `\GMCMTableNote{}` 用于可换行的独立说明，不能把这些说明塞入正式 caption。

排版回归使用隔离目录运行 `python -B 华为杯_论文规范模板/tools/run_layout_regression.py --maintenance --output output/layout-regression --xelatex <实际XeLaTeX路径>`，真实编译不同 Q 和故意破坏的页数、字重、字号、长标题用例。该演练不包含合格科学图或完整科学证据，不能作为正式论文通过证明。

前三章扩展回归：`python -B 华为杯_论文规范模板/tools/run_first_chapters_regression.py --maintenance --output output/first-chapters-regression --xelatex <实际XeLaTeX路径>`。覆盖合计2/3/6/7页、符号2/3页、表注单独溢出、错误字号/前缀/内部线；沿用同一生成器、XeLaTeX和生产PDF测量，不关闭生产门禁。源合同的三题型及硬错/风格建议测试见 `tools/test_first_chapters.py`。只验证维护用例，不表示后续真实论文的自然度或科学质量已自动通过。

求解阶段另使用 `华为杯_求解规范/视觉计划.schema.json`、`tools/init_visual_plan.py` 和 `tools/audit_visual_plan.py` 管理视觉证据。它们不并入论文 manifest，避免把求解/绘图状态混入 TeX 章节协议。

支撑材料使用独立的 `华为杯_求解规范/支撑材料清单.schema.json` 和 `华为杯_求解规范/tools/init_supporting_materials.py`、`华为杯_求解规范/tools/build_supporting_materials.py`、`华为杯_求解规范/tools/audit_supporting_materials.py`。论文 manifest 仍只管理 TeX；论文定稿后由支撑材料清单接收正文未完整展示的长表/批量图，并与每问完整源码、自主数据溯源、官方输出共同生成 `提交附件/支撑材料说明.md`。

## 前三章的真实入口

完整读取[前三章写作与验收](前三章写作与验收.md)。两端Phase 1登记题意来源/任务子项，Phase 4实际语义审阅；manifest增加first_chapters_evidence_path和first_chapters_review_path。build_latex与audit_tex通过paper_contract调用first_chapters核对覆盖、符号定义和当前源绑定。第2、3章自然接排，前三章去重占3～6页为推荐范围，超出须复查内容与版面；符号章≤2页仍为硬限制。第一章取消两页上限，扣除流程图、图题、标题及空白后，正文文字至少一页有效排版量，由真实PDF基线与TeX段落记录共同测量。其他章起页和35页正文门禁不变。

collect_academic_paper_review编译到aux/toc/out稳定，自动按manifest路径生成当前PDF的前三章逐页及第4章交界、符号局部待审图片；实际看图后填写观察，不能自动批准。audit_paper复核测量、图片像素和逐页审阅，finish复用该门禁。参数是项目选择，不能冒称国标规定。模板符号表使用GMCMSymbolTable/GMCMSymbolRow局部样式，通用表注不变。

## 推荐工作流

```text
求解结果/图片/文献
  → 按 agent_manifest.schema.json 写入论文/章节内容/*.tex
  → tools/audit_abstract.py
  → tools/audit_citations.py（正文实引预检）
  → build_supporting_materials.py --package-only 构建待验快照
  → reproduce_supporting_materials.py 在项目外的新目录实际复现
  → build_supporting_materials.py 纳入复现记录并自动生成动态附录
  → audit_supporting_materials.py --stage final
  → tools/build_appendix.py → tools/build_latex.py 生成论文/论文.tex
  → tools/audit_appendix.py → tools/audit_tex.py
  → collect_academic_paper_review.py（XeLaTeX -shell-escape 双遍与实际图片路径/宽度/页码采集）
  → 实际打开论文页面并填写待审记录
  → audit_visual_plan.py --runtime codex --stage paper
  → tools/audit_paper.py
  → PDF 字体、日志和页面视觉检查（前三章每页、符号局部及第4章交界必须全查）
  → 只修改真实内容、图表布局和章节拆分，不修改字号/页边距/行距来凑页数
```

最终论文正文禁止以 Markdown `.md` 作为章节源文件。`.md` 只用于求解计划、结果索引、AI 记录、内部审计和 `legacy_markdown/` 归档。`论文/论文.tex` 是唯一主入口，`论文/章节内容/*.tex` 是唯一正式论文 source of truth。

## LaTeX 主路线

封面赛事标题由 `gmcm-title.sty` 统一生成，调用 `\GMCMContestTitle{届次中文数字}`。该组件使用 XeLaTeX 和系统字体 `STXinwei`；正常情况下不要修改此文件，字体缺失时应报告错误。

执行下面的最终命令链之前，先按支撑材料skill完成待验快照和独立目录实际复现；复现记录过期时须重跑。

```powershell
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_论文规范模板/tools/audit_abstract.py -- --manifest 论文\论文输入.json --report 论文\验收输出\摘要.audit.json
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_论文规范模板/tools/audit_citations.py -- --manifest 论文/论文输入.json --report 论文/验收输出/文献.source.audit.json
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/build_figure_accounting.py -- --project-root . --plan 求解/视觉计划.json --stage render --runtime $runtime
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/build_supporting_materials.py -- --manifest 求解\支撑材料清单.json --project-root . --output 提交附件 --runtime $runtime
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/audit_supporting_materials.py -- --manifest 求解\支撑材料清单.json --stage final --project-root . --output 提交附件 --report 论文\验收输出\支撑材料.final.audit.json --runtime $runtime
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_论文规范模板/tools/build_appendix.py -- --project-root . --runtime $runtime
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_论文规范模板/tools/build_latex.py -- --manifest 论文\论文输入.json --output 论文\论文.tex --template-dir "$templateRoot/华为杯_论文规范模板" --manifest-out 论文\论文.inputs.json --runtime $runtime
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_论文规范模板/tools/audit_appendix.py -- --project-root . --main-tex 论文\论文.tex --report 论文\验收输出\附录.audit.json --runtime $runtime
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_论文规范模板/tools/audit_tex.py -- --manifest 论文\论文输入.json --main 论文\论文.tex --report 论文\验收输出\论文.tex.audit.json --runtime $runtime
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/collect_academic_paper_review.py -- --runtime $runtime --plan 求解/视觉计划.json --main-tex 论文/论文.tex --output 论文/验收输出/图形入文.review.json --project-root .
# 实际打开生成的论文页面，填写逐次出现及全篇视觉复核；工具只生成待审记录。

& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/build_figure_accounting.py -- --project-root . --plan 求解/视觉计划.json --stage paper --runtime $runtime
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/audit_visual_plan.py -- --runtime $runtime --plan 求解\视觉计划.json --stage paper --project-root . --main-tex 论文\论文.tex --report 论文\验收输出\视觉计划.paper.audit.json
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_论文规范模板/tools/audit_paper.py -- --pdf 论文\论文.pdf --source 论文\论文.tex --targets "$templateRoot/华为杯_论文规范模板/page_targets.json" --report 论文\验收输出\论文.audit.json
```

最终附录固定为“附录 1：附件文件及内容”加“附录 2～N+1：问题一～问题 N 关键代码”。`N` 来自论文 manifest 的 `role=problem`，并与 `求解/支撑材料清单.json` 双向校验。附件表只读取最终 `提交附件`；代码只读取已登记、已打包的真实源码，并统一由 `章节模板/附录模板.tex` 以 `\inputminted`、Pygments `lovelace` 浅色主题、连续行号和可分页细线版式排版。最终 XeLaTeX 命令必须带 `-shell-escape`，且环境中必须有 `latexminted`/Pygments。`--draft-without-appendix` 仅供未完成支撑包时的内部草稿，不能通过最终 `audit_tex.py`。

编译日志不得包含致命错误、字体缺字、未定义引用或不可接受的 `Overfull \hbox`。摘要为 1–2 页，可自然延续至第 2 页；单页摘要必须实质填充第 1 页。关键词后由工具链自动生成三级动态目录，正文从目录结束后的下一页开始。总页数不等于正文页数；正文到参考文献标题前结束，附录不计入。

## 可选 Word 派生路线

```powershell
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_论文规范模板/tools/build_docx.py -- --template "$templateRoot/第二十三届研赛论文Word标准模板.docx" --input 论文\论文输入.json --output 论文\验收输出\论文.docx --manifest-out 论文\验收输出\论文.chapters.json
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_论文规范模板/tools/audit_docx.py -- --docx 论文\验收输出\论文.docx --report 论文\验收输出\论文.docx.audit.json
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_论文规范模板/tools/run_word_render.py -- --input 论文/验收输出/论文.docx --output 论文/验收输出/论文.word.pdf --report 论文/验收输出/论文.word.json
```

Word 输出只能从 TeX-only manifest 和 `.tex` 章节派生，不能手工修改后反向覆盖 `.tex`。不要以 `docProps/app.xml` 中保存的页数作为验收结果。

## 章节页数策略

`tools/calibrate_page_targets.py` 根据两份优秀论文建立**角色区间**，而不是把样例页数硬复制到每篇文章：

```powershell
# 仅在明确维护模板页数配置时执行；正常论文运行只读取配置。
& $python -B "$templateRoot/华为杯_论文规范模板/tools/calibrate_page_targets.py" --maintenance --baseline "$templateRoot/华为杯_论文规范模板/章节页数基线.json" --output "$templateRoot/华为杯_论文规范模板/page_targets.json"
```

默认硬门槛：正文（不含摘要、目录、参考文献、附录）至少 35 页。问题章节区间是异常检测窗口；问题之间允许明显不均衡。正文不足时，智能体必须补充真实的模型推导、数据处理、结果分析和验证，不能通过缩小字体、页边距、行距或堆砌虚假内容达标。

补页按“问题章内证据恢复”执行：先补真实的阻断互验、误差结构、参数可辨识性、敏感性/鲁棒性、场景/边界，再补与主入口一致的伪代码和复杂度，随后把逐折分布、设备/场景差异、模型胜负和特征响应转为已审计多面板 Figure。全量逐折表、特征字典、文件行数、哈希、序列化和交付完整性进入附录、结果索引或支撑材料，不得单独撑起正文后置章节。每问首节“问题的描述与分析”内强制放置1张额外主要综合图，实际PDF不得越过第二个二级标题。图须有实质图形面板，不能只有文字框箭头；它不抵扣4–6张科学图或全文16张门槛，但合格流程语义可计入全文至少2张流程图。总体路线另放1.2问题重述。来源、引用、当前结果和实际视觉复核仍须通过。细则见结构图工作流。

每轮 PDF 除页数外还要生成逐页联系表，检查图表是否全部集中在前半段、正文后 1/3 是否出现连续稀疏页以及短表是否造成异常大空白。总页数达标但后段证据稀薄仍需重排；不能用装饰性/无意义图、同一结果换图型、放大图表或强制分页消除稀疏告警。

## 当前演练结果

历史 Word 示例 PDF 为 4 页、正文 1 页，是页数门槛的故意负例。任何示例产物都不是赛题答案或通过证据。真实论文必须以 XeLaTeX 最终 PDF 通过正文 35 页硬门槛后才交付。

## 证据链与科研图工作流

先按绘图规范第1.3–1.4节逐面板分类：原始影像与专业空间/信号渲染使用`.media.json`，普通统计结果按来源分别使用academic的`.assets.json`或modelviz的`.modelviz.json`，结构图保持专用skill。允许原生位图作为primary；入文采集器的历史vector_path字段表示实际主文件，不证明矢量。各路径共同接受实际TeX/PDF尺寸、页码、来源及看图检查；地图还须核验适用的公开审核状态。不得借文件扩展名豁免统计图，亦不得要求照片继承academic源码。

求解计划中的每个问题应同时维护 `Evidence Matrix`、`Figure Plan` 和 `求解/视觉计划.json`。Evidence Matrix 每行填写适用性、原因、数据形态、`figure / schematic / table / text / N/A`、结果路径和关联 ID；Figure Plan 在探索/求解明确结果结构后、正式绘图前声明结果字段、扫描/重复实验、Panel、archetype、hero/layout、输出、统计/QA 路径，以及普通科研结果图选定的 skill 后端（平等选择academic-figure-skill或modelviz-skill，先完成双来源预检、候选精读、各自证据与参考/成图实际对照）。机理/算法/图文综合图按结构图工作流建立对应计划与专用skill映射，普通流程保持scibox-diagram。论文阶段只引用 `qa_pass` 且通过视觉计划 render/paper 审计的正式图。

图数硬门禁采用“每问4–6张独立科学图 + 1张额外主要综合图”。各问主要综合图及其面板不计入逐问科学图额度或全文至少16张门槛；总体路线只计全文。用途、归属和额度按绘图规范的图数账表登记，不能只数caption。不得换图型重复呈现同一证据来凑数；证据不足时补充真实适用实验，仍无法满足则报告真实阻断，不伪造或自动豁免。独立验证可使用图、表、解析证明或可复核重算；无法获得真值时登记限制与替代证据，不把辅助证据冒充准确率验证。

`audit_paper.py` 最终命令会重新执行视觉计划的 paper 门禁，核对图数账表、真实当前图件、入文查看以及综合图/总体路线的实际 PDF 位置；不能用一份旧的 PASS JSON 替代。标准目录自动使用主 TeX 上一级项目的 `求解/视觉计划.json` 及其中明确保存的运行时；非标准目录使用 `--project-root`、`--plan`、`--runtime`。缺计划、缺当前编译/查看证据时必须失败，排版演练仍不能作为正式交付。

摘要manifest必须提供`abstract_evidence_path`；格式及来源要求统一见`摘要题型规则.md`和`摘要证据.schema.json`。最终PDF命令还运行`audit_abstract_pdf.py`，检查实际字符与四类强调字形；不会只看到源码textbf就判通过。

manifest另须提供`references_evidence_path`，绑定实际正文文献的来源和用途；`audit_citations.py`在生成前和最终PDF审计中都重读该证据。依赖按当前解释器安装：`python -m pip install -r 华为杯_论文规范模板/tools/requirements.txt`。此依赖表补充文献解析与证据校验，不替代环境规范中的XeLaTeX、PDF、绘图等依赖。旧文献键数量通过或旧演练记录不能替代新的来源审阅。

新项目部署和已有项目更新统一按 `../华为杯_求解规范/工作流部署.md` 执行；两个历史部署入口共用完整清单，包含摘要/文献证据、图数与位置审计及其样式依赖。

独立复现的参数数组、输出比较、记录保留和失败重跑规则唯一见两端 `gmcm-supporting-materials/SKILL.md`。`run_appendix_smoke.py` 现需显式提供已准备真实证据的隔离项目、独立工作目录和运行时；不再生成虚假的pass记录或删除旧验收目录。它执行生产门禁，编译成功后只生成待审页面，不自动宣布整篇论文通过。


## 模型比较的自动生成与审计

模型选择唯一详细接口见[模型选择与竞赛协议](../华为杯_求解规范/模型选择与竞赛协议.md)。每问通过支撑材料清单model_selection引用报告；model_selection.py run执行候选及独立验证，audit进行plan/question/paper/final检查，publish从真实结果生成比较CSV与TeX并更新结果索引。

每个问题章在合适的比较位置恰好引用一次`\input{章节内容/q1_模型比较.generated.tex}`（q1换成本问ID）。生成内容包含候选动机、统一条件、指标、复杂度、成本及选择依据；正文继续解释数学模型、变量、假设、机理和局限，不靠网络术语堆砌。非冠军DL保留，失败不填虚假分数。build_latex刷新片段，paper_contract同时供生成与TeX审计拦截遗漏或过期片段。纯理论问题展示具体不适用理由，不伪造比较表。

模型评价与展望按 evaluation 角色执行：正常排版净正文至少一整页，无一页上限；优缺点分别分点且各至少3点并具体解释，推广与改进至少两个自然段且不分点。生成与源审计、PDF净正文测量及全部评价章页面/内容复核共同验收；详细规则唯一见论文章节规范第7节。现有 first_chapters_review_path 同时承载评价章待审记录，旧记录须重新编译、渲染和实际审查。

## 参考文献维护回归

正式文献证据采用1.1版，显式区分至少10条普通正文实引与末尾固定AI工具披露。无语言数量或比例限制；固定条目与真实使用事实分别登记，旧证据须补齐类型/使用字段并重审。详细要求见章节规范第9节。

`run_ai_disclosure_regression.py --maintenance --output <全新隔离目录> --xelatex <实际路径>` 实际生成并编译10/14条普通文献的手写与BibTeX夹具，复用生产源码/PDF门禁核验早期AI上标、[11]/[15]末尾编号及重复生成。加 `--negative-pdf` 编译缺失、重复、错误型号/日期、额外标识、AI非末尾及普通排序错误的PDF，并检查对应物理门禁确实拒绝。`test_ai_disclosure.py` 与原有来源/引用/书目闭包单元测试共同覆盖退化行为。

所有夹具、来源快照及AI日志均明确标注为合成维护测试；PASS仅指软件行为符合预期，不代表真实文献、实际AI使用或正式论文验收。可选DOCX仍是原有有限派生路径，正式参考文献的上标、链接和最终条目以TeX/PDF门禁为准。
