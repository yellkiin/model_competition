# 数字生态旅游三带整合框架图

独立ID：`ecotourism-integration-3band`；来源：ref-01。

技术—方法—应用三带，每带左侧研究任务通过块箭头关联右侧综合解释。保留三角机制、技术影响矩阵、无刻度示意曲线、定性上升/持平符号表、案例推进及三路政策输出。适合数字技术与领域应用的综合概览；这些示意面板不能替代真实结果图，也不能仅凭此模板抵扣逐问主要综合图要求。

## 固定数量与内容接口

example.json含template_id、texts；文字字符串或字符串数组，按字段替换，可用\n断行。拓扑及节点数量固定，缺少/多余字段均拒绝；不承诺无限节点。关系不适合时另选模板或重排，不改题意硬套。

|字段|每行全角上限|行数上限|
|---|---|---|
|stage_1|1|12|
|stage_2|1|11|
|stage_3|1|6|
|technology_title|17|1|
|technology_map|16|1|
|model_title|17|1|
|case_title|17|1|
|band_number_1|2|1|
|band_title_1|30|1|
|band_number_2|2|1|
|band_title_2|30|1|
|band_number_3|2|1|
|band_title_3|30|1|
|stakeholder_4|5|1|
|stakeholder_5|6|1|
|stakeholder_6|5|1|
|tech_13|5|1|
|tech_14|6|1|
|tech_15|5|1|
|tech_details_16|6|5|
|tech_details_17|7|5|
|tech_details_18|6|5|
|mechanism_heading|17|1|
|mechanism_subtitle|10|1|
|ecosystem|6|1|
|economy|5|1|
|inclusion|4|1|
|monitor|5|1|
|analyse|5|1|
|manage|5|1|
|integration|1|4|
|impact_heading|14|1|
|impact_header_0|8|1|
|impact_header_1|8|1|
|impact_header_2|7|1|
|impact_type_0|7|1|
|impact_claim_0_1|8|1|
|impact_detail_0_1|8|1|
|impact_claim_0_2|7|1|
|impact_detail_0_2|7|1|
|impact_type_1|7|1|
|impact_claim_1_1|8|1|
|impact_detail_1_1|8|1|
|impact_claim_1_2|7|1|
|impact_detail_1_2|7|1|
|impact_type_2|7|1|
|impact_claim_2_1|8|1|
|impact_detail_2_1|8|1|
|impact_claim_2_2|7|1|
|impact_detail_2_2|7|1|
|subsystem_25|5|2|
|subsystem_33|5|2|
|subsystem_40|5|2|
|subsystem_47|5|2|
|method_27|6|2|
|method_34|6|2|
|method_41|6|2|
|method_48|6|2|
|system_step_0|5|1|
|system_step_1|5|1|
|system_step_2|5|1|
|system_step_3|5|1|
|ecology_heading|11|1|
|ecology_subtitle|12|1|
|ecology_y_label|6|1|
|ecology_x_label|5|1|
|optimum_label|6|1|
|legend_0|5|1|
|legend_1|6|1|
|legend_2|4|1|
|society_heading|10|1|
|society_header_0|8|2|
|society_header_1|3|2|
|society_header_2|4|2|
|society_header_3|4|2|
|society_header_4|3|2|
|society_0_0|8|1|
|society_0_1|3|1|
|society_0_2|3|1|
|society_0_3|3|1|
|society_0_4|3|1|
|society_1_0|8|1|
|society_1_1|3|1|
|society_1_2|3|1|
|society_1_3|3|1|
|society_1_4|3|1|
|society_2_0|8|1|
|society_2_1|3|1|
|society_2_2|3|1|
|society_2_3|3|1|
|society_2_4|3|1|
|society_3_0|8|1|
|society_3_1|3|1|
|society_3_2|3|1|
|society_3_3|3|1|
|society_3_4|3|1|
|society_4_0|8|1|
|society_4_1|3|1|
|society_4_2|3|1|
|society_4_3|3|1|
|society_4_4|3|1|
|case_0|6|3|
|case_1|6|3|
|case_2|5|3|
|case_summary|19|1|
|outcome_0|11|1|
|policy_0|11|1|
|outcome_1|12|1|
|policy_1|12|1|
|outcome_2|12|1|
|policy_2|12|1|
|demo_notice|51|1|

## 调用与适配

按SKILL.md共享包装器调用`scripts/ecotourism_integration_3band.py`，传入工作区内容JSON与`-o`输出路径；`--check`只校验。然后strict版式检查、实际导出PNG/PDF、逐区看图及最终入文尺寸检查。共享源只读。

## 已知近似与尺寸状态

所有框、三角机制、表格单元、曲线与箭头均为原生可编辑图元；无截图嵌入。原图纸面阴影不复刻，右面板圆角由折线近似，渐变三角及曲线只复刻示意形状。为灰度可辨，将三条曲线改为较深的同色系及虚线/实线/点线，并同步图例；保留实际采样形状。原图无数值轴/数据来源，故额外加入可见演示标识；不能解释为当前赛题结果。色义按三带和面板归并。表内上升/持平符号为定性示意，可在JSON替换；曲线几何可在draw.io编辑，正式数据图须按双来源结果图规则另行生成并替换，不能只换轴名。

模板已同步到 `.agents` 与 `.claude`；物理尺寸审核见 defect-log，不能凭模板存在自动用于第一章。

## 已审查的尺寸限制

当前模板137节点、37条边（含分区边界与图例），拓扑固定。A4宽160mm时最小文字约4.51pt，A3宽247mm约6.97pt，均不推荐直接用于正文；A2宽370mm约10.44pt，可用于大幅展示。正文适配应拆分/精简并重新渲染审查，不能只缩图。曲线仅为参考像素采样示意，绝非可复用的实测数据。四轮实际审查和改动依据见assets/ecotourism-integration-3band/defect-log.md。
