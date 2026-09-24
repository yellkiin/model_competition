# 五阶段研究框架与多场景决策流程图

独立ID：`research-framework-5band`；来源：ref-19。

五个彩色工作包按阶段推进：整体框架、双向关联的三阶段、数据到模型分析、三个相互关联场景及五分支成果。左右分别为独立向下的研究方法链和研究阶段链；不使用ref-04的向内箭头侧栏。首带保留五个立体卡片，场景输入与约束围绕菱形决策，不能解释成串行条目。与ref-04存在相同结构族但侧链、配色和成果节点设计不同，独立ID与配置调用。

## 固定数量与内容接口

example.json含template_id、texts；文字字符串或字符串数组，按字段替换，可用\n断行。拓扑及节点数量固定，缺少/多余字段均拒绝；不承诺无限节点。关系不适合时另选模板或重排，不改题意硬套。

|字段|每行全角上限|行数上限|
|---|---|---|
|header_framework|5|1|
|header_content|5|1|
|header_methods|5|1|
|band_title_0|17|1|
|left_method_0|1|5|
|right_text_0|1|5|
|band_title_1|17|1|
|left_method_1|1|5|
|right_text_1|1|5|
|band_title_2|17|1|
|left_method_2|1|5|
|right_text_2|1|5|
|band_title_3|17|1|
|left_method_3|1|5|
|right_text_3|1|5|
|band_title_4|17|1|
|left_method_4|1|5|
|right_text_4|1|5|
|framework_header_0|5|1|
|framework_detail_0|5|3|
|framework_header_1|5|1|
|framework_detail_1|5|3|
|framework_header_2|5|1|
|framework_detail_2|5|3|
|framework_header_3|5|1|
|framework_detail_3|5|3|
|framework_header_4|5|1|
|framework_detail_4|5|3|
|stage_0_0|7|1|
|stage_0_1|7|1|
|stage_0_2|7|1|
|stage_0_3|7|1|
|stage_1_0|7|1|
|stage_1_1|7|1|
|stage_1_2|7|1|
|stage_1_3|7|1|
|stage_2_0|7|1|
|stage_2_1|7|1|
|stage_2_2|7|1|
|stage_2_3|7|1|
|data_header|7|1|
|model_header|13|1|
|data_0|7|1|
|data_1|7|1|
|data_2|7|1|
|model_0_0|6|1|
|model_0_1|6|1|
|model_0_2|6|1|
|model_1_0|6|1|
|model_1_1|6|1|
|model_1_2|6|1|
|model_2_0|6|1|
|model_2_1|6|1|
|model_2_2|6|1|
|scenario_heading_0|7|1|
|scenario_0_input|1|4|
|scenario_0_constraint|1|4|
|decision_0|2|2|
|scenario_output_0|7|1|
|scenario_heading_1|7|1|
|scenario_1_input|1|4|
|scenario_1_constraint|1|4|
|decision_1|2|2|
|scenario_output_1|7|1|
|scenario_heading_2|7|1|
|scenario_2_input|1|4|
|scenario_2_constraint|1|4|
|decision_2|2|2|
|scenario_output_2|7|1|
|core_outcome|29|1|
|outcome_0|5|1|
|outcome_1|5|1|
|outcome_2|5|1|
|outcome_3|5|1|
|outcome_4|5|1|

## 调用与适配

按SKILL.md共享包装器调用`scripts/research_framework_5band.py`，传入工作区内容JSON与`-o`输出路径；`--check`只校验。然后strict版式检查、实际导出PNG/PDF、逐区看图及最终入文尺寸检查。共享源只读。

## 已知近似与尺寸状态

前一简化初稿已退回rejected-drafts/ref19-simplified，不采用其坐标或语义；现重建全部卡片面、胶囊、菱形、双向箭头和母线。水印不复刻。标题条沿用原参考色系但改深色文字，改善灰度可读性；底部可见示例标记，参考文案不是赛题事实。场景胶囊与菱形为同对象原生表面有意交叠，文字使用独立安全区。固定五带和三场景，实测例图与容量边界必须实际渲染复查，不能凭脚本执行宣称完成。

模板已同步到 `.agents` 与 `.claude`；物理尺寸审核见 defect-log，不能凭模板存在自动用于第一章。

## 经实际渲染验证的使用限制

固定五阶段、三场景、五项成果；模板适合总体研究安排及场景对比框架，不适合只有单串算法步骤的任务。左右竖栏最多五个全角字，逐字换行；其他字段按上表预算，不能通过新增JSON字段增添节点。主图使用中文微软雅黑，五带标题改深色字以增强灰度可读性；原稿白字、圆角与线型有记录的近似。

A4正文宽160mm时图高231.23mm、最小约8.27pt，不推荐原样第一章。A3宽247mm时图高356.96mm、最小约12.77pt，适合展示。正文须按真实任务精简或重新排版后审图，不可只缩小；图题和1.2位置须在最终论文审核。
