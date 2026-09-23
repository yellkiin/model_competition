# D 题：基础调研与写作方向

核查日期：2026-09-23。本报告已读题面并检查附件参数表和结果模板；尚未计算最优航线或进行通信覆盖仿真。下述模型和实验是实施建议，不是已经获得的数值解。

## 1. 题目拆解与真实数据现状

本题必须贯通“地形决定航段高度与能耗—调度决定运输位置和时间—通信决定中继资源—分区检验独立执行资源”。只做平面车辆路径或静态通信圆覆盖无法满足题意。

|核查对象|本地情况与关键数值|
|---|---|
|场景|O01 调度中心＋15 个服务区，节点表及 DEM 均已存在|
|货箱|逐箱表 80 箱，总质量 758 kg、总体积 2.011 m³；30 箱首批、16 箱医疗|
|汇总一致性|按服务区及物资类型聚合后与需求表完全匹配|
|运输机|A/B/C 共 4/2/2 架；额定载荷 25/30/80 kg；容积 0.060/0.073/0.250 m³|
|共享电池|A/B/C 各 6/4/4 组，充满等效时间 1800/2400/3000 s；库存已包含初装电池|
|中继|2 架、6 个能源组件；组件 3.2 kWh；最高离地悬停 300 m|
|通信|2400 MHz；系统损耗 3 dB；遮挡附加损耗 10 dB；接收灵敏度 −98 dBm、裕量 8 dB|
|地理文件|30 m GeoTIFF、MAT，以及道路、水系、水体、村镇点位和说明 PDF|
|尚待核实|DEM 坐标/高程基准、NoData、边界、节点高程一致性；全部航段净空与可行性|

题面服务区写作 Si，附件实际编号为 S001–S015，所有输出应保留附件原编号。Copernicus 官方说明其产品具有 DSM 属性；报告需区分“题目将栅格作为地面高程使用”的计算口径与真实地形精度，不额外把建筑高度重复叠加。[D09](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM)

## 2. 主写作方向及小问—模型—输出

建议题名：**基于地形可行航段与通信服务时窗的无人机运输—中继联合调度及独立分区资源核算**。主要贡献放在统一物理引擎、可行性可复核的分解算法和资源共享价值，算法名称不宜堆叠。

|问题|基线|主模型与算法|输出|
|---|---|---|---|
|Q1 单点往返|按质量/体积降序贪心装箱|单点安全载荷一维搜索＋按箱集合划分 MILP|45 个机型—服务区载荷上限；逐架次组批；安全余量曲线|
|Q2 运输调度|医疗/首批优先的最早可行插入|候选路线集合划分＋资源约束调度；ALNS 改进|路线、实体机、电池、启返时刻、逐箱送达、SOC|
|Q3 联合通信|固定候选中继点、运输时刻调整|地形链路覆盖集合＋运输/中继分解迭代与冲突修复|悬停点/海拔/时段、能源组件、全程链路证明|
|Q4 固定任务分区|共架次节点缩并后均衡分组|2/3 组枚举或整数规划＋固定时序资源重编号|分组、各类最少资源、冗余/缺口/均衡指标|

