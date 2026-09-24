# 数据归集建模与系统落地五阶段流程图

独立ID：`data-model-deployment-5stage`；来源：ref-20。

五阶段数据到模型及系统落地路线：四数据库共同连接清洗与标注两个面板；三立体数据封装块；双输入各二分支汇入核心训练并与推理接口双向关联；三项优化与性能评估相连，右侧六模块架构并列展开；最终集成联调分出四项落地活动。阶段之间使用灰色向下箭头，内部黑色无箭头关联不改成单向流程。

## 固定数量与内容接口

example.json含template_id、texts；文字字符串或字符串数组，按字段替换，可用\n断行。拓扑及节点数量固定，缺少/多余字段均拒绝；不承诺无限节点。关系不适合时另选模板或重排，不改题意硬套。

|字段|每行全角上限|行数上限|
|---|---|---|
|flag_text_0|1|10|
|flag_text_1|1|5|
|flag_text_2|1|7|
|flag_text_3|1|8|
|flag_text_4|1|4|
|database_name_0|7|1|
|database_name_1|7|1|
|database_name_2|7|1|
|database_name_3|7|1|
|prepare_title_0|11|1|
|prepare_detail_0_0|15|1|
|prepare_detail_0_1|15|1|
|prepare_title_1|11|1|
|prepare_detail_1_0|15|1|
|prepare_detail_1_1|15|1|
|package_title_0|9|1|
|package_detail_0|9|3|
|package_title_1|9|1|
|package_detail_1|9|3|
|package_title_2|9|1|
|package_detail_2|9|3|
|model_input_0|5|3|
|model_input_1|5|3|
|training_branch_0|10|1|
|training_branch_1|10|1|
|training_branch_2|10|1|
|training_branch_3|10|1|
|core_training|6|6|
|weight_interface|6|6|
|optimization|1|6|
|evaluation|1|6|
|optimization_axis_0|10|1|
|optimization_axis_1|10|1|
|optimization_axis_2|10|1|
|model_deployment|18|1|
|system_architecture|9|1|
|system_module_0|1|6|
|system_module_1|1|6|
|system_module_2|1|6|
|system_module_3|1|6|
|system_module_4|1|6|
|system_module_5|1|6|
|integration|15|1|
|implementation_0|8|1|
|implementation_1|8|1|
|implementation_2|8|1|
|implementation_3|8|1|

## 调用与适配

按SKILL.md共享包装器调用`scripts/data_model_deployment_5stage.py`，传入工作区内容JSON与`-o`输出路径；`--check`只校验。然后strict版式检查、实际导出PNG/PDF、逐区看图及最终入文尺寸检查。共享源只读。

## 已知近似与尺寸状态

完整保留四圆柱数据库、三块立体封装、所有分支与共享母线、双向接口箭头和六条架构斜线。三块立体封装稍缩正面并调整步距，是明确的可读性适配，不能称像素一致；原“归一化归一处理”重复文字规范为演示文案“归一化处理”。不复刻水印。参考流程为教学示例，训练/验证拆分必须按真实赛题避免泄漏，不能由本模板推断已完成计算。实际渲染与印刷尺寸尚待复查。

模板已同步到 `.agents` 与 `.claude`；物理尺寸审核见 defect-log，不能凭模板存在自动用于第一章。

## 经渲染核实的适用范围与尺寸

适合四类数据源归集、固定三类数据封装、二输入/四分支模型训练、三向优化与六功能模块系统落地的总体路线。数量固定；模块与实际任务不匹配时另选或重新设计，不伪造阶段。黑线表示关联而非额外方向，模型接口双向箭头和阶段单向推进不可随意互换。

顶面标题最多9全角字；侧旗与竖栏一字一行；核心训练/推理框最多6行；集成及落地项固定单行。每个字段仍须通过其实际预算。三块立体模块正面由源图约294px缩至270px、横向步距调整到328px，以使各侧面完整可辨；深度52px及三维结构保留，此为明确适配，不能声称像素一致。

A4正文宽160mm时图高231.23mm、最小约9.40pt，可作近整页第一章候选；实际图题、版心留白、1.2位置和真实内容必须复核。A3宽247mm时图高356.96mm、最小14.51pt适合展示。原文重复“归一化归一处理”改为演示“归一化处理”；末项标示示例，文案不代表实际科学成果。
