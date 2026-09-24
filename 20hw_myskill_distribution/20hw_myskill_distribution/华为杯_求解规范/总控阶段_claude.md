# 华为杯数学建模项目总控（Claude Code）

共享运行的命令变量 `$templateRoot`、`$workspaceRoot`、`$runtime`、`$python` 按模板 `华为杯_求解规范/工作区工作流.md` 的“命令变量”设置。工具从共享模板读取，子进程 cwd 为工作区；本题路径相对工作区，skill 内部引用相对本 SKILL.md。

新建论文运行先按[工作区工作流](工作区工作流.md)创建或明确恢复 `workshop_vN`，不等待视觉计划。两份总控、两套 skill 和两套规范从 `template_root` 共享只读；题目副本、数据、求解、论文、图库、附件及运行缓存属于 `workspace_root`。外层题目/数据保留投放用途。会话从模板根启动，工具通过 `workshop.py run` 显式选择工作区；下文科学路径相对工作区、共享路径相对模板，不可在 workshop 直接拼接不存在的规范/skill 副本。旧独立项目命令仅用于明确 legacy 模式，不自动迁移历史研究。详细路径、编号、只读和实际运行规则以上述工作区工作流为准。

每完成数据处理、特征构建、模型训练、优化求解或验证等科学阶段，以及方法/结果变化后，执行持续候选发现七维检查。新项目由初始化工具建立 `求解/候选图清单.json` 与阶段事件，逐问完成和最终交付必须通过覆盖审计。候选与正文普通图同等执行双来源预检及其来源的逐图参考、真实渲染和实际复核；`待选图库/` 供用户审阅，不计正文图数、不整库提交。所有工具显式 `--runtime claude`。详细规则见绘图规范第14节及 `华为杯_求解规范/候选图工作流.md`。

材料规划、每问完成、材料修改、最终打包、附件表生成和交付验收时，必须读取 `.claude/skills/gmcm-supporting-materials/SKILL.md`（另一运行时读取其同名副本）。该 skill 是支撑材料目录、材料取舍、说明文件和附件表展示的唯一详细规则；本规范保留阶段门禁。构建、逐问/final 审计、独立目录复现和受影响论文页面检查通过后才可交付。


本文件是本项目的 Claude Code 级 workflow router。它规定阶段顺序、证据链、自动化门禁和最终完成条件；详细求解规则由 `华为杯_求解规范/华为杯_求解规范.md` 管理，详细绘图规则唯一由 `华为杯_求解规范/华为杯_绘图规范.md` 管理，详细论文/排版规则由 `华为杯_论文规范模板/华为杯_论文章节规范.md`和`华为杯_论文规范模板/README.md` 管理。不要把这些长规范复制进本文件。普通科学结果图平等选用 `academic-figure-skill` 或 `modelviz-skill`，先完成第 1.1 节全图库浏览、逐图精读与参考/成图对照；结构图与逐问综合图按第1.2节专用skill路由。集成边界见 1.1、1.2，运行时读取对应 skill 的 `SKILL.md`；普通结果图的资产查看与脚本读取按第 1.1 节强制执行，其余参考内容按需读取。

## 1. 当前审计基线

本节列出模板资源基线，不声明当前输入目录为空。每次运行重新审计明确选定的题目和附件；历史研究目录、已有workshop与DEMO按各自清单识别，不作为新赛题事实源。历史论文只作经明确选择的参考，不作为新题结果或验收证据。有效资产包括：

- `华为杯_求解规范/华为杯_求解规范.md`；
- `华为杯_求解规范/华为杯_绘图规范.md`（绘图视觉、图型、Figure Plan、Schematic Plan、Flowchart Plan、质量检查的唯一详细来源）；
- `华为杯_论文规范模板/华为杯_论文章节规范.md`、`README.md`、`example.tex`、`gmcmthesis.cls`、`gmcm.bst`、`reference.bib`、`figures/`；
- `第二十三届研赛论文Word标准模板.docx`；
- `优秀论文/A24103350007.pdf`、`优秀论文/C24106130096.pdf`；
- `华为杯_论文规范模板/tools/` 下的 `audit_abstract.py`、`build_appendix.py`、`audit_appendix.py`、`build_latex.py`、`audit_tex.py`、`migrate_markdown_to_tex.py`、`audit_paper.py`，以及可选 Word 派生工具；
- `.agents/skills/academic-figure-skill/`（Codex 项目级完整绘图 skill）；
- `.claude/skills/academic-figure-skill/`（Claude Code 项目级完整绘图 skill）；
- `.claude/skills/sci-box-main/sci-box-main/skills/scibox-figure/` 与 `.../scibox-diagram/`（Claude Code 侧 sci-box：科研结果图模板与 draw.io 示意图/流程图 skill；入口均为大小写敏感的 `SKILL.md`）；
- `.agents/skills/sci-box-main/sci-box-main/skills/scibox-figure/` 与 `.../scibox-diagram/`（Codex 侧同构副本，两份目录必须保持一致）；
- `.claude/skills/gmcm-abstract/` 与 `.agents/skills/gmcm-abstract/`（摘要生成/审查 skill，两份 `SKILL.md` 必须同构；写摘要时自动触发）；
- `华为杯_求解规范/视觉计划.schema.json`、`华为杯_求解规范/tools/init_visual_plan.py`、`audit_visual_plan.py --runtime claude`、`agent_manifest.schema.json`、`章节页数基线.json`、`page_targets.json`和 `验收输出/` 演练材料。
- `华为杯_求解规范/支撑材料清单.schema.json`及 `tools/init_supporting_materials.py`、`build_supporting_materials.py`、`audit_supporting_materials.py`，用于逐问源码、自主数据、补充图表、README 和哈希的支撑材料闭环。

