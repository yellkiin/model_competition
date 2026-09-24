# 双圆机制与实验框架变体图

独立ID：`dual-circle-biological-framework-variant`；来源：ref-28。

独立模板保留参考图的主要分区、标题层级、阶段连接和可替换字段；模板中的示例术语仅用于演示排版，使用前须按实际题意替换并审查。

## 固定数量与内容接口

example.json含template_id、texts；文字字符串或字符串数组，按字段替换，可用\n断行。拓扑及节点数量固定，缺少/多余字段均拒绝；不承诺无限节点。关系不适合时另选模板或重排，不改题意硬套。

|字段|每行全角上限|行数上限|
|---|---|---|
|title|46|1|
|upper_title|49|1|
|ul_0|9|1|
|ul_1|9|1|
|ul_2|9|1|
|ur_0|9|1|
|ur_1|9|1|
|ur_2|9|1|
|uc|19|3|
|middle_title|49|1|
|ml_0|10|1|
|ml_1|10|1|
|ml_2|10|1|
|mr_0|10|1|
|mr_1|10|1|
|mr_2|10|1|
|mc|16|3|
|lower_title|49|1|
|ll_0|11|1|
|ll_1|11|1|
|ll_2|11|1|
|lr_0|11|1|
|lr_1|11|1|
|lr_2|11|1|
|lc|15|2|

## 调用与适配

按SKILL.md共享包装器调用`scripts/dual_circle_biological_framework_variant.py`，传入工作区内容JSON与`-o`输出路径；`--check`只校验。然后strict版式检查、实际导出PNG/PDF、逐区看图及最终入文尺寸检查。共享源只读。

## 已知近似与尺寸状态

原始截图保留在reference.png/reference-crop.png；无法可靠辨识的文字采用明确演示字段，不把示例术语当作论文事实。

模板已同步到 `.agents` 与 `.claude`；物理尺寸审核见 defect-log，不能凭模板存在自动用于第一章。
