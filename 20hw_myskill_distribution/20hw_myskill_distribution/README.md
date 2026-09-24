# 华为杯论文生成与验收工具

共享运行的命令变量 `$templateRoot`、`$workspaceRoot`、`$runtime`、`$python` 按模板 `华为杯_求解规范/工作区工作流.md` 的“命令变量”设置。工具从共享模板读取，子进程 cwd 为工作区；本题路径相对工作区，skill 内部引用相对本 SKILL.md。

新建论文运行先按[工作区工作流](华为杯_求解规范/工作区工作流.md)创建或明确恢复 `workshop_vN`，不等待视觉计划。两份总控、两套 skill 和两套规范从 `template_root` 共享只读；题目副本、数据、求解、论文、图库、附件及运行缓存属于 `workspace_root`。外层题目/数据保留投放用途。会话从模板根启动，工具通过 `workshop.py run` 显式选择工作区；下文科学路径相对工作区、共享路径相对模板，不可在 workshop 直接拼接不存在的规范/skill 副本。旧独立项目命令仅用于明确 legacy 模式，不自动迁移历史研究。详细路径、编号、只读和实际运行规则以上述工作区工作流为准。

图件先按[绘图规范第1.3–1.4节](华为杯_求解规范/华为杯_绘图规范.md)逐面板分类：普通统计结果按双来源规则选择academic或modelviz，原始图片/视频帧与专业GIS/遥感/科学场等使用独立media证据，结构图保留专用skill。素材登记、候选发现、真实处理、图数、支撑材料及实际PDF入文审计贯通；地图适用第15节，不因免academic而免真实性或合规检查。

结构图与逐问主要综合图执行 `华为杯_求解规范/结构图工作流.md`；每问综合图为必需，规划、逐问与入文通过现有工具接入审计。

新项目持续候选发现入口：[候选图工作流](华为杯_求解规范/候选图工作流.md)。初始化视觉计划同时建立候选清单；科学阶段结束即检查七个角度，逐问与交付前核验覆盖。候选图同等执行其来源质量要求和双来源选型，用户通过 `待选图库/index.html` 检查合格备选；正式入文后再做实际页面门禁。

材料规划、每问完成、材料修改、最终打包、附件表生成和交付验收时，必须读取 `.agents/skills/gmcm-supporting-materials/SKILL.md`（另一运行时读取其同名副本）。该 skill 是支撑材料目录、材料取舍、说明文件和附件表展示的唯一详细规则；本规范保留阶段门禁。构建、逐问/final 审计、独立目录复现和受影响论文页面检查通过后才可交付。


本目录提供 LaTeX-first 论文生产链和可选 Word 派生链。绘图视觉、图型选择、Figure/Schematic/Flowchart Plan、三维/柱状/饼图限制和质量检查统一由 `华为杯_求解规范/华为杯_绘图规范.md` 管理；它是项目内绘图规则的唯一详细来源。`求解/求解计划.md` 保存解释性计划，`求解/视觉计划.json` 按 `视觉计划.schema.json` 保存机器可审计合同。

`视觉计划.schema.json` 供编辑器或外部 JSON Schema 工具执行完整结构校验；项目自带 `audit_visual_plan.py --runtime codex` 仅使用 Python 标准库，强制检查证据覆盖、图数门禁、引用关系、渲染产物和论文接入等语义门禁，不要求额外安装 `jsonschema`。正式流程必须运行审计器，外部 schema 校验不能替代它。

提交附件另由 `华为杯_求解规范/支撑材料清单.schema.json`、`华为杯_求解规范/tools/init_supporting_materials.py`、`华为杯_求解规范/tools/build_supporting_materials.py` 和 `华为杯_求解规范/tools/audit_supporting_materials.py` 管理。它们按 skill 生成面向评阅者的提交包，并将实际运行记录、完整库存和 SHA-256 清单保留在内部验收目录；schema 校验同样不能替代语义审计。