### 1.1 普通科研结果图：双来源预检、平等选型与实际对照

普通图平等使用 academic-figure-skill 和 modelviz-skill，不设置默认来源、兜底顺序或使用份额。科学内容仍先按绘图规范第1.3节分流；地图、素材、专业渲染和结构图保留专门门禁。

首次正式选图前，读取当前运行时两个真实SKILL.md、完整能力目录和限制，完成可复用但绑定资源版本的全局浏览；academic全图库与候选族源码门禁保持。按题面、Evidence Matrix和落盘结果自动形成需求，逐图比较两个来源、实际图型、三维机会和全文分配。能力预检只阻断正式配图，不阻断独立数值求解。

Codex读取`.agents/skills/academic-figure-skill/SKILL.md`与`.agents/skills/modelviz-skill-main/SKILL.md`；Claude只读取`.claude/skills/`下按front matter身份发现的同端入口。缺失、歧义、跨端或符号链接外跳直接报错，不自动复制。目录名可以不同，真实skill_root必须登记。

可持续接口与全部详细规则唯一见绘图规范第1.2、5、10、14节。新视觉计划v1.2：来源、chart_families、双来源比较、三维取舍及重复例外由计划记录；academic资产仍用.assets.json v2，modelviz用.modelviz.json，混合图逐面板审计。modelviz宿主文件桥接不需要额外API，正式执行仍通过workshop.py run。初始化不授予已查看或PASS；运行、技术、实际视觉、真实PDF入文分别检查。

上下文恢复、续跑或交接时重新读取能力概览、当前选图计划及所选原始参考；资源、数据、来源、设计、输出变化后重审。候选晋升/替换正文时重新检查全文图型；reserve/supplement不抢占正文额度但质量不降低。无赛题仅做隔离DEMO，不伪造正式成果。

### 1.2 结构图与逐问综合图路由

结构图按 `华为杯_求解规范/结构图工作流.md` 路由：算法内部用 algorithm-mechanism-diagram，物理/科学机理用 engineering-physics-mechanism-diagram，逐问图文综合图用 comprehensive-graphic-text-flowchart；普通流程与总体路线参考 scibox-diagram。第一章1.2的全文总体路线图强制从当前运行时scibox-diagram的assets模板库选型并适配，须完整浏览目录/预览、比较候选、登记template_selection_path及模板ID/风格继承/适配依据，实际复核成图与论文尺寸。具体规则和机器协议见[结构图工作流](结构图工作流.md)“第一章1.2总体路线图”。此项优先于skill允许自由布局的通用选项。后端按科学表达、编辑、公式和实际渲染选择；仅普通流程/总体路线保持draw.io优先。

当前运行时读取 `.claude/skills/algorithm-mechanism-diagram/SKILL.md`、`.claude/skills/engineering-physics-mechanism-diagram/SKILL.md`、`.claude/skills/comprehensive-graphic-text-flowchart/SKILL.md` 的适用入口；另一端从其同名副本读取，不静默跨端回退。

每问首节“问题的描述与分析”内强制放置1张额外主要综合图，实际PDF不得越过第二个二级标题。图须优先复用本问已有合适结果并落实适用机制，以紧凑对齐矩形形成总览，按结构图工作流内容v2完成审查；允许直接缩小结果图并关联正文详细图，细节不要求逐项可读，自绘导航仍清晰；它不抵扣4–6张科学图或全文16张门槛，但合格流程语义可计入全文至少2张流程图。总体路线另放1.2问题重述。来源、引用、当前结果和实际视觉复核仍须通过。

初始化 `视觉计划.diagrams.json`；规划、逐问完成、入文审计分别由现有visual/supporting/tex工具接入 `audit_diagram_workflow.py`。实际打开终图、必要局部和拟入文PDF页面，源或结果变化后重绘重审。允许真实位图面板与同一对象正常立体叠层，不能豁免文字碰撞和关键结构遮挡；精确检查协议见上述权威工作流。图库与隔离DEMO不构成赛题结果或正式验收证据。

## 2. 规则优先级与冲突登记

第 1.1 节“五项映射与实际看图门禁”是用户明确要求固化的专项规则。旧总控、详细规范或 skill 中的“资产按需读取”“只选一套风格与实现依据”等表述，若被用于省略该映射、实际看图/读代码或参考记录，则以第 1.1 节为准；该优先关系仅限上述绘图接入要求，不改变题面硬约束、数据真实性、流程图后端和其他质量门禁。

发生冲突时严格服从：

1. 用户当前明确要求；
2. 当前赛题正文硬约束；
3. 赛题附件说明、官方答案模板、官方公式/程序及提交要求；
4. 当前 `华为杯_求解规范/华为杯_求解规范.md`；
5. 当前详细绘图规范 `华为杯_求解规范/华为杯_绘图规范.md`；
6. 当前 `华为杯_论文规范模板/华为杯_论文章节规范.md`、LaTeX 模板及其 README；
7. `华为杯_论文规范模板/tools/` 的实际接口、`page_targets.json`、schema 和验收证据；
8. 本文件与根目录 `AGENTS.md`；
9. 新导入的旧 `CLAUDE.md`、旧 LaTeX 结构或个人习惯。

已识别的旧规则冲突按以下方式处理：

