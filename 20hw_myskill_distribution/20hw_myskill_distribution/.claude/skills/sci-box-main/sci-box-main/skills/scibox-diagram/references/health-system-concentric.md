# 智慧康养同心架构与层级系统图

独立ID：`health-system-concentric`；来源：ref-02。

同一截图包含顶部教学协作残片、同心环体系架构和椭圆层级系统三部分。中央由核心→目标→功能/协同/效用/要素→模块→细项逐层展开，下方3H与4S为模型类别；底图表达后台—感知—需求三层及四类参与方的协同。适合系统设计架构展示，不等价于顺序算法或全文技术路线；不能默认选作第一章。

## 固定数量与内容接口

example.json含template_id、texts；文字字符串或字符串数组，按字段替换，可用\n断行。拓扑及节点数量固定，缺少/多余字段均拒绝；不承诺无限节点。关系不适合时另选模板或重排，不改题意硬套。

|字段|每行全角上限|行数上限|
|---|---|---|
|teaching_0|5|1|
|teaching_1|5|1|
|teaching_2|5|1|
|teaching_3|5|1|
|teaching_4|5|1|
|teaching_5|5|1|
|teaching_6|5|1|
|teaching_7|5|1|
|teaching_relation_0|2|1|
|teaching_relation_1|2|1|
|teaching_relation_2|2|1|
|source_fragment_note|23|1|
|core_title|4|3|
|goal_0|6|1|
|goal_1|6|1|
|goal_2|6|1|
|level_0|6|1|
|level_1|6|1|
|level_2|6|1|
|level_3|6|1|
|module_0|3|2|
|module_1|3|2|
|module_2|3|2|
|module_3|3|2|
|module_4|6|1|
|module_5|6|1|
|module_6|4|1|
|module_7|4|1|
|module_8|4|1|
|module_9|6|1|
|module_10|6|1|
|detail_0|2|3|
|detail_1|6|3|
|detail_2|4|3|
|detail_3|7|3|
|detail_4|8|3|
|detail_5|6|3|
|detail_6|6|3|
|detail_7|6|2|
|detail_8|2|3|
|detail_9|2|3|
|detail_10|2|3|
|detail_11|2|3|
|outer_statement_0|21|1|
|outer_statement_1|18|1|
|outer_statement_2|15|1|
|outer_statement_3|23|1|
|model_name|8|1|
|health_zh_0|4|1|
|health_en_0_0|6|1|
|health_en_0_1|3|1|
|health_zh_1|4|1|
|health_en_1_0|3|1|
|health_en_1_1|3|1|
|health_zh_2|4|1|
|health_en_2_0|3|1|
|health_en_2_1|3|1|
|smart_zh_0|4|1|
|smart_en_0_0|5|1|
|smart_en_0_1|3|1|
|smart_zh_1|4|1|
|smart_en_1_0|2|1|
|smart_en_1_1|5|1|
|smart_zh_2|4|1|
|smart_en_2_0|2|1|
|smart_en_2_1|5|1|
|smart_zh_3|4|1|
|smart_en_3_0|6|1|
|smart_en_3_1|3|1|
|three_h|3|1|
|four_s|3|1|
|backstage|5|1|
|perception|5|1|
|user_need|5|1|
|internal_top|7|2|
|external|7|2|
|internal_bottom|7|2|
|system_tag_0|5|1|
|system_tag_1|5|1|
|actor_0|3|2|
|actor_1|3|2|
|actor_2|3|2|
|actor_3|3|2|
|component_0|5|1|
|component_tag_0|5|1|
|component_1|5|1|
|component_tag_1|5|1|
|outcome_zh_0|4|1|
|outcome_en_0_0|4|1|
|outcome_en_0_1|3|1|
|outcome_zh_1|4|1|
|outcome_en_1_0|3|1|
|outcome_en_1_1|3|1|
|outcome_zh_2|4|1|
|outcome_en_2_0|3|1|
|outcome_en_2_1|3|1|
|sharing_label_0|5|1|
|sharing_label_1|5|1|
|environment_0|6|1|
|environment_tag_0|7|1|
|environment_1|6|1|
|environment_tag_1|7|1|
|environment_2|6|1|
|environment_tag_2|7|1|
|environment_3|6|1|
|environment_tag_3|7|1|

## 调用与适配

按SKILL.md共享包装器调用`scripts/health_system_concentric.py`，传入工作区内容JSON与`-o`输出路径；`--check`只校验。然后strict版式检查、实际导出PNG/PDF、逐区看图及最终入文尺寸检查。共享源只读。

## 已知近似与尺寸状态

原截图是多个图的拼接，不臆造跨面板箭头；顶部右侧原已裁断，其可辨文字转录并保留片段说明。顶部三叶形由像素边界测量后简化为原生可编辑路径。环形文字以切向文本近似原弧排，外环细项与四条长句分别由旋转局部和极坐标展开核对；detail_4第三行末字仍不可确认，明确改为“外部协同（示例）”，不声称准确转录。曲面以原生路径及椭圆近似，颜色取源像素；英文断行与椭圆尺寸为避免原图碰线做了调整。八条环境内外通路保留，内路在其自身蓝色标签处显式留出遮挡段，只有末端保留箭头。尺寸与最终复查见defect-log，不凭存在自动用于论文。

模板已同步到 `.agents` 与 `.claude`；物理尺寸审核见 defect-log，不能凭模板存在自动用于第一章。

## 已审查的尺寸限制

全图为三段截图合集，174节点、67条连接/边界，拓扑固定。A4、A3、A2完整放入25mm边距页面时最小文字约3.97、5.95、8.75pt，均不推荐整图入文。420×820mm长页宽370mm、高757.37mm、最小字约12.18pt可展示；它不是论文页面规格。

不默认用于1.2总体路线。正式使用应根据真实关系选择必要面板并另行适配，替换示例文案、复核结构语义及最终页面。示例中detail_4末行“外部协同（示例）”为无法辨认原文字的明确替代；切向直排、3H/4S圆尺寸及曲面近似详见元素台账与五轮缺陷记录。