## 科研绘图 skill 集成

普通科研结果图平等选用 academic-figure-skill 或 modelviz-skill：Codex 从 `.agents/skills/`、Claude Code 从 `.claude/skills/` 按SKILL.md的name发现同端身份。当前目录分别为 `academic-figure-skill/` 和 `modelviz-skill-main/`。选图前完成双来源预检，academic全图库与modelviz完整模板预览实际浏览；逐图比较候选、精读原图/源码并记录各自映射、适配和实际对照。细则与桥接命令见[绘图规范第1.2、8.1节](华为杯_求解规范/华为杯_绘图规范.md)，academic原v2资产协议继续保留。原 scibox-figure 保留安装文件，仅在用户未来明确要求时使用，不能自动二选一。初始化工具不代填查看结论；结果必须真实且中文可读。

机理/几何示意图用 `Schematic Plan`，含顺序、分支或数据流的结构用 `Flowchart Plan`。按[结构图工作流](华为杯_求解规范/结构图工作流.md)选择算法、物理或逐问综合图专用 skill；普通流程和总体技术路线参考同端 `scibox-diagram`（Codex 为 `.agents/skills/sci-box-main/sci-box-main/skills/scibox-diagram/`，Claude 为 `.claude` 对应路径）。按科学内容选择后端，保留可编辑源并实际审查 PNG/PDF、灰度和入文尺寸，不将全部结构图强制为同一固定模板。

不强制触发 skill 的任务包括交互式 dashboard、探索性可视化、数学函数图、PowerPoint/Illustrator/Figma 设计、纯代码调试、统计检验本身和数据清洗本身。20

1. `tools/build_latex.py`：根据 TeX-only manifest 生成唯一主入口 `论文/论文.tex`，并刷新、复制和实际调用统一动态附录；
2. `tools/audit_abstract.py`：检查摘要六要素、逐问题闭环/递进、带单位结果、选择性加粗、关键词唯一和交付内容禁写，并由 LaTeX/Word 构建与 TeX 审计复用；
3. `tools/audit_tex.py`：检查 `.tex` 输入链、Markdown 残留、环境/花括号、图片、匿名、标签/引用、Unicode 数学字符和显式斜体；
4. `论文.tex`：匿名 LaTeX 生产骨架，保留 `gmcmthesis.cls + gmcm.bst + figures/`，使用 A4、四边 25 mm、摘要页起始页码 1、摘要可自然延续至第 2 页、正文小四宋体、无页眉和页脚居中页码；
5. `tools/audit_paper.py`：检查最终 PDF 页数、摘要 1–2 页、关键词标签唯一、单页摘要填充度、摘要/正文边界、普通文献数量、AI披露末尾位置、参考文献/附录边界和各章页数；

6. `tools/build_docx.py`：从同一批 `.tex` 章节生成可选 DOCX 派生物，明确拒绝 Markdown 和旧 inline content 字段；
7. `tools/audit_docx.py`、`tools/render_word.vbs`：仅用于可选 Word 派生输出的审计与渲染；
8. `tools/build_appendix.py` / `tools/audit_appendix.py`：扫描最终 `提交附件`，动态识别问题数、筛选真实关键代码并审计附件—代码—正文一致性；
9. `agent_manifest.schema.json`：TeX-only 智能体输入协议，关键词为 3–5 个且不得重复，附录不再作为手写 chapter role；
10. `华为杯_求解规范/tools/build_supporting_materials.py`：从 `求解/支撑材料清单.json` 重建 `提交附件/支撑材料文件/`，刷新 `支撑材料说明.md`，内部目录保存构建清单和 SHA-256；完整构建后触发动态附录；
11. `华为杯_求解规范/tools/audit_supporting_materials.py`：执行逐问和最终支撑材料门禁，检查源码完整性声明、运行记录、外部数据溯源、补充图表、官方输出、README 覆盖和哈希漂移。

