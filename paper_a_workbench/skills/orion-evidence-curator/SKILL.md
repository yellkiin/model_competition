---
name: orion-evidence-curator
description: 整理A题本地原始实验包、Git报告、来源与论文数据。
---

# 共同输入

先读本Agent的AGENTS、ORION_论文总控提示词.md、paper_a_workbench/policies/WRITING_CONSTITUTION.md，以及SESSION指向的THEORY_BINDING和READ_BEFORE_DRAFTING。所有角色共用prepare-theory生成的THEORY/ALGORITHM/TERMS/SOURCE_MAP/PAPER_ROUTE与schema=1 GLOSSARY。来源包的APPEND_PROMPT不再是执行入口。

# 本角色执行

读取SESSION.local_data_root的原件和Git报告，生成显式publication/分片对应。使用scan-local、materialize-local、local-spec、intake；保留主实验、诊断、参数和历史对照的区别。输出RESULT_BINDING、原记录索引和待数据项；不要重新运行搜索或下载大原始Release。

结果写本次明确工作区。任务文件生成不替代实际阅读、推导、编辑或图件审阅。题面、有效推导和实际执行证据优先；先完善共有理论与已有数据支持的内容。
