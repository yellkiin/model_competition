# PR 标题与说明

标题：`figures(A): 完整整合流程图交付包并以第二版为主入口`

## 内容

图件目录原来的首页仍展示第一版黑白流程图，且第二版交付包中的提交说明和缓存文件尚未纳入。此次完整整合用户提供的交付包，并将图件总入口、流程图目录与工具 README 指向第二版青绿流程图。

- 包含四套配色的 SVG／SVGZ、PDF、高清 PNG、预览、色板、样式工具及示例图。
- 补齐原包中的提交说明与缓存文件，图稿和源码使用交付包内容。
- 增加第二版资产表和整合清单，将第一版过程文件标为历史源母版记录。

## 本地构建

`D:\python\python.exe paper_a_figures/engraved_workflow/ink_v2/build.py --all-palettes --svg-only` 可生成四套第二版 SVG。本机缺少 Inkscape，PDF／PNG 使用交付包内已完成的导出文件。
