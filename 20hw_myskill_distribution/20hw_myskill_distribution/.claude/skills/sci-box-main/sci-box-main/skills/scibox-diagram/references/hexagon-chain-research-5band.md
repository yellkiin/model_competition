# 双侧六边形阶段链五带研究路线图

独立ID：`hexagon-chain-research-5band`；来源：ref-06。

五个中心工作包由向下箭头串接，左右为无箭头的六边形阶段/解释链。第一带三组方案横向推进；第二带两组各五个竖排条目通过母线分类；第三、四带各有三列研究维度与下方依据/目标；第五带三项总结推进。保留双侧六边形外轮廓和大范围边界，不将阶段链改为普通矩形列表。

## 固定数量与内容接口

example.json含template_id、texts；文字字符串或字符串数组，按字段替换，可用\n断行。拓扑及节点数量固定，缺少/多余字段均拒绝；不承诺无限节点。关系不适合时另选模板或重排，不改题意硬套。

|字段|每行全角上限|行数上限|
|---|---|---|
|project_title|30|1|
|left_label_0|1|4|
|left_label_1|1|4|
|left_label_2|1|4|
|left_label_3|1|4|
|left_label_4|1|4|
|right_label_0|2|2|
|right_label_1|2|2|
|right_label_2|2|2|
|right_label_3|2|2|
|iteration_title|26|1|
|iteration_label_0|8|1|
|iteration_input_0|7|1|
|iteration_output_0|7|1|
|iteration_label_1|8|1|
|iteration_input_1|7|1|
|iteration_output_1|7|1|
|iteration_label_2|8|1|
|iteration_input_2|7|1|
|iteration_output_2|7|1|
|data_model_title|26|1|
|data_model_header_0|12|1|
|data_model_item_0_0|1|5|
|data_model_item_0_1|1|5|
|data_model_item_0_2|1|5|
|data_model_item_0_3|1|5|
|data_model_item_0_4|1|5|
|data_model_header_1|12|1|
|data_model_item_1_0|1|5|
|data_model_item_1_1|1|5|
|data_model_item_1_2|1|5|
|data_model_item_1_3|1|5|
|data_model_item_1_4|1|5|
|behavior_title|25|1|
|mechanism_title|25|1|
|research_header_0_0|9|1|
|research_detail_0_0|9|2|
|research_header_0_1|9|1|
|research_detail_0_1|9|2|
|research_header_0_2|9|1|
|research_detail_0_2|9|2|
|research_header_1_0|9|1|
|research_list_0|7|3|
|research_header_1_1|9|1|
|research_list_1|7|3|
|research_header_1_2|9|1|
|research_list_2|7|3|
|data_basis|30|1|
|research_goal|30|1|
|policy_title|26|1|
|policy_0|7|1|
|policy_1|7|1|
|policy_2|7|1|

## 调用与适配

按SKILL.md共享包装器调用`scripts/hexagon_chain_research_5band.py`，传入工作区内容JSON与`-o`输出路径；`--check`只校验。然后strict版式检查、实际导出PNG/PDF、逐区看图及最终入文尺寸检查。共享源只读。

## 已知近似与尺寸状态

全部文字、六边形、箭头、母线及矩形可编辑，无整图位图。原参考多处XXXX及重复标题替换成明确的演示研究安排，标题显式含示例；来源原图保留。原图左侧长竖六边形用原生east hexagon近似，尖角比例、圆角与字体存在差异。第二带分类母线无箭头，不能解释成五步顺序；双侧长链无箭头，底部连接不推断反馈回路。阶段名及机理词组仅为示例，不是当前赛题结论。

模板已同步到 `.agents` 与 `.claude`；物理尺寸审核见 defect-log，不能凭模板存在自动用于第一章。

## 实际尺寸与适用边界

四轮实际画布复查后，补齐原图“数据归一化”的漏字，并完成PDF、灰度、替换文案、满容量及尺寸页复核。A4宽160mm时高约231.23mm、最小字约9.03pt；可以作为近整页候选，不能再缩成半页，须为真实论文中的图题及1.2位置另做排版审核。A3宽247mm时最小字约13.93pt，可作展示。此结论不替代正式论文当前内容的审查。

适合固定五阶段、双侧解释链、两组五项分类和两组三列分析的研究安排。第二带竖条是并列类别，不能表达有先后依赖的预处理步骤；侧链无箭头，底部闭合边界不代表反馈。不同任务关系应选择其他模板或重新布局。

research_list_0/1/2各对应三个固定圆点，替换内容保持三行、一行一个条目。模板不自动增删圆点或重排节点。总体文字为完整演示文案，原图的XXXX及重复标题已明确替换；不得沿用作当前赛题事实。