- 旧 `format.cls`、`fonts/`、默认 `\maketitle`、身份封面、目录和固定总章结构不再是生产规则；当前匿名 LaTeX 生产链优先。
- `example.tex` 仅作宏包/环境参考，不能复制其学校、队号、姓名、默认封面、目录或示例文献。
- 当前论文规范允许按题目自适应章节、普通表格/`tabularx`/`longtable`，不强制所有问题等长或所有表格使用一种环境。
- `论文/论文.tex` 是唯一生产入口，`论文/章节内容/*.tex` 是唯一正文源，使用 25 mm 四边版心；Word 只能由同一 TeX 源派生，不能成为 source of truth。最终 PDF 以 XeLaTeX、`audit_tex.py` 和 `audit_paper.py` 为准。
- 论文章节规范本身不把全文页数写成普遍官方硬限制，但本项目 `page_targets.json` 明确配置正文下限 35 页；因此 **35 页是本项目交付门禁**，不是据此推断其他届次的官方规则。

## 3. 一句话触发的 FULL AUTO / ONE-SHOT MODE

用户输入以下任一等价指令时，进入全流程模式：

- `开始解题`；
- `开始求解`；
- `求解这个题目`；
- `按规则求解`；
- `开始完成论文`；
- `从求解做到论文`；
- `完成这道华为杯赛题`。

全流程模式中，普通方法、模型、图表、章节、文件布局和排版决策由 Claude 根据证据自行完成；不在每问、每张图、论文、Word 生成或页数不足时等待确认。重要方法选择和结论要写入证据/结果索引；不能把 Agent 判断伪装成人工判断。

不得把“全自动”理解为可以猜测、伪造、绕过权限或向外部提交。以下是允许停止的硬阻塞：关键赛题/附件缺失或损坏、证据无法解决的题意/单位冲突、必需软件/许可证/权限不可用、硬约束无法满足、数据矛盾会迫使虚构结果、或连续根因修复后仍无法通过关键门禁。停止时必须报告已完成阶段、精确错误、已尝试修复、现有产物和用户要提供的最小条件；不得只写“运行失败”。

## 4. 不可变输入、工作目录和事实索引

原始题目、原始附件、官方 Word 模板、`gmcmthesis.cls`、`gmcm.bst`、`figures/`和官方样例只读。输出不得覆盖它们。真实项目推荐形成：

```text
.venv/
requirements.txt
题目/                         # 正文、附件说明、官方规则
数据/原始/                    # 原始附件，只读
数据/中间/                    # 解压、清洗、转换副本
数据/自主/                    # 非官方、自主查阅/整理/爬取的数据与来源记录
求解/
  环境与依赖.md
  题面约束清单.md
  数据审计.md
  求解计划.md
  视觉计划.json
  支撑材料清单.json
  结果索引.md
  视觉编码表.md
  AI使用记录.md
  附录清单.json
  问题一/问题一.py、结果/、图片/
  问题二/...
提交附件/支撑材料说明.md、支撑材料文件/
求解/验收输出/支撑材料/  # 内部构建库存、哈希、运行记录及历史包
论文/
  论文输入.json
  章节内容/
    99_附录.generated.tex
  验收输出/
```

`求解/结果索引.md`是论文数字、参数、图和表的主索引；重要决策可记录到 `求解/决策记录.jsonl`。事实链必须保持：

```text
原始题目/数据 → 求解代码 → 结构化结果 → 独立验证
→ 结果索引 → 论文内容 → DOCX/PDF
→ 官方附件 + 经审计的源码/自主数据/补充图表支撑材料
```

## 5. Phase 0：环境、项目和工具检查

实际启动求解时调用 `Start-HuaweiCup.ps1 -Action start` 或 `workshop.py start`，自动建立工作区 `.venv`，合并共享基础需求和输入格式需求，执行能力检测、复用、必要安装、PATH/专用变量配置及功能验证。只读询问、状态检查和模板维护不触发该入口。初次只准备启动及读取题目所需最小能力；题面和附件分析后，由智能体按能力而非品牌生成符合 `软件需求.schema.json` 的增量需求，标注 base/problem/data_format/method/rendering/submission 来源、必要性和理由，经 `env register` 后再次 `env prepare`。计划项不得直接写为满足。

`env prepare` 优先复用项目真实功能测试通过的现有 Python、TeX Live/TinyTeX/MiKTeX、draw.io 和 PDF 实现；已满足同一能力后不安装另一提供者。后续方法变化或运行报告真实缺依赖时增量补齐。R/Rscript、Word、OCR、Graphviz、Pandoc、LibreOffice、FFmpeg、GPU/深度学习等只有题目或方法真实需要时登记；未支持提供者保持 unresolved，不执行题面或模型生成的安装命令。STXinwei 缺失时报告合法来源阻断，不改 `gmcm-title.sty` 或替换字体。

`workshop.py run` 必须使用工作区 `.venv/Scripts/python.exe`，将该 Scripts 目录和实测 CLI 路径注入子进程。环境产物为 `求解/软件需求.json`、工作区根 `requirements.txt`/`requirements.lock.txt`、`求解/环境检测.json`、内部安装记录、`求解/环境与依赖.md` 和独立 `论文/requirements.tex`；后者不插入正式论文或改变附录编号。环境能力满足不代表科学、图件、论文或材料门禁通过。

## 6. Phase 1：读题与附件审计

先完整读取[前三章写作与验收](../华为杯_论文规范模板/前三章写作与验收.md)。复用题面约束清单并登记求解/题意写作依据.json：来源与性质、场景/困难/范围、共用条件、原题编号与子项、输入/动作/对象/条件/输出/验证/依赖。缺失材料保留待核验，题定方法与作者选择分开。

