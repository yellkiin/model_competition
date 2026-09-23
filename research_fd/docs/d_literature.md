# D 理论与文献地图

检索与版本核验：2026-09-23。本轮是针对方法路线的深读，不宣称穷尽所有最新文献。下列均为作者或出版方原始来源；阅读深度逐条标明。相关工作给出思路，不提供本题可直接照抄的参数或成绩。

|编号|原始来源与阅读范围|对本题的作用|移植边界／代码|
|---|---|---|---|
|D01|Faiz, Vogiatzis, Noor-E-Alam. *Computational Approaches for Solving Two-Echelon Vehicle and UAV Routing Problems for Post-Disaster Humanitarian Operations*. 2020作者预印本；2024 ESWA 237:121473。读摘要与出版元数据。[arXiv](https://arxiv.org/abs/2001.06456)，[正式论文](https://www.sciencedirect.com/science/article/pii/S0957417423019759)|灾后信息需求与运输协同、分解和路线列|其车辆两级结构和信息发现任务，不等于本题全程通信。`d_routes.py` 为自行实现，非完整复现|
|D02|Wouda, Lan (2023). *ALNS: a Python implementation of the adaptive large neighbourhood search metaheuristic*. JOSS 8(81):5028。[出版页](https://joss.theoj.org/papers/10.21105/joss.05028)。读软件论文主页与软件方法说明|自适应破坏—修复结构和可替换接受规则|本代码直接实现三算子和 MILP 修复，不依赖该包，不宣称复现其例题性能|
|D03|Hooker (2007). *Planning and Scheduling by Logic-Based Benders Decomposition*. OR55(3):588–602。[出版页](https://pubsonline.informs.org/doi/10.1287/opre.1060.0371)。读摘要及书目信息|路线/机型分配与累计资源调度分离；成本、工期、迟到不同目标|本轮未实现完整 LBBD 割生成器。不要以启发式排不出解为依据加全局 no-good 割。CMU镜像元数据的1984不能取代正式2007年份|
|D04|Ropke, Pisinger (2006). *An Adaptive Large Neighborhood Search Heuristic for the Pickup and Delivery Problem with Time Windows*. Transportation Science40(4):455–472。[出版页](https://pubsonline.informs.org/doi/10.1287/trsc.1050.0135)。沿用上轮摘要核验|时间窗下破坏修复的原始背景|无人机箱组、共享电池与中继约束由本题重新建模，不使用其参数成绩|
|D05|SciPy官方 [milp](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html)、[linprog-highs](https://docs.scipy.org/doc/scipy/reference/optimize.linprog-highs.html)。实际阅读状态、time_limit、mip_gap、约束与marginals说明|MILP状态、最优界；LP对偶扩列|网页当前显示1.18，实际执行为1.17.0。status=1超时不同于status=2不可行；后者也只针对实际构造的有限模型|
|D06|Google OR-Tools [Job Shop官方教程](https://developers.google.com/optimization/scheduling/job_shop)。阅读区间、先后和资源建模代码|CP-SAT 可选区间承载不同路线选择、整秒开始时间与累计资源|标准job-shop教程不是无人机模型；本次提供`cpsat`但本容器未安装OR-Tools，结果为空而非预填成功|
|D07|Hu, Zhang, Wang等 (2025). *Radio Map-Enabled 3D Trajectory and Communication Optimization for Low-Altitude Air-Ground Cooperation*. [作者HTML v1](https://arxiv.org/html/2505.06944v1)。选读§II、§III-A/C，特别是离散路径损耗地图与位置搜索|传播地图、调度/位置分块、先建立有用位置再搜索|本文最大化地面车吞吐率、可优化发射功率及无人机轨迹；D题固定参数/航段不能直接放开。我们用DE细化悬停点，不是复现WS-PSO-CM；原文实验百分比不移植|
|D08|Pradhan, Rajawat, Kothari (2026). *Communication-Constrained Energy-Optimal Trajectory Generation for Quadrotor UAVs in Urban Environments*. [作者HTML v1](https://arxiv.org/html/2605.24865v1)。选读§III-D/E、§IV开头|通信约束与能量最优控制、信赖域、比较真实改进与线性预测改进|2026预印本；不能把驻点性质说成全局最优。原文连续动力学不同于题给航段，列为理论扩展而非已跑主模型；没有移植其完整控制器|
|D09|Elçi, Hooker. *Stochastic Planning and Scheduling with Logic-Based Benders Decomposition*. [2020作者预印本](https://arxiv.org/abs/2012.14074)。读摘要及元数据|两阶段随机分配与排程、组合补救问题|本轮仅做扰动重放，不是随机LBBD求解；应区分假设扰动和经验分布|
|D10|Rasterio官方[变换](https://rasterio.readthedocs.io/en/latest/topics/transforms.html)、[读栅格API](https://rasterio.readthedocs.io/en/latest/api/rasterio.io.html)。阅读坐标变换和采样语义|像元边界、原生CRS、坐标转换与最近像元取值|原栅格不重投影平滑，但米制直线映入地理坐标仍需折线近似；切勿只修改CRS标签|

## 研究路线之间的关系

集合划分表达“选哪些架次”；对偶扩列扩大候选集合；累计资源调度表达“何时、用哪些能源执行”；中继会话列表达“何时在何处保障”；ALNS负责跨这些组合的局部重组；ε-约束负责展示不同目标取舍。它们并非互斥算法排名。

最值得本地继续检验的方向是：将仅含箱覆盖的对偶代价扩为资源拥挤代价；保留同箱组不同服务访问序的非支配列；将通信失败反馈为对当前开始时窗的约束；用较小固定路线 MILP 做 ALNS 的精确修复而非总是重解大模型。REPORT_D 的窗口必要条件是本轮推导，不伪称已实现的论文定理。