参考文献门禁要求至少 10 条普通文献。生成器在同一列表末尾追加唯一的 `DeepSeek，DeepSeek-V4.1-Flash，深度求索（DeepSeek），2026-09-23。` 工具使用披露；该条目不计入普通文献，也不能作为学术论据来源。`参考文献证据.schema.json` 使用 `reference_type` 明确区分两类记录，`audit_citations.py` 和最终 PDF 审计分别检查普通文献首次引用顺序与 AI 末尾排序。

## 推荐工作流

```text
原始数据 → 求解代码 → 结构化结果
  → 读取华为杯_求解规范/华为杯_绘图规范.md
  → Figure/Schematic/Flowchart Plan/视觉编码表 → audit_visual_plan.py --runtime codex --stage plan
  → 绘图脚本只读结果并完成渲染检查 → audit_visual_plan.py --runtime codex --stage render
  → 每问更新支撑材料清单 → build_supporting_materials.py → --stage question 审计
  → 求解/问题X/图片/ → 按 agent_manifest.schema.json 写入论文/章节内容/*.tex
  → 重审补充材料 → build_supporting_materials.py 完成提交附件 → --stage final 审计
  → build_appendix.py → build_latex.py 生成论文/论文.tex
  → audit_appendix.py → tools/audit_tex.py
  → collect_academic_paper_review.py（XeLaTeX -shell-escape 双遍与实际图片路径/宽度/页码采集）
  → 实际打开论文页面并填写待审记录
  → audit_visual_plan.py --runtime codex --stage paper
  → tools/audit_paper.py
  → PDF 字体、日志和页面视觉抽检
  → 只修改真实内容、图表布局和章节拆分，不修改字号/页边距/行距来凑页数
```

最终论文正文禁止以 Markdown `.md` 作为章节源文件。`.md` 只用于求解计划、结果索引、AI 记录、内部审计和 `legacy_markdown/` 归档。`论文/论文.tex` 是唯一主入口，`论文/章节内容/*.tex` 是唯一正式论文 source of truth。论文规范只处理图像路径、尺寸、图题、标签、正文引用、PDF 缩放和裁切；不得在论文规范中另建颜色或图型规则。

## LaTeX 主路线

封面赛事标题由 `gmcm-title.sty` 统一生成，调用 `\GMCMContestTitle{届次中文数字}`。该组件使用 XeLaTeX 和系统字体 `STXinwei`；正常情况下不要修改此文件，字体缺失时应报告错误。

```powershell
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_论文规范模板/tools/audit_abstract.py -- --manifest 论文\论文输入.json --report 论文\验收输出\摘要.audit.json
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/build_supporting_materials.py -- --manifest 求解\支撑材料清单.json --project-root . --output 提交附件 --runtime $runtime
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/audit_supporting_materials.py -- --manifest 求解\支撑材料清单.json --stage final --project-root . --output 提交附件 --report 论文\验收输出\支撑材料.final.audit.json --runtime $runtime
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_论文规范模板/tools/build_appendix.py -- --project-root .
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_论文规范模板/tools/build_latex.py -- --manifest 论文\论文输入.json --output 论文\论文.tex --template-dir "$templateRoot/华为杯_论文规范模板" --manifest-out 论文\论文.inputs.json
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_论文规范模板/tools/audit_appendix.py -- --project-root . --main-tex 论文\论文.tex --report 论文\验收输出\附录.audit.json
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_论文规范模板/tools/audit_tex.py -- --manifest 论文\论文输入.json --main 论文\论文.tex --report 论文\验收输出\论文.tex.audit.json
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/collect_academic_paper_review.py -- --runtime $runtime --plan 求解/视觉计划.json --main-tex 论文/论文.tex --output 论文/验收输出/图形入文.review.json --project-root .
# 实际打开生成的论文页面，填写逐次出现及全篇视觉复核；工具只生成待审记录。

& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/audit_visual_plan.py -- --runtime $runtime --plan 求解\视觉计划.json --stage paper --project-root . --main-tex 论文\论文.tex --report 论文\验收输出\视觉计划.paper.audit.json
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_论文规范模板/tools/audit_paper.py -- --pdf 论文\论文.pdf --source 论文\论文.tex --targets "$templateRoot/华为杯_论文规范模板/page_targets.json" --report 论文\验收输出\论文.audit.json
```

