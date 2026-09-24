# 多特征融合与目标检测五带研究路线图

独立ID：`feature-detection-research-5band`；来源：ref-22。

五带研究路线：四阶段总体流程、双栏关键技术路径、核心方法及左圆环/右反馈图、双栏实施验证、四节点双向迭代。左侧四个竖旗为特征提取网络/融合/检测/输出层说明，不擅自增加旗标间流程箭头。保留条件判断三路汇合、双验证合流、结果反馈双平行双向线与原图各虚线箭头方向。

## 固定数量与内容接口

example.json含template_id、texts；文字字符串或字符串数组，按字段替换，可用\n断行。拓扑及节点数量固定，缺少/多余字段均拒绝；不承诺无限节点。关系不适合时另选模板或重排，不改题意硬套。

|字段|每行全角上限|行数上限|
|---|---|---|
|title|37|1|
|flag_text_0|1|7|
|flag_text_1|1|7|
|flag_text_2|1|7|
|flag_text_3|1|7|
|band_title_0|20|1|
|band_title_1|20|1|
|band_title_2|20|1|
|band_title_3|20|1|
|band_title_4|20|1|
|overview_stage_0|7|1|
|overview_detail_0|7|1|
|overview_stage_1|7|1|
|overview_detail_1|7|1|
|overview_stage_2|7|1|
|overview_detail_2|7|1|
|overview_stage_3|7|1|
|overview_detail_3|7|1|
|data_base|16|1|
|feature_engineering|16|1|
|method_design|16|1|
|method_implementation|16|1|
|feature_definition_0|5|1|
|feature_object_0|5|2|
|feature_definition_1|5|1|
|feature_object_1|5|2|
|feature_definition_2|5|1|
|feature_object_2|5|2|
|design_chevron_text_0|4|1|
|design_chevron_text_1|4|1|
|design_chevron_text_2|4|1|
|validation_0|5|2|
|validation_1|5|2|
|validation_2|5|2|
|cycle_input|3|1|
|cycle_processing|3|1|
|cycle_features|3|1|
|cycle_assessment|3|1|
|cycle_model|3|1|
|data_node|1|4|
|optimization_node|1|4|
|core_heading|13|1|
|core_output|13|1|
|core_submodule_0|12|1|
|core_submodule_1|12|1|
|core_submodule_2|12|1|
|optimization_action|3|1|
|optimization_result|3|1|
|optimization_feedback|3|1|
|research_question|15|1|
|research_implementation|15|1|
|condition_text|2|2|
|path_0|5|1|
|path_1|5|1|
|path_2|5|1|
|path_integration|15|1|
|phase_conclusion|10|1|
|experiment_0|7|1|
|experiment_1|6|1|
|result_analysis|15|1|
|result_visualization|15|1|
|conclusion_text|2|2|
|iteration_0|6|1|
|iteration_1|6|1|
|iteration_2|6|1|
|iteration_3|6|1|

## 调用与适配

按SKILL.md共享包装器调用`scripts/feature_detection_research_5band.py`，传入工作区内容JSON与`-o`输出路径；`--check`只校验。然后strict版式检查、实际导出PNG/PDF、逐区看图及最终入文尺寸检查。共享源只读。

## 已知近似与尺寸状态

全部框、菱形、圆弧、箭头与文字原生可编辑，无整图位图。水印不复刻；主标题添加示例标记。三枚浅绿箭形是路径标签，不新增节点间因果线；左环无方向，右侧两条双向反馈线照参考保留而不解释成独立实验。源图概念模块混合算法与研究流程，文案仅作演示；真实论文按所需专用skill路由，不可代替算法内部科学说明。字体、圆角与斜边间距存在明确近似，三轮实际渲染审查已完成，具体观察和限制见 defect-log.md。

模板已同步到 `.agents` 与 `.claude`；物理尺寸审核见 defect-log，不能凭模板存在自动用于第一章。

## 经渲染核实的适用范围与尺寸

适合四阶段总体推进、双栏特征与方法分解、五节点环形关联、右侧三节点反馈、三路径融合和双验证合流共同存在的研究安排。五带及分支数量固定，不能为套版添加虚构步骤。算法内部科学解释按专用 skill 路由，本图不代替其证据。

左圆环没有方向箭头；右动作到结果为单向，动作与反馈双向，结果与反馈保留两条平行双向线。核心上下端均向左侧数据接口回接，右侧优化接口均指向核心上下端。适配时必须先确认这些关系适用，不按“常见流程”擅自反转。

六个浅绿底层框最多两行；浅绿箭形各最多四个全角字、单行；窄竖栏一字一行；判断菱形最多两行、每行两字。其余字段预算见模板说明。标题中的示例标记说明当前文案不是赛题结果。

A4正文宽160mm时高231.23mm，最小字约7.52pt，环内节点和反馈标签过小，不推荐原样作为第一章总体路线图。A3宽247mm时高356.96mm，最小字约11.61pt，可用于大幅展示。用于A4论文时应基于真实内容精简或重排并重新审查，不把字体整体缩小。

原图字体、圆角、箭头大小、虚线相位和少量网格位置有近似；浅绿箭形留4–5px间隔，三路径横线准确接到各分支。圆弧由350个源像素拟合，以约4°弦段重建，最大弦偏差约0.05px；不复刻水印。完整复核见 defect-log.md，当前仅完成暂存审核。
