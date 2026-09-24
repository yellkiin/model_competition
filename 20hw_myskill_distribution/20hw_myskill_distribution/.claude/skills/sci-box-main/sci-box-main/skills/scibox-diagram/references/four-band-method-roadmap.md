# 四阶段研究总体技术路线图

独立ID：`four-band-method-roadmap`；来源：ref-08。

四个阶段依次向下推进：前期调研、方案拆解、系统实现、测试总结。第一带中央思路向两侧输出；第二带左四项及右三项母线分支，三条带标签箭头对应参数/模型/逻辑；第三带原图无箭头母线连接处理与调试；第四带中栏向左数据归集、向右方案验证，保留巨型箭头和六边形标签。

## 固定数量与内容接口

example.json含template_id、texts；文字字符串或字符串数组，按字段替换，可用\n断行。拓扑及节点数量固定，缺少/多余字段均拒绝；不承诺无限节点。关系不适合时另选模板或重排，不改题意硬套。

|字段|每行全角上限|行数上限|
|---|---|---|
|title|38|1|
|side_text_0|1|6|
|side_text_1|1|6|
|side_text_2|1|6|
|side_text_3|1|6|
|research_goal|15|1|
|literature|10|1|
|initial_plan|10|1|
|gap|10|3|
|implementation|10|3|
|overall_thought|9|3|
|decomposition|4|4|
|requirement_0|6|1|
|requirement_1|6|1|
|requirement_2|6|1|
|requirement_3|6|1|
|algorithm|8|1|
|algorithm_output_0|4|1|
|algorithm_output_1|4|1|
|algorithm_output_2|4|1|
|algorithm_arrow_text_0|2|1|
|algorithm_arrow_text_1|2|1|
|algorithm_arrow_text_2|2|1|
|submodule_design|3|3|
|design_0|6|1|
|design_1|6|1|
|design_2|6|1|
|integrated_check|10|1|
|platform_header|36|1|
|raw_data|1|6|
|clean|7|1|
|normalize|7|1|
|split|7|1|
|training|7|4|
|tuning|7|1|
|iteration|7|1|
|testing|7|1|
|deployment|1|6|
|test_title_0|7|1|
|test_title_1|7|1|
|test_title_2|7|1|
|test_card_0_0|7|2|
|test_card_0_1|7|2|
|test_card_0_2|7|1|
|test_card_1_0|7|2|
|test_card_1_1|7|2|
|test_card_1_2|7|1|
|test_card_2_0|7|2|
|test_card_2_1|7|2|
|test_card_2_2|7|1|
|arrow_label_0|2|2|
|arrow_label_1|2|2|

## 调用与适配

按SKILL.md共享包装器调用`scripts/four_band_method_roadmap.py`，传入工作区内容JSON与`-o`输出路径；`--check`只校验。然后strict版式检查、实际导出PNG/PDF、逐区看图及最终入文尺寸检查。共享源只读。

## 已知近似与尺寸状态

全部图形文字可编辑，保留原图连接、方向、母线及双色巨型箭头。只省略水印/手机界面，标题增示例标识。微软雅黑字形、箭头尖比例与圆角/虚线节距存在近似；无科学事实声明。此前省略连接的草稿及其通过记录已撤回，不沿用其分数或尺寸结论。

模板已同步到 `.agents` 与 `.claude`；物理尺寸审核见 defect-log，不能凭模板存在自动用于第一章。

## 使用限制与尺寸

固定四阶段，第二带四项需求/三项设计、第三带两组三项处理、第四带三列各三卡。只替换JSON文字，不自动增减拓扑。raw_data及deployment须单列竖排，每行1字；紫色六边形标签为2字×2行。

A4宽160mm时约231.23mm高，最小字约8.27pt，不推荐原样用于第一章；A3宽247mm时约356.96mm高，最小字约12.77pt，可大幅展示。正式论文应按真实任务选用或重排并检查实际PDF，不为适配图增加不存在的步骤。

参考的“总体方案拆解拆分”等表述保留为演示转录，不代表推荐论文用词；原始数据采集/系统集成部署两竖栏原图未用线连接，不能自动解释为具体因果链。第一带中央思路向两侧输出；第四带向左数据归集、向右方案验证。终图保留全部原图关系；字体、虚线节距、箭头肩部与采样边界有已登记近似。

早期省略关系的草稿已撤回。当前依据Rebuild1–3三次实际渲染和复核，详见defect-log.md，不沿用旧草稿通过结论。
