# 主机2：完整SMF研究与正式分片

在yellkiin/model_competition拉取完整PR #37，独立工作区运行，不覆盖其他实验。阅读research_a_orion_fusion/README.md、REVIEW.md、EXPERIMENT_PLAN.md，然后实际执行。

原题DOCX在题目/A题；图/config/官方评估器在同名“通用神经网络处理器下的多核调度问题  附件”；文献在调研/A题_文献库。S是结构/分核，M是驻留/Task边界，F是真实FIFO与候选机会分配，已经在同一共享最好解算法中组合。主要依据实际plan/响应，不把报告数字当可用方案。

取得day01完整100图参考表和selected_plans.zip，不能只有原某台50图。程序自动读取仓库已有好方案，并解包本PR的6份实际种子；本会话26方案包或本地更强结果用-ExtraPlans补入。所有种子目标场景重评，历史取得成本未知不填零。

每(图,小问,核数)本次最多600秒，包括回放、构造、评估及保存；每30秒记录已有最好解和来源/阶段。近界/充分停滞可提前停止，不空转。三台算法参数一致。

你是分片1。Windows优先D:\python\python.exe、Python3.12 x64、CPU-only，无求解pip依赖。不符合的机器自行配置独立解释器并传-Python，不影响正在运行环境。不要哈希/指纹、冒烟、pytest/unittest、全仓审计前置；启动必需检查后跑真实图，保留官方合法性检查。自动workers目标留25%CPU/RAM；workers不是NPU核数。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a_orion_fusion\run_windows.ps1 -ShardIndex 1 -Out 'research_a_orion_fusion\runs\round02_smf_shard_1'
```

先本片两个本轮未测过的组合配置，通过后自动跑本片全部图、三问和要求核数；先行结果复用，不三台各跑100图。之后同方案无L2、问题配置SM/SF/MF及必要S/M/F、缓存九格、论文数据。默认12小时绝对截止，续跑不重置；团队共同DeadlineUtc时三台传同一个值。

效果差先看真实attempts：候选生成贵就缩小/缓存；Spill查容量微波次；命中高而低收益查真正尾部依赖；增核退化将较少核好方案补空核后目标重评。保留已有好解但raw候选质量另报。改算法/预算另开根，不事后用消融最好值覆盖固定策略主表。

完成或到点后读shard_status、report、paper_data、mechanism_status，保留失败/缺失。已有GitHub授权下实际执行：
```powershell
.\research_a_orion_fusion\publish_results.ps1 -RunRoot 'research_a_orion_fusion\runs\round02_smf_shard_1' -ShardIndex 1
```

只写research_a_orion_fusion/team_results/round02_smf/shard_1/，结果分支results/orion-round02_smf-shard-1-<时间>。上传实际方案、响应、30秒轨迹、逐图表、阶段、论文数据和错误，40MiB分块。提交PR不自动合并，不覆盖另外两台。不以只给命令代替执行。
