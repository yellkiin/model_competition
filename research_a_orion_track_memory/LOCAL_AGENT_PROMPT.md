# 下一轮本地 Agent：先原定差图，不扩大

在 `yellkiin/model_competition` 的 `orion/track-memory` 独立工作树继续。不要切换或修改其他运行中的工作树。先读本目录 README、METHOD、LITERATURE、主结果 REPORT，再读 PR24 COMMON。当前插件不是全面优于 Anytime 的替代品；不得在未通过下列定向门槛前扩大到 100 图或写三线汇总代码。

## 输入与正式种子

沿用 `D:\python\python.exe`，Python 3.12.x，CPU-only。只检查启动必需文件和解释器，不跑 smoke、pytest、unittest、哈希/指纹/checksum 或全仓审计。环境不符自行在独立目录适配，不安装 CUDA/Conda、不影响现有实验；实际解释器写入 manifest。

优先样本是 005、051、073、090（差图）与 092、083（改善机制），可另加 059、067 对照。原路径 `题目/A题/通用神经网络处理器下的多核调度问题  附件/data/` 有两个空格；只从已含 PR25 的 main 或明确修复分支取得图。需要分片时按 `tools/a_input_payloads/MANIFEST.json` 取齐完整文本，再运行官方 restore 工具，不手抄或改写载荷。不得提交原始图、config、文献。

先读取最新 `research_a_orion_anytime/team_results/day01/latest.json`，核对更新 PR/分支/发布索引。读 combined_final 的 per_case/lower_tail/improvements/budget_prefixes/cache_pairs；到 shard_0/final、shard_1/final 原包取得目标作业的 progress/summary/方案/原响应，不能用 pilot 或阶段快照替代正式选中方案。只在新目录解包。重定位旧 Windows 路径时使用显式配置字段，保留原 request 原文。

建立不进入算法的 `memory_day01_seeds.json`，每个 case/q/n 一项，格式如下（占位值必须由实际原记录填好）：

```json
[{"case":"case_051","q":1,"n":5,"job":"D:/orion_evidence/shard0/run/实际选中作业","config":"D:/model_competition/题目/A题/通用神经网络处理器下的多核调度问题  附件/data/config.txt","seed_solve_seconds":null,"cost_status":"待填完整成本后改为complete","provenance":"填写完整覆盖+重试+续优化成本来源"}]
```

`seed_solve_seconds` 必须是实际完整取得成本，不是最后一次成功评估时间，不把其他图的团队耗时均摊进来。上面的 null 只是未填占位，运行器会拒绝，不能替代逐作业核算。缺项必须失败并补齐，不免费回退为新种子。运行器会重新原评估并比较 Makespan 与搬运分解。

## 先暖启动的真实小批次

在仓库根目录的 PowerShell 会话执行（数组参数由当前 PowerShell 传入）：

```powershell
& .\research_a_orion_track_memory\run_windows.ps1 -Cases 5,51,73,90,92,83 -Questions 1,2,3 -Cores 2,5 -Seconds 300 -MaxEvaluations 24 -TotalSeconds 3600 -Workers auto -Modes warm_start -SeedIndex .\memory_day01_seeds.json -Out .\research_a_orion_track_memory\results\priority_warm_local
```

同一机保持相同 workers 政策；记录实际并发与内存。不要把一次单 worker 的秒数与混合并发旧成绩比较来宣称更快。难图可用独立、标记清楚的 600 秒实验，不混进同一条 300 秒轨迹。达到本轮总截止即停，保留有效 incumbent 和失败。`--resume` 仅补从未启动的作业，不重置已经中止或完成的轨迹。

暖启动通过后，再用**新输出目录**、同机同配置同求解预算运行 `-Modes cold_start`，不提供正式种子。保留完整旧臂，不能只与三次构造的粗方案比较。冷启动没有种子时，明确把 startup 成本算入总时间。

## 验证优先级与停止

051 Q1、005 Q2 的零 Spill 先看 Task 边界、切分和同步。073 Q2 检查原 Step2/3 导致的驻留/Spill，不能由同核合并推出无 Spill。092 Q1n5 必须找出 2,438,012→915,907 的实际候选名称、父方案、核心变化与边界 Tensor，而不是只复述 131,186,400→10,301,824 字节；原表 10.125+60.047 秒属于旧方法追加预算，不能算本插件收益。

每个成功候选同时报告 Makespan、partition/Spill/总 added bytes、可信界和同方案无 L2。对重复集合只计真实生产/消费者核对；缓存命中不得当物理 DDR 字节已确定。少搬运但慢、更多 Spill 却快，都保留。没有新可行解、候选非法、穷尽、超时及无收益尝试也必须保留。

读取同一轨迹已完成可用解的 30/60/120/300 秒前缀；早停后的值标明 stopped carry-forward。旧 1.3 主实验时钟有进程启动缺项，不能改写其历史事件；1.4 新实验记录 wall 启动偏移，并单列 Q3 配对成本。端到端曲线必须包括种子完整获取成本。

原定六图暖/冷对照未通过，停止扩大并报告机制局限。通过后才另行决定 100 图三问、一至五核及第三问同方案无 L2 正式曲线。未来三机分片用同一完整小清单加 `-Shards 3 -ShardIndex 0/1/2`，每个图的三问与核数留在同一机；绝不三台各自重复100图。

只提交本目录代码/文档/新 results，保留原 day01 和其他研究线。较大原响应打包并写明实际位置。更新独立 PR，不自动合并、不上传赛事平台。