最终附录固定由 `章节模板/附录模板.tex` 排版：附录 1 是最终 `提交附件/支撑材料文件/` 的直属目录概括表；附录 2～N+1 是论文 manifest 中问题一～问题 N 的关键实现，且 N 与支撑材料清单双源校验。代码通过 `\inputminted` 直接读取已登记真实源码，默认自动筛选，也可用 `appendix_code` 覆写文件与行范围；统一使用 Pygments `lovelace` 浅色主题、8.5 pt 紧凑字号、连续行号、自动换行和上下细线。最终 XeLaTeX 必须带 `-shell-escape`，环境必须可调用 `latexminted`/Pygments。

编译日志不得包含致命错误、字体缺字、未定义引用或不可接受的 `Overfull \hbox`。摘要为 1–2 页，可自然延续至第 2 页；单页摘要必须实质填充第 1 页。关键词后自动生成三级动态目录（含页码、超链接和书签），正文从目录结束后的下一页开始。总页数不等于正文页数；正文到参考文献标题前结束，附录不计入。

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

## 当前演练结果

历史 Word 示例 PDF 为 4 页、正文 1 页，是页数门槛的故意负例。任何示例产物都不是赛题答案或通过证据。真实论文必须以 XeLaTeX 最终 PDF 通过正文 35 页硬门槛后才交付。

## 证据链与科研图工作流

求解计划中的每个问题应同时维护 `Evidence Matrix`、`Figure Plan` 和 `视觉计划.json`；机理/几何图按需建立 `Schematic Plan`，多阶段/迭代/数据流结构按需建立 `Flowchart Plan`（在第一章1.2问题重述规划总体技术路线图，并明确为本文研究安排，全文流程图至少 2 张）。Evidence Matrix 每行必须填写适用性、原因、数据形态、`figure / schematic / table / text / N/A`、结果路径和关联 ID。Figure Plan 在正式绘图前根据真实计算结果定义结果字段、扫描/重复实验、Panel、archetype、hero/layout、图型、视觉 token、选定来源（academic-figure-skill 或 modelviz-skill）及实际绘图后端、输出、统计和 QA 路径。论文阶段只引用 `qa_pass` 且通过 render/paper 两阶段视觉审计的正式图。

任何创建、修改、审查或解释 Figure 前，Codex 和 Claude Code 都必须读取绘图规范；绘图失败时先修复字体、布局、编码或数据源，不得把未通过检查的图写入论文，也不得为了 35 页门禁机械增加图数。

生成、修改或审查结构图前读取绘图与论文章节规范，按结构图工作流路由对应skill；每问主要综合图必需，总体路线单独保留，严格检查真实关系、参考、渲染和实际版面。

### 绘图规则迁移与冲突处理

- 原 `华为杯_求解规范.md` 的大段颜色、图型、透明度和布局细节已收敛为接口摘要；详细规则统一迁移到 `华为杯_求解规范/华为杯_绘图规范.md`。
- 旧的“低饱和度/克制配色”与“禁止所有多色渐变”类表述不再作为项目规则；当前规则允许有数据语义的高亮度离散色和连续渐变，但禁止无语义彩虹色，并要求灰度可辨。
- 柱状图不再是默认图型；饼图不能单独承担核心证据；三维图只有在真实三变量关系或空间/轨迹含义存在时才使用，不得伪造，缺少真实三维关系时使用二维替代并记录原因。
- 论文规范已移除旧 A/B/C 流程图代码；普通流程模板参考 scibox-diagram，算法、物理和逐问综合图按专用 skill 路由。论文规范负责 LaTeX/PDF 接入和可读性，不提供另一套固定视觉模板。
- `gmcmthesis.cls`、`gmcm-title.sty`、`gmcm.bst`、官方 `figures/` 和 Word 模板保持只读，绘图迁移不改变 LaTeX-first、XeLaTeX 或正文 35 页门禁。

