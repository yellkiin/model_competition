# 图1.1 · 线刻流程图第三版（字体与位置修订）

保留 ink_v2 的六算子案例、子图包络、核心任务条、硬件剖面和排线质感，不改论文正文、求解算法或实验数据。本目录为 PR #58 的修订版本；PR 合入 main 前，请从 PR 分支查看最新成图。

## 成图

![灰阶完整预览](exports/workflow_mono_v3_preview.png)

| 版本 | 跨电脑稳定 SVG | 文字可编辑 SVG | 矢量 PDF | 6000 像素 PNG |
|---|---|---|---|---|
| 灰阶 | [SVG](assets/workflow_mono_v3.svg) | [可编辑源图](assets/workflow_mono_v3_editable.svg) | [PDF](exports/workflow_mono_v3.pdf) | [PNG](exports/workflow_mono_v3.png) |
| 青绿·赭石 | [SVG](assets/workflow_qinglu_v3.svg) | [可编辑源图](assets/workflow_qinglu_v3_editable.svg) | [PDF](exports/workflow_qinglu_v3.pdf) | [PNG](exports/workflow_qinglu_v3.png) |

常规 `.svg` 与 `.svgz` 已将文字转换为矢量路径，不依赖查看电脑的字体。`_editable.svg` 保留中文和西文文字，编辑时需要本机宋体与 Times New Roman。公式以 Computer Modern 矢量保存，其 LaTeX 源在 `math_layout.py` 和公式对象的 `data-tex` 属性中。

## 本次七项处理

1. **字体**：直接检查 `workshop_v2/论文/论文.pdf` 的字体资源和第9页公式，而不只依据模板。正文为 SimSun（宋体）与 Times New Roman；数学字体为 Computer Modern（CMMI12、CMSY10、CMR12 等）。先前说明中的 STIX / Liberation Serif 只是近似，不是论文实际字体，现已纠正。花体 P 改为 LaTeX `\mathcal{P}`，相关公式和上下标同步排版。
2. **PR 冲突**：保持 PR #58 的第三版结构，以本次修订源文件为准；不以 main 的旧图生成脚本覆盖。是否可合并以 PR 页面实时状态为准，本流程不自动合并 main。
3. **B 的深色**：旧色块仅提示迁移，不代表另一种任务类别。现在 A、B、C、D 使用统一纸面样式，由箭头与短语“迁移 B”表达操作。
4. **底部文字**：删除“Q3：固定同一方案……”整行，输出说明重新定位。该实验对照口径仍可在独立图解中说明。
5. **COPY 标注**：COPY_OUT、COPY_IN 分别居中放在对应搬运张量上方，保留白色描边避开背景线。
6. **核心编号**：核心 k_1、k_2 居中对齐两组核心剖面，编号按真实数学下标排版。
7. **图定义公式**：G=(T∪O,E) 放在左列输入行右侧的独立留白处，不再悬压在计算图上；Makespan 公式也统一了基线和下标。

## 字体与复现

本次正式成图使用 Windows 原生 SimSun 与 Times New Roman 生成实际文字路径，数学公式由与论文一致的 LaTeX Computer Modern 排版。缺少规定字体时导出脚本会报错，不会偷偷改用兼容字体。只保存图中实际使用的文字/公式矢量对象，不附带任何字体文件。

`docs/FONT_AUDIT.json` 记录各文字对象实际采用的字体。`docs/EXPORT_RECEIPT.json` 记录 SVG/PDF 校验和、图面内容与结构检查；结构检查不替代人工查看成图。

在仓库根目录、具备本地合法字体及 Inkscape 的 Windows 环境执行：

```powershell
python -m pip install fonttools
python paper_a_figures/engraved_workflow/ink_v3/build.py
```

生成流程已集成修订步骤，不会出现重新运行 build.py 后恢复旧字体、深色 B 或底部 Q3 文字的问题。已有 `assets/math_layout.json` 公式缓存时，无须安装 TeX；修改公式后重新生成缓存需要 pdflatex 与 PyMuPDF。仅生成保留文字的矢量中间稿可加 `--svg-only`，该稿在缺少宋体的电脑上显示可能被系统替换，正式插图应使用文字转曲后的 SVG 或 PDF。

GitHub 自动导出通过修改 `RENDER_REQUEST.json` 发起：Linux 排版公式 → Windows 原生字体转曲 → Linux 导出与结构校验。各阶段只传递图形和源码，不传递字体文件。流程只提交本目录，不合并 PR，也不运行求解实验。

独立图解：[FIGURE_EXPLANATION.md](docs/FIGURE_EXPLANATION.md)。画布 420 × 255.5 mm；缩小插入论文时优先使用矢量 PDF。