无人机路由研究支持多架次复用和能量约束进入同一优化模型 [D01](https://arxiv.org/abs/1608.02305)；灾后运输与信息保障的集合覆盖/分解方法可参考 [D07](https://www.sciencedirect.com/science/article/abs/pii/S0957417423019759)。两者具体场景均与赛题不同，不能照搬参数和最优性结论。

## 3. 公共物理引擎：先固定口径

经纬度须转换到适用的米制投影或一致的局部坐标，不能直接以度计算距离。对 16 个节点的有向航段遍历所有相交 DEM 像元，最高像元高程加 50 m 得巡航海拔；节点间取水平直线，不擅自用 A* 绕山改变题目航段规则。起终点作业海拔分别按 O01 地面高度、服务区地面＋30 m 确定，多点投送后重新爬升。

```math
zcruise_ij = max_{cell intersecting segment ij} zcell + 50,
t_gij = h⁺_ij/v↑_g + d_ij/vc_g + h⁻_ij/v↓_g,
L_g(q) = L0_g − (L0_g−LF_g)(q/Q_g)^(3/2),
Σ_(ij in sortie p) E_gij(q_pij) ≤ (1−ρ_g) Euse_g .
```

沿途交付后 q 递减，返程为空载；不能把全部航段都用起飞载荷或平均载荷。题面原文只显式给出 E=Ehor+Eup 的分解，实施时应将以下写作**与航程定义一致的计算约定**并核对附件说明：Ehor=Euse·d/L(q)，Eup=(m0+q)g h⁺/(η↑·3.6×10⁶)，能量单位 kWh。运输交接时间计入调度，若没有给定运输悬停功率，不应暗中增加或忽略一项后仍声称完全由题面唯一确定。能耗模型的取舍会影响路线可行性，应明确引用与赛题口径的差异。[D02](https://www.sciencedirect.com/science/article/pii/S1361920920308531)

Q1 对每组 (g,i) 求最大 q，使满载去程、卸载后空返满足安全余量；检查 q=0 都不可行的情况，再用二分求根并截断到额定载荷。载荷上限只反映质量/能量能力，装箱仍需独立体积约束。Q1 架次目标可按“最少架次→其下最小能耗→其下最短累计时间”词典序优化，并提供改变优先级的对照，不把不同单位直接相加。

## 4. Q2：路线和可周转能源的同步调度

80 箱虽少，联合排列、机型、实体和电池分配仍易组合爆炸。先生成满足质量、体积、能量的单点及少量多点候选架次，每列记录箱集合、访问序、航段载荷、相对交付时间和返航 SOC。主问题约束每箱恰好被一个选中架次覆盖；调度层分配实体机、电池与起始时刻；检测失败后补充路线或时间冲突约束。

所有医疗期望时限与首批截止时间按硬约束处理；其他箱的期望时间用加权迟到度 Σ w_b max(0,T_b−d_b) 度量。目标建议在硬可行前提下依次优化迟到度、全部返回时刻 Cmax，再比较总能耗与架次，或固定可接受迟到上界求能耗 Pareto 曲线。[D03](https://pubsonline.informs.org/doi/fpi/10.1287/opre.35.2.254)、[D15](https://doi.org/10.1109/4235.996017)

实体机的准备、装载、飞行、交接与周转构成占用区间；电池占用区间还延伸到回仓后充满。按题面两阶段充电函数计算，每架次出发时必须满电，不能把 SOC 大于安全线当作可以立即复用。同机型电池可跨实体流转，不同机型不可混用；不同电池允许并行充电，不凭空添加充电桩数量限制。区间调度与 NoOverlap 可采用 [D10](https://developers.google.com/optimization/scheduling/job_shop) 的建模方式，但能量和兼容性须自行补齐。

ALNS 可用随机删箱、迟到箱聚集删除、同服务区删除、昂贵航段删除，再用后悔值插入与调度修复。[D04](https://pubsonline.informs.org/doi/10.1287/trsc.1050.0135) 每个候选解都调用同一个独立检查器，记录随机种子、时间预算及最优可行值；只有获得下界和 gap 才讨论接近最优，不能将启发式最好解写成全局最优。

## 5. Q3：通信覆盖必须进入时间轴

按三维端点和 DEM 实施遮挡检测，无遮挡不一定可通信，遮挡也不一定必然中断：题面只增加 10 dB，再与链路预算比较。不能用城市概率视距模型替代真实 DEM 规则。

```math
Lpath_ab(t) = 32.45 + 20 log10(f_MHz) + 20 log10(D_km(t)) + Lobs*b_ab(t),
Lmax_a↔b = min(Lmax_a→b, Lmax_b→a),
connected(t) = A_TG(t) OR [A_TR(t) AND A_RG(t) AND relay_ready(t)] .
```

频率和距离单位依据 [D08](https://www.itu.int/rec/R-REC-P.525-5-202411-I/en)。回传与接入接口功率/增益不同，双向门限须取弱方向。中继到达后还要完成建链，运输降到作业高度及交接阶段都必须有通信，中继回仓时间计入联合 Cmax。

候选中继点在 DEM 内由地形高点、服务区邻域和受遮挡航段附近生成，海拔＝当地高程＋候选离地高度，并满足 ≤300 m。对每个候选点/高度预计算回传可用性和运输轨迹覆盖时段；先保留少量非支配位置，再做细网格局部改进。运输调度给出通信需求，中继层用带能源预算的时段覆盖安排保障；若失败，反馈调整出发时刻、换运输机型或多点访问序，不改变固定航段定义。[D05](https://arxiv.org/abs/1602.03602)、[D06](https://arxiv.org/abs/1804.02238)

“连续通信”不能仅在每 60 秒采一个点就宣布成立。至少对爬升/巡航/下降/交接边界、栅格穿越和覆盖切换加密检测，链路裕量接近零时自适应细分；尽可能对分段线性运动与栅格模型构造保守区间界。报告最小链路裕量、最大检测间隔及加密一致性；有限抽样无法证明严格连续时，应明确数值验证层级。射线追踪文献 [D14](https://arxiv.org/abs/2303.11103)只能用于扩展讨论，本题主结果不更换传播规则。

## 6. Q4：冻结 Q3 后核算独立执行代价

先把 Q3 同一运输架次访问的服务区建立超边并取连通分量；这些分量不能再拆开。若只有少于 K 个可分单元，K 组方案在当前冻结运输计划下不可行，应报告原因，不能重新安排访问顺序来“凑够”分组。

共同中继保障还需明确解释：若同一个固定中继架次同时保障两组，跨组共享实体与题意冲突。严格不改变中继任务的口径下，应增加对应同组约束并核查是否仍可划为 2/3 组；若讨论为每组复制相同悬停位置与时段的独立保障，则新增架次和能源必须明确列出，并作为另一解释情景，不能混入“原安排完全不变”的基准结果。

给定分区后，对固定时间表重编号资源：同机型运输任务按含周转的区间着色；电池按任务开始至充满的占用区间计数；中继实体和能源组件同理。全部任务从同一仓出入且兼容性相同时，最大并发是该区间模型的资源需求；若保留更复杂准备先后关系，则用小规模整数模型核验。不得按飞行时段算电池数，也不能简单把原 U01 等编号在每组出现次数相加。

比较 R_total=Σ_k R_k、相对联合共享需求的增量、各类 max(0,R_total−库存)、组间任务时间/箱质量均衡。工作量指标只反映分组均衡，不替代资源缺口；2 组和 3 组应在相同冻结计划上比较。

## 7. 验证、图表、风险与执行安排

建立独立可行性检查器逐项检查 80 箱唯一交付、质量/体积、逐航段能量、返航 SOC、硬时限、所有实体与能源不重叠、充满再用、DEM 边界及通信。小规模 3–5 服务区实例用 MILP/穷举核对主启发式；消融比较单点/多点、不可换电/共享电池、无通信/有通信、固定中继/联合优化，最后两组差异衡量保障代价，不能将无通信解当作实际可行救灾方案。

敏感性优先分析安全余量 15%/20%/25%/30%、服务时间、额外一架中继或一组电池的边际收益；扰动属于附加情景，正式答案保持附件参数。地形精度、链路裕量和时间离散粒度也应测。不要把背景中的现实灾情叙述直接作为已核实事实，主计算是题设标准场景。

结果模板含 Q1_单点组批、Q2_运输架次、Q2_逐箱交付、Q3_中继架次、Q3_通信保障、Q4_分区配置。Q3 的运输时刻通常不同于 Q2，需另附 Q3 运输与逐箱交付表，并注明表间引用关系，不能让 Q3 中继表隐式引用已过期的 Q2 调度。

论文顺序：数据与规则→统一航段/链路引擎→单点能力→多点调度→运输中继联合优化→冻结分区配置→敏感性。必备图表：地形及节点、典型航段高程剖面、安全载荷热力图、路线图、两类无人机甘特图、电池 SOC 与充电占用、全程通信状态、2/3 分区资源缺口对比。

0–12 小时锁定单位和检查器、完成 Q1；12–30 小时建立 Q2 可行解；30–48 小时完成通信检测与中继联合修复；48–60 小时冻结 Q3 并完成 Q4；60–72 小时做消融、模板和重运行。若联合模型求解过慢，保留可行解并缩减候选路线/中继点，同时公开搜索范围；“可复现且全约束可行”是优先保障的写作基础。

## 8. 经核查文献

D01–D10 为核心，D11–D15 为补充，含 2022–2024 年论文/综述五篇及官方资料。预印本与正式论文明确区分；全文网页可访问不等于阅读全文。机器可读记录见 [D题_文献.json](./D题_文献.json)。

- **D01** Kevin Dorling; Jordan Heinrichs; Geoffrey G. Messier; Sebastian Magierowski (2017). [Vehicle Routing Problems for Drone Delivery](https://arxiv.org/abs/1608.02305). *IEEE Transactions on Systems, Man, and Cybernetics: Systems 47(1):70–85*. DOI: 10.1109/TSMC.2016.2582745。用途：核心；问题1–2：多架次复用和载荷相关能耗的无人机路由；本文能耗公式不能替代赛题统一规则。核查：作者预印本摘要页及IEEE检索页（2016在线，2017卷期）。

- **D02** Juan Zhang; James F. Campbell; Donald C. Sweeney; Andrea C. Hupman (2021). [Energy consumption models for delivery drones: A comparison and assessment](https://www.sciencedirect.com/science/article/pii/S1361920920308531). *Transportation Research Part D 90:102668*. DOI: 10.1016/j.trd.2020.102668。用途：核心；问题1–3：比较不同能耗建模口径，强调载荷、爬升和设备参数一致性。核查：出版社摘要/分节预览及作者机构书目页。

- **D03** Marius M. Solomon (1987). [Algorithms for the Vehicle Routing and Scheduling Problems with Time Window Constraints](https://pubsonline.informs.org/doi/fpi/10.1287/opre.35.2.254). *Operations Research 35(2):254–265*. DOI: 10.1287/opre.35.2.254。用途：核心；问题2：时间窗插入启发式及可行起始解。核查：出版社摘要页。

- **D04** Stefan Ropke; David Pisinger (2006). [An Adaptive Large Neighborhood Search Heuristic for the Pickup and Delivery Problem with Time Windows](https://pubsonline.informs.org/doi/10.1287/trsc.1050.0135). *Transportation Science 40(4):455–472*. DOI: 10.1287/trsc.1050.0135。用途：核心；问题2–3：破坏/修复算子自适应选择；需增加电池与通信可行性修复。核查：出版社摘要页。

- **D05** Yong Zeng; Rui Zhang; Teng Joon Lim (2016). [Wireless Communications with Unmanned Aerial Vehicles: Opportunities and Challenges](https://arxiv.org/abs/1602.03602). *IEEE Communications Magazine 54(5):36–42*. DOI: 10.1109/MCOM.2016.7470933。用途：核心；问题3：空中中继网络结构和通信/机动耦合的背景。核查：作者预印本摘要页；期刊信息与题面参考文献对应。

- **D06** Yong Zeng; Jie Xu; Rui Zhang (2018). [Energy Minimization for Wireless Communication with Rotary-Wing UAV](https://arxiv.org/abs/1804.02238). *arXiv:1804.02238（作者预印本；后发表于 IEEE TWC，2019）*. 用途：核心；问题3：悬停位置、时长与推进/通信能耗联合优化思路；只借鉴分解策略。核查：作者预印本摘要页，未取得出版社正文。

- **D07** Tasnim Ibn Faiz; Chrysafis Vogiatzis; Md. Noor-E-Alam (2024). [Computational approaches for solving two-echelon vehicle and UAV routing problems for post-disaster humanitarian operations](https://www.sciencedirect.com/science/article/abs/pii/S0957417423019759). *Expert Systems with Applications 237 Part B:121473*. DOI: 10.1016/j.eswa.2023.121473。用途：核心；问题2–3：救灾运输与通信任务结合、集合覆盖/列生成；卡车两级体系不能直接照搬。核查：出版社摘要及引言/贡献预览。

- **D08** International Telecommunication Union (2024). [Recommendation ITU-R P.525-5: Calculation of free-space attenuation](https://www.itu.int/rec/R-REC-P.525-5-202411-I/en). *ITU-R Recommendation P.525-5 (11/2024)*. 用途：核心；问题3：自由空间损耗与MHz/km单位核对；遮挡附加损耗仍用赛题给定值。核查：ITU官方标准页面，已打开。

- **D09** Copernicus Data Space Ecosystem; European Space Agency (2019). [Copernicus DEM - Global and European Digital Elevation Model](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM). *Copernicus DEM 数据集与在线说明（首版2019，网页含后续发布记录）*. DOI: 10.5270/ESA-c5d3d65。用途：核心；全部问题：DEM分辨率、DSM性质、坐标与高程基准说明；实际计算使用附件数据。核查：官方数据页面，核查分辨率、基准、版本与DOI段落。

- **D10** Google OR-Tools (2024). [The Job Shop Problem](https://developers.google.com/optimization/scheduling/job_shop). *Google for Developers，页面最后更新2024-08-28*. 用途：核心；问题2–4：区间、先后和NoOverlap约束，表达实体无人机及能源资源占用。核查：官方教程页面及代码示例，已打开。

- **D11** Giulio Attenni; Viviana Arrigoni; Novella Bartolini; Gaia Maselli (2023). [Drone-Based Delivery Systems: A Survey on Route Planning](https://doi.org/10.1109/ACCESS.2023.3329195). *IEEE Access 11:123476–123504*. DOI: 10.1109/ACCESS.2023.3329195。用途：补充；问题1–2：单仓、多机、充换电约束的无人机配送方法分类。核查：IEEE论文页面及作者机构书目页；未通读全文。

- **D12** Carlos Muli; Sangyoung Park; Mingming Liu (2022). [A Comparative Study on Energy Consumption Models for Drones](https://arxiv.org/abs/2206.01609). *arXiv:2206.01609（作者预印本）*. 用途：补充；问题1–3：能耗模型外推风险和敏感性；本题无实飞数据不训练LSTM替换统一模型。核查：作者预印本摘要及机构论文首页。

- **D13** Naveed Khan; Ayaz Ahmad; Abdul Wakeel; Zeeshan Kaleem; Bushra Rashid; Waqas Khalid (2024). [Efficient UAVs Deployment and Resource Allocation in UAV-Relay Assisted Public Safety Networks for Video Transmission](https://arxiv.org/abs/2401.01636). *arXiv:2401.01636（作者预印本）*. 用途：补充；问题3：灾后中继位置和资源分配分块优化；视频效用目标与本题硬链路约束不同。核查：作者预印本摘要页。

- **D14** Jakob Hoydis; Fayçal Aït Aoudia; Sebastian Cammerer; Merlin Nimier-David; Nikolaus Binder; Guillermo Marcus; Alexander Keller (2023). [Sionna RT: Differentiable Ray Tracing for Radio Propagation Modeling](https://arxiv.org/abs/2303.11103). *arXiv:2303.11103（作者预印本）*. 用途：补充；问题3：几何传播和位置优化的扩展方向；竞赛主模型不引入射线多径替换题面FSPL规则。核查：作者预印本摘要页。

- **D15** Kalyanmoy Deb; Amrit Pratap; Sameer Agarwal; T. Meyarivan (2002). [A fast and elitist multiobjective genetic algorithm: NSGA-II](https://doi.org/10.1109/4235.996017). *IEEE Transactions on Evolutionary Computation 6(2):182–197*. DOI: 10.1109/4235.996017。用途：补充；问题1–4：非支配解与多指标比较；需设计可行编码，不能靠惩罚掩盖硬约束违反。核查：IEEE摘要页面及公开论文首页，未通读全文。