图数硬门禁采用“每问4–6张独立科学图 + 1张额外主要综合图”。各问主要综合图及其面板不计入逐问科学图额度或全文至少16张门槛；总体路线只计全文。用途、归属和额度按绘图规范的图数账表登记，不能只数caption。不得换图型重复呈现同一证据来凑数；证据不足时补充真实适用实验，仍无法满足则报告真实阻断，不伪造或自动豁免。独立验证可使用图、表、解析证明或可复核重算；无法获得真值时登记限制与替代证据，不把辅助证据冒充准确率验证。

---

## 项目使用说明（华为杯自动化论文 skill）

### 1. 项目是什么

本项目是一个面向华为杯数学建模竞赛的自动化论文辅助项目，提供“题目/数据审计 → 建模求解 → 结果验证 → 科研绘图 → LaTeX 论文 → PDF 审计”的可追溯工作流。日常使用时把它称作“华为杯自动化论文 skill”即可，但它本质上是一个项目文件夹，不能脱离其中的规范、工具和结果文件单独使用。

项目支持的自动化 harness 包括：

- **Codex**：读取根目录 `AGENTS.md`，适合在项目目录内执行命令、编写代码、运行审计和维护结果链；
- **Claude Code（CC）**：读取根目录 `CLAUDE.md`，可执行同一项目流程。两套规则应保持一致，具体运行时以当前 harness 能实际读取到的规则文件为准。

使用任一 harness 时，都应把工作目录设为本项目根目录（从当前总控文件所在位置定位 template_root，不硬编码本机路径），不要只打开某个子目录。模板源文件和规范文件默认只读，赛题数据和生成结果应保持事实链可追溯。

### 2. 赛题和数据放置位置

收到新赛题后，建议为该赛题新建独立工作目录（或先确认现有目录中没有其他赛题产物），再按以下约定放置文件：

```text
题目/
  题目正文.pdf、题目正文.docx、附件说明.txt 等（题面和官方规则，只读）
数据/
  原始/          原始 Excel、CSV、TXT、图片、压缩包等（只读）
  中间/          解压副本、清洗数据、转换后的中间文件
  自主/          非官方、自主查阅/整理/爬取并实际用于建模的数据、来源记录和采集脚本
求解/
  问题一/问题一.py、结果/、图片/
  问题二/问题二.py、结果/、图片/
  支撑材料清单.json
  ...
提交附件/
  支撑材料说明.md
  支撑材料文件/  逐问材料、其他数据、其他支撑材料
求解/验收输出/支撑材料/  内部清单、哈希、运行记录及历史包
论文/             论文.tex、章节内容/*.tex、验收输出/
```

> **使用者应将赛题正文放至项目文件 `题目/` 中，官方附件数据放在 `数据/原始/` 中；如用 Codex，请授予项目所需的文件与命令权限，并在 goal 模式下输入一键启动提示词。**
## 3. Windows 自动环境准备

首版正式支持 Windows 10/11 x64 和 PowerShell 5.1 以上。收到压缩包后，在模板根打开 PowerShell；无需预装 Git。将题目和数据放进入口目录后运行：

```powershell
.\Start-HuaweiCup.ps1 -Action start -Runtime codex `
  -Input '题目/题目.pdf' -Input '数据/附件.xlsx'
