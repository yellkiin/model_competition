# 第二版流程图交付包的仓库整合

完整交付包已整合到仓库。主入口是 [A 题图件 README](../paper_a_figures/README.md)，流程图展示、编辑和论文排版采用 [第二版 ink_v2](../paper_a_figures/engraved_workflow/ink_v2/README.md)。

1. `paper_a_figures/engraved_workflow/ink_v2/` 包含四套配色的 SVG／SVGZ、PDF、高清 PNG、预览、生成器和来源／制作记录。
2. `paper_a_figures/ink_engraving_agent/` 包含色板、样式页、Agent 提示词、样式适配器，以及三类 Matplotlib 示例的四套配色成图。
3. `paper_a_figures/engraved_workflow/assets/workflow.svg` 是保留的第一版源母版；第二版生成器依赖这个文件。
4. 图件总入口和流程图目录 README 已以第二版为主；第一版过程文件标为历史记录。
5. 本包中的提交说明和 Python 缓存文件一并保留，缓存文件仅来自原包，重新生成请运行 Python 源文件。

本机可运行第二版 SVG 构建命令。PDF／PNG 已来自交付包并纳入仓库；重新导出 PDF／PNG 需要 Inkscape。完整清单与本次整合记录见 [BUNDLE_INTEGRATION.md](../paper_a_figures/engraved_workflow/ink_v2/docs/BUNDLE_INTEGRATION.md)。