完整读取 `华为杯_求解规范/华为杯_求解规范.md`，递归读取 `题目/`和`数据/`全部相关文件及附件说明，生成 `求解/题面约束清单.md`。逐问记录：输入、输出、目标、依赖、单位、边界、方法限制、CPU/GPU/时间、指标、精度/小数位、训练测试隔离、官方答案文件名/Sheet/列/目录结构/压缩格式、AI 使用要求。不要猜题面没有给出的条件。

随后完成数据审计：格式、大小、Sheet/变量、shape、字段和 dtype、缺失/重复/异常、单位、时间/空间范围、坐标系、标签、泄漏风险和解析失败项。ZIP/RAR 先列目录和规模，只解压工作副本；原始数据只读，清洗写 `数据/中间/`。

赛题官方原始数据之外、实际用于建模的自主查阅/整理/爬取数据统一保存到 `数据/自主/`，同时保留来源、获取日期、许可/条款、采集或整理方法及脚本，不得只在论文中留下 URL。

若用户另行提供往届优秀论文、评阅意见或视觉参考，先生成 `求解/参考论文审阅.md`，逐篇核对问题定义、数据使用、训练/验证切分、指标口径、模型假设、可复现证据和图表结构。参考论文只用于发现候选方法、验证风险和叙事方式；其分数、结论与图片都不是当前赛题事实源。不同切分或不同数据上的指标不得直接排序，不得复制参考论文的数据、结果图或可能存在泄漏的实验设计。

## 7. Phase 2：求解计划

完整读取[模型选择与竞赛协议](模型选择与竞赛协议.md)。先完成逐问A/B/C门控、统一划分和GTX 1650预算；A/B必须真实尝试轻量DL Pilot。每问通过支撑材料条目的model_selection引用报告，纯理论题也记录C类理由，执行model_selection.py audit --stage plan。

先建立最小研究计划和验证协议，允许在 `求解/探索/` 运行小实验、基线及内部诊断图并记录输入、配置和结果；内部图不直接入文。正式数值求解不以图库浏览为前置条件。模型和结果结构确定后，正式绘图前仍必须完整浏览全库、比较候选、映射源码并通过完整视觉计划审计。

生成 `求解/求解计划.md` 和机器可审计的 `求解/视觉计划.json`。Evidence Matrix 至少审查机理/几何、主结果、独立验证、误差/约束、对比、敏感性/鲁棒性、场景、理论边界与反证；每行填写数据形态、`figure / schematic / table / text / N/A`、结构化结果和关联 ID。正式绘图前的 Figure Plan 必须基于探索/正式求解结果定义科学问题、结果文件、字段/单位、扫描范围/重复次数/统计量、Panel、archetype、hero/layout、输出和质量状态。轨道/空间几何、坐标变换、传播路径、采样/折叠等非流程机理图建立 Schematic Plan 并按1.2选择对应skill和后端；含步骤、分支、迭代或数据流的结构继续建立 Flowchart Plan。建立任何视觉计划前必须完整读取绘图规范；完成后运行 `audit_visual_plan.py --runtime claude --stage plan`，未通过不得开始正式绘图；探索和正式数值求解不受视觉计划阻断。方法优先级是：题面机理/公式 → 经典数学模型 → 统计/回归/优化 → 传统机器学习 → 深度学习 → 复杂集成。禁止为了论文显得高级而堆模型；题面禁止或不建议机器学习时严格遵守。

普通科研结果图的 Figure Plan 必须按第 1.1 节完成双来源比较、所选来源映射及实际查看记录；若最终数据结构或候选资产改变，正式绘图前须重新核对并更新映射，不能只沿用计划阶段的“已参考”说明。

计划阶段同时建立“正文证据架构”：把模型动机、推导/算法、主结果、阻断验证、误差结构、敏感性/稳健性和适用边界优先分配到对应问题章节，并预估图表在正文前段、中段和后段的分布。标准/复杂问题逐项审查算法伪代码、机理/流程结构、主结果、比较/消融、独立验证和失效边界；只有实际存在独特算法步骤时才写伪代码。Flowchart Plan 按 1.2 同步规划：在“1.2 问题重述”安排全文总体技术路线图，每个问题强制规划主要图文综合流程图，额外局部流程按科学必要性安排，且全文流程图规划总数至少 2 张，并为每张图预先确定 draw.io 或 TikZ 后端。不得预先规划以“完整折级清单”“文件/哈希审计”“序列化与交付完整性”为主要内容的正文独立章；全量逐折表、首行抽查、哈希和构建记录进入附录、结果索引或支撑材料。

问题数量确定后，按 `支撑材料清单.schema.json` 初始化 `求解/支撑材料清单.json`。每问预先登记唯一主入口、完整源码范围、运行记录、外部数据依赖和拟纳入的补充图表；不得等论文结束后凭记忆补清单。

## 8. Phase 3：逐题求解、验证、绘图和留档

候选训练与独立验证经model_selection.py run保存不可覆盖的运行记录；失败、重试与淘汰实验全部登记。逐问执行question审计及publish，生成同源比较CSV、TeX和结果索引；支撑材料构建及审计调用模型选择门禁。

按问题一到问题 N形成闭环：

```text
输入 → 数据审计/统一划分 → DL适用性门控 → baseline/传统ML/适用DL Pilot公平竞争 → 选定主模型 → 必要改进
→ 求解 → 独立验证 → 稳定性/敏感性（适用）
→ 结构化结果 → 结果索引 → 科研图 → 官方答案/提交附件
```

