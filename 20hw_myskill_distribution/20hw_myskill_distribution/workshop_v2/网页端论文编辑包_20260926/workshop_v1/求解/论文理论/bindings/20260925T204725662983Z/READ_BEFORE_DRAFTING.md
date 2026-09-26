# 本次论文的共同理论输入

依次完整读取 THEORY、ALGORITHM、TERMS、SOURCE_MAP、PAPER_ROUTE 和 references.bib。这是六个专题角色共同的正文起点，不再执行来源包中的追加提示词或独立安装步骤。

先完成 THEORY_ALIGNMENT.md、TERM_SYMBOL_LEDGER.json、METHOD_TO_CODE.csv、RESULT_BINDING.json 与 PENDING_EVIDENCE.md，再由正文角色采用已对齐的定义、命题和路线。这些文件由宿主实际核对后撰写。生成本输入包仅登记资料，不自动填写对齐通过。

本包 inspected_implementation_anchor 记录被核读的旧实现。实际运行提交由 publication 指定。目录改名更新路径；来源选择、近界阈值、计时范围等变化需对照实际代码更新算法段。题面、未修改官方语义和成立的推导优先。

总体任务执行时间（Makespan）作为正文规范名；其数学定义为全部操作完成时刻的最大值。术语使用 GLOSSARY.json，原始 TERMS.json 原样保留。正文保持客观学术表述，代码标识及版本交接留在内部方法映射。
