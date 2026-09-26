# 第二版交付包的仓库整合记录

输入包：`ORION_figures_workflow_pr_bundle.zip`（用户提供）。包内 79 个文件均纳入仓库，包含流程图和示例图的矢量文件、PDF、PNG、预览、生成脚本、样式工具、制作记录、提交说明及原包缓存文件。

当前入口为 [A 题图件总页](../../../README.md) → [流程图目录](../../README.md) → [第二版 ink_v2](../README.md)，默认展示青绿·赭石第二版。第一版黑白 SVG 是第二版生成器的固定输入，其历史过程说明保留并标注版本。

## 本次整理

- 图件总页与流程图目录以第二版成图、编辑路径和构建命令为主。
- 第二版 README 列出四套配色的 SVG／SVGZ、PDF、高清 PNG 和预览的直接链接，移除“成图只在会话完整包内”的旧说明。
- 工具 README 指向第二版范例；提交说明更新为完整包整合。
- 第一版 PROCESS、SOURCE_MAP、AI_USAGE 添加历史版本说明。
- 包内图稿、Python 源码、色板、PDF／PNG 和其他非 Markdown 文件保留提供时的文件内容。

## 本机构建

在独立临时目录运行以下命令，退出码 0，实际生成青绿、浅绛、烟岚、灰阶四个第二版 SVG：

```powershell
D:\python\python.exe paper_a_figures/engraved_workflow/ink_v2/build.py --all-palettes --svg-only
```

本机 PATH 未提供 Inkscape，因此本次没有重新渲染 PDF／PNG；仓库内的 PDF／PNG 是交付包已有的完成品。原包 `LOCAL_REVIEW.md` 与 `LAYOUT_REVIEW.json` 记录原制图环境的渲染与检查，本文件记录本次导入，二者不混写。机器可读摘要见 `BUNDLE_INTEGRATION.json`。

现有 `.github/workflows/engraved-workflow.yml` 属于第一版历史构建入口；第二版在仓库根目录运行上述 `ink_v2/build.py` 命令。

## 原包完整文件清单

