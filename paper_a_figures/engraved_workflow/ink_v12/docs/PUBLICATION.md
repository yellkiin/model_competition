# 第十二版发布核对

- 基线：main 提交 `d421c7e5fc1c2d8fd9d85ae29902b2f97462459f` 中已发布的 ink_v11。
- 发布分支：`figures/workflow-v12-a4-uniform-20260927`。
- 构建入口提交：`376fed09490792d9bdf243400a3bbcc916960a44`。
- 图件发布提交：`2ccbb1a2d762189cedabf470f724c4d3f9c9fffb`。
- GitHub Actions 运行：[36278611678](https://github.com/yellkiin/model_competition/actions/runs/36278611678)，全部步骤成功。
- 发布产物：`workflow-ink-v12-reviewed`，artifact ID `10918625764`。

已下载这次实际发布的 ZIP，在本地再次核对：八份 SVG 与本地已审版本逐字节相同；四份紧裁 PDF 的 MuPDF 三倍渲染与本地版本逐像素相同。全部十二份图件/纸面校样 PDF 均单页、无位图和字体资源。紧裁 PDF 为 247×109.841343 mm，纵向 A4 校样为 210×297 mm，横向 A4 校样为 297×210 mm。再次查看了四色整图与同纸张大小前后对照，未发现新增遮挡、裁边或缺字。产物不含字体文件。

另以 A4、25 mm 页边距的最小 LaTeX 文档测试实际紧裁 PDF 的两种插入方式：横向 `\linewidth` 为 702.78308 TeX pt（247 mm），纵向 `\textwidth` 为 455.24411 TeX pt（160 mm）；完成两页编译并检查页面与图注位置。此测试不是对 PR #69 整篇论文的重编译，不把它表述为整篇论文已经更新。

发布完成后，一次性工作流已删除。最终变更仅保留 ink_v12 新目录，旧版图件、现稿论文、求解代码和实验记录均不覆盖。