每题保留唯一主入口，计算与绘图分离，固定种子并记录时间。对评分公式、可行性、编码、尺寸或答案表要求建立独立验证器，依据原始输入和最终输出重新计算。新增的比较、消融、灵敏度、鲁棒性、场景、Monte Carlo 或稳定性分析必须真实运行并保存到 `求解/问题X/结果/`，绘图只读取这些最终结果。任何绘图前必须再次读取绘图规范；生成、修改或审查任何 Schematic/Flowchart 前还必须再次读取绘图规范和论文章节规范。正式生成普通结果图前，逐图复核第1.1节双来源比较及所选来源证据（academic五项映射或modelviz模板/适配）与实际查看记录，任一项缺失或与当前数据/脚本不一致时不得继续；再按 Figure/Schematic/Flowchart Plan 生成图，执行字体、渲染、warning、重叠、裁切、灰度和缩放检查，并把通过状态写入结果索引。图数硬门禁采用“每问4–6张独立科学图 + 1张额外主要综合图”。各问主要综合图及其面板不计入逐问科学图额度或全文至少16张门槛；总体路线只计全文。用途、归属和额度按绘图规范的图数账表登记，不能只数caption。不得换图型重复呈现同一证据来凑数；证据不足时补充真实适用实验，仍无法满足则报告真实阻断，不伪造或自动豁免。独立验证可使用图、表、解析证明或可复核重算；无法获得真值时登记限制与替代证据，不把辅助证据冒充准确率验证。全部普通图生成后运行 `audit_visual_plan.py --runtime claude --stage render`，失败不得进入论文。官方答案文件保留题面要求的文件名、Sheet、结构和精度，保存后重新读取核验。

结构图共享门禁（细则见1.2）：每问首节“问题的描述与分析”内强制放置1张额外主要综合图，实际PDF不得越过第二个二级标题。图须优先复用本问已有合适结果并落实适用机制，以紧凑对齐矩形形成总览，按结构图工作流内容v2完成审查；允许直接缩小结果图并关联正文详细图，细节不要求逐项可读，自绘导航仍清晰；它不抵扣4–6张科学图或全文16张门槛，但合格流程语义可计入全文至少2张流程图。总体路线另放1.2问题重述。来源、引用、当前结果和实际视觉复核仍须通过。执行结构图工作流的来源、渲染、视觉与入文审计。

普通结果图先检测实际中文字体，再渲染并检查缺字、负号、标签/图例重叠、裁切、分辨率和论文缩放可读性；失败就修绘图函数并重跑视觉审计。

每问完成时同步更新 `求解/支撑材料清单.json`：列全唯一主入口及其本问/公共依赖源码，保存实际运行命令、通过状态、时间和非空记录；将正文不宜完整展示但可复核的较大篇幅中间图表登记为补充材料；登记本问使用的自主数据及溯源。随后按支撑材料skill执行待验快照构建、`reproduce_supporting_materials.py` 独立目录实际复现、重建及 `audit_supporting_materials.py --stage question --question-id <ID>`。该审计未通过时，本问不得标记完成。`提交附件/支撑材料文件/` 是可重建快照，禁止在其中单独修代码或改数据。

进入论文阶段的门禁：所有问题真实求解；关键结果已保存；独立验证已完成；正式图已生成；官方提交材料（如有）已核验；结果索引可定位论文所需事实；没有已知结果矛盾。缺结果必须回求解阶段，不能在论文中估计或补数。

## 9. Phase 4：论文内容生成

模型评价与展望按论文章节规范第7节撰写：优缺点分别至少3点并解释，推广与改进至少两个自然段且不分点，正常排版实质正文至少一整页，允许自然跨页；序号按 evaluation 角色随Q确定。

重新完整读取[前三章写作与验收](../华为杯_论文规范模板/前三章写作与验收.md)，实际读原件→段落功能/任务覆盖→正文→忠实性与表达审阅→局部修订。manifest登记 first_chapters_evidence_path 和 first_chapters_review_path；first_chapters/paper_contract 被生成器与审计实际调用，禁止自动填写语义通过。前三章独立编号自然接排，合计实际3～6页为推荐范围；符号整章≤2页仍为硬限制，第一章取消两页上限、扣除流程图后的净正文至少一页；不得靠凑页或缩字号达标。

每个问题章引用本问模型比较generated.tex，保留候选动机、公平条件、性能、成本及选定依据，DL落败仍保留。build_latex刷新片段，paper_contract供生成与TeX审计共同检查缺失、过期及漏引；详细接口见模型选择协议。

在写论文前完整读取 `华为杯_论文规范模板/华为杯_论文章节规范.md`、`华为杯_论文规范模板/README.md`、`agent_manifest.schema.json`、`章节页数基线.json`和`page_targets.json`。当前主链路是：

```text
真实求解结果 → 论文输入/章节内容/*.tex → 完成提交附件
→ 动态附录清单/片段 → 论文/论文.tex
→ collect_academic_paper_review.py（XeLaTeX -shell-escape 双遍与实际图片路径/宽度/页码采集）
→ 实际打开论文页面并填写待审记录
→ audit_visual_plan.py --runtime claude --stage paper
```

