# 双研究模块圆柱模型技术路线图

独立ID：`dual-study-cylinder-roadmap`；来源：ref-03。

背景条件归纳、问题与三分支研究框架、两组重复研究工作包、三项展望。每个工作包有三对圆柱模型，双向块箭头表达配对关系，侧向箭头连到方法说明；这不是六种模型的串行训练顺序。适合双模块研究安排或模型对照的版式展示；示例混有不同课题，不能把截图文案解释为同一真实实验。

## 固定数量与内容接口

example.json含template_id、texts；文字字符串或字符串数组，按字段替换，可用\n断行。拓扑及节点数量固定，缺少/多余字段均拒绝；不承诺无限节点。关系不适合时另选模板或重排，不改题意硬套。

|字段|每行全角上限|行数上限|
|---|---|---|
|main_title|29|1|
|flag_text_0|1|5|
|flag_text_1|1|5|
|flag_text_2|1|5|
|right_label_0|1|4|
|right_label_1|1|4|
|right_label_2|1|4|
|right_label_3|1|4|
|right_label_4|1|4|
|right_label_5|1|4|
|background_heading|10|1|
|background_detail|13|4|
|left_background_0|12|1|
|left_background_1|12|1|
|left_plus|1|1|
|left_conclusion|12|2|
|right_background_0|12|1|
|right_background_1|12|1|
|right_plus|1|1|
|right_conclusion|12|2|
|problem_heading|9|1|
|problem_detail|13|2|
|framework_heading|9|1|
|framework_detail|13|1|
|left_transformer|12|3|
|right_transformer|12|3|
|framework_leaf_0|3|3|
|framework_leaf_1|3|3|
|framework_leaf_2|3|3|
|framework_leaf_3|3|3|
|framework_leaf_4|3|3|
|framework_leaf_5|3|3|
|multidisciplinary|3|1|
|research_banner_title|25|1|
|cross_modal|3|1|
|work_package_title_1|40|1|
|1_left_description_0|9|2|
|1_right_description_0|9|2|
|1_left_model_0|5|1|
|1_right_model_0|5|1|
|1_left_description_1|9|2|
|1_right_description_1|9|2|
|1_left_model_1|5|1|
|1_right_model_1|5|1|
|1_left_description_2|9|2|
|1_right_description_2|9|2|
|1_left_model_2|5|1|
|1_right_model_2|5|1|
|work_package_title_2|40|1|
|2_left_description_0|9|2|
|2_right_description_0|9|2|
|2_left_model_0|5|1|
|2_right_model_0|5|1|
|2_left_description_1|9|2|
|2_right_description_1|9|2|
|2_left_model_1|5|1|
|2_right_model_1|5|1|
|2_left_description_2|9|2|
|2_right_description_2|9|2|
|2_left_model_2|5|1|
|2_right_model_2|5|1|
|conclusions_title|32|1|
|conclusion_1|12|2|
|conclusion_2|12|2|
|conclusion_3|12|2|
|demo_notice|44|1|

## 调用与适配

按SKILL.md共享包装器调用`scripts/dual_study_cylinder_roadmap.py`，传入工作区内容JSON与`-o`输出路径；`--check`只校验。然后strict版式检查、实际导出PNG/PDF、逐区看图及最终入文尺寸检查。共享源只读。

## 已知近似与尺寸状态

原截图包含“内容内容”等占位，四背景与两结论槽替换为明确的演示条件与归纳，底部可见说明声明示例性质。题名、横幅与工作包混合不同研究主题，保留为版式演示，不作为真实课题推荐。手机界面和无语义截图底线不重绘；渐变用原生渐变近似；圆柱用原生cylinder3而非位图，其顶面深度为避字调整；虚线框采用原生圆角折线近似。标题以圆角顶面加直边下沿构成，旗标和块箭头比例存在原语近似；横幅“跨模态”改深蓝以改善对比。图中未提供模型间比较指标，双向符号仅复刻原有配对关系，正式使用须核实其科学含义。

模板已同步到 `.agents` 与 `.claude`；物理尺寸审核见 defect-log，不能凭模板存在自动用于第一章。

## 已审查的尺寸限制

97节点、48连接/边界，固定两组研究工作包，每组3对模型。A4宽160mm图高232.29mm，最小文字约8.44pt，不推荐默认作为第一章插图；A3宽247mm高358.61mm，最小约13.03pt，可作大幅展示。不要直接缩为半页。实际论文适配应精简真实关系并重新渲染、检查图题与位置。

原参考混合不同研究题目并含背景占位。示例已补充演示条件并在底部标明性质；这不是当前赛题事实。模型配对双向箭头无给定指标，只有实际任务存在明确关系时才保留。三轮修复与灰度、容量、尺寸审查见本模板defect-log.md。
