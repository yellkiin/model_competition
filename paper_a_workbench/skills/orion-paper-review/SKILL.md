---
name: orion-paper-review
description: 独立审查A题论文的题面对应、理论、术语、数据和图文。
---

# 共同输入

先读本Agent的AGENTS、ORION_论文总控提示词.md、paper_a_workbench/policies/WRITING_CONSTITUTION.md，以及SESSION指向的THEORY_BINDING和READ_BEFORE_DRAFTING。所有角色共用prepare-theory生成的THEORY/ALGORITHM/TERMS/SOURCE_MAP/PAPER_ROUTE与schema=1 GLOSSARY。来源包的APPEND_PROMPT不再是执行入口。

# 本角色执行

先读原题与共同理论，再读实际版本和原记录，最后读稿件。按章节顺序检查符号首次定义、后续使用、数字分母、同方案配对和量纲；实际检查图件/PDF。独立上下文可用时分开审阅，记录真实完成步骤。

结果写本次明确工作区。任务文件生成不替代实际阅读、推导、编辑或图件审阅。题面、有效推导和实际执行证据优先；先完善共有理论与已有数据支持的内容。