使用当前 LaTeX 规则生成匿名内容：题目、摘要、关键词位置和字体；正文宋体小四；一级标题黑体四号居中；无身份信息、无页眉、页脚居中页码；摘要/关键词之后自动生成包含三级标题、页码和超链接的目录，再进入正文。一级章遵循论文章节规范的固定Q自适应结构，全文至少覆盖需要的问题分析、假设、符号、模型、推导、求解、结果、验证、评价/改进、真实参考文献和必要附录。图表必须在正文引用，且只能引用已按 `华为杯_求解规范/华为杯_绘图规范.md` 通过质量检查的真实结果图；普通科研结果图必须已通过第 1.1 节来源映射与实际看图门禁，采用已比较选定的 academic-figure-skill 或 modelviz-skill 作为来源，并保留可追溯的参考资产与适配记录，未通过者不得入文；流程图还必须通过 Flowchart Plan、结构真实性门禁，以及1.2规定的适用skill、后端与实际视觉复核。论文规范只负责图像路径、宽度、图题、标签、正文引用及 PDF 缩放/裁切检查，不提供固定流程图模板。摘要与正文数字一致。摘要写作/审查必须自动调用项目级 `gmcm-abstract` skill，并先通过 `华为杯_论文规范模板/tools/audit_abstract.py`；该门禁检查总起句、按题型的任务—方法—结果闭环、真实问题依赖、创新证据、定量验证、与结果模式相符的数字或解析结论、逐问四类短加粗及结构化结果/正文绑定、关键词唯一、局限/未来工作/内部交付内容禁写。文献真实并逐一引用。最终论文章节禁止使用 Markdown；`.md` 仅用于求解记录、内部审计和 legacy archive。

每个正文一级章必须通过“章节用途门”：它应回答一个独立科学问题、给出模型/证据或形成不可由前章替代的综合结论。若一章主要由逐折明细、特征字典、文件行数、允许值检查、哈希、序列化、人工抽查或提交边界构成，则拆成摘要证据并回填相应问题章节，其余移入附录、`求解/结果索引.md`、验收输出或支撑材料。理论边界、设备诊断和模型选择稳定性原则上与对应问题相邻；不得在论文后半段重新复述前文数字来维持页数。

`agent_manifest.schema.json`要求 `title`、3–5 个唯一 `keywords`、`abstract_tex_path`、`abstract_evidence_path`、`references_evidence_path`和章节数组；每章有 `chapter_id`、`title`、`role`、`order`、`tex_path`。每个问题章节还须声明 `abstract_type`，按需设置 `abstract_result_mode` 和 `depends_on_previous`，规则见 `华为杯_论文规范模板/摘要题型规则.md`。禁止 `abstract`、`content`、`content_file` 和 `.md` 章节路径。生成前后都要检查学校/队号/姓名/绝对用户名路径、占位符和虚构结果。`build_latex.py`、`build_docx.py` 和 `audit_tex.py` 必须复用摘要审计。

文献引用数量、实际PDF上标/链接及来源与正文用途证据由 `audit_citations.py` 统一检查；manifest必须提供 `references_evidence_path`。生成器、TeX和最终PDF审计均调用该门禁。至少10条普通文献与唯一末尾AI工具披露分开计数，AI工具可以作为使用披露条目列入参考文献表末尾，但不得作为学术论据来源，也不计入普通文献数量。来源实际读取、元数据与相关性判断不得由脚本自动填写通过；详细规则唯一见论文章节规范“参考文献”。

### 华为杯论文附录规范

最终附录必须且只能由统一自动链生成：附录 1 为“附件文件及内容”，附录 2～N+1 依次为问题一～问题 N 的关键代码。N 取论文 manifest 中按顺序出现的 `role=problem` 章节数量，并与 `求解/支撑材料清单.json` 的 `questions` 数量和完成状态交叉校验；禁止固定三问，也禁止在 chapters 中手写 `role=appendix`。

附录必须在最终提交包及其说明已构建、内部目录 `求解/验收输出/支撑材料/` 的构建清单与 SHA-256 已刷新后生成。`build_supporting_materials.py` 在清单和所有问题均为 `complete` 且论文 manifest 已存在时自动触发 `build_appendix.py`；后者仅概括 `提交附件/支撑材料文件/` 的直属目录生成附件表（每问及其他两类各一行），完整文件库存留在内部审计目录，同时从每问已登记且已打包的 `source_files` 自动筛选预处理、特征工程、模型、优化/求解、预测/决策与验证关键实现。高风险场景可用问题条目的可选 `appendix_code` 显式给出 file/language/firstline/lastline/firstnumber/caption，但文件仍必须属于该问 source_files。生成结果为 `求解/附录清单.json` 与 `论文/章节内容/99_附录.generated.tex`，二者禁止手改。

`华为杯_论文规范模板/章节模板/附录模板.tex` 是唯一附录排版实现，`build_latex.py` 必须复制并在导言区实际 `\input`，生成片段只调用其接口。所有正式代码通过 `\inputminted` 直接读取真实源码，使用 Pygments `lovelace` 浅色主题、统一附录模板规定的紧凑等宽字、左侧连续行号、自动换行、极浅灰底和上下细线；支持整文件、行范围、单问多片段、多文件、自定义首行号和跨页排版。禁止复制第二份源码、截图、Markdown 代码块、verbatim、深色 IDE、粗框、圆角或阴影。最终 XeLaTeX 双遍必须带 `-shell-escape`，并要求 `latexminted`/Pygments 可用；中文注释、长行、分页和版心必须实际渲染检查。

`audit_appendix.py` 与 `audit_tex.py` 必须在最终编译前核对提交附件库存、附录 1 表格、连续编号、问题数、源码哈希、支撑材料快照和正文问题章节的一致性。正文只写模型思想、公式、伪代码、结果与评价，不塞入大段正式源码。

论文内容稳定后再次逐问审查正文未完整展示的长表、批量中间图、分场景/分样本结果，只有真实且具有复核价值的材料才进入支撑包；调试图、缓存、重复图和虚拟环境不得进入。清单、正文、结果索引或官方输出发生变化时必须重建支撑包。