```

入口先复用通过实测的 Python；没有兼容解释器时，按共享目录中固定的国内镜像、官方回退和发布方 SHA-256 安装用户级 CPython。随后创建 `workshop_vN`、复制登记明确输入、建立独立 `.venv`，并准备读取题目所需的最小依赖。智能体读题后会按数据格式和所选方法增量登记能力，再继续检测、复用、安装、配置和验证。普通讨论、状态查询或模板维护不会启动安装。

续跑须明确原工作区：

```powershell
.\Start-HuaweiCup.ps1 -Action prepare -Runtime codex -WorkspaceRoot '.\workshop_v1'
.\Start-HuaweiCup.ps1 -Action check -Runtime codex -WorkspaceRoot '.\workshop_v1'
```

`check`、`list` 和 `env check` 均为只读，不安装软件。`-Offline` 只复用现有软件和已验证缓存；`-NoPersistUserEnvironment` 禁止写用户级 PATH/`DRAWIO_CLI`，但当前受控子进程仍注入已验证路径。项目不改全局 pip/TeX 默认源，不把 `.venv` 永久加入 PATH，也不需要用户把开发机私有目录复制过来。

共享事实源位于 `华为杯_求解规范/环境/软件目录.json` 和 `基础需求.json`。每个工作区保存 `求解/软件需求.json`、根 `requirements.txt`（直接依赖）、`requirements.lock.txt`（精确版本）、`求解/环境检测.json`、内部安装记录、`求解/环境与依赖.md` 和独立的 `论文/requirements.tex`。模板根 `requirements.tex` 是基础软件说明。环境 TeX 不插入正式论文，不改变附录编号或 35 页门禁。

软件按能力验收：XeLaTeX 必须完成中文、标题组件、TikZ、BibTeX、minted/Pygments 编译；draw.io 必须真实导出并解码 PNG/PDF；Python 包必须在本工作区解释器中导入并通过版本约束和最小功能测试。已有 TeX Live、TinyTeX 或 MiKTeX 通过即复用；缺包使用原发行版机制，不另装第二套。`STXinwei` 等模板字体缺失且无合法自动来源时会精确阻断，不替换官方样式。R、Word、OCR、Graphviz、Pandoc、LibreOffice、FFmpeg、GPU/深度学习等仅在题目和方法真实需要时登记，未支持的软件不会因名称出现而下载。

故障先查看工作区 `求解/环境检测.json` 和 `求解/安装记录.json` 指向的内部日志。常见状态包括 `unexamined`、`satisfied`、`missing`、`installing`、`failed`、`blocked`、`not_applicable` 和 `unresolved`。环境通过只证明执行能力，不表示模型、图件或论文完成。

### 4. 一键启动提示词

在项目根目录启动 Codex 或 Claude Code 后，可直接粘贴以下提示词。它会要求 agent 遵守现有门禁，并在缺少关键材料时停止，而不是猜测结果：

```text
请从当前模板根加载规则，先创建或明确恢复一个 workshop_vN，再在该工作区执行“华为杯自动化论文”全流程。后文题目、数据、求解、论文和提交附件路径均相对 workspace_root，共享规范与工具路径相对 template_root。先读取并遵守 AGENTS.md（Claude Code 同时遵守 CLAUDE.md），再完整读取华为杯_求解规范/华为杯_求解规范.md、华为杯_求解规范/华为杯_绘图规范.md，以及论文阶段需要的论文规范、README、schema 和 page_targets.json。

