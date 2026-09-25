# 本轮最终执行与交付状态

这是 COMPARISON_REPORT.md 之后完成的控制链与Windows验证，算法源码没有因后续报告更新而改动。

## 直接比较

同day01实际起点、同Linux主机、40秒搜索帽/256次评估，Fusion、Trident、Unified共15个臂；15份选中响应和9份Q3同方案对照通过时间线核验。Q3对照独立计时，不把这组对比伪称40秒包含对照。逐例结果见matched_comparison.csv和unified_comparison.csv。

新Unified在5个配置中相对Fusion两胜两平一负，相对Trident一胜四平。五个配置旧周期/新周期的几何均值分别1.010305881与1.011980595；这是一次小样本观察，不是百图均值或统计显著性证明。086二核仍比Fusion慢82周期，完整保留。

## 完整冷启动控制链

Linux CPython3.13.5，一个worker，每配置60秒总帽，Q3配对在帽内：

|图/配置|结果周期|同方案无L2|含必要配对的本次墙钟秒|
|---|---:|---:|---:|
|044 Q1 n2|63171|不适用|24.244|
|044 Q3 n2|45377|50849|26.836|
|059 Q3 n5|150455|150455|48.265|

三配置均完整。这里冷启动first_valid字段只是本次首份构造解，不是题目规定的原始单核T1。不能用它计算正式多核加速比。见evidence/local_pipeline.json。

## 已实际完成Windows验证

GitHub Actions运行36173491379的actual_windows_graphs，Windows Server 2025 x64、CPython3.12.5、一个worker，每配置45秒总帽。

|图/配置|结果周期|本次墙钟秒|原图/同方案核验|
|---|---:|---:|---|
|044 Q1 n2|63171|39.299|通过|
|044 Q3 n2|45377|35.738|通过；同方案无L2=50849|

两个配置成功完成，没有在本轮出现PermissionError。下载实际响应后又复核了原操作/依赖/Pipe时间线，以及Q3配对方案对象一致性；不是只看CI绿色状态。Linux与Windows这些选中周期一致，但两环境预算和机器不同，不能拿墙钟做算法加速对比。

Windows原始制品：运行36173491379，artifact10880628491，orion-unified-real-windows-results。源文件制品artifact10880963897。evidence/windows_real.json保存摘要；原响应见制品和本会话原始证据包。这次是单worker少量真实图，并非对用户三台Windows电脑、同步盘、杀毒软件和更高并发的全覆盖证明。旧#39失败究竟由哪个句柄导致，原证据仍不足以唯一归因。

## 仓库整理完成

当前新入口：ORION_START_HERE.md → research_a_orion_unified/PLAN.md → HOST_0/1/2.md。

两份旧计划、旧README/主机指令原文共11个文件，已归档到history/orion_plans/fusion_smf23与trident_v13。旧位置改为历史指引；旧Python源码、旧team_results、其他研究目录、原题和官方评估器均保留原路径。现有实验只在自己的旧工作区恢复，不在运行中切换新版本。

本PR源码安装阶段的一次性压缩传输片段和工作流已经移除；最终是可读Python/PowerShell/Markdown源文件，不要求用户运行解码器或重做源码安装。保留的vendor是有来源的依赖快照，避免之后另一研究线改文件时悄悄改变本轮算法。

## 下一步

用一份统一方案完成三片34/33/33图，不再开Fusion、Trident、Unified三份百图矩阵。已有强方案进入共同池并在目标q/n重新评估，最终不覆盖已验证更好解。只对组合退化或仍有明显差距的配置做少量定向比较，先三选二再必要三选一，额外成本单列。正式1400主配置与500配对尚未由本轮新算法完成；缺失项目不填成功。
