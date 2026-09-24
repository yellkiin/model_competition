# 五阶段立体卡片与场景决策流程图

独立ID：`stage-design-prism-5band`；来源：ref-04。

五个彩色工作包按阶段推进：整体框架、可回溯的三阶段、数据到模型分析、三个相互关联场景及五分支成果。左右分别为研究方法链和指入内容的阶段说明。首带保留五个立体卡片；场景输入与约束围绕菱形决策，不能解释成串行条目。与stageflow-3col同族但立体卡片、侧栏箭头和固定实测几何不同，因此独立调用。

## 固定数量与内容接口

example.json含template_id、texts；文字字符串或字符串数组，按字段替换，可用\n断行。拓扑及节点数量固定，缺少/多余字段均拒绝；不承诺无限节点。关系不适合时另选模板或重排，不改题意硬套。

|字段|每行全角上限|行数上限|
|---|---|---|
|header_framework|5|1|
|header_content|5|1|
|header_methods|5|1|
|band_title_0|17|1|
|left_method_0|3|5|
|right_text_0|1|4|
|band_title_1|17|1|
|left_method_1|3|5|
|right_text_1|1|4|
|band_title_2|17|1|
|left_method_2|3|5|
|right_text_2|1|4|
|band_title_3|17|1|
|left_method_3|3|5|
|right_text_3|1|4|
|band_title_4|17|1|
|left_method_4|3|5|
|right_text_4|1|4|
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

按SKILL.md共享包装器调用`scripts/stage_design_prism_5band.py`，传入工作区内容JSON与`-o`输出路径；`--check`只校验。然后strict版式检查、实际导出PNG/PDF、逐区看图及最终入文尺寸检查。共享源只读。

## 已知近似与尺寸状态

原图手机界面与斜向水印不重画。所有文字、块箭头、立体卡片面和决策菱形均可编辑，未嵌入整图截图。立体卡片为前/顶/侧三个原生图元，视角与描边存在像素级差异；圆角框和块箭头用原生路径近似。场景两侧胶囊与菱形有原图明确的同组轮廓交叠，文字独立放在内部安全区。示例方法/术语是参考转录，不是当前赛题结论；真实任务没有迭代或场景关联时须重新选型，不能硬套箭头。

模板已同步到 `.agents` 与 `.claude`；物理尺寸审核见 defect-log，不能凭模板存在自动用于第一章。

## 已核查的展示尺寸与适用限制

三轮实际画布复查及PNG/PDF、灰度、替换文案、满容量和尺寸页检查见defect-log.md。A4宽160mm时图高231.23mm，最小文字约8.27pt，首带小字偏小，不推荐默认用于第一章；A3宽247mm时图高356.96mm，最小约12.77pt，可用于大幅展示。正式论文必须按实际版心和图题重新审查，不能直接缩成半页。

固定五阶段、五立体卡片、三实施组、九模型条目、三场景及五成果分支。三实施组之间和相邻场景之间为双向联系；模型网格各格是并列清单，不能据行列位置推断完整执行顺序。菱形表示该场景的决策活动，本图没有是/否出口，不能当作二元判断流程。输入与约束围绕菱形表达条件关联，不把重叠轮廓解释为数据连接箭头。

当前转录仅是版式示例，不是任何赛题的已验证方法或结果。选型时核对任务关系；不需要这些关系的题目应另选模板或重排。
