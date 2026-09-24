---
name: scibox-diagram
description: 制作与修改可编辑的 draw.io / diagrams.net 示意图（.drawio XML），产出 .drawio + PNG/PDF。三条路径：套用内置模板（五带技术路线图、三栏研究框架图、三栏阶段流程图、横版任务流水线图）、从零手写 XML、高保真复刻参考图。当用户要求技术路线图、全文概览、研究框架图、论文流程图、算法流程图、模型/系统架构图、方法示意图、把论文或课题做成一张图、答辩用图，或要求画 drawio 图、照着某张图重画成可编辑矢量图、修图（文字溢出/箭头错乱/配色不一致/排版对不齐）时使用。本华为杯项目普通结果图平等选用academic-figure-skill或modelviz-skill；算法、物理及逐问图文综合图优先按项目专用skill路由。
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# 论文与研究示意图（draw.io）

主产物是**可编辑的 .drawio**，PNG/PDF 是附带导出。模板、脚本和参考文件从本共享目录读取；内容 JSON、draw.io、预览、导出及复核记录全部写入本次工作区。

## 共享路径与命令

按模板 `华为杯_求解规范/工作区工作流.md` 设置 `$python`、`$templateRoot`、`$workspaceRoot`、`$runtime`。本 skill 及 references 中的命令共用以下变量：

```powershell
$skillSide = if ($runtime -eq 'codex') { '.agents' } else { '.claude' }
$skillRelative = "$skillSide/skills/sci-box-main/sci-box-main/skills/scibox-diagram"
```

共享脚本通过 `run_shared_skill.py` 在当前工作区执行，保留缓存和写入边界；不要切换到共享 skill 目录生成图。参考和 assets 链接相对本 SKILL.md；content.json、fig.drawio、out.drawio 等命令参数相对 workspace_root，实际使用时放入本题求解目录。修改模板内容先复制选定 JSON，不复制整套 skill。

## 先判断走哪条路

| 情况 | 路径 | 入口 |
|---|---|---|
| 全文脉络、研究框架、执行流程，或课题的任务分解 | **A 按科学内容选模板或自由布局** | 下方模板索引 |
| 其他示意图：算法流程、模型架构、实验设计、机制示意… | **B 从零手写 XML** | `references/authoring.md` |
| 给了参考图，要照着重画成可编辑矢量图 | **C 高保真复刻** | `references/replication.md` |

三条路的 XML 写法一致，产物可互相接着改；区别只在**流程纪律的严格程度**。

## A. 套模板

| 模板 id | 版式 | 适合表达 | 说明 |
|---|---|---|---|
| `roadmap-5band` | 954×1296 竖版，五条点线带 + 左旗标 + 右竖排标签 | 提出问题 → 数据与指标 → 方法与机制 → 结果对比 → 评价推广 | `references/roadmap-5band.md` |
| `framework-3col` | 1026 宽三栏，左阶段链 / 中内容块 / 右方法清单，高度自适应 | 研究**内容**全景：每个阶段对应哪些研究内容、用什么方法 | `references/framework-3col.md` |
| `stageflow-3col` | 1000 宽三栏，中栏每块实色标题条 + 独立色系，高度自适应 | 研究/系统的**执行流程**：阶段推进、决策分支、成果分发 | `references/stageflow-3col.md` |
| `taskflow-land` | **横版** 1360 宽，若干任务块，块内流水线 + 每步挂做法细节 | 课题拆成「任务一…任务四」，每步要写清方法与结论；适合 16:9 | `references/taskflow-land.md` |

本端共同步 32 套模板（原有 4 套＋新增 28 套）；新增 28 套独立参考模板均有 `example.json`、`preview.png`、可编辑 `example.drawio`、PDF、说明和 `qa/visual-review.json`，状态须以当前工作区真实调用和最终审计为准：

