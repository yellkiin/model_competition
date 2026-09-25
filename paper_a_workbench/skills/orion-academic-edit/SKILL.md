---
name: orion-academic-edit
description: 在保留数学含义和证据的前提下编辑A题学术正文。
---

# 共同输入

先读本Agent的AGENTS、ORION_论文总控提示词.md、paper_a_workbench/policies/WRITING_CONSTITUTION.md，以及SESSION指向的THEORY_BINDING和READ_BEFORE_DRAFTING。所有角色共用prepare-theory生成的THEORY/ALGORITHM/TERMS/SOURCE_MAP/PAPER_ROUTE与schema=1 GLOSSARY。来源包的APPEND_PROMPT不再是执行入口。

# 本角色执行

使用本次合并GLOSSARY及TERM_SYMBOL_LEDGER，一概念一名称、先定义后使用。编辑前后核对公式、数字、引用、量纲、条件和因果强度；去掉机械/空泛修饰，不替换标准术语，不增强结论。输出编辑稿与内部修改记录。

结果写本次明确工作区。任务文件生成不替代实际阅读、推导、编辑或图件审阅。题面、有效推导和实际执行证据优先；先完善共有理论与已有数据支持的内容。
