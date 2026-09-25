# ORION Fusion SMF：600秒内的三线组合调度

当前算法版本 `fusion-smf-2.3`。结构 S、内存驻留 M、真实 FIFO 事件与候选分配 F 已全部接入同一求解过程。不是三套程序各跑完后拼均值，也不重复把 FIFO 研究中的 private-island 微波次算作 F 的贡献：该原语已由 M 提供。

本轮增量与新实测见 [CONSOLIDATION_2_3.md](CONSOLIDATION_2_3.md)。保留已合并PR #37三线主算法，主要减少未参与排序的代理计算并更新实际可用强种子。

## 方法

S 负责关键路径、分组/分核、较少核好解在目标核数的重新评估；M 负责 Task 边界、Tensor 集合交易、容量受控微波次；F 根据真实读发射/完成/驱逐事件提出重排，并按本实例实际收益/成本分配候选机会。

先让 S/M/原有局部候选完成短时结构与驻留下降，再引入 F 联合改进。共享已验证 incumbent；其他来源改变方案后，耗尽的来源可以在新方案上重新产生候选。停滞同时检查真实时间与各来源尝试条件，避免多了一个来源就更早停止。只用可信下界剪枝；近似内存、FIFO 和代价分数不作真实性能。

最新 FIFO 资料中 repair-v6 与 peer-v4 的暖启动结果一致，冷启动有一胜一负，因此未整体覆盖现有求解器。接入 peer-v4 的三类事件重排与有界长窗口，保留候选代表/来源公平性；不接入约2%的激进早停，默认剩余相对改善证书阈值为0.25%。

## 单例时间

一个配置=(一张图，一个小问，一个核数) 的本次进程从启动至保存结果最多600秒：包含读图、历史方案重新评估、构造、搜索、原评估和结果保存，不是免费回放后再搜索600秒。600是用户本轮工程上限；本次提取的原DOCX文字为“合理时间”，未把未出现的数字引文写成已核验题文。

父进程到点结束进程树并记录清理时间；操作系统清理可能略超过帽，不把这段算成额外有效搜索。队列等待另算批次时间。截止前尚无有效解就记录失败。

本轮从已有实际方案续优化。历史取得成本已知时单列，未知时留空，不能把历史池说成600秒冷启动生成。冷启动对照须去掉seed/alternatives，在独立输出根运行，不混入续优化均值。

## Windows与三机

在完整仓库checkout中运行，无新增pip依赖。参考解释器 `D:\python\python.exe`，Python3.12 x64/CPU-only；其他机器用 `-Python` 指定已有兼容解释器。原题/数据为 `题目/A题/通用神经网络处理器下的多核调度问题  附件/`，文献为 `调研/A题_文献库/`。原图/config/Step1–3及官方评估器不变。

```powershell
# 三台分别用0、1、2，其他算法参数相同
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a_orion_fusion\run_windows.ps1 `
  -ShardIndex 0 -Out 'research_a_orion_fusion\runs\round03_smf23_shard_0'
```

默认600秒、2048次评估上限、SMF、自动workers、12小时整批截止。600秒是上限而非必须耗尽；候选耗尽、充分停滞或证书接近可早停。同根恢复不重新获得12小时。

所有主机使用同一份day01百图参考表和selected_plans.zip生成34/33/33分片；按旧实际成本+规模LPT平衡。一图全部小问/核数在同一台。已有S/M/F真实好方案自动从仓库选中结果目录发现；本次另提供19份实际好方案的可读游程记录，Windows入口解包后直接作为候选种子，仍在目标场景原评估。其他完整实际方案包或本地目录通过 `-ExtraPlans '目录1','目录2'` 补充。只有数字没有plan时只记录目标差距，不虚构seed。

不运行哈希、冒烟、单元测试或全仓审计前置。启动必需项后直接跑本片两个尚未做过的真实SMF配置，通过即继续全片，先行结果复用。官方校验与最终时间线复核保留。缺数据只补本片A图。

自动worker逐渐增加；逻辑CPU最多约75%，整机RAM保留25%为准入目标，同时考虑其他软件与已观察作业峰值。不是瞬时绝对配额，不凑内存负载、不杀他人进程。`resources.jsonl` 保存实际利用率和决定。

## 执行顺序

先真实新组合小样本，再本片全部主配置；每个选定Q3方案用原Q2作同方案无L2对照。仅对raw候选退化或落后于已发布强目标的配置做SM/SF/MF，仍不清楚才S/M/F；每片默认最多6个，余项留队列。最后选缓存低/高收益的两个小图作九格参数研究，默认格复用主结果，另两角点作60秒适配，不计正式均值。

整批截止预留：主阶段80%、配对到90%、定向诊断到95%、最后余量做缓存研究与收集。时间不足保留缺失，不删配置。诊断/参数实验成本单列，不伪称主结果免费组成。

## 必需结果与论文数据

1400主记录：100原始单核基准+1200个三问二至五核方案+100个Q3单核方案。另500个Q3同方案无L2对照。Q1/2单核曲线从原始基准派生，明示来源，不增造独立主键。

`report/paper_data/`包含三问附录、1–5核均值/中位数/P10/P90、逐例搬运/Spill/命中、同方案缓存比、每30秒真实最好解、来源/阶段、每次改善、候选成本、Pipe利用率及图结构。`optimization_phase_seconds.csv`区分结构驻留阶段和联合阶段。`stopped_hold`是早停后持有，不表示继续搜索。早期无解留空，不倒填最终值。

可选画图用matplotlib，求解不依赖它：
```powershell
& 'D:\python\python.exe' -m research_a_orion_fusion.plot_paper `
  --data 'research_a_orion_fusion\runs\round03_smf23_shard_0\report\paper_data' `
  --out 'research_a_orion_fusion\runs\round03_smf23_shard_0\report\figures'
```

完成/截止后按用户要求，用本机已有GitHub授权实际发布：
```powershell
.\research_a_orion_fusion\publish_results.ps1 `
  -RunRoot 'research_a_orion_fusion\runs\round03_smf23_shard_0' -ShardIndex 0
```

只写 `research_a_orion_fusion/team_results/round03_smf23/shard_N/`，新建独立结果PR，不自动合并。原始档案按40MiB分块，附顺序清单；图/官方代码/文献不重复上传，selected_plans.zip单独提供。

三片到齐后：
```powershell
& 'D:\python\python.exe' -m research_a_orion_fusion.unpack_results '<片0发布目录>' --out '<片0新目录>'
# 同样恢复另两片，然后
& 'D:\python\python.exe' -m research_a_orion_fusion.campaign collect '<片0新目录>\run' '<片1新目录>\run' '<片2新目录>\run' `
  --out 'research_a_orion_fusion\team_results\round03_smf23\combined' --require-complete
```

## 无收益时

先看progress：某来源没首评查选择公平性；长期生成但少评估查候选规模和缓存；高Spill查有限微波次；高命中低收益查真正控制尾部的读；增核退化将少核方案补空核后目标重评。通过S/M/F开关定向消融，同起点/本机/预算，不能用异机秒数作同条件结论。

保留seed不等于新模块有效，因此额外记录raw候选最好值。改变算法或预算另开根，不事后挑消融结果覆盖固定策略表。未知历史成本不填零。当前新100图未跑；真实局部结果、负结果和修正见REVIEW.md。
