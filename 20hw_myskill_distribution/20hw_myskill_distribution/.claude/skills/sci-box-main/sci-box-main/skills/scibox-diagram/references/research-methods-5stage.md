# 研究内容与方法五阶段框架图

独立ID：`research-methods-5stage`；来源：ref-11。

五行研究工作包，左列研究阶段、右列方法分别指向中央内容；行间没有原图不存在的流程箭头。保留第一行三组并列梳理、第二行因子提取与理论论证、第三行四类输入支持技术方案、第四行相向实验与对照分析、第五行双输出。适合多阶段研究安排，不适合需要真实跨阶段变量箭头或算法循环的场景。

## 固定数量与内容接口

example.json含template_id、texts；文字字符串或字符串数组，按字段替换，可用\n断行。拓扑及节点数量固定，缺少/多余字段均拒绝；不承诺无限节点。关系不适合时另选模板或重排，不改题意硬套。

|字段|每行全角上限|行数上限|
|---|---|---|
|framework_heading|5|1|
|content_heading|9|1|
|method_heading|5|1|
|stage_1|3|4|
|method_1|3|4|
|stage_2|3|4|
|method_2|3|4|
|stage_3|3|4|
|method_3|3|4|
|stage_4|3|4|
|method_4|3|4|
|stage_5|3|4|
|method_5|3|4|
|title_1|22|1|
|title_2|22|1|
|title_3|22|1|
|title_4|16|1|
|title_5|16|1|
|title_6|22|1|
|question_heading_1|10|1|
|question_heading_2|10|1|
|question_heading_3|10|1|
|question_6|8|1|
|question_11|8|1|
|question_12|8|1|
|question_7|8|1|
|question_9|8|1|
|question_13|8|1|
|question_8|8|1|
|question_10|8|1|
|question_14|8|1|
|parameter_heading|8|1|
|theory_heading|10|1|
|data|1|6|
|feature|1|6|
|factor|1|6|
|theory_model|6|2|
|theory_constraints|6|2|
|theory_validity|1|8|
|theory_25|8|1|
|theory_26|8|1|
|theory_28|8|1|
|design_33|8|1|
|design_37|8|1|
|design_39|8|1|
|design_41|8|1|
|strategy_34|15|2|
|strategy_38|15|2|
|strategy_40|15|2|
|simulation|1|8|
|initial_result|1|8|
|experiment_heading|7|1|
|comparison_heading|7|1|
|experiment_45|5|2|
|experiment_53|5|2|
|experiment_57|5|2|
|experiment_48|5|2|
|experiment_54|5|2|
|experiment_58|5|2|
|evidence_51|7|1|
|evidence_55|7|1|
|evidence_59|7|1|
|evidence_52|7|1|
|evidence_56|7|1|
|evidence_60|7|1|
|conclusion|14|1|
|outlook|14|1|

## 调用与适配

按SKILL.md共享包装器调用`scripts/research_methods_5stage.py`，传入工作区内容JSON与`-o`输出路径；`--check`只校验。然后strict版式检查、实际导出PNG/PDF、逐区看图及最终入文尺寸检查。共享源只读。

## 已知近似与尺寸状态

手机界面及斜向水印不复刻。原图第一行中列重复两次“理论体系梳理”，如实保留为演示字段，应用时按真实内容替换。第四行白色分析容器用直角线框近似原图圆角；无额外统计结果或位图面板。字体采用本机SimSun，笔画与原图存在渲染差异；配色取测量值并归并同族。

模板已同步到 `.agents` 与 `.claude`；物理尺寸审核见 defect-log，不能凭模板存在自动用于第一章。

## 已完成的暂存尺寸审查

A4宽160mm最小字约8.27pt，细宋体偏小，不推荐默认第一章使用；A3宽247mm最小字约12.77pt可读。详见资产defect-log.md及qa/visual-review.json。
