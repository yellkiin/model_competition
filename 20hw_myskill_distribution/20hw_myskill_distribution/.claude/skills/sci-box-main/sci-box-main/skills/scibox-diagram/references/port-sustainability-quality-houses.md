# 港口供应链双质量屋与减排策略研究图

独立ID：`port-sustainability-quality-houses`；来源：ref-09。

四阶段研究安排：研究基础分发至理论及文献；双质量屋串联技术需求与评价指标；CH-DEA接收内部障碍及外部驱动信息并形成两类可持续性评价；底部静态/动态博弈与系统仿真通过微观向右、宏观向左的箭头交换。保留质量屋屋顶/侧三角矩阵、三向关联块、政策—企业—能源—环境—经济关系及场景指标框。

## 固定数量与内容接口

example.json含template_id、texts；文字字符串或字符串数组，按字段替换，可用\n断行。拓扑及节点数量固定，缺少/多余字段均拒绝；不承诺无限节点。关系不适合时另选模板或重排，不改题意硬套。

|字段|每行全角上限|行数上限|
|---|---|---|
|title|40|1|
|stage_text_0|1|6|
|stage_text_1|1|6|
|stage_text_2|1|6|
|stage_text_3|1|6|
|research_base|8|1|
|theory_title|11|1|
|related_title|13|1|
|theory_item_0|10|1|
|theory_item_1|10|1|
|theory_item_2|10|1|
|related_item_0|13|1|
|related_item_1|13|1|
|related_item_2|13|1|
|methods|6|5|
|house_heading|17|1|
|two_stages|1|6|
|roof_text_0|4|1|
|house_head_0|9|1|
|house_matrix_0|9|1|
|house_absolute_0|11|1|
|house_relative_0|11|1|
|roof_text_1|4|1|
|house_head_1|9|1|
|house_matrix_1|9|1|
|house_absolute_1|11|1|
|house_relative_1|11|1|
|left_correlation_text|2|2|
|customer|1|4|
|weight|1|4|
|sustainability|1|4|
|importance|2|5|
|evaluation_heading|17|1|
|barriers|9|1|
|drivers|9|1|
|obstacle_model|9|1|
|tobit_model|9|1|
|ch_dea|8|2|
|overall_sustainability|6|1|
|regional_sustainability|6|1|
|investment_stage|1|16|
|simulation_stage|1|16|
|equilibrium|4|2|
|short_game|5|2|
|long_game|5|2|
|game_model_left|5|2|
|game_model_right|5|2|
|recommendation|9|4|
|micro_label|4|1|
|macro_label|4|1|
|economy|2|1|
|environment|2|1|
|energy|2|1|
|enterprise|2|2|
|policy|2|1|
|abatement_selection|6|1|
|scenarios|6|1|
|port|2|1|
|shipping|3|1|
|market|6|1|
|abatement|3|1|
|intensity_1|3|1|
|intensity_2|3|1|

## 调用与适配

按SKILL.md共享包装器调用`scripts/port_sustainability_quality_houses.py`，传入工作区内容JSON与`-o`输出路径；`--check`只校验。然后strict版式检查、实际导出PNG/PDF、逐区看图及最终入文尺寸检查。共享源只读。

## 已知近似与尺寸状态

主要结构、文字、格线、曲线与箭头均原生可编辑，无整图位图。原图“资源基础理论理论”去重复词、“Tobit可归模型”改为明确演示的“Tobit回归模型”；保留右下重复碳强度字段但不赋予真实指标有效性。字体/渐变及曲线平滑度近似，原图投影阴影和水印有意不复刻。标题加示例；所有方法、因果和结论仅转录参考布局，正式使用必须按真实项目重写和科学审核。

模板已同步到 `.agents` 与 `.claude`；物理尺寸审核见 defect-log，不能凭模板存在自动用于第一章。

## 实际尺寸与适用限制

第三轮终图、替换图、满容量图、PDF渲染、灰度、差分及A4/A3完整预览已经实际打开复查。此结论仅适用于当前维护示例。

- A4宽160mm时整图高约231.23mm，最小字号约6.77pt；质量屋窄栏和底部策略细字偏小，不推荐原样放入第一章。
- A3宽247mm时高约356.96mm，最小字号约10.45pt，可作大幅展示。论文正文须按真实关系重新选取或设计布局，不通过缩字强塞。
- 固定双质量屋、两类评价输入、两种博弈分支与右侧循环。JSON替换文字不改变箭头含义；真实任务无此关系时不能机械套用。
- 顶部两组三条列表各有独立字段；屋顶、三角侧栏与椭圆输出使用收紧的容量。重要性窄栏为18px，其他主要字段20–26px。
- 原图重复“资源基础理论理论”已去重，“Tobit可归模型”按演示文案改为“Tobit回归模型”；右下两个“碳强度”槽保留原样，正式使用必须核对指标意义。此模板不证明所示研究方法或因果关系科学有效。
- 原图宋体与当前微软雅黑、研究基础标题阴影、下方弧形箭头曲率、顶部列表缩进存在已记录差异；主要图形保持可编辑矢量。
