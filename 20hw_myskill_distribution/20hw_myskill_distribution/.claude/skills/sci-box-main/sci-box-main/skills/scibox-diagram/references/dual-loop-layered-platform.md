# 双循环算法与三层平台架构图

独立ID：`dual-loop-layered-platform`；来源：ref-07。

上部六组算法模块围绕内循环和经验池展开；中部两个三段环形箭头分别连接强化学习/深度学习核心，并由斜向指令与标注箭头关联；下部三层平台包含成对框架模块、双向数据/指令、分层锥面和三个侧向圆徽。用于复杂算法与系统设计概览，不把混杂的参考术语当成成立的单一算法。

## 固定数量与内容接口

example.json含template_id、texts；文字字符串或字符串数组，按字段替换，可用\n断行。拓扑及节点数量固定，缺少/多余字段均拒绝；不承诺无限节点。关系不适合时另选模板或重排，不改题意硬套。

|字段|每行全角上限|行数上限|
|---|---|---|
|title|40|1|
|side_tab_text_0|1|7|
|side_tab_text_1|1|7|
|side_tab_text_2|1|7|
|side_tab_text_3|1|7|
|module_title_0_0|8|1|
|module_layer_0_0_0|8|1|
|module_layer_0_0_1|8|1|
|module_title_0_1|8|1|
|module_layer_0_1_0|8|1|
|module_layer_0_1_1|8|1|
|module_title_0_2|8|1|
|module_layer_0_2_0|8|1|
|module_layer_0_2_1|8|1|
|module_title_1_0|8|1|
|module_layer_1_0_0|8|1|
|module_layer_1_0_1|8|1|
|module_title_1_1|8|1|
|module_layer_1_1_0|8|1|
|module_layer_1_1_1|8|1|
|module_title_1_2|8|1|
|module_layer_1_2_0|8|1|
|module_layer_1_2_1|8|1|
|access_0_0|6|1|
|access_0_1|6|1|
|access_0_2|6|1|
|access_1_0|6|1|
|access_1_1|6|1|
|access_1_2|6|1|
|pool_0|1|5|
|interaction_0|5|2|
|inner_label_0|1|3|
|pool_1|1|5|
|interaction_1|5|2|
|inner_label_1|1|3|
|agent_input|2|3|
|agent_description|18|1|
|outer_loop_label_0|1|3|
|outer_loop_label_1|1|3|
|outer_loop_label_2|1|3|
|outer_loop_label_3|1|3|
|loop_core_title_0|5|1|
|loop_core_detail_0|4|2|
|loop_core_title_1|5|1|
|loop_core_detail_1|4|2|
|ring_green_top|5|1|
|ring_green_left|1|4|
|ring_green_bottom|5|1|
|ring_blue_top|5|1|
|ring_blue_right|1|4|
|ring_blue_bottom|5|1|
|system_command_label|6|1|
|data_annotation_label|6|1|
|double_loop_top|4|1|
|double_loop_bottom|3|1|
|left_cycle_word_0|2|1|
|left_cycle_word_1|2|1|
|left_cycle_word_2|2|1|
|right_cycle_word_0|2|1|
|right_cycle_word_1|2|1|
|right_cycle_word_2|2|1|
|distillation|9|1|
|moe|9|1|
|federated_top|9|1|
|layer_title_0|3|1|
|framework_0_0|9|1|
|framework_0_1|9|1|
|badge_text_0|3|2|
|layer_title_1|5|1|
|layer_detail_1|11|1|
|framework_1_0|9|1|
|framework_1_1|9|1|
|badge_text_1|3|2|
|layer_title_2|5|1|
|layer_detail_2|11|1|
|framework_2_0|9|1|
|framework_2_1|9|1|
|badge_text_2|3|2|
|layer_exchange_text_0_0|1|2|
|layer_exchange_text_0_1|1|2|
|layer_exchange_text_0_2|1|2|
|layer_exchange_text_0_3|1|2|
|layer_exchange_text_1_0|1|2|
|layer_exchange_text_1_1|1|2|
|layer_exchange_text_1_2|1|2|
|layer_exchange_text_1_3|1|2|
|infrastructure|10|1|
|acceleration|16|1|
|data_source|9|1|

## 调用与适配

按SKILL.md共享包装器调用`scripts/dual_loop_layered_platform.py`，传入工作区内容JSON与`-o`输出路径；`--check`只校验。然后strict版式检查、实际导出PNG/PDF、逐区看图及最终入文尺寸检查。共享源只读。

## 已知近似与尺寸状态

原生框、路径、环箭头、锥面、文字和接口均可编辑，无整图位图。环箭头轮廓由实际颜色区域测量，简化误差约1px；字体、平滑曲线、顶部重复箭头与锥面为原语近似。原图多处“点入接”、标题占位及混杂生物学题名改为明确演示字段，不声称准确转录无法确认文字。原参考强化学习、门控、联邦学习、MOE及新药平台概念混合，图不证明算法有效或科学因果。正式题目必须逐条核验环的方向、数据与指令关系。

模板已同步到 `.agents` 与 `.claude`；物理尺寸审核见 defect-log，不能凭模板存在自动用于第一章。

## 实际尺寸与适用边界

三轮以上实际画布复查，另审PDF、灰度、替换文案、满容量和尺寸预览。A4宽160mm、高约232.29mm，最小字约7.59pt，原样过密；A3宽247mm、最小约11.72pt，可作大幅展示。正式论文须按真实内容拆分或重新排版。

模板保留上部六模块双向接口、中部两套环形循环、跨环斜向指令/标注以及下部三层平台。外循环虚线是关联边界；中部彩色环是结构箭头；下部四组“数据/指令”双向箭头表示接口关系。若实际任务没有这些关系，应另选模板。

原参考把新药、强化学习、深度学习、联邦学习和 MOE 等术语放在同一张图中。本模板示例文案仅用于版式演示，已在标题和说明中标注，不可当作科学结论或当前赛题对象。环形箭头轮廓由颜色连通域测量后以原生可编辑路径近似，文字仍是独立槽位。

应用层三角形标题限制为每行3个全角字（独立文字槽宽72px），不可按三角形外接矩形宽度扩充文字。浅绿底白字灰度对比弱，宜A3展示；论文重排可按实际用途调整配色后重新审查。