| 模板 ID | 参考结构 |
|---|---|
| `behavior-intervention-3column` | 行为机制与干预三栏 |
| `coupled-method-experiment-framework` | 耦合方法与实验验证 |
| `cube-venn-model-research` | 立方体与双圆交叉任务 |
| `data-model-deployment-5stage` | 数据、建模与系统落地五阶段 |
| `drug-discovery-triad-planes` | 三环耦合与三层斜面 |
| `dual-circle-biological-framework` | 双圆机制与双层实验框架 |
| `dual-circle-biological-framework-variant` | 双圆机制实验框架变体 |
| `dual-loop-layered-platform` | 双循环三层平台 |
| `dual-study-cylinder-roadmap` | 双研究模块圆柱路线 |
| `ecotourism-integration-3band` | 数字生态旅游三带整合 |
| `feature-detection-research-5band` | 多特征融合与目标检测五带 |
| `fieldwork-analysis-3band` | 调研采集与实证分析三阶段 |
| `five-chapter-research-roadmap` | 五章节研究内容与方法 |
| `four-band-method-roadmap` | 四阶段研究总体路线 |
| `four-content-evidence-roadmap` | 四内容模块与证据链 |
| `four-stage-research-framework` | 四阶段研究与成果推广 |
| `health-system-concentric` | 智慧康养同心架构 |
| `hexagon-chain-research-5band` | 双侧六边形阶段链 |
| `innovation-chain-5stage` | 创新产业链五阶段 |
| `model-optimization-6stage` | 模型优化六阶段 |
| `port-sustainability-quality-houses` | 港口双质量屋与减排策略 |
| `research-columns-evidence-cards` | 三列研究与证据卡 |
| `research-design-vertical-loop` | 纵向研究设计与实证闭环 |
| `research-framework-5band` | 五阶段研究框架 |
| `research-methods-5stage` | 研究内容与方法五阶段 |
| `stage-design-prism-5band` | 五阶段立体卡片与决策 |
| `triple-band-experiment-roadmap` | 三阶段联合实验与机制验证 |
| `triple-band-research-validation` | 三带研究基础与联合验证 |

1. 读模板说明的两节：**语义约定**（哪些槽位并列、哪些汇流、哪两组必须可对比）与**字数预算**。语义放错比字数超框严重。
2. 从用户材料抽内容，**不要编**；有源文件（`.tex`/`.md`/代码）时逐个核对数值，术语用原文。
3. 复制 `assets/<template_id>/example.json` 改写，`"\n"` 手动断行。
4. 渲染（写文件前逐槽校验字数，超框报出具体预算）：

```powershell
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/run_shared_skill.py -- --script "$skillRelative/scripts/roadmap_5band.py" -- content.json -o out.drawio     # 模板 roadmap-5band
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/run_shared_skill.py -- --script "$skillRelative/scripts/framework_3col.py" -- content.json -o out.drawio    # 模板 framework-3col
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/run_shared_skill.py -- --script "$skillRelative/scripts/stageflow_3col.py" -- content.json -o out.drawio    # 模板 stageflow-3col
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/run_shared_skill.py -- --script "$skillRelative/scripts/taskflow_land.py" --  content.json -o out.drawio    # 模板 taskflow-land（横版）
```

新增模板见 `references/adding-templates.md`。

## B. 从零手写 XML

读 `references/authoring.md`：骨架、样式速查、中文字宽预算、连接器写法、四个必踩的坑。图标与特殊图元见 `references/icons.md`。

三条最容易翻车的：

- **先排栅格再写图元**：定死画布、列基线、步距；同族同宽同步距，数量可变的组用等分公式。
- **中文手动断行**：全角≈字号、半角≈字号/2、行高≈字号+3；16px 字号下 160px 宽的盒子每行最多 9 个汉字。竖排逐字 `&lt;br&gt;` 堆叠，**不要用 `horizontal=0`**（中文会躺倒）。
- **连接器端点离盒边 1px**；一分多/多合一画成"竖线+横母线+分支"，不要画成 N 条独立斜线。

