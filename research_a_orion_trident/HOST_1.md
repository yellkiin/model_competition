# 主机1提示词：ORION Trident

你负责`yellkiin/model_competition`的Trident主机1。先读取本目录`LOCAL_AGENT_PROMPT.md`并完整执行其中共同约定。本机专属参数是 **ShardIndex=1**，33图、462主配置、165个Q3同方案配对。

代码已在 **PR #38**：https://github.com/yellkiin/model_competition/pull/38
分支：`integration/orion-trident-publish-20260925`。与另外两台固定同一提交；只写`research_a_orion_trident/`，不修改并行Fusion或三线源目录、原图/config/官方评估器。

本机图号：
`003 006 009 010 012 019 027 038 040 041 042 043 044 049 051 055 057 059 061 070 071 072 073 074 075 081 085 087 088 092 095 097 098`

## 获取与启动

在已有已授权仓库中，建立不存在的新worktree路径，保护正在执行的其他实验：

```powershell
git fetch --filter=blob:none --no-tags origin integration/orion-trident-publish-20260925
git worktree add --no-checkout --detach D:\orion_trident_host1 FETCH_HEAD
git -C D:\orion_trident_host1 sparse-checkout set research_a_orion_trident
git -C D:\orion_trident_host1 checkout --detach
Set-Location D:\orion_trident_host1
git rev-parse HEAD
& .\research_a_orion_trident\run_windows.ps1 -ShardIndex 1 -FetchInputs -Seconds 600 -Hours 12
```

优先D:\python\python.exe、64位Python3.12.x、CPU-only。首次`-FetchInputs`分批取本片原图、原评估器/config、正式方案、三线研究、DOCX/PDF，准备阶段独立计时；以后去掉开关复用。只检查启动项，直接真图，不加冒烟/单测/哈希/全仓审计。两个本机新配置通过后自动继续本片并复用，不重复整合小样本。

每配置600秒包含搜索和Q3同一plan无L2配对；每30秒记录真实最好解与阶段，早停持有、不倒填。自动workers按实际负载留25%CPU/RAM。保留实际好种子，官方更优才更新。明显差距才用原配置剩余预算做SM/SF/MF，必要S/M/F；同机同起点，诊断单列。

输入：`research_a_orion_trident/runs/assets_shard_1/`
求解：`research_a_orion_trident/runs/round01/shard_1/`
发布：`research_a_orion_trident/team_results/trident_round01/shard_1/`

## 结束或截止后发布

```powershell
& .\research_a_orion_trident\publish_results.ps1 -RunRoot .\research_a_orion_trident\runs\round01\shard_1 -ShardIndex 1 -Round trident_round01
```

保留全部主表/配对、30秒曲线、候选成本、计划/官方响应和源码快照。结果脚本新建本片分支/PR，大原始包40MiB分块进本仓库Release并读回确认。只发布1号片，不重开代码PR，不自动合并，不重复三台100图。所有失败和未启动键照实保留，批次时钟不重置。