- `paper_a_figures/engraved_workflow/assets/workflow.svg`
- `paper_a_figures/engraved_workflow/ink_v2/README.md`
- `paper_a_figures/engraved_workflow/ink_v2/__pycache__/build.cpython-313.pyc`
- `paper_a_figures/engraved_workflow/ink_v2/assets/workflow_mono.svg`
- `paper_a_figures/engraved_workflow/ink_v2/assets/workflow_mono.svgz`
- `paper_a_figures/engraved_workflow/ink_v2/assets/workflow_qianjiang.svg`
- `paper_a_figures/engraved_workflow/ink_v2/assets/workflow_qianjiang.svgz`
- `paper_a_figures/engraved_workflow/ink_v2/assets/workflow_qinglu.svg`
- `paper_a_figures/engraved_workflow/ink_v2/assets/workflow_qinglu.svgz`
- `paper_a_figures/engraved_workflow/ink_v2/assets/workflow_yanlan.svg`
- `paper_a_figures/engraved_workflow/ink_v2/assets/workflow_yanlan.svgz`
- `paper_a_figures/engraved_workflow/ink_v2/build.py`
- `paper_a_figures/engraved_workflow/ink_v2/docs/LAYOUT_REVIEW.json`
- `paper_a_figures/engraved_workflow/ink_v2/docs/LOCAL_REVIEW.md`
- `paper_a_figures/engraved_workflow/ink_v2/docs/REFERENCES.md`
- `paper_a_figures/engraved_workflow/ink_v2/docs/SOURCE_ALIGNMENT.md`
- `paper_a_figures/engraved_workflow/ink_v2/exports/workflow_mono.pdf`
- `paper_a_figures/engraved_workflow/ink_v2/exports/workflow_mono.png`
- `paper_a_figures/engraved_workflow/ink_v2/exports/workflow_mono_preview.png`
- `paper_a_figures/engraved_workflow/ink_v2/exports/workflow_qianjiang.pdf`
- `paper_a_figures/engraved_workflow/ink_v2/exports/workflow_qianjiang.png`
- `paper_a_figures/engraved_workflow/ink_v2/exports/workflow_qianjiang_preview.png`
- `paper_a_figures/engraved_workflow/ink_v2/exports/workflow_qinglu.pdf`
- `paper_a_figures/engraved_workflow/ink_v2/exports/workflow_qinglu.png`
- `paper_a_figures/engraved_workflow/ink_v2/exports/workflow_qinglu_preview.png`
- `paper_a_figures/engraved_workflow/ink_v2/exports/workflow_yanlan.pdf`
- `paper_a_figures/engraved_workflow/ink_v2/exports/workflow_yanlan.png`
- `paper_a_figures/engraved_workflow/ink_v2/exports/workflow_yanlan_preview.png`
- `paper_a_figures/engraved_workflow/ink_v2/inspect_figure.py`
- `paper_a_figures/ink_engraving_agent/AGENT.md`
- `paper_a_figures/ink_engraving_agent/README.md`
- `paper_a_figures/ink_engraving_agent/STYLE_PLAYBOOK.md`
- `paper_a_figures/ink_engraving_agent/__init__.py`
- `paper_a_figures/ink_engraving_agent/__pycache__/__init__.cpython-313.pyc`
- `paper_a_figures/ink_engraving_agent/__pycache__/style.cpython-313.pyc`
- `paper_a_figures/ink_engraving_agent/draw_palette_sheet.py`
- `paper_a_figures/ink_engraving_agent/examples/README.md`
- `paper_a_figures/ink_engraving_agent/examples/demo_matplotlib.py`
- `paper_a_figures/ink_engraving_agent/examples/outputs/bar_demo_mono.pdf`
- `paper_a_figures/ink_engraving_agent/examples/outputs/bar_demo_mono.png`
- `paper_a_figures/ink_engraving_agent/examples/outputs/bar_demo_mono.svg`
- `paper_a_figures/ink_engraving_agent/examples/outputs/bar_demo_qianjiang.pdf`
- `paper_a_figures/ink_engraving_agent/examples/outputs/bar_demo_qianjiang.png`
- `paper_a_figures/ink_engraving_agent/examples/outputs/bar_demo_qianjiang.svg`
- `paper_a_figures/ink_engraving_agent/examples/outputs/bar_demo_qinglu.pdf`
- `paper_a_figures/ink_engraving_agent/examples/outputs/bar_demo_qinglu.png`
- `paper_a_figures/ink_engraving_agent/examples/outputs/bar_demo_qinglu.svg`
- `paper_a_figures/ink_engraving_agent/examples/outputs/bar_demo_yanlan.pdf`
- `paper_a_figures/ink_engraving_agent/examples/outputs/bar_demo_yanlan.png`
- `paper_a_figures/ink_engraving_agent/examples/outputs/bar_demo_yanlan.svg`
- `paper_a_figures/ink_engraving_agent/examples/outputs/heatmap_demo_mono.pdf`
- `paper_a_figures/ink_engraving_agent/examples/outputs/heatmap_demo_mono.png`
- `paper_a_figures/ink_engraving_agent/examples/outputs/heatmap_demo_mono.svg`
- `paper_a_figures/ink_engraving_agent/examples/outputs/heatmap_demo_qianjiang.pdf`
- `paper_a_figures/ink_engraving_agent/examples/outputs/heatmap_demo_qianjiang.png`
- `paper_a_figures/ink_engraving_agent/examples/outputs/heatmap_demo_qianjiang.svg`
- `paper_a_figures/ink_engraving_agent/examples/outputs/heatmap_demo_qinglu.pdf`
- `paper_a_figures/ink_engraving_agent/examples/outputs/heatmap_demo_qinglu.png`
- `paper_a_figures/ink_engraving_agent/examples/outputs/heatmap_demo_qinglu.svg`
- `paper_a_figures/ink_engraving_agent/examples/outputs/heatmap_demo_yanlan.pdf`
- `paper_a_figures/ink_engraving_agent/examples/outputs/heatmap_demo_yanlan.png`
- `paper_a_figures/ink_engraving_agent/examples/outputs/heatmap_demo_yanlan.svg`
- `paper_a_figures/ink_engraving_agent/examples/outputs/line_demo_mono.pdf`
- `paper_a_figures/ink_engraving_agent/examples/outputs/line_demo_mono.png`
- `paper_a_figures/ink_engraving_agent/examples/outputs/line_demo_mono.svg`
- `paper_a_figures/ink_engraving_agent/examples/outputs/line_demo_qianjiang.pdf`
- `paper_a_figures/ink_engraving_agent/examples/outputs/line_demo_qianjiang.png`
- `paper_a_figures/ink_engraving_agent/examples/outputs/line_demo_qianjiang.svg`
- `paper_a_figures/ink_engraving_agent/examples/outputs/line_demo_qinglu.pdf`
- `paper_a_figures/ink_engraving_agent/examples/outputs/line_demo_qinglu.png`
- `paper_a_figures/ink_engraving_agent/examples/outputs/line_demo_qinglu.svg`
- `paper_a_figures/ink_engraving_agent/examples/outputs/line_demo_yanlan.pdf`
- `paper_a_figures/ink_engraving_agent/examples/outputs/line_demo_yanlan.png`
- `paper_a_figures/ink_engraving_agent/examples/outputs/line_demo_yanlan.svg`
- `paper_a_figures/ink_engraving_agent/palette_sheet.svg`
- `paper_a_figures/ink_engraving_agent/palettes.json`
- `paper_a_figures/ink_engraving_agent/style.py`
- `submission/APPLY_TO_REPO.md`
- `submission/PR_TITLE_BODY.md`
