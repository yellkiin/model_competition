# 耦合方法构建与实验验证五带研究框架图

独立ID：`coupled-method-experiment-framework`；来源：ref-14。

五带框架：研究基础与总体方案两卡，双耦合圆分别向左右三项分析扇出，模型开发与技术优化分区，六站实验处理链（包含四项与三项组合卡），成果总结四分支。左右各三条阶段标签跨带对应；模型和技术优化框之间没有凭空新增流程箭头。

## 固定数量与内容接口

example.json含template_id、texts；文字字符串或字符串数组，按字段替换，可用\n断行。拓扑及节点数量固定，缺少/多余字段均拒绝；不承诺无限节点。关系不适合时另选模板或重排，不改题意硬套。

|字段|每行全角上限|行数上限|
|---|---|---|
|title|28|1|
|left_label_0|1|10|
|right_label_0|1|10|
|left_label_1|1|10|
|right_label_1|1|10|
|left_label_2|1|10|
|right_label_2|1|10|
|basis_header|15|1|
|scheme_header|15|1|
|key_identification|5|1|
|research_goal|5|1|
|survey|15|1|
|method_selection|5|1|
|overall_planning|5|1|
|route_design|14|1|
|plus|0|1|
|theory|3|4|
|coupled_framework|3|4|
|analysis_left_0|5|1|
|analysis_right_0|5|1|
|analysis_left_1|5|1|
|analysis_right_1|5|1|
|analysis_left_2|5|1|
|analysis_right_2|5|1|
|coupling_label_0|2|2|
|coupling_label_1|2|2|
|model_header|33|1|
|model_structure|10|1|
|model_parameters|10|1|
|model_performance|10|1|
|optimization_header|33|1|
|optimization_diagnosis|33|1|
|parameter_iteration|10|1|
|structure_improvement|10|1|
|performance_check|10|1|
|platform|1|9|
|experiment_design|1|9|
|condition_quality|1|9|
|preprocessing|1|9|
|statistics|1|9|
|iteration|1|9|
|simulation|7|2|
|data_collection|7|2|
|initial_analysis|7|2|
|performance_optimization|7|2|
|metric_evaluation|7|2|
|error_diagnosis|7|2|
|optimization_strategy|7|2|
|results_header|22|1|
|result_0|7|1|
|result_1|7|1|
|result_2|7|1|
|result_3|7|1|

## 调用与适配

按SKILL.md共享包装器调用`scripts/coupled_method_experiment_framework.py`，传入工作区内容JSON与`-o`输出路径；`--check`只校验。然后strict版式检查、实际导出PNG/PDF、逐区看图及最终入文尺寸检查。共享源只读。

## 已知近似与尺寸状态

原生框、文字、箭头、折角、双箭纹和双椭圆可编辑；白色交叠透镜保留原图并重新覆盖两圆轮廓。标题标注示例。截图实验组合卡首行“仿真实验开”疑似缺末字，本模板明确采用演示文案“仿真实验开展”，不是声称精确转录。右侧“耦合工艺”保留截图措辞，不证明适用于任意方法。水印有意不重建；字体、椭圆曲线采样、箭尖与细微底色存在近似。固定五带和节点数量，允许范围内换文案，不承诺任意增删。

模板已同步到 `.agents` 与 `.claude`；物理尺寸审核见 defect-log，不能凭模板存在自动用于第一章。

## 当前复刻复查与适用尺寸

三轮真实渲染/实际查看记录见defect-log.md，最终示例、替换和容量图通过当前暂存复查，已同步到 `.agents` 与 `.claude` 两端。这不是赛题科学审核或论文入文通过。

画布1206×1743，最小文字26px。实际PDF完整按宽160mm放入A4时，高231.23mm，最小字约9.78pt；可作近整页总体路线候选，不能直接缩成半页。正式入文还要给图题留空间，核对1.2实际节边界，并替换为当前真实任务关系。A3宽247mm时高356.96mm、最小字约15.09pt，可展示。灰度下文字、框和箭头可区分；并不依赖颜色判断流程方向。

左右双圆各向外分发三条分析路径，不是左右互相传递；白透镜仅表示交叠，不擅自加入交集成果。右上方案卡保留整体规划到路线的无箭尖连线与路线到方法选择的上箭头。中部模型与优化各项按原图分组，没有绘制不存在的流程箭头。实验链的两组明细卡分别有4行、3行，箭头从整体框右缘输出。

固定节点数量；实验链6个竖排字段每行最多1个全角字、最多9行。其他槽位容量见上表。替换配置必须与实际科学关系一致，示例文字不是可直接搬入论文的研究成果。

已知近似：标题保留原意并加“示例”；“仿真实验开”演示替换为“仿真实验开展”；同类填色的细微采样差异已归并；中文字体、虚线相位、箭尖和椭圆边缘抗锯齿与原图不完全一致。水印不复刻。两圆为有意相交的同一对象无字轮廓，文字和连接器检查仍执行。
