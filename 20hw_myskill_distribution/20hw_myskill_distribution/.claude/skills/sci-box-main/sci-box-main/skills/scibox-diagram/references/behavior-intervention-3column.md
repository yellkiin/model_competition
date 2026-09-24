# 行为机制与干预研究四阶段三栏框架图

独立ID：`behavior-intervention-3column`；来源：ref-16。

三栏对应研究思路、研究内容、研究方法，四阶段分别为背景与三个问题、三类理论与三步框架、四项调查/干预工作、三项综合分析到双输出及末端汇流。保留三理论之间的双细带、左侧下弯曲箭头、综合分析大括号与左右两列阶段箭头。

## 固定数量与内容接口

example.json含template_id、texts；文字字符串或字符串数组，按字段替换，可用\n断行。拓扑及节点数量固定，缺少/多余字段均拒绝；不承诺无限节点。关系不适合时另选模板或重排，不改题意硬套。

|字段|每行全角上限|行数上限|
|---|---|---|
|thinking|6|1|
|content|6|1|
|methods|6|1|
|demo_note|32|1|
|thinking_0|5|1|
|thinking_1|5|1|
|thinking_2|5|1|
|thinking_3|5|1|
|thinking_4|5|1|
|thinking_5|5|1|
|thinking_6|5|1|
|thinking_7|5|1|
|method_0|5|1|
|method_1|5|1|
|method_2|5|1|
|method_3|5|1|
|method_4|5|1|
|method_interview|5|1|
|digital_context|6|1|
|usage_context|6|1|
|question_0|7|2|
|question_1|7|2|
|question_2|7|2|
|theory_0|8|1|
|theory_1|8|1|
|theory_2|8|1|
|framework_0|8|2|
|framework_1|8|2|
|framework_2|8|2|
|research_title_0|5|1|
|research_detail_0|21|1|
|research_title_1|5|1|
|research_detail_1|21|1|
|research_title_2|5|1|
|research_detail_2|21|1|
|research_title_3|5|1|
|research_detail_3|21|1|
|synthesis|8|1|
|analysis_0|10|2|
|analysis_1|10|2|
|analysis_2|7|2|
|output_0|6|1|
|output_detail_0|14|2|
|output_1|6|1|
|output_detail_1|14|2|
|final_output|28|2|

## 调用与适配

按SKILL.md共享包装器调用`scripts/behavior_intervention_3column.py`，传入工作区内容JSON与`-o`输出路径；`--check`只校验。然后strict版式检查、实际导出PNG/PDF、逐区看图及最终入文尺寸检查。共享源只读。

## 已知近似与尺寸状态

全部主要元素为原生可编辑mxGraph。原图多处XXXXX占位替换为明确网络使用行为研究演示文案，底部增示例说明；不当作真实赛题事实或成果。原末端将策略应用也汇入学术发表节点的关系保留，仅适用于确实有此报告汇总关系的任务。理论双带与弯曲箭头用原生路径近似，字体、圆角与水印省略存在差异。固定四阶段及三/四/三/二的内部数量，支持字段容量内替换，不任意增加节点。

模板已同步到 `.agents` 与 `.claude`；物理尺寸审核见 defect-log，不能凭模板存在自动用于第一章。

## 当前复查与尺寸限制

三轮真实渲染及实际看图记录见defect-log.md；仅通过暂存模板复查，已同步 `.agents` 与 `.claude` 两端，不代表正式论文验收。

1206×1743画布，最小22px文字。实际PDF以160mm宽完整放入A4时，高231.23mm、最小字约8.27pt，研究明细及理论框架文字偏小，不推荐原样放入第一章。以247mm宽放入A3时，高356.96mm、最小字约12.77pt，可用于大幅展示；需要A4正文时应按真实任务精简和重排，再重新审核，不能简单缩字。

固定三栏四阶段，背景2项→共同母线→3个问题；3个理论通过双带关联，再由左侧弯箭头支持3步框架；4项调查/干预工作分别对应右侧说明；综合分析3项汇入2个输出，再汇入最后报告节点。左右栏是阶段及方法对应，不能凭列相邻就新增因果连接。若当前任务没有末端报告汇总关系，应改选其他结构，不能将本示例套成事实。

原XXXXX均替换为演示文案，底部明确注明示例。为提高可读性，四个浅紫标题略加深为#9682bd，“综合分析”改深色字；灰度下这两组标题均已实际查看。框架灰色衬底已恢复。保留字体、弯箭头轮廓、圆角及虚线相位近似；不复刻水印，不声称逐像素一致。主形状、文字和连接均可编辑。
