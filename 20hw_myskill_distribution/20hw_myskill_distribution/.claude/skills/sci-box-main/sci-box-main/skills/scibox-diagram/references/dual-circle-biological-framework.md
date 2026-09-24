# 双圆机制与双层实验框架图

独立ID：`dual-circle-biological-framework`；来源：ref-23。

上部保留双荧光素酶/靶点抑制双栏、四个实测椭圆轮廓、中央双向强化学习块、三类侧向输入和上下细胞行为胶囊。中部保留蓝色联邦学习框架、蝴蝶结交叉模块、数据/模型半圆、双头标注箭和两侧到达过程。下部保留绿色双层联邦框架与多学科/跨模态中心。所有原图混杂术语均为演示文案，不能直接当作论文科学事实。

## 固定数量与内容接口

example.json含template_id、texts；文字字符串或字符串数组，按字段替换，可用\n断行。拓扑及节点数量固定，缺少/多余字段均拒绝；不承诺无限节点。关系不适合时另选模板或重排，不改题意硬套。

|字段|每行全角上限|行数上限|
|---|---|---|
|upper_left_title|11|1|
|upper_right_title|10|1|
|upper_left_subtitle|23|1|
|upper_right_subtitle|21|1|
|upper_left_0_head|7|1|
|upper_left_0_body|7|1|
|upper_left_1_head|7|1|
|upper_left_1_body|7|1|
|upper_left_2_head|7|1|
|upper_left_2_body|7|1|
|upper_right_0_head|8|1|
|upper_right_0_body|7|1|
|upper_right_1_head|8|1|
|upper_right_1_body|7|1|
|upper_right_2_head|8|1|
|upper_right_2_body|7|1|
|upper_top_capsule|10|1|
|upper_bottom_capsule|10|1|
|upper_strategy|6|1|
|upper_arrow_body|6|3|
|upper_warmup|4|1|
|upper_simulation|5|1|
|blue_strategy|4|1|
|blue_rule|4|2|
|blue_action|5|1|
|green_strategy|4|1|
|green_rule|5|2|
|green_space|5|1|
|framework_title|36|1|
|blue_panel_title|44|1|
|green_panel_title|44|1|
|blue_framework_l_0|9|1|
|blue_framework_l_1|9|1|
|blue_framework_l_2|9|1|
|blue_framework_r_0|9|1|
|blue_framework_r_1|9|1|
|blue_framework_r_2|9|1|
|green_framework_l_0|9|1|
|green_framework_l_1|9|1|
|green_framework_l_2|9|1|
|green_framework_r_0|9|1|
|green_framework_r_1|9|1|
|green_framework_r_2|9|1|
|blue_left_note|6|5|
|blue_right_note|6|5|
|green_left_note|6|5|
|green_right_note|6|5|
|blue_butterfly_left_text|3|2|
|blue_butterfly_right_text|3|2|
|blue_cloud|0|1|
|blue_target|1|1|
|blue_side_l|6|1|
|blue_side_l_body|6|1|
|blue_side_l_2|6|1|
|blue_side_l_body2|6|1|
|blue_side_r|6|1|
|blue_side_r_body|6|1|
|blue_side_r_2|6|1|
|blue_side_r_body2|6|1|
|blue_data|2|3|
|blue_model|2|3|
|blue_arrow_left|2|7|
|blue_arrow_right|2|7|
|blue_core|15|1|
|blue_core_middle|15|2|
|blue_core_bottom|15|1|
|green_multi|6|2|
|green_cross|6|2|
|green_cloud|0|1|
|green_target|1|1|
|lower_bar|36|1|

## 调用与适配

按SKILL.md共享包装器调用`scripts/dual_circle_biological_framework.py`，传入工作区内容JSON与`-o`输出路径；`--check`只校验。然后strict版式检查、实际导出PNG/PDF、逐区看图及最终入文尺寸检查。共享源只读。

## 已知近似与尺寸状态

所有框、文字、椭圆曲线、双向块箭头、斜面、半圆、双头箭与分区边界均为原生可编辑图元，无整图位图。顶部半透明渐变与下部梯形阴影以无文字分区框和线条近似；原图遮挡/不确定文字使用明确演示字段。ref-28为独立保留变体，不能合并。A4/A3尺寸、三轮渲染、容量替换和视觉得分尚待实际验证。

三轮实际渲染审查已完成；最终 PNG/PDF、A4/A3、灰度、替换、容量边界、差异图与椭圆拟合叠加均已检查。模板已同步到 `.agents` 与 `.claude`；不能凭模板存在自动用于第一章。

# 使用说明与限制

- `template_id` 固定为 `dual-circle-biological-framework`，通过 `scripts/dual_circle_biological_framework.py` 调用。
- `example.json` 只允许替换既有 `texts` 字段；节点拓扑、椭圆轮廓和分区数量固定。原图文字混杂且有遮挡，模板中的术语是演示字段，使用前必须按题意重写并做语义审查。
- ref-23 的四个椭圆采用轴对齐椭圆拟合；被文字、卡片和箭头遮挡处以分段曲线保留，圆拟合失败证据与椭圆拟合证据均保留。
- A4 预估最小字约 7.59 pt，适合 A3 展示（约 11.72 pt）；第一章入文仍需按最终版页面实际检查。
- ref-28 是独立变体，不能通过本模板替代。
