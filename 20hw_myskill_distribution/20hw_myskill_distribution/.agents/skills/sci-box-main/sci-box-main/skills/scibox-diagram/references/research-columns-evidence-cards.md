# 三列研究路线与基础证据卡框架图

独立ID：`research-columns-evidence-cards`；来源：ref-10。

三带框架：上部国内/国外/趋势三栏现状，中部三列研究内容，底部理论/成果/团队三张基础证据卡。保持上下箭头、右侧对应关系、半圆标题页签、勾星图标、多模态阶梯块与三种原生示意统计图。适合并列研究路线及基础说明；参考的医学标题与AI术语混杂，示例不证明这些科学关系成立。

## 固定数量与内容接口

example.json含template_id、texts；文字字符串或字符串数组，按字段替换，可用\n断行。拓扑及节点数量固定，缺少/多余字段均拒绝；不承诺无限节点。关系不适合时另选模板或重排，不改题意硬套。

|字段|每行全角上限|行数上限|
|---|---|---|
|title|41|1|
|side_0|1|8|
|side_1|1|21|
|side_2|1|16|
|status_heading_0|13|1|
|status_heading_1|14|1|
|status_heading_2|13|1|
|domestic_text_0|10|1|
|domestic_text_1|10|1|
|domestic_text_2|10|1|
|foreign_text_0|10|2|
|foreign_text_1|10|2|
|trend_text_0|8|2|
|trend_text_1|8|2|
|content_number_0|6|1|
|content_title_0|9|2|
|content_number_1|6|1|
|content_title_1|9|2|
|content_number_2|6|1|
|content_title_2|9|2|
|gradcam|10|2|
|network_name_0|8|1|
|network_name_1|8|1|
|multimodal|9|1|
|modal_face_0|4|1|
|modal_face_1|4|1|
|modal_face_2|4|1|
|attention|11|1|
|attention_name_0|8|1|
|attention_name_1|8|1|
|attention_name_2|8|1|
|attention_name_3|8|1|
|attention_name_4|8|1|
|accuracy|2|1|
|accuracy_unit|1|1|
|improvement|3|1|
|improvement_unit|1|1|
|prediction|7|1|
|ablation|6|1|
|ablation_0|9|1|
|ablation_1|9|1|
|ablation_2|9|1|
|ablation_3|9|1|
|method_correspondence|1|4|
|basis_correspondence|1|4|
|evidence_heading_0|7|1|
|detail_heading_0|9|1|
|detail_subheading_0|9|1|
|detail_label_0_0|6|1|
|detail_value_0_0|1|1|
|detail_label_0_1|6|1|
|detail_value_0_1|1|1|
|detail_label_0_2|6|1|
|detail_value_0_2|1|1|
|evidence_heading_1|7|1|
|detail_heading_1|9|1|
|detail_subheading_1|9|1|
|detail_label_1_0|6|1|
|detail_value_1_0|1|1|
|detail_label_1_1|6|1|
|detail_value_1_1|1|1|
|detail_label_1_2|6|1|
|detail_value_1_2|1|1|
|evidence_heading_2|7|1|
|detail_heading_2|9|1|
|detail_subheading_2|9|1|
|detail_label_2_0|6|1|
|detail_value_2_0|1|1|
|detail_label_2_1|6|1|
|detail_value_2_1|1|1|
|detail_label_2_2|6|1|
|detail_value_2_2|1|1|
|tick_0_0|1|1|
|tick_0_1|1|1|
|tick_0_2|1|1|
|tick_0_3|1|1|
|month_0_0|1|1|
|month_0_1|1|1|
|month_0_2|1|1|
|month_0_3|1|1|
|month_0_4|1|1|
|month_0_5|1|1|
|month_0_6|1|1|
|month_0_7|1|1|
|month_0_8|1|1|
|month_0_9|1|1|
|month_0_10|1|1|
|tick_1_0|1|1|
|tick_1_1|1|1|
|tick_1_2|1|1|
|tick_1_3|1|1|
|tick_1_4|1|1|
|tick_1_5|1|1|
|month_1_0|1|1|
|month_1_1|1|1|
|month_1_2|1|1|
|month_1_3|1|1|
|month_1_4|1|1|
|month_1_5|1|1|
|tick_2_0|1|1|
|tick_2_1|1|1|
|tick_2_2|1|1|
|tick_2_3|1|1|
|month_2_0|1|1|
|month_2_1|1|1|
|month_2_2|1|1|
|month_2_3|1|1|
|month_2_4|1|1|
|month_2_5|1|1|
|month_2_6|1|1|
|month_2_7|1|1|
|month_2_8|1|1|
|month_2_9|1|1|
|month_2_10|1|1|
|bar_annotation|2|1|
|demo_note|71|1|

## 调用与适配

按SKILL.md共享包装器调用`scripts/research_columns_evidence_cards.py`，传入工作区内容JSON与`-o`输出路径；`--check`只校验。然后strict版式检查、实际导出PNG/PDF、逐区看图及最终入文尺寸检查。共享源只读。

## 已知近似与尺寸状态

全部主要对象、图标和统计小图为原生图元。图中99.56%、35.32%、+56%及42/56/3等均为参考示例，底部显式标注演示。原图缺少Oct且写Des/Jau的月份标签保留，不改成真实时间序列。标题XXX占位改为明确演示标题；侧栏用正立竖排替代旋转文字。圆标阴影及图标线条近似；不保留手机界面与水印。图中曲线/柱形/面积为固定布局图元，JSON可换标签但不能只换数字冒充新数据；正式科研结果应走双来源真实数据绘图并重审。

模板已同步到 `.agents` 与 `.claude`；物理尺寸审核见 defect-log，不能凭模板存在自动用于第一章。

## 实际尺寸与科学使用边界

三轮真实渲染后，示例、替换文案、满容量、PDF渲染、灰度、差分及A4/A3/A2完整预览均已实际查看。当前已完成模板复查并同步两端。

- A4宽160mm、高232.29mm时最小字约5.06pt，A3宽247mm、高358.61mm时约7.82pt；均不推荐原样作为论文正文或第一章总体路线。
- A2宽370mm、高537.18mm时最小字约11.71pt，可完整展示。若要正文使用，须保留真实关系重新组织布局、删除无科学用途的演示数据，并重新检查。
- 固定三列卡片、两组跨带箭头、右侧对应关系与三种底部小图；JSON支持各字段字符串或分行数组，不支持任意增加节点。
- 底部折线、柱形和面积来自参考图的几何复刻，**不是可替换真实数据的统计生成器**。不能只改刻度或数字、保留旧曲线就宣称已绘制新结果；正式结果必须走项目双来源规则，使用真实数据绘制并重审混合图。
- 示例中的99.56%、35.32%、+56%及九项基础数量均非本题成果。原图缺Oct、Des/Jau等标签及重复“奖”字保留；无科学有效性背书。
- 保留原图浅蓝页签与白字，其灰度对比弱于深蓝页签；建议正式适配时提高页签对比。左侧旋转文字改为正立竖排，顶部占位主题改成演示标题；三种小图的细线、简化小图标及阴影保留已知近似。
- 后续正式适配优先改进：提高第二/三列页签白字对比、扩大统计小图文字或拆分面板、按真实用途精简基础信息。上述改进需要新一轮真实渲染审核，不能自动继承本模板结论。
