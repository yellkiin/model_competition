# 调研采集与实证分析三阶段图

独立ID：`fieldwork-analysis-3band`；来源：ref-26。

三个阶段依次推进：筹备、采集、分析产出。每带保留左右两面板，首带文献双列相互参照，方案设计两组扇出；第二带三组双向校核与三路处理汇总核验；第三带要素/路径/模型双向串联、两个分析视角和右侧四步对策链。适合调研类研究安排，不适合简单算法循环或无实地调研的数据分析。

## 固定数量与内容接口

example.json含template_id、texts；文字字符串或字符串数组，按字段替换，可用\n断行。拓扑及节点数量固定，缺少/多余字段均拒绝；不承诺无限节点。关系不适合时另选模板或重排，不改题意硬套。

|字段|每行全角上限|行数上限|
|---|---|---|
|stage_1|1|15|
|stage_2|1|14|
|stage_3|1|20|
|heading_1|32|1|
|heading_2|32|1|
|heading_3|32|1|
|review|17|1|
|design|17|1|
|survey|17|1|
|cleaning|17|1|
|coding|17|1|
|strategy|17|1|
|prep_8|5|1|
|prep_12|5|1|
|prep_16|5|1|
|prep_9|5|1|
|prep_13|5|1|
|prep_17|5|1|
|prep_10|5|2|
|prep_5|7|1|
|prep_11|7|1|
|prep_15|5|2|
|prep_14|7|1|
|prep_18|7|1|
|survey_25|7|2|
|survey_26|7|2|
|survey_30|7|2|
|survey_31|7|2|
|survey_32|7|2|
|survey_27|7|2|
|survey_sample|7|2|
|survey_entry|7|2|
|survey_archive|7|2|
|collect|1|6|
|verify|1|6|
|analysis_44|3|2|
|analysis_50|3|2|
|analysis_55|3|2|
|analysis_43|5|1|
|analysis_46|5|1|
|analysis_49|5|1|
|analysis_54|5|1|
|analysis_56|5|1|
|analysis_42|7|1|
|analysis_47|7|1|
|analysis_51|7|1|
|analysis_53|7|1|
|analysis_57|15|1|
|evolution|5|1|
|process|1|9|
|mechanism|1|6|
|system|1|6|
|problem|1|9|
|causes|1|9|

## 调用与适配

按SKILL.md共享包装器调用`scripts/fieldwork_analysis_3band.py`，传入工作区内容JSON与`-o`输出路径；`--check`只校验。然后strict版式检查、实际导出PNG/PDF、逐区看图及最终入文尺寸检查。共享源只读。

## 已知近似与尺寸状态

框与箭头、竖向标签均可编辑。少量连通域被文本割裂的节点（第二带调研对象抽样、问卷录入、政策档案与第三带阶段演化）根据同族描边扫描补齐矩形；节点明细有记录。原图“政策文本档案整编”按截图断成两行，示例术语不构成赛题事实。矩形标题不复刻轻微圆角，上下粗箭头用原生图形近似。

模板已同步到 `.agents` 与 `.claude`；物理尺寸审核见 defect-log，不能凭模板存在自动用于第一章。

## 已完成的暂存尺寸审查

A4宽160mm近整页可用，最小字约9.4pt；不可直接缩为半页，图题与前后正文须实际论文页复核。详见资产defect-log.md及qa/visual-review.json。