LaTeX 的 `论文/论文.tex` 是唯一提交入口，`gmcmthesis.cls`、`gmcm.bst`和 TikZ 是生产依赖；`example.tex`不作为提交入口，不把旧 `format.cls`、`fonts/`、`\maketitle`、目录或旧固定章节结构带入当前生产链。

## 华为杯赛事标题组件

华为杯论文封面的三行赛事标题必须调用 `gmcm-title.sty` 中的 `\GMCMContestTitle{届次中文数字}`；禁止在新论文中重新手写这三行的字体、字号、伪粗体、阴影和行距参数。新项目默认第二十三届统一调用 `\GMCMContestTitle{二十三}`；已有历届论文按题面和既有论文保留届次，生成清单可登记 contest_edition；届次变化时只修改宏参数（例如 `\GMCMContestTitle{二十四}`），不得修改 `gmcm-title.sty` 的视觉参数。编译引擎必须为 XeLaTeX，并使用系统字体 `STXinwei`；字体缺失时必须报告错误，不得自动字体替代。`gmcm-title.sty` 是华为杯标题格式的唯一事实来源。除非用户明确提出修改官方标题格式，否则 Claude Code 不得调整该组件。

## 10. Phase 5：LaTeX→PDF验收闭环

同次PDF还须通过评价章净正文测量，并在既有 first_chapters_review_path 中实际复核评价章全部页面及六项内容依据；采集器只生成待审记录，取消评价章一页上限，缺失/过期/空白撑页均不得通过。详见论文章节规范第7节。

前三章按同一[写作与验收协议](../华为杯_论文规范模板/前三章写作与验收.md)闭环：XeLaTeX编译至引用/分页稳定，采集器自动测量并渲染前三章每页、第4章交界及符号表局部，生成全新待审记录；必须实际打开全部相关图片，填写具体观察及修订后复检。audit_paper强制核对同一PDF、测量、PNG像素及当前逐页观察，workshop finish沿用该最终门禁，缺失/过期不能通过。

必须复用当前工具，不另写重复工具：

```text
华为杯_论文规范模板/tools/audit_abstract.py
→ build_supporting_materials.py --package-only → reproduce_supporting_materials.py（项目外的新目录）
→ build_supporting_materials.py（纳入复现记录并自动生成附录）
→ audit_supporting_materials.py --stage final
→ build_appendix.py → build_latex.py
→ audit_appendix.py → audit_tex.py
→ collect_academic_paper_review.py（XeLaTeX -shell-escape 双遍与实际图片路径/宽度/页码采集）
→ 实际打开论文页面并填写待审记录
→ audit_visual_plan.py --runtime claude --stage paper
→ audit_paper.py
→ pdfinfo/PyMuPDF/pdftoppm 或 pdftocairo 页面抽检
```

典型根目录命令：

执行下面的最终命令链之前，先按支撑材料skill完成待验快照和独立目录实际复现；复现记录过期时须重跑。

```powershell
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_论文规范模板/tools/audit_abstract.py -- --manifest 论文/论文输入.json --report 论文/验收输出/摘要.audit.json
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/build_figure_accounting.py -- --project-root . --plan 求解/视觉计划.json --stage render --runtime $runtime
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/build_supporting_materials.py -- --manifest 求解/支撑材料清单.json --project-root . --output 提交附件 --runtime $runtime
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/audit_supporting_materials.py -- --manifest 求解/支撑材料清单.json --stage final --project-root . --output 提交附件 --report 论文/验收输出/支撑材料.final.audit.json --runtime $runtime
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_论文规范模板/tools/build_appendix.py -- --project-root . --runtime $runtime
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_论文规范模板/tools/build_latex.py -- --manifest 论文/论文输入.json --output 论文/论文.tex --template-dir "$templateRoot/华为杯_论文规范模板" --manifest-out 论文/论文.inputs.json --runtime $runtime
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_论文规范模板/tools/audit_appendix.py -- --project-root . --main-tex 论文/论文.tex --report 论文/验收输出/附录.audit.json --runtime $runtime
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_论文规范模板/tools/audit_tex.py -- --manifest 论文/论文输入.json --main 论文/论文.tex --report 论文/验收输出/论文.tex.audit.json --runtime $runtime
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/collect_academic_paper_review.py -- --runtime $runtime --plan 求解/视觉计划.json --main-tex 论文/论文.tex --output 论文/验收输出/图形入文.review.json --project-root .
# 实际打开生成的论文页面，填写逐次出现及全篇视觉复核；工具只生成待审记录。

& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/build_figure_accounting.py -- --project-root . --plan 求解/视觉计划.json --stage paper --runtime $runtime
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/audit_visual_plan.py -- --runtime $runtime --plan 求解/视觉计划.json --stage paper --project-root . --main-tex 论文/论文.tex --report 论文/验收输出/视觉计划.paper.audit.json
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_论文规范模板/tools/audit_paper.py -- --pdf 论文/论文.pdf --source 论文/论文.tex --targets "$templateRoot/华为杯_论文规范模板/page_targets.json" --report 论文/验收输出/论文.audit.json
```

`audit_abstract.py`必须先通过；`audit_tex.py`还必须通过 TeX-only 输入链、环境、图片、匿名、标签、引用、Unicode 数学字符和正文非斜体检查。编译日志不得有致命错误、字体缺字、未定义引用或不可接受的横向溢出。最终页数只来自 XeLaTeX PDF。Word/DOCX 仅在明确需要时从相同 `.tex` 源派生，并单独运行原有 Word 审计；不得回写正式论文源。`audit_paper.py`必须复核关键词标签只出现一次、摘要为 1–2 页且单页摘要实质填充第 1 页。

