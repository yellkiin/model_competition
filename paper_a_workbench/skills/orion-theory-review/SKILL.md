---
name: orion-theory-review
description: 核对A题统一理论、实际执行语义、证明与符号。
---

# 共同输入

先读本Agent的AGENTS、ORION_论文总控提示词.md、paper_a_workbench/policies/WRITING_CONSTITUTION.md，以及SESSION指向的THEORY_BINDING和READ_BEFORE_DRAFTING。所有角色共用prepare-theory生成的THEORY/ALGORITHM/TERMS/SOURCE_MAP/PAPER_ROUTE与schema=1 GLOSSARY。来源包的APPEND_PROMPT不再是执行入口。

# 本角色执行

完整读THEORY/ALGORITHM/TERMS/SOURCE_MAP/PAPER_ROUTE及所引用原文。按实际执行版本核对定义、变量域、Task/容量/FIFO、下界、命题、来源选择和停止。输出THEORY_ALIGNMENT、METHOD_TO_CODE与符号定义，记录数学条件和真实代码对应。

结果写本次明确工作区。任务文件生成不替代实际阅读、推导、编辑或图件审阅。题面、有效推导和实际执行证据优先；先完善共有理论与已有数据支持的内容。