画之前想清楚每根箭头的语义（谁到谁、单向还是双向、扇入还是扇出）；说不出含义的箭头不要画。

## C. 高保真复刻参考图

比 B 多一套证据链，照 `references/replication.md` 执行，要点：

1. **先标定再动笔**：连通域抠盒子坐标与填充色、行列扫描找框线、颜色普查取配色、量字宽反推字号。**不要目测**，也不要假设"标题一定比正文大"。
2. **四件中间产物**：`visual-spec.md`（看到了什么）、`layout-grid.md`（坐标计划）、`asset-ledger.md`（哪些是近似的，防止悄悄丢元素）、`defect-log.md`（首次截图后只增不改）。
3. **≥3 轮**"截图 → 九区盘点 → 修完所有 P0/P1 → 重渲 → 逐条核销"；截图必须是画布本身。
4. **红队复审 + 自评分卡**（见 `references/self-check.md`）：总分 <40 或任一维 ≤4 不交付。
5. 像素差分定位残留差异，逐条写进 `defect-log.md`，不写"已完美还原"。

## 通用：校验、预览、导出

```powershell
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/run_shared_skill.py -- --script "$skillRelative/scripts/check_layout.py" -- fig.drawio      # 溢出/越界/重复 id/重叠/穿盒/位图（--strict 作门禁）
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/run_shared_skill.py -- --script "$skillRelative/scripts/export_figure.py" -- fig.drawio     # 1:1 PNG + 矢量 PDF（需 drawio 命令行）
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/run_shared_skill.py -- --script "$skillRelative/scripts/preview_html.py" -- fig.drawio      # 浏览器预览，无需 drawio 命令行
```

`check_layout` 用中文字宽模型、噪声低，正常的图应当 **FAIL 0 / WARN 0**；报警就值得认真看。它刻意不查紧密堆叠的行列间距和同族尺寸对齐（前者是刻意排版，后者机器判族必然误报）——这两项交给眼睛。规则详解与四个规避手法见 `references/preflight-rules.md`。

**不看渲染图不算画完**：XML 里看不出文字溢出、箭头压字、盒子挤扁。打开 PNG 至少过两轮：① 文字溢出/压线；② 箭头方向与语义；③ 同族元素对齐同宽；④ 数值有没有抄错。完整的九区盘点与交付清单见 `references/self-check.md`。

交付 `.drawio` + PNG/PDF；走模板路径时保留 content JSON 作为可复现源。尺寸提醒：954px 宽、16px 字号的图压到 A4 正文 `0.97\textwidth` 约 6.5pt，建议整页横排或答辩使用，正文小图另做精简版。

## 参考索引

| 文件 | 何时读 |
|---|---|
| `authoring.md` | 手写示意图：骨架、样式串、字宽预算、连接器 |
| `icons.md` | 需要图标、旗标、块箭头、弯箭头等特殊图元 |
| `roadmap-5band.md` | 用五带路线图模板 |
| `framework-3col.md` | 用三栏研究框架模板（内容全景）|
| `stageflow-3col.md` | 用三栏阶段流程模板（执行流程）|
| `taskflow-land.md` | 用横版任务流水线模板 |
| `adding-templates.md` | 新增一个模板 |
| `replication.md` | 复刻参考图：标定方法、四件产物、迭代闭环 |
| `self-check.md` | 九区盘点、红队复审、自评分卡、交付清单 |
| `preflight-rules.md` | 静态检查在查什么、误报如何绕开 |

## 不适用

- 折线图、热图、统计图等**数据图表** → 按项目双来源规则平等选用 `academic-figure-skill` 或 `modelviz-skill`；
- 需要 LaTeX 排版的公式推导链 → 用 TikZ 或写进正文。

项目中 algorithm-mechanism-diagram、engineering-physics-mechanism-diagram、comprehensive-graphic-text-flowchart 的专用语义与自由布局优先；本skill提供可复用原语、配色和严格检查，不用固定三栏五带限制综合图。位图与同对象叠层例外见preflight-rules。
