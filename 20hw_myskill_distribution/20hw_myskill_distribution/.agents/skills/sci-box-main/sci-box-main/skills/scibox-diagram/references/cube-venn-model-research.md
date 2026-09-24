# 立方体协作与双圆交叉三任务研究框架图

独立ID：`cube-venn-model-research`；来源：ref-12。

上部三类研究现状及两组四支母线汇入三项研究内容；中部三个工作包分别采用嵌套立方体与六支协作、重叠双圆与六支联邦框架、CNN/RNN/GAN三块模型及双侧输出；底部三项预期成果横向推进。保留左右括号、原生小图标、编号圆点和箭头方向，不压成普通矩形流程。

## 固定数量与内容接口

example.json含template_id、texts；文字字符串或字符串数组，按字段替换，可用\n断行。拓扑及节点数量固定，缺少/多余字段均拒绝；不承诺无限节点。关系不适合时另选模板或重排，不改题意硬套。

|字段|每行全角上限|行数上限|
|---|---|---|
|title|34|1|
|side_0|1|5|
|side_1|1|5|
|side_2|1|5|
|task_flag_label_0|1|5|
|task_flag_label_1|1|5|
|task_flag_label_2|1|5|
|background_header|37|1|
|status_header_0|9|1|
|status_header_1|9|1|
|status_header_2|9|1|
|frontier_0|1|6|
|frontier_1|1|6|
|frontier_2|1|6|
|frontier_3|1|6|
|frontier_4|1|6|
|frontier_5|1|6|
|frontier_6|1|6|
|frontier_7|1|6|
|knowledge_distillation|9|3|
|self_supervision|9|3|
|contents_header|31|1|
|content_0|11|1|
|content_1|11|1|
|content_2|11|1|
|main_topic|21|1|
|left_topic|4|2|
|right_topic|4|2|
|task_heading_0|45|1|
|task_heading_1|45|1|
|task_heading_2|45|1|
|unlabeled_text_left|4|4|
|unlabeled_text_right|4|4|
|federated_cube_0|10|1|
|federated_cube_1|10|1|
|federated_cube_2|10|1|
|federated_cube_3|10|1|
|federated_cube_4|10|1|
|federated_cube_5|10|1|
|gradcam_0|5|6|
|gradcam_1|5|6|
|federated_venn_0|8|1|
|federated_venn_1|8|1|
|federated_venn_2|8|1|
|federated_venn_3|8|1|
|federated_venn_4|8|1|
|federated_venn_5|8|1|
|discipline_text|3|2|
|modality_text|3|2|
|generative_left|1|5|
|generative_right|1|5|
|federated_models_0|13|1|
|federated_models_1|11|1|
|federated_models_2|9|1|
|federated_models_3|13|1|
|federated_models_4|11|1|
|federated_models_5|9|1|
|step_label_left_0|0|1|
|step_label_left_1|0|1|
|step_label_left_2|0|1|
|step_label_right_0|0|1|
|step_label_right_1|0|1|
|step_label_right_2|0|1|
|cnn_text|2|1|
|rnn_text|2|1|
|gan_text|2|1|
|outcome_title|38|1|
|outcome_0|10|2|
|outcome_1|11|2|
|outcome_2|11|2|

## 调用与适配

按SKILL.md共享包装器调用`scripts/cube_venn_model_research.py`，传入工作区内容JSON与`-o`输出路径；`--check`只校验。然后strict版式检查、实际导出PNG/PDF、逐区看图及最终入文尺寸检查。共享源只读。

## 已知近似与尺寸状态

原生mxGraph图元重建全部框、立体面、Venn双圆、图标和箭头，无整图位图。原图的图像/机器人/联邦学习混杂主题只作示例，标题加示例；不证明实际科学关系成立。多处重复“前沿学科”“联邦学习框架”和Grad-CA原样保留。小飞机/人群/云/靶心用原语近似，渐变、弧度与阴影有差异；截图纸张阴影有意不复刻。固定拓扑可换文案，不把任务数量或关系任意重写成真实研究。

模板已同步到 `.agents` 与 `.claude`；物理尺寸审核见 defect-log，不能凭模板存在自动用于第一章。

## 已审核的适用范围与尺寸

三轮实渲与实际看图已完成，限暂存模板复刻审核，不代表正式论文验收。适合三项并列工作、协作中心、双集合交叉与三模型对照均确实存在的研究概览；不适合顺序单链、任意增减任务或以圆交叉暗示不存在的融合关系。

A4宽160mm时约高232.29mm，最小字7.59pt，不推荐原样作为第一章图；A3宽247mm时约高358.61mm、最小字11.72pt，可作大幅展示。正式入文仍须用当前真实内容重排并检查图题、尺寸和1.2位置。

图像分割、机器人路径规划、联邦学习等来自原参考混杂演示，不能当作统一已验证研究。Grad-CA按原图保留，不自动推断为Grad-CAM；换文案测试只验证接口，不证明术语替换科学合理。小飞机、人群、云和靶心是原生图元近似；字体、渐变、圆角、虚线节奏与原图存在差异。
