# 第七版发布后复核

## 实际发布

从main提交 `8e1ed56df8d8da755c27a2be14a50e22cfbf5d02` 建立独立分支 `figures/workflow-v7-layout-arrows-20260927`。GitHub Actions运行 `36273635614` 已成功完成四配色重建、逐对象核验、PDF/PNG导出、实际发布包上传、生成文件提交及一次性发布工作流清理。

图件发布提交：`69197fac15419b66dcb7366f15a11d541051651b`。

实际产物：`workflow-ink-v7-reviewed`，artifact ID `10915924624`，40个文件。ZIP SHA256：`1a99b3f3cc8b831bbd850937bd2bda31db7392eeccc4fd7219109b1faf6f372c`。本记录为发布后补充，不包含在该原始artifact内。

## 下载后检查

已通过GitHub连接下载真实发布ZIP，核对ZIP哈希并解压。八份SVG全部与本地已审文件逐字节相同；三个Python源文件、README及配套Markdown/LaTeX文字也与本地版本一致。四份发布PDF均为单页、零字体资源、零位图资源。

再次用独立MuPDF渲染发布青绿PDF并查看整图，确认顶部两条箭头已删除，a图与b/c整体图形中心对齐，预算标题框无残留副标题，四条核心至L1/UB的箭头竖直向下，DDR至L2填充虚线靠近说明文字。底部候选—评价—反馈闭环和所有原有操作示意保留。

## 范围

最终交付只新增 `paper_a_figures/engraved_workflow/ink_v7/`；此前版本、论文源文件、80页论文PDF、求解代码及实验数据均不修改。PR #69已经合并，本次提供可直接替换图1.1及相关说明的Markdown与LaTeX片段，没有声称已重新编译整篇论文或执行新求解实验。交付不含字体文件。一次性发布工作流不留在最终变更中。
