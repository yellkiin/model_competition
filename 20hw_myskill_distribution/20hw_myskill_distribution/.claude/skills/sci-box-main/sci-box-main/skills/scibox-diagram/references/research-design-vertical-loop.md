# 纵向研究设计与实证闭环图

独立ID：`research-design-vertical-loop`；来源：ref-24。

独立模板保留参考图的主要分区、标题层级、阶段连接和可替换字段；模板中的示例术语仅用于演示排版，使用前须按实际题意替换并审查。

## 固定数量与内容接口

example.json含template_id、texts；文字字符串或字符串数组，按字段替换，可用\n断行。拓扑及节点数量固定，缺少/多余字段均拒绝；不承诺无限节点。关系不适合时另选模板或重排，不改题意硬套。

|字段|每行全角上限|行数上限|
|---|---|---|
|title|45|1|
|left_title|7|1|
|middle_title|28|1|
|right_title|7|1|
|leftnode_0|6|2|
|leftnode_1|6|2|
|leftnode_2|6|2|
|leftnode_3|6|2|
|leftnode_4|6|2|
|rightnode_0|6|2|
|rightnode_1|6|2|
|rightnode_2|6|2|
|rightnode_3|6|2|
|rightnode_4|6|2|
|m0|25|2|
|m1|25|2|
|m2|25|2|
|m3|25|2|
|m4|25|2|
|footer|50|2|

## 调用与适配

按SKILL.md共享包装器调用`scripts/research_design_vertical_loop.py`，传入工作区内容JSON与`-o`输出路径；`--check`只校验。然后strict版式检查、实际导出PNG/PDF、逐区看图及最终入文尺寸检查。共享源只读。

## 已知近似与尺寸状态

原始截图保留在reference.png/reference-crop.png；无法可靠辨识的文字采用明确演示字段，不把示例术语当作论文事实。

模板已同步到 `.agents` 与 `.claude`；物理尺寸审核见 defect-log，不能凭模板存在自动用于第一章。

# 使用说明与限制

- `template_id` 固定为 `research-design-vertical-loop`，通过 `scripts/research_design_vertical_loop.py` 调用。
- `example.json` 只允许替换既有 `texts` 字段，拓扑和节点数量固定；字段容量以 `references/research-design-vertical-loop.md` 和生成器检查为准。
- 本模板是 ref-24 的结构化可编辑重建，示例术语仅用于演示排版，使用前必须按题意重写并审查。
- A4/A3 尺寸已生成并标注为 REVIEW_REQUIRED；正文使用前需要结合图题、字号和版面再次审核。
