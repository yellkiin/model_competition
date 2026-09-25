# ORION 论文更新：同一项目、同一生产会话

完整读取当前Agent的AGENTS、ORION_论文总控提示词.md及SESSION。工作区只使用SESSION.workspace_root，不按目录编号猜测，也不另起算法设计。

从SESSION.repo_cache发现新的报告、方法提交和PR44理论更新。实验原数据继续从SESSION.local_data_root读取，默认C:\Users\LEGION\Desktop\数据。scan-local刷新本地目录/归档清单，与新的报告轮次对应；无原始包的报告不自动补造数据，也不自动拉取大Release。

保留当前active_publication，选择新实验时用新的PAPER_EXPORT执行adopt-export；理论源theory_pr38_v1由工具保留。sync创建新快照并固定所有提交；changes对比SOURCE_LOCK。目录变化更新映射；新数据重算图表；候选/选择/停止/计时行为变化同步算法段；执行语义变化重审模型与证明。PR44仍在更新时，本次始终使用已经固定的提交。

prepare-theory生成新理论输入及schema=1术语表。package-inputs输出真实文件，按原add-input登记到同一工作区；再prepare-theory --workspace指向该明确工作区。实际更新THEORY_ALIGNMENT、TERM_SYMBOL_LEDGER、METHOD_TO_CODE和RESULT_BINDING，六个角色读取同一新输入，不叠加来源包的APPEND_PROMPT。

本地新数据经local-spec/intake进入新的派生目录，主结果、定向消融、参数研究、历史对照分别管理。旧表和旧稿保留，只重写依赖已变内容的正文、图、摘要、结论与附录。使用新术语表lint、check-edit及独立语义审核，编译后实际查看PDF，完成原工作流后重新finish。

本任务默认只读仓库并在项目内写论文，不运行百图、不上传实验大包、不自动合并或提交赛事。
