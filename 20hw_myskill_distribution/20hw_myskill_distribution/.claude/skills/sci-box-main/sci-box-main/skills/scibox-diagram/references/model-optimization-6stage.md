# 模型优化六阶段双列技术路线图

独立ID：`model-optimization-6stage`；来源：ref-13。

六阶段研究路线：三组调研/采集到产出映射；架构与实现双列分支；A/B测试汇入集成并列性能检验；三方案各三条方法说明；三评价维度各两分支；底部四步整理与输出。保留六个右指侧旗和各层母线，阶段之间不凭空增加箭头。

## 固定数量与内容接口

example.json含template_id、texts；文字字符串或字符串数组，按字段替换，可用\n断行。拓扑及节点数量固定，缺少/多余字段均拒绝；不承诺无限节点。关系不适合时另选模板或重排，不改题意硬套。

|字段|每行全角上限|行数上限|
|---|---|---|
|title|33|1|
|stage_text_0|1|4|
|stage_text_1|1|4|
|stage_text_2|1|4|
|stage_text_3|1|4|
|stage_text_4|1|4|
|stage_text_5|1|4|
|problem_input_0|13|1|
|problem_input_1|13|1|
|problem_input_2|13|1|
|problem_output_0|18|1|
|problem_output_1|18|1|
|problem_output_2|18|1|
|architecture|16|1|
|implementation|16|1|
|modules_ab|16|3|
|modules_cd|16|3|
|integration_0|8|1|
|integration_1|8|1|
|integration_2|7|1|
|integration_3|7|1|
|integration_4|18|1|
|integration_5|7|1|
|integration_6|7|1|
|comparison_header|34|1|
|comparison_title_0|9|1|
|comparison_item_0_0|7|1|
|comparison_item_0_1|7|1|
|comparison_item_0_2|7|1|
|comparison_title_1|9|1|
|comparison_item_1_0|7|1|
|comparison_item_1_1|7|1|
|comparison_item_1_2|7|1|
|comparison_title_2|9|1|
|comparison_item_2_0|7|1|
|comparison_item_2_1|7|1|
|comparison_item_2_2|7|1|
|evaluation_heading_0|11|1|
|evaluation_heading_1|11|1|
|evaluation_heading_2|11|1|
|evaluation_item_0|4|2|
|evaluation_item_1|5|2|
|evaluation_item_2|4|2|
|evaluation_item_3|5|2|
|evaluation_item_4|4|2|
|evaluation_item_5|4|2|
|output_0|7|1|
|output_1|7|1|
|output_2|7|1|
|output_3|7|1|

## 调用与适配

按SKILL.md共享包装器调用`scripts/model_optimization_6stage.py`，传入工作区内容JSON与`-o`输出路径；`--check`只校验。然后strict版式检查、实际导出PNG/PDF、逐区看图及最终入文尺寸检查。共享源只读。

## 已知近似与尺寸状态

全部框、文字、旗标、九个折角圆点和母线均为原生可编辑图元；不复刻截图水印。原标题XX替换为显式示例模型；原“不同数/据测试”位置截图写“ 不用数/据测试”，按上下文纠正为“不同数据测试”并在此登记，不能作为准确转录。重复系统性能及三卡重复条目保留原图，示例关系不证明科学充分性。字体、圆角、箭尖与背景细微渐变存在近似；固定六阶段和三方案，只支持规定容量内替换文字。

模板已同步到 `.agents` 与 `.claude`；物理尺寸审核见 defect-log，不能凭模板存在自动用于第一章。

## 已审核尺寸与适用条件

本模板三轮实渲与实际看图完成，仅为暂存复刻模板审核。适用于六阶段研究安排、双列研发/实现、三方案验证及三维度二分支评价；固定数量，不适合改变真实任务依赖硬套。重复“系统性能”和各卡三条相同文案仅为原图演示，适配时须替换为实际有效且不重复的研究内容。

A4宽160mm约高231.23mm，最小字9.78pt，实际完整尺寸页可读，可作1.2近整页候选；不能压成半页。A3宽247mm约高356.96mm，最小字15.09pt。正式入文必须检查实际版心、图题、引导语和分页，不将此尺寸试页当作正式论文通过。

原图XX标题已显式改成示例；“不用数据测试”按上下文纠正成“不同数据测试”，保留差异说明。水印不复刻；字体字宽、矩形细边、圆角和项目符号存在近似。原六阶段标签不自动决定论文结构，图中的研究方法或政策建议不冒充题面硬要求。
