# 源文件与语义保持

本次直接输入：已合并PR #58的第三版`workflow_mono_v3.svg`及`workflow_mono_v3_editable.svg`，从实际导出artifact取得；仓库阅读基线`f1574d71b7aa273d9971171ffbe9698ab6d792c2`。

修改依据为用户本次14条原始批注及截图，不以早期35页论文或其他算法报告替换这些要求。颜色读取用户指定`ink_v2/assets`使用的`paper_a_figures/ink_engraving_agent/palettes.json`，只使用qinglu/qianjiang/yanlan/mono。

四版都保留联合划分、核心归属、核内顺序、候选来源、完整执行评价、Makespan和反馈改进。划分集合式、当前方案式、候选式、Makespan式、FIFO复用窗口原数学路径未改；唯一删除的是批注05指定的G定义式。删除图内停止/输出区域是压缩展示内容，并非变更算法终止或返回规则。

新增标题只有“原始计算图”“子图划分与归核”“总体评价”，用于批注要求的层级和连接。已有示意图不是#38的数值实验轨迹。本轮没有重跑实验或改变任何实验数据。

转曲版重用已在第三版使用的SimSun、Times New Roman和Computer Modern图中文字形，没有打包字体。编辑SVG保留原字体名称；没有宣称在未安装这些字体的机器上文本渲染能自动一致。
