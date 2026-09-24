# 本地 Agent：补齐本轮尚未完成的真实图实验门

你在 yellkiin/model_competition 的 orion/track-anytime 分支工作。只写 research_a_orion_track_anytime/。当前实现尚未完成真实图评估，不要把 PR 或 REPORT 的发布表复核称作性能通过；不要直接启动正式百图。

先读本目录 README、METHOD、REPORT 和已合并的 research_a_orion_review_3pc/COMMON.md。实际读取题目/A题 的原 DOCX，再核对原附件 config 与未修改的官方评估器。不要修改原图、config、公共 solver/campaign 或其他研究线。

先只检查启动必需项。Windows 优先 D:\python\python.exe、Python 3.12.x、CPU-only；不适配的机器使用已有合适解释器或独立环境，不能中断正在运行的作业。不运行单元测试、冒烟或全仓检查。核心运行器不要求第三方库；已有 psutil 可改善资源采样，画曲线时才需要 matplotlib。

输入修复 PR25 已合并。先读 tools/A_DATA_ACCESS.md，使用普通 JSON 或按工具说明自动取得完整压缩传输分片；不把截断文本或手工改写内容保存为官方图。重新确认 day01/latest.json 与最新分支/PR 的正式发布位置。解包两片 FINAL 原始包，并用上游 transfer 工具完成 Windows 路径迁移；阶段快照和 pilot 不充当正式数据。对选定七图运行 review_records，从五张 CSV 回查原 progress、summary、方案、官方响应。发现差异先保留冲突，不能把不一致的种子放入对照。

第一步使用 024、083、086、001、059，并以044、084为对照，二核/五核、三问。先续优化：通过 review_records 生成的 seed_index 保留原种子成本，本机重新评估相同种子；然后对 old、budget、combined 用相同追加预算运行。本轮默认一次连续轨迹最多300秒，只有真实大图需要时单独600秒。30/60/120/300的值来自真实历史，不能从最终值补齐早期。

首先在单个外层 worker 的同机条件下取得可解释对照。外层 workers 与 NPU 核数完全分开。后续提高 MaxWorkers 时记录 RAM/CPU/峰值及并发波次；不得把不同并发度、不同机器的墙钟直接合并成公平加速比。

对第三问原响应运行 diagnose，阅读原 COPY 发射/完成、cache insert/eviction 和 frozen slack。重点核查：024高字节命中为何不缩短终点；086二核与五核为何不同；044正收益发生在哪些读；083五核是否被错误称作无收益；084零命中加速来自哪些非缓存调度变化。零 frozen slack 不是缓存因果收益保证，整体缓存节省用同一plan的Q2/Q3重新验证。

旧新方法必须各自独立运行。budget改变路径，不是对旧最终轨迹重排计时。完成续优化机制观察后，另建 run_id 做 cold 对照，保留首次有效解、每次改善、所有失败和超时、候选生成/原调用/I/O与总耗时。旧源码没有可分离的所有时间字段时留空，不能推算成实测值。

同方案无L2对照必须使用本次选中的Q3 plan，不能使用独立Q2最优结果。运行截止时未完成对照的作业保持 pair_status 不完整，不宣布通过。耗时预算受总截止限制；全局可信界、小队列估时准入、停滞和有限邻域耗尽均可提前停止，不空转。

Windows入口 run_small.ps1；参数包括 Cases、Mode、Seconds、WallSeconds、SeedIndex、Workers、MaxWorkers、Shards、ShardIndex、RunId。先执行本轮小批次，不是“已经通过之后”的扩展命令。

三机需要一起跑本轮时，同一份七图清单，Shards=3，三机 ShardIndex 分别0/1/2；每张图的所有问题、核数、版本留在同机。按排序后清单，分片为：0号001/059/086，1号024/083，2号044/084。不要三台各自跑完整100图。每机必须分别完成该图的同机旧新对照。

实测后写逐图报告：收益、退化、相同预算下首次可行时间和分阶段成本；对 budget 和 combined 的差异做有限消融解释，不能仅归因于“多花了时间”。没有收益时提出针对原因的下一次修改，不扩大参数矩阵。只有小样本合法、同机同预算结果与早期曲线可接受，且第三问成对对照齐全后，再由队伍确认扩展至百图。正式三问一至五核曲线及原单核基准约定不变。

所有结果写本目录 results/<run_id>/。保留当前未完成证据，不覆盖既有运行。提交本分支 PR，不自动合并，也不实现三线最终汇总代码。
