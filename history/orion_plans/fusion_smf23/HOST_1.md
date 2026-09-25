# 主机2：ORION SMF 2.3完整运行与结果发布

在yellkiin/model_competition拉取分支`feat/orion-fusion-smf-consolidated-20260925`对应的完整PR；已合并则使用包含该提交的main。独立工作区运行，不改其他仍在跑的目录。阅读research_a_orion_fusion/README.md、CONSOLIDATION_2_3.md、EXPERIMENT_PLAN.md后实际执行，不只复述命令。

问题源DOCX在题目/A题；原始图/config/官方评估器在“题目/A题/通用神经网络处理器下的多核调度问题  附件/”。文献在调研/A题_文献库。结构S、驻留M、FIFO/候选时间分配F已共享一个最好解；默认先S/M短阶段，再联合F。原图/config/Step1–3不改，不重复计084微波次为缓存收益。

取得day01完整100图表和selected_plans.zip，不能仅有原机器50图。入口恢复随代码提供的19份真实强方案，并发现研究目录已有可用plan；本地更多好方案用-ExtraPlans传入。只有报告数字但没有实际plan的目标如实列缺失，不造种子。种子在目标小问/核数重新评估，历史完整成本未知不写零。

每(图,q,n)本次从进程启动到保存最好解最多600秒，含读图、种子回放、构造、原评估。每30秒保存已有最好值、候选来源和优化阶段；无改进或近界可早停，停止后持有值不冒称还在搜索。正式缓存对照/诊断/参数研究另计。主流程最多12小时，同目录恢复不刷新时钟。

你负责分片1，三台算法与预算相同、仅分片路径不同。默认按旧工作量+规模分成34/33/33图，每图全部核数/问题留同机。Windows优先D:\python\python.exe，Python3.12 x64、CPU-only，无新增求解依赖。不符则本机Agent配置独立解释器并传-Python，不升级正在运行的环境。不要哈希/指纹、冒烟、pytest/unittest或全仓审计前置；启动必需项后直接真实图，保留官方合法性检查。

自动workers依据整机CPU/RAM和实际作业峰值留25%余量；workers与题目核心数不同，不为拉满内存制造空负载。使用默认SourcePolicy staged，不让三台各自更换策略后混报。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a_orion_fusion\run_windows.ps1 -ShardIndex 1 -Out 'research_a_orion_fusion\runs\round03_smf23_shard_1'
```

先本片两个本轮未验证的真实小配置，通过自动继续本片；先行成绩复用，不重复全100图。正式1400主+500同方案对照分布在三片。没有明显原因的差配置先SM/SF/MF，再必要S/M/F；完整共用种子、原配置和预算不变，诊断成本单列。旧好解不被差候选覆盖，但raw候选表现仍报告，不能用保留种子冒充每个组件有效。少核方案须补空核后在目标核数重新评估，不能直接复制分数。

效果不好依次查看attempts与阶段数据：候选生成占时多则缓存/限制生成批量；高Spill查有限微波次；高命中低收益查控制最后完成的读；新模块首评不足查来源公平；改进停滞看实际连续曲线，不默认无限加预算。改算法/参数使用新输出根，不边跑边改Python。主样本和消融不事后取最低值混成固定策略主表。

完成或截止后读取shard_status、report、paper_data和mechanism_status；保留全部缺失/失败。已有GitHub授权下实际执行：

```powershell
.\research_a_orion_fusion\publish_results.ps1 -RunRoot 'research_a_orion_fusion\runs\round03_smf23_shard_1' -ShardIndex 1
```

只发布`research_a_orion_fusion/team_results/round03_smf23/shard_1/`，结果分支`results/orion-round03_smf23-shard-1-<时间>`。上传实际两字段方案、原响应、逐例表、30秒曲线、优化阶段、论文数据及参数网格，原档案40MiB分块，提交完整结果PR不自动合并、不覆盖另两台、不上传赛事平台。返回实际PR链接和有效/缺失数，而不是声称命令写好就已运行。
