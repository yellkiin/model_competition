# 图1.1 · 第十三版（ink_v13）

基于 `ink_v11`，按最新确认将环节 02 改为**两列三排**：第一排 a／b，第二排 c／d，第三排 e／f。保留 01 联合决策 → 02 候选生成 → 03 统一执行评价与底部反馈闭环。四套配色采用相同布局和文字。

## 版式与文字

- 环节 02 列距由 475 增至 550，行距为 530；六项统一汇入完整候选，不把 a—f 画成串行步骤。
- 整图由 3500×1550 调整为 3120×2100。两列布局节约横向空间，纵向容纳三排操作。
- 多数正文与操作标题在原字号上放大约 20%–27%，栏目标题约 18%；数学混排整体缩放，保持文字与公式相对位置。固定行距的 L2 竖排说明放大 16%，相邻 COPY 标签放大 14%并向两侧错开。
- 同步拉开前后说明、切分示意与下方标签的间距，重新连接汇总线、完整候选及评价反馈箭头。保留原生宋体、Times New Roman 和 Computer Modern 字形。

字号是 SVG 用户单位，不能当作论文中的 pt。按相同论文宽度放置时，整图收窄与文字放大共同提高可读性。主图适合 `width=\textwidth`；另附 02 独立矢量图，可按论文需要用作局部补图。

## 四套配色

### 青绿·赭石
![青绿第十三版](exports/workflow_qinglu_v13_preview.png)
[矢量 PDF](exports/workflow_qinglu_v13.pdf) · [便携 SVG](assets/workflow_qinglu_v13.svg) · [可编辑 SVG](assets/workflow_qinglu_v13_editable.svg) · [高清 PNG](exports/workflow_qinglu_v13.png) · [02 局部 PDF](exports/workflow_qinglu_v13_detail.pdf)

### 浅绛·苔色
![浅绛第十三版](exports/workflow_qianjiang_v13_preview.png)
[矢量 PDF](exports/workflow_qianjiang_v13.pdf) · [便携 SVG](assets/workflow_qianjiang_v13.svg) · [可编辑 SVG](assets/workflow_qianjiang_v13_editable.svg) · [高清 PNG](exports/workflow_qianjiang_v13.png) · [02 局部 PDF](exports/workflow_qianjiang_v13_detail.pdf)

### 烟岚·石青
![烟岚第十三版](exports/workflow_yanlan_v13_preview.png)
[矢量 PDF](exports/workflow_yanlan_v13.pdf) · [便携 SVG](assets/workflow_yanlan_v13.svg) · [可编辑 SVG](assets/workflow_yanlan_v13_editable.svg) · [高清 PNG](exports/workflow_yanlan_v13.png) · [02 局部 PDF](exports/workflow_yanlan_v13_detail.pdf)

### 墨线·灰阶
![灰阶第十三版](exports/workflow_mono_v13_preview.png)
[矢量 PDF](exports/workflow_mono_v13.pdf) · [便携 SVG](assets/workflow_mono_v13.svg) · [可编辑 SVG](assets/workflow_mono_v13_editable.svg) · [高清 PNG](exports/workflow_mono_v13.png) · [02 局部 PDF](exports/workflow_mono_v13_detail.pdf)

主图 PDF 为 468×315 mm 的矢量母版，论文通过 `\includegraphics` 等比缩放；高清 PNG 宽 6000 像素，预览宽 2100 像素。局部 PDF 宽 150 mm，保留完整 02 和下方完整候选。便携 SVG、SVGZ 和 PDF 的文字已转曲；可编辑 SVG 保留 107 个文字对象，编辑时需要对应字体。交付不含字体文件。

## PR #69 配套正文

[一段式论文正文与插入说明](docs/PAPER_TEXT_PR69.md) · [可直接替换的 LaTeX 图文片段](docs/PR69_figure_and_text.tex) · [A4 排版样张](docs/workflow_qinglu_v13_A4.pdf)

PR #69 已合并，本次单独提交 v13 图件及配套文字。插入片段替换原 `fig:roadmap` 图环境和其后三段旧图说明，保留原标签。本次没有修改或重新编译原 80 页论文。

## 重建与核验

```bash
python -m pip install pymupdf pillow pypdf
# 安装 Inkscape；或将 INKSCAPE_BIN 指向便携版命令行程序。
python paper_a_figures/engraved_workflow/ink_v13/build.py --all
python paper_a_figures/engraved_workflow/ink_v13/verify.py --json paper_a_figures/engraved_workflow/ink_v13/docs/VERIFICATION.json
```

重建需要相邻的 `ink_v11/assets/` 八份原始 SVG。`build.py` 沿用已有原生字形，不重新排字或下载字体。PDF 由 Inkscape 导出，PNG 由 MuPDF 独立渲染。核验包括两列三排的明确位置、四套配色的几何一致性、SVG 引用、SVGZ 内容、PDF 单页和无位图纹理、PNG 尺寸；同时查看整图及局部，不能以结构检查替代视觉审阅。

[实际检查记录](docs/LOCAL_REVIEW.md) · [自动核验](docs/VERIFICATION.json) · [四色总览](docs/four_palettes_review.png)
