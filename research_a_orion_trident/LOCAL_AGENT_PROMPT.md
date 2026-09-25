# 三机共同提示词：Trident 1.3 / PR #38

你在`yellkiin/model_competition`执行已发布的ORION Trident三线整合。代码PR为#38，分支`integration/orion-trident-publish-20260925`。只写`research_a_orion_trident/`，保护并行的`research_a_orion_fusion/`、三条研究源、官方图/config/评估器。三台记录并固定同一提交，长实验中不更新代码或解释器；代码PR已经创建，不重复调用publish_code，不重复开代码PR。

先读本机HOST_N.md、METHOD、EXPERIMENT_PLAN、REVIEW_AND_RESULTS和SOURCE_MANIFEST。在已有授权Git仓库建立独立稀疏worktree，按INSTALL_AND_PUBLISH获取代码。Windows优先现有D:\python\python.exe、64位Python3.12.x、CPU-only。不运行smoke、pytest/unittest、哈希/指纹测试、环境benchmark或全仓审计，只检查启动必要项并执行真实官方图。

按HOST_N的ShardIndex启动`run_windows.ps1 -ShardIndex N -FetchInputs -Seconds 600 -Hours 12`。输入读取、原文和历史记录按固定Git引用分批获取，单独记录准备时间；已有输入复用，原始研究大ZIP不是开跑前置条件。运行器先选本片两个未在本目录证据覆盖的真实配置，通过即继续本片其他图并复用结果，不重复既有小样本。

每配置=(图,q,n)，600秒包括启动/解析、全部本次种子回放、构造/搜索/保存、Q3同方案无L2配对；全图14个主配置总耗时另报。源码冻结的S/M/F共享同一合法incumbent，B基础路径始终保留。只接受官方(Makespan,额外COPY)更优方案；失败/较慢候选保留记录，不覆盖好解。历史仅有数字而无计划时作为追赶目标，不伪造种子；未知历史成本留空。

自动workers目标CPU和整机RAM各留25%，按实际RSS/CPU渐进准入，不与NPU核数混淆，不结束别人进程，不为填满预算空转。批次默认12小时，clock文件持久保存，重启不重置；已启动中断作业保留最后方案，继续搜索必须显式新round并累计成本。

每30秒保留当时真实已持有的最好解、来源、候选、活动阶段、调用数及成本；早停后标记持有，不以最终值倒填早期。Q3配对是本次同一plan用原Q2语义评估，不使用独立Q2最优当分母。

默认先完整SMF；明显质量短缺进入有限队列，Q3先SM/SF/MF、必要再S/M/F，Q1/Q2直接S/M。每组同机、同起点、同档预算；只用该配置600秒尚余预算，不足则记录延期。诊断另列，不从各臂挑最优偷偷拼正式SMF成绩；可显式在下一轮采用诊断好方案。

低收益先看首次有效解/各源首评、重复生成、陈旧父方案、次数上限和终点COPY约束。011展示了来源竞争造成的短冷差距；高Spill查看M开放宽度，零Spill长Task/DDR等待查看S释放和Tensor端点，高命中低收益看全局终点。结构标签只是提案触发，084五核有效而三核无收益，不强制采用同一波次。

结束或截止后，导出主表/配对/每次改善/30秒曲线、COPY/Spill/hit、来源成本、Pipe和图特征、真实计划/响应、请求/源码快照/错误。敏感性独立目录、默认点复用、不混正式配置。每机运行publish_results.ps1，只发布自己的team_results/trident_round01/shard_N和Release原响应分块；读回真实上传/PR回执。不自动合并、不上传赛事平台、不覆盖其他分片。三片齐后指定一台collect，不再重复跑100图。
