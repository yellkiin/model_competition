你继续负责这台Windows电脑的ORION Anytime A题分片1（偶数50图）。这是对现有任务的补充，不要重新下载代码覆盖当前运行，不要重启或重复启动campaign。先读取最新用户消息、实际进程、team_status.json指向的日志和auto下已有结果；已经给出的环境、路径、预算不再询问。

我们要快速迭代：本轮改进阶段结束后，先整理一份可复核的阶段结果，同时让原进程继续缓存配对和最终验证。不要等全部配对结束才整理第一版。我们还需要解释哪些图好、哪些图差、为什么均值被拉低，不能只给平均数或“已完成”。

请读取统一交接规范：
https://github.com/yellkiin/model_competition/blob/codex/orion-team-run-20260924/research_a_orion_anytime/handoff_20260924/ITERATION_HANDOFF.md
本地若已有同文件也可直接读。私有仓库不可访问时，让用户把这个Markdown发来；继续既有计算，不重新部署环境。新规范仅新增结果交接文档，实验Python仍用本机已通过pilot的版本。

输出根保持 research_a_orion_anytime/runs/team_day01_shard1/auto。发布文件统一放 research_a_orion_anytime/team_results/day01/shard_1/，分成 refinement_complete/ 和 final/ 两个目录。另一台只把shard_1换成shard_0，除此之外文件名、列名、单位、统计口径、ZIP内部结构保持一致。不要为发布时间或运行速度另起本轮编号，不移动活动auto目录，不覆盖已发阶段结果。

改进阶段结束须确认本机refinement_policy.json中计划作业均有终态，且pairs下已出现request.json或final_index.json已生成；不能只看最后一个summary就提前复制，因为程序还要合并和更新阶段时间。先冻结coverage、coverage_retry、refinement和必要元数据到活动auto之外的新snapshot根，不纳入正在写的pairs。复制后的JSON输出路径按现有transfer.rewrite规则重定位，方案JSON不改。按coverage→有效retry→不退化有效refinement规则建立phase_index.json；不是跨运行择优。

按统一规范生成 PHASE_STATUS.json、REPORT.md、现有格式per_case.csv/report.json/SVG、improvements.csv、lower_tail.csv、budget_prefixes.csv，以及外层状态/时钟/日志副本。用现有reporting.collect只汇总已完成快照，verify=False、require_complete=False，明确本版最终统一验证尚未执行；原进程的官方合法性检查和最终验证必须照常保留。缓存配对本阶段标pending，formal_complete=false、shard_complete=false，700主记录有效不代表本片所有阶段完成。

改进快照包名固定 team_day01_shard1_refinement_complete.zip，使用现有transfer pack对完成路径重定位的冻结根打包，保持TRANSFER.json + run/结构。放在refinement_complete/，连同同目录可读报告交给用户转发协调机。不要直接对正在写入的活动auto做全量打包，不要创建仍依赖本机旧绝对路径的坏包。

报告要求：
- 三问1–5核逐图T1/Tk的算术平均、各组样本数，5核中位数/P10/最差图/低于1倍/缺失。Q1/Q2单核按原始基线定义为1，Q3单核取实测。保留全部50图，不只发好图。
- 按同图同核同问题比较coverage与最终选中方案，说明改善/持平/退化/缺失数量、Makespan、DDR、Spill以及实际求解成本。覆盖失败重试补齐和算法收益分开。
- 列出最低10%的5张图，以及它们对均值的影响；结合实际关键路径、负载、通信、复制、Spill、缓存命中和预算轨迹解释为什么好/差。事实、推断、待验证假设分开。时间帽不等于失败，也不等于改善；理论下界不等于保证能达到的成绩。
- 改进结束时同方案缓存对照尚未齐，不得以独立优化的Q2/Q3差值宣称Cache收益。final阶段再补同方案no-L2/with-L2比和命中率。
- 给最多3项有证据的下一轮建议，不现场改当前Python/参数。任何后续算法修改仍需两机同源、新输出根、同预算pilot，不能混入day01成绩。

原进程继续跑，完成或截止后在final/另发 team_day01_shard1_final.zip，包含实际final_index.json与最终报告/验证，补齐同方案对照。700主+250缓存全部有效且检查通过才能说本片完成；单片formal_complete=false按原报告保留，整队100图需要协调机合并两片1400主+500缓存。未完成明确缺失，phase_index不能改名冒充final_index。

每5分钟汇报北京时间、阶段、主记录有效数/700、完整图数/50、改进已完成/本机计划数、缓存有效数/250、历史失败与当前未解决失败、触帽有有效解/无有效解、当前作业及下一步。队友两机改进计划数量可能不同，以本机policy为准。

本补充默认要求本地准备和回传，不要求你自行push共用GitHub分支；由协调机统一发布片1对应目录。不要自动merge、force push或上传赛事平台。禁止smoke、哈希/指纹/checksum测试、pytest、unittest、全仓审计或benchmark；官方图/config/evaluator/合法性检查不改，不动其他实验。

继续原绝对截止：主计算2026-09-24T16:43:48.3137853+00:00（北京时间9月25日00:43:48），团队最终2026-09-24T17:43:48.3137853+00:00（北京时间01:43:48）。快迭代和先发报告都不重置窗口。现在先回复实际进度、采用的运行根和交接目录，然后继续执行。
