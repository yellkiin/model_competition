# 三环耦合与三层斜面研究路线图

独立ID：`drug-discovery-triad-planes`；来源：ref-05。

顶部三项输出、三环耦合示意与三层斜面工作包：保留蝴蝶形背景、三角关系、三个环形核心、两侧方法卡片、提示符、跨层红箭头和底部双向联系。适合多层研究架构与循环协同概览，不是普通串行算法流程。原图混杂生物医学、强化学习和电网术语，示例不据此承诺科学关系成立。

## 固定数量与内容接口

example.json含template_id、texts；文字字符串或字符串数组，按字段替换，可用\n断行。拓扑及节点数量固定，缺少/多余字段均拒绝；不承诺无限节点。关系不适合时另选模板或重排，不改题意硬套。

|字段|每行全角上限|行数上限|
|---|---|---|
|title|36|1|
|top_output_0|8|1|
|top_output_1|17|1|
|top_output_2|8|1|
|triad_title|16|1|
|core_value_0|3|1|
|core_note_0|5|2|
|core_demo_0|2|1|
|core_value_1|3|1|
|core_note_1|5|2|
|core_demo_1|2|1|
|core_value_2|3|1|
|core_note_2|5|2|
|core_demo_2|2|1|
|strategy_text_0|16|3|
|strategy_header_0|15|1|
|strategy_text_1|16|3|
|strategy_header_1|15|1|
|agent_text_0|8|2|
|agent_header_0|7|1|
|effect_text_0|8|3|
|effect_header_0|7|1|
|agent_text_1|8|2|
|agent_header_1|7|1|
|effect_text_1|8|3|
|effect_header_1|7|1|
|central_association|8|7|
|clinical_note|5|2|
|multidimensional_note|5|1|
|asterisk|0|1|
|alert|0|1|
|planes_title|19|1|
|plane_top_title|21|1|
|plane_method_0|5|1|
|plane_detail_0|5|1|
|plane_method_1|5|1|
|plane_detail_1|5|1|
|plane_method_2|5|1|
|plane_detail_2|5|1|
|plane_method_3|5|1|
|plane_detail_3|5|1|
|plane_middle_title|21|1|
|signal_0|5|1|
|signal_1|5|1|
|signal_2|5|1|
|signal_3|5|1|
|base_0|3|2|
|base_1|3|2|
|base_2|3|2|
|base_3|3|2|
|base_forward_label|5|1|
|base_return_label|5|1|
|outer_left_note|1|17|
|outer_right_note|1|18|
|bottom_summary|44|1|
|demo_notice|45|1|

## 调用与适配

按SKILL.md共享包装器调用`scripts/drug_discovery_triad_planes.py`，传入工作区内容JSON与`-o`输出路径；`--check`只校验。然后strict版式检查、实际导出PNG/PDF、逐区看图及最终入文尺寸检查。共享源只读。

## 已知近似与尺寸状态

全部形状是可编辑原生填充路径、椭圆、矩形、文字与连接。装饰表面使用外/内两层填充形成边线，避免把大背景误当流程节点；文字和语义连接仍独立校验。原图渐变光效以浅色面和部分原生渐变近似，环径、三角轮廓、曲线与层面描边有差异。百分比38/31/46保留为可替换字段并显式标示例；核心PPO改为示例标识，标题去原图不自然的“某基于”并加示例。底部新增可见演示声明。没有使用截图冒充矢量图。

模板已同步到 `.agents` 与 `.claude`；物理尺寸审核见 defect-log，不能凭模板存在自动用于第一章。

## 适用语义与展示尺寸

固定三核心、三层斜面、四项方法、四个信号节点、底层两组各两模块。用于循环协同与分层研究安排；三角和蝴蝶翼是关系背景，不能直接解释成有向算法。蓝色块箭头表示参考中的循环方向；红色细箭头表示跨层关联；底层黑色双向路线对应检测与相关性反馈。真实使用必须核对这些关系是否确实存在，不能以漂亮的布局代替机制证据。

原参考混合生物医学、强化学习、电网术语以及38/31/46三个百分比，均只有版式演示意义。标题、核心“示例”和底部声明已明确其性质，替换时不得保留没有结果来源的数字。没有真实指标时可以把百分比字段替换成简短阶段名，而不能编造数据。

星号和感叹号是窄符号槽，容量为一个半角字符；不支持在图标槽放中文。三个圆形核心采用独立百分比、两行说明和末行短标签槽，最后一行最多两个全角字，避免触碰圆弧。

四轮实际复查记录见defect-log.md。A4正文宽160mm时图高232.29mm，最小7.59pt，核心文字及声明偏小，不推荐默认第一章整图；A3宽247mm时图高358.61mm，最小11.72pt，可大幅展示。当前参考信息密集，正式论文若需使用应按真实内容精简/拆分并重新布局审查，不能直接压成半页。

已知近似：三核心光晕、半透明环带、渐变、翼面边线、斜面边线、曲线以及字体与源图有差异。提示符用原生圆形与可编辑字符近似；未嵌入整图截图。三层斜面是示意空间层级，不是具有真实三维坐标的科研结果图。