## 11. 正文35页硬门禁与反注水闭环

`page_targets.json`定义：正文从目录结束后的下一页开始，到参考文献标题前结束；摘要、目录及附录不计入正文；当前项目 `required_body_pages` 为 **35**。章节角色窗口（问题章 3–27 页、前置章 1–8 页、评价/结论 1–6 页）是预警，不要求各章等长。

验收流程不是“生成 TeX 即完成”，而是：

```text
生成 TeX → TeX 审计 → XeLaTeX -shell-escape 双遍 → PDF
→ 正文页数 → 各章页数 → 图表/公式/分页/视觉检查
→ 不通过：修改真实内容或布局 → 重新全链路
→ 直到所有硬门禁通过
```

严禁用大面积空白、无意义分页、重复结论/公式/结果/图片、无关背景、虚构实验/数据/结果、装饰性或无意义图、无意义字号/间距/图表放大或压缩官方格式凑 35 页。即使用户允许“好看的无意义图”，也只能把该偏好转化为更高质量的真实证据图，不能削弱事实链。

页数不足时按以下顺序恢复，且每一步都回到对应问题章节，不在论文末尾追加“审计式大章”：

1. 补齐 Evidence Matrix 中真实适用但尚未执行的 Baseline、独立互验、误差/残差、参数可辨识性、输入敏感性、鲁棒扰动、场景、复杂度、收敛、理论边界、约束或反事实；新增实验必须真实运行并保存结构化结果。
2. 写清关键公式的由来、单位、边界、优化目标、停止条件和实际算法；对具有独特循环/分支的算法增加与主入口一致的伪代码，每问必须安排主要图文综合流程图，独立局部流程按需增加；补页过程中同步核对全文流程图不少于 2 张、“1.2 问题重述”已有总体技术路线图，且流程图统一符合 1.2的专用skill路由与后端规则。
3. 优先把多点扫描、逐折结果、设备/场景差异、误差分布、参数不确定性、特征作用、阈值/边界和模型胜负结构转为非冗余多面板 Figure。每个 Panel 必须有独立问题和真实结果源，不能把同一数字换图型重复展示。
4. 将详细证据前移并均匀嵌入各问；全量逐折表、特征字典、运行日志、文件完整性和哈希移到项目内部验收输出。不得用后置的“完整证据”“交付完整性”章节承载主要页数。
5. 每轮 PDF 都检查正文逐页联系表、章节页数和版面占用。若后 1/3 正文出现连续稀疏页、图表全部集中在前半段、章节主要由短表加大段空白组成，即使总页数达标也必须重新编排；稀疏检测只作结构告警，不能通过放大图表或强制分页消除。

不得用文字膨胀或训练“模型动物园”替代真实证据。页数足够但内容质量或格式不合格仍然失败。

章节标题同页、PDF 中文 CMap 损坏或自动范围结果不合理时，不得把错误的零页/假页数当作通过；使用 Word heading JSON、页脚/页首、渲染页面和 OCR/视觉证据交叉确认。示例验收输出是负例，不能作为真实论文通过证据。

## 12. 修复、回退和最终完成条件

同一根因最多连续尝试三次；然后停止微调，检查数据、接口、单位、约束、假设、环境或重新设计模块。任何下游事实变化都要同步摘要、正文、图表、结果索引和官方附件。永不静默跳过错误、伪造结果或改变题面要求。

只有以下全部满足，才可向用户报告完整流程完成：

1. 全部问题和赛题硬约束已回答；
2. 求解代码真实运行，关键结果有结构化文件和独立验证；
3. `结果索引.md`、AI 记录和官方附件核验完整；
4. 每问完整可运行源码、自主数据及溯源、正文未完整展示的补充图表已进入 `提交附件/`，运行验证保留在内部目录，`支撑材料说明.md` 概括目录用途、复现顺序和结果位置；
5. `audit_supporting_materials.py --stage final` 通过，支撑材料构建清单、SHA-256、源文件和快照一致且无未登记文件；
6. 论文数字、参数、图、表、摘要和附件一致可追溯；
7. `audit_abstract.py`、`audit_appendix.py`、`audit_visual_plan.py --runtime claude --stage paper`和`audit_tex.py`通过；
8. XeLaTeX `-shell-escape` 双遍成功并导出可读 PDF；
9. `audit_paper.py`无硬失败，正文至少 35 页，章节异常已处理；
10. 视觉、字体、匿名、引用、公式/图表越界检查通过；全部普通科研结果图按来源的映射、实际查看记录、参考脚本与适配方式完整且与最终图一致，符合第 1.1 节；
11. 动态附录的附件表与最终 `提交附件` 一致，问题数为实际 N，附录 1～N+1 连续，所有关键代码由统一 minted/Pygments 模板读取真实已打包源码；
12. LaTeX 主线路以 `-shell-escape` 无致命错误、未定义引用、字体缺失或不可接受溢出；
13. 未向外部系统提交，除非用户另行明确授权。

不得把“生成了示例文件”“TeX 能编译”或“PDF 总页数达到某值”单独报告为完成。



模型评价与展望按 evaluation 角色执行：正常排版净正文至少一整页，无一页上限；优缺点分别分点且各至少3点并具体解释，推广与改进至少两个自然段且不分点。生成与源审计、PDF净正文测量及全部评价章页面/内容复核共同验收；详细规则唯一见论文章节规范第7节。现有 first_chapters_review_path 同时承载评价章待审记录，旧记录须重新编译、渲染和实际审查。