请按 FULL AUTO / ONE-SHOT MODE 工作：
1. 使用统一 start/env 入口自动准备最小环境；审计工作区题目/和数据/副本，按格式与方法增量登记能力，生成环境与依赖说明、题面约束清单和数据审计；
2. 为每个问题建立最小求解计划及验证协议，先运行探索小实验/基线并完成正式数值求解；正式绘图前再完成全图库浏览、候选比较、源码映射及完整 Evidence/Figure/Schematic/Flowchart Plan，运行 audit_visual_plan.py --runtime codex --stage plan；
3. 初始化求解/支撑材料清单.json；逐题真实运行代码，保存结构化结果、独立验证、敏感性/稳健性分析、图片和结果索引，不得伪造或凭感觉补数；
4. 普通科研结果图必须平等比较并选用 academic-figure-skill 或 modelviz-skill（Codex 用 .agents/skills/ 下对应 SKILL.md，Claude Code 用 .claude/skills/ 下同构路径），禁止自创第三种绘图风格；流程图格式必须参考 sci-box 的 scibox-diagram，结构图按对应skill与结构图工作流选择后端、保留源并实际复核；
5. 每问完成时将完整可运行源码、实际运行验证、自主查阅/整理/爬取数据及溯源、正文未完整展示的补充图表写入支撑材料清单，运行 build_supporting_materials.py 和 audit_supporting_materials.py --stage question；
6. 通过 render 审计后，以论文/章节内容/*.tex 为唯一正文源；写摘要时自动读取 `gmcm-abstract` skill，先运行 audit_abstract.py，再生成论文/论文.tex，执行 audit_tex.py、入文采集器双遍编译、实际页面复核、paper 视觉审计和 audit_paper.py；
7. 论文定稿后重审补充图表，重建提交附件，运行 audit_supporting_materials.py --stage final；核对摘要、正文、图表、结果索引、官方输出和支撑材料数字完全一致，并报告每个门禁的证据路径。

不要等待我在阶段之间确认普通技术选择。只有关键材料缺失/损坏、题意或单位无法判定、必需软件不可用、硬约束无法满足，或继续计算会制造虚假结果时才停止，并说明精确错误、已尝试修复、现有产物和最小解决条件。
```

### 5. 图表瑕疵修复提示词

生成图表后如出现乱码、字体缺失、标签重叠、图例遮挡、裁切、空白、坐标单位错误、颜色不可辨或图与结论不一致，可把图片路径、脚本路径和审计报告一起交给 Codex/CC，并粘贴：

```text
请修复这张科研图，不要只做表面美化。先读取华为杯_求解规范/华为杯_绘图规范.md，以及本图选定 skill 的 SKILL.md（academic-figure-skill 或 modelviz-skill，按登记来源，不得临时自创风格），再检查原始结构化结果、Figure Plan、绘图脚本及 QA 报告。

图片：<图片路径>
脚本：<脚本路径>
问题描述：<乱码/重叠/裁切/单位/图例/颜色/数据不一致等>

请定位根因并修改绘图代码或数据接口；不要手工篡改图片，不要编造数据，不要用未验证的占位值。重新运行脚本和字体检测，输出 PDF/SVG/PNG、统计报告和 QA 报告，更新求解/视觉计划.json 与求解/结果索引.md，并运行 audit_visual_plan.py --runtime codex --stage render。只有审计通过后才允许重新接入论文，同时说明修改前后差异。
```

若问题发生在 PDF 排版，可追加：

```text
请继续检查论文 PDF 中的图表越界、浮动位置、图题/label、正文引用和字体。保持字号、页边距和行距规范不变，只调整真实内容或合法布局；修复后重新执行 audit_tex.py、XeLaTeX -shell-escape 双遍和 audit_paper.py。
```

### 6. 结果、验收与安全边界

最终交付至少应能从原始题目/数据追溯到代码、结构化结果、独立验证、结果索引、正式图片、论文 PDF、官方输出和支撑材料。`提交附件/支撑材料说明.md` 必须概括主要目录、复现顺序及数据和结果位置；每问源码、运行记录、自主数据溯源、补充图表和 SHA-256 必须通过 final 审计。示例 PDF、模板示例和历史演练产物仅用于测试工具链，不能当作赛题答案或验收证据。未经用户明确授权，agent 不进行竞赛系统登录、外部提交或代替参赛者作出诚信声明。

### 7. 免责声明

本项目及其生成的代码、模型、图表、文字、LaTeX、PDF 和 DOCX **仅供学习、研究、流程演示和写作辅助参考**，不保证正确性、完整性、适用性或符合当届竞赛的全部要求。生成的竞赛论文不得未经人工复核直接提交，也不得将其视为官方答案、专家意见或获奖保证。使用者必须自行核验题意、数据、单位、公式、程序、引用、图表、格式和学术诚信要求，并对最终提交材料及其后果承担全部责任。不得使用本项目伪造数据、抄袭他人成果、规避查重/反作弊或违反竞赛和学校规定。

### 8. 版权与署名

“华为杯自动化论文 skill”项目归属：**小红书 ID：小红薯65F5F4DC；小红书号：49469317685**。未经权利人许可，不得移除本版权声明、冒用项目作者身份或将项目整体包装为他人原创。项目中引用的华为杯模板、字体、第三方库、示例论文和其他素材仍归其原权利人所有，使用时应遵守相应许可证、竞赛规则和版权要求。

本节是面向使用者的补充说明，不替换或降低本 README 前文、`AGENTS.md`、`CLAUDE.md`、`华为杯_求解规范/` 和 `华为杯_论文规范模板/` 中的任何技术门禁；发生冲突时，以项目总控文件规定的权威顺序为准。

## 支撑材料规则部署

新运行优先使用 `Start-HuaweiCup.ps1 -Action start` 或 `workshop.py start --template-root <模板根> --runtime <codex或claude>` 注册共享关联并准备环境；明确选择题目和数据并通过 `--input` 复制登记。低级 `create` 只建立工作区，不代表环境已准备。兼容入口 sync_supporting_skill.py 的默认 shared 模式同样注册工作区，不复制共享资源。仅对明确要求维护的旧独立项目使用其 --mode legacy；旧工作区不会自动采用新资源或重写历史证据，须显式 `adopt-resources` 后重新准备及验证。工具依赖见环境目录和工作区生成的 requirements 文件。论文 manifest 可用 contest_edition 保留实际届次、title_lines 保留题目原有断行；后者拼接必须等于 title，不改赛事标题组件参数。

模型选择规则见 华为杯_求解规范/模型选择与竞赛协议.md；A/B 类数据驱动问题必须按真实资源执行轻量 DL Pilot，C 类必须记录不适用理由。


## 模型比较的自动生成与审计

模型选择唯一详细接口见[模型选择与竞赛协议](华为杯_求解规范/模型选择与竞赛协议.md)。每问通过支撑材料清单model_selection引用报告；model_selection.py run执行候选及独立验证，audit进行plan/question/paper/final检查，publish从真实结果生成比较CSV与TeX并更新结果索引。

每个问题章在合适的比较位置恰好引用一次`\input{章节内容/q1_模型比较.generated.tex}`（q1换成本问ID）。生成内容包含候选动机、统一条件、指标、复杂度、成本及选择依据；正文继续解释数学模型、变量、假设、机理和局限，不靠网络术语堆砌。非冠军DL保留，失败不填虚假分数。build_latex刷新片段，paper_contract同时供生成与TeX审计拦截遗漏或过期片段。纯理论问题展示具体不适用理由，不伪造比较表。


## 双绘图来源接入

普通科研结果图平等检查 academic-figure-skill 与 modelviz-skill 两个来源，按科学问题选择，不设默认或份额。首次正式配图须完成双来源能力预检；academic 全库浏览和五项映射保留，modelviz 使用自己的目录、预览、源码、字段及适配证据。全文图型默认最多两张，第三次须重新比较或登记当前例外；逐图主动评估真实三维机会，合格且无明确劣势时优先三维。详细规则见绘图规范第1.2、5、10、14节。

新建计划由init_visual_plan生成v1.2和drawing_preflight_path。首次正式选图调用drawing_sources.py生成待审能力记录，实际阅读/浏览后填入；modelviz通过modelviz_bridge.py按每图job_dir运行，使用.modelviz.json；academic保留.assets.json。candidate figure/gallery/select-paper、图数账表、真实入文采集、支撑材料与finish复用来源审计；正文晋升全篇重核，旧资源/结果/源码/样式/输出变化须重新验证。
