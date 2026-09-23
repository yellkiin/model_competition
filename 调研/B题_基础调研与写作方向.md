# B题：氢燃料电池低温冷启动建模与控制策略研究

调研日期：2026-09-23。本文提出待实现、待验证的模型与写作路线，不提供虚构启动时间、最优功率或拟合精度。已读取题面正文，并以只读方式检查两份Excel附件；数学公式图片中的阈值仍应对照原Word逐项录入。

## 1. 材料核对与首先需要解决的口径

附件1只有“参数清单”工作表，61行×5列，含表头及60行参数。附件2的“-20℃”“-25℃”各186行×5列，含两行表头及184个观测点，时间0～36.6 s、间隔0.2 s，字段是时间、电流、电压、平均温度、电流密度。附件比正文每5秒一行的表格更细，应使用完整时间序列。

**重要数据矛盾：面积与电流密度。** 附件1“参数清单”!C2给活化面积25 cm²；附件2“-25℃”!B3=2 A、E3=0.006600660066 A/cm²，二者隐含面积303 cm²，全部184点均一致。“-20℃”对应比值也远非25 cm²，末点B186=92.5 A、E186=0.299 A/cm²，隐含约309.36 cm²。不能同时把两列当独立准确输入。建议校准主路线暂用附件给定电流密度列驱动面积归一化模型，明确这是工作假设，并以 $I/25$ 作为口径敏感性对照；待有正式解释再定稿，不改原表。若两种口径导致完全不同结论，应报告这一识别边界。

附件还有需要交代的适用差异：端部/中间浓差极化系数分别10/1，而题面强调气体均匀供应、只考虑端部热效应，需说明该经验系数如何进入模型及是否与热效应重复；不应将其额外塞入题面固定的扩散率指数。开路电压0.95 V不能强制当作附件实验t=0的0.799 V，因为此时已加载非零电流。若使用相变“系数”，必须确认源项方程及量纲，表中标“-”不意味着可直接作为s⁻¹速率。

36.6秒内两条温度曲线仍低于0℃，仅能直接验证早期冷启动过程，不能据此宣称已实验验证−30℃启动成功。题面工况3称40分钟预冷产生比20分钟“更明显”的非均匀场，应由热传导计算检验；随冷却时间延长，温差可能先增后减，最终趋于环境均温。

| 小问 | 建议模型与方法 | 主要输出 |
|---|---|---|
| 1：单电池 | 五层MEA一维有限体积、多相水守恒、冻结/融化、电压闭合；少参数校准 | 两温度下V、平均T、局部冰峰值；正文指定时刻的误差表 |
| 2：5片串联自启动 | 五个单片模型＋端板/片间热网络；恒流、线性、阶梯参数优化 | −10℃三策略结果；最低可行初温、失效单片及原因 |
| 3：辅助加热 | 双极板热源；常功率向量与持续时间优化 | 预热/协同最小辅助能耗、总时间、逐片能量、冰峰值 |
| 4：动态反馈 | 状态估计＋受约束MPC，规则控制作基线；先求预冷温度场 | 三初态动态/恒功率比较；10～100min预冷与成功域 |

## 2. 可闭合的物理模型与假设

从题面备注1出发，保留阳极GDL、阳极CL、膜、阴极CL、阴极GDL五层空间离散；催化层和膜使用较细网格。用有限体积保证界面通量守恒，时间推进采用隐式方法。先运行非冻结基准，再加入相变，避免一开始把所有耦合误差混在一起。Vetter的开放五层模型和AlphaPEM可提供实现组织参考，但前者稳态两相、后者的公开摘要不保证冻结模型，均不能直接冒充本题解答。[B13](https://arxiv.org/abs/1811.09811) [B14](https://arxiv.org/abs/2407.12373)

局部水按题目要求分为 $m_w=m_v+m_l+m_i$，膜吸附水应另说明如何与题面总水变量及含水量$\lambda$对应，避免把全部膜水视为可自由冻结水。给出质量守恒的相变源项，例如
```math
\partial_t m_i=R_f(T,m_l)-R_m(T,m_i),\quad
R_f=k_fm_l f_-(T),\quad R_m=k_mm_i f_+(T),
```
其中 $f_-,f_+$ 分别在冰点以下/以上激活。这个式子是**建议的简化动力学闭合**，不是题目指定定律；必须说明适用性、系数量纲、平滑过渡宽度与校准来源。冰点附近过冷成核可作改进项，不宜无数据拟合大量参数。冻结放热、融化吸热应以同一 $L_f\partial_t m_i$ 计入能量式，避免源项重复。[B01](https://www.sciencedirect.com/science/article/pii/S0360128517300175) [B12](https://www.sciencedirect.com/science/article/abs/pii/S0013468607008973)

严格区分控制体冰体积分数与孔隙冰饱和度：
```math
\epsilon_{\rm ice}=m_i/\rho_i,\quad s_i=\epsilon_{\rm ice}/\epsilon_0,\quad
\epsilon_g=\epsilon_0-m_l/\rho_l-m_i/\rho_i.
```
题面阈值针对$\epsilon_{\rm ice}$，不能直接替换成$s_i$。扩散系数保持题面规定的有效孔隙率1.5次关系；活性面积可采用 $a_{\rm eff}=a_0(1-s_i)^\beta$，附件冰覆盖指数3.5可作为已知值/有界敏感性参数，不能在未核对原定义时将指数施加在另一种冰分数上。检查 $m_\alpha\ge0$、$\epsilon_g\ge0$ 和各相总量，越界应触发失败/缩步，不能靠截断掩盖守恒误差。

单片热平衡耦合为
```math
C_k\dot T_k=A j(t)[E_{\rm th}-V_k]
+\sum_{\ell\in\mathcal N_k}G_{k\ell}(T_\ell-T_k)
-Q_{{\rm loss},k}+Aq_k(t)+Q_{{\rm phase},k}.
```
此式适合电堆控制降阶模型；问题1仍需保留空间温度场。5片电池与两端板分别建热节点，端板具有显式热容，按题面材料热阻连接。双极板、端板热容只能计入一次；内部单片边界不能重复施加对环境换热。电化学产热采用题面 $E_{\rm th}=1.48$ V，与活化/欧姆热分项不能重复叠加。[B05](https://doi.org/10.1016/j.jpowsour.2007.05.028)

安全阈值、成功温度和冰阈值统一读取题面式(7)～(9)及成功条件；文本提取未完整恢复这些公式，本文不猜数值。全程约束最低电压和最大局部冰，而非只在启动终点检查。给每次仿真定义成功、冰堵、低电压、电荷用尽、未收敛、超时六类状态。

## 3. 校准、优化与反馈的逐问路线

**问题1：把有限数据用于少量参数。** 固定几何、热物性与题面公式，只对确有必要且可识别的2～4个参数校准，例如交换电流密度修正、有效冻结速率或接触电阻。先比较灵敏度和参数相关性，不能同时自由调整热容、换热、冰指数和多种相变系数以追求拟合曲线。使用按测量量纲归一的电压/温度残差；−20℃校准、−25℃整条曲线验证，再交换检验迁移性，不随机打散相邻时间点。正文填规定的相对误差，另报电压MAE、温度MAE(℃)、RMSE及残差时间图；温度相对误差依赖摄氏/开尔文口径，不能偷偷换单位改善指标。冰曲线没有直接观测，只能称模型预测。[B03](https://www.mdpi.com/1996-1073/13/1/256)

**问题2：先可行性，再求最快。** 明确 $0\le j\le0.5$ A/cm²、$\int_0^{t_s}jdt\le20$ C/cm²。恒流优化一个电流值；线性升载优化初值/斜率并设上限；阶梯先用2～3段，优化电平和切换时刻。用网格筛选加有界局部搜索，失败方案保留原因。最低初温先作粗网格可行性扫描；只有检查到单调可行区后才二分，并在临界点邻域加密。端片可能成为瓶颈，但应由逐片电压/冰/能量收支证明，不能预先写死。[B04](https://ecec.me.psu.edu/Pubs/2010-Jiang-JES.pdf) [B06](https://www.sciencedirect.com/science/article/pii/S1385894726041987)

**问题3：用统一目标公平比较。** 纯预热先使全部单片满足题设温度要求再加载；协同策略从加载时刻加恒功率，保持题给0.005 A·cm⁻²·s⁻¹上升60s后0.3 A/cm²的电流输入。每片 $0\le q_k\le1$ W/cm²，优化 $q_1,\ldots,q_5,t_h$，计算
```math
E_h=25\sum_{k=1}^{5}\int_0^{t_h}q_k(t)\,dt\quad(\mathrm J).
```
全程使用cm²或统一SI换算，不能漏掉面积25。预热方案总启动时间必须包含预热时间；辅助能耗与氢气消耗分开报告。对称边界下可先用 $q_1=q_5,q_2=q_4$ 减维，再放开验证。优先做端板升温所需热量下界与可用反应热核算，避免优化器花时间寻找不存在的可行解。[B09](https://www.sciencedirect.com/science/article/pii/S1359431125040712) [B10](https://www.sciencedirect.com/science/article/pii/S0306261920312939)

**问题4：从可解释控制起步。** 基线用带滞环的分段规则：温度低/温升不足时加强加热，出现电压下降风险时提高对应单片功率，接近成功时降低功率，全部成功后关闭。对T、V导数做因果滤波，加入最短保持时间，避免噪声使开关抖振。主路线用降阶状态估计器预测不可直接测量的冰量，以辅助能耗为主目标，时间、最大温差和功率变化作次目标的受约束MPC。优化器异常时退回规则控制；不能直接将真实仿真冰量作为“实时测量”。MPC文献的操纵量是电流，本题需重写为逐片加热功率，保持题给加载曲线。[B07](https://www.mdpi.com/2077-0375/13/2/184) [B11](https://www.sciencedirect.com/science/article/pii/S0306261918301909)

预冷阶段令反应电流和辅助热源为零，从25℃解到−30℃边界下的20/40分钟，完整保留端板及各层温度，作为启动初值。10～100分钟扫描先粗后细，输出预冷时间—端片温度—温差—启动能耗/成败的关系图；不要只用一个平均初温代表非均匀场。

## 4. 验证与可写的创新

数值验证包括水质量和能量余额、零电流降温、无冰极限、无散热极限、网格/时间步加密。加密后关键输出变化阈值应事先约定，并记录实际差异。校准验证应包括整温度工况留出、初始膜水变化、换热和相变参数敏感性；控制验证增加测量噪声、采样延迟和参数失配。

建议消融：去掉冰占孔、去掉活性面积衰减、去掉端板热容、平均温度控制替代逐片控制、去掉电压下降反馈、MPC替代为恒功率。前三项用于机制解释，不应作为正式“更优模型”。一维模型不能描述沿流道冰前沿或非均匀气体分配，这一点有空间可视化实验支持，应写作模型边界。[B08](https://www.nature.com/articles/s44172-024-00176-6)

最值得做的创新是**“最弱单片风险感知的逐片加热分配”**：在同等安全约束下，验证能否减少过热单片的无效加热。次选是包含初始温度场的鲁棒成功域，以及物理模型与快速降阶控制模型交叉验证。没有实测冰量和更低温实验时，不宜宣传已证明通用冷启动极限。

## 5. 写作结构与48～72小时安排

推荐题名：**水热相变耦合下燃料电池冷启动边界与逐片辅助加热控制**。论文按“单电池验证—电堆差异—静态优化—动态反馈”递进，而不是四套互不衔接的模型。

目录建议：题意和数据口径；文献与假设；一维守恒及数值离散；参数校准/独立验证；电堆自启动优化；两种辅助加热；预冷场与反馈控制；稳健性/局限；结论。图表包括水热耦合框图、分层网格、实验拟合与残差、冰量时空图、5片温度/电压图、恒流/升载/阶梯对比、端板能量收支、逐片功率热图、能耗—时间Pareto图和预冷成功域。

0～8小时核对面积、阈值和单位；8～24小时跑通守恒和单片校准；24～36小时建5片＋端板并完成问题2；36～48小时完成问题3；48～60小时实现预冷和规则反馈，资源允许再加MPC；最后完成验证、误差表和复现附件。若数据口径仍未澄清，应保留双口径结论和明确限制，不能靠拟合参数吸收十余倍的电流密度差异。

题面明确要求披露AI使用，并要求公式和文献能在正式来源查询。论文末附AI辅助范围、主要输入、参考核验、独立推导及代码检查过程；正文引用原论文，不能将本调研或AI输出作为科学证据。四问程序最后按题面附件要求打包，调研阶段不虚填结果表。

## 6. 核验文献与阅读顺序

B01～B10为核心阅读，B11～B15为补充；含2023～2026年直接相关工作。题面2026年Ma等论文已在出版社页面核实。证据层级区别“摘要/预览”与“全文”，下列资料均未在本次调研中完整复现。网页访问受限的条目说明具体限制，不用访问失败冒充全文阅读。

|编号|文献（作者，年份，出处）|本题用途|核验证据|
|---|---|---|---|
|B01|[Cold start of proton exchange membrane fuel cell](https://www.sciencedirect.com/science/article/pii/S0360128517300175)；Luo, Y.; Jiao, K.；2018；Progress in Energy and Combustion Science 64:29–61|问题1–4：水/冰相变、传输及启动策略的综述入口；优先追溯所需模型原文。|出版社摘要页和章节片段|
|B02|[Three-dimensional multiphase modeling of cold start processes in polymer electrolyte membrane fuel cells](https://www.sciencedirect.com/science/article/abs/pii/S0013468609009013)；Jiao, K.; Li, X.；2009；Electrochimica Acta 54(27):6876–6891|问题1：冰相、膜水及多孔介质传输耦合的物理依据；按题目降为厚度方向一维。|出版社论文页面搜索索引及摘要片段；直接打开受403限制|
|B03|[Analysis of the Failure Modes in the Polymer Electrolyte Fuel Cell Cold-Start Process—Anode Dehydration or Cathode Pore Blockage](https://www.mdpi.com/1996-1073/13/1/256)；Yao, L.; Ma, F.; Peng, J.; Zhang, J.; Zhang, Y.; Shi, J.；2020；Energies 13(1):256|问题1/2：区分阳极脱水与阴极孔隙堵塞，避免把所有低电压都解释为冰堵。|原论文PDF首页与摘要检索核验；出版社直开429，未全文精读|
|B04|[Current Ramping: A Strategy for Rapid Start-up of PEMFCs from Subfreezing Environment](https://ecec.me.psu.edu/Pubs/2010-Jiang-JES.pdf)；Jiang, F.; Wang, C.-Y.; Chen, K. S.；2010；Journal of The Electrochemical Society 157(3):B342–B347|问题2：线性升载参数化、热容和初始含水量对升载策略的影响。|作者机构PDF首页及摘要搜索索引；直接打开超时|
|B05|[One-dimensional thermal model of cold-start in a polymer electrolyte fuel cell stack](https://doi.org/10.1016/j.jpowsour.2007.05.028)；Khandelwal, M.; Lee, S.; Mench, M. M.；2007；Journal of Power Sources 172:816–830|问题2–4：逐组件热平衡、端板热容和电堆传热的一维模型。|出版社摘要及章节预览页（PII:S0378775307009548）；原论文PDF首页核对作者|
|B06|[Diagnosing the cold start failure of fuel cell system: End-plate cell's thermo-hydraulic imbalance and its mitigation through loading control](https://www.sciencedirect.com/science/article/pii/S1385894726041987)；Ma, T.; Du, C.; Gu, Z.; Lin, W.; et al.；2026；Chemical Engineering Journal 538:176737|问题2/4：端部单片失效、水热竞争及加载控制；题面原引文已核实存在。|出版社摘要、作者和章节预览页|
|B07|[Research on Cold Start of Proton-Exchange Membrane Fuel Cells Based on Model Predictive Control](https://www.mdpi.com/2077-0375/13/2/184)；Xiong, S.; Wu, Z.; Jiang, Q.; Zhao, J.; Wang, T.; Deng, J.; Huang, H.；2023；Membranes 13(2):184|问题4：约束MPC的可行参考；原文操纵电流，本题应改成逐片加热功率。|原论文PDF首页和摘要；PMC正文检索片段，未完整复现|
|B08|[Experimental visualization of water/ice phase distribution at cold start for practical-sized polymer electrolyte fuel cells](https://www.nature.com/articles/s44172-024-00176-6)；Higuchi, Y.; Yoshimune, W.; Kato, S.; Hibi, S.; et al.；2024；Communications Engineering 3:33|问题1/4：相变与空间非均匀性的实验证据；也说明一维模型无法描述流向冰前沿。|出版社作者/摘要页和PMC实验方法片段|
|B09|[Optimizing current loading strategies for PEMFC stacks and predictions of needed powers for successful cold starts](https://www.sciencedirect.com/science/article/pii/S1359431125040712)；Chen, Y.-J.; Fang, W.-Z.; Zhao, G.-R.; Bai, F.; Tao, W.-Q.；2026；Applied Thermal Engineering 287:129479|问题2/3：两阶段升载、一维多物理电堆与最小辅助功率的近年直接参考。|出版社作者、年份、DOI和摘要页|
|B10|[Efficient thermal management strategies for cold starts of a proton exchange membrane fuel cell system](https://www.sciencedirect.com/science/article/pii/S0306261920312939)；Montaner Ríos, G.; Schirmer, J.; Gentner, C.; Kallo, J.；2020；Applied Energy 279:115813|问题3：被动/辅助加热的能耗与时间比较，设计公平的预热和协同加热对照。|出版社摘要页；作者机构相关公开论文参考表核对作者|
|B11|[Real time adaptive efficient cold start strategy for proton exchange membrane fuel cells](https://www.sciencedirect.com/science/article/pii/S0306261918301909)；Amamou, A.; Kandidayeni, M.; Boulon, L.; Kelouwani, S.；2018；Applied Energy 216:21–30|问题4：实时自适应与参数变化，启发在线状态估计及鲁棒性实验。|出版社摘要页及作者postprint首页|
|B12|[Non-isothermal cold start of polymer electrolyte fuel cells](https://www.sciencedirect.com/science/article/abs/pii/S0013468607008973)；Jiang, F.; Fang, W.; Wang, C.-Y.；2007；Electrochimica Acta 53(2):610–621|问题1：非等温冰生成与热量耦合，检查相变潜热和温升反馈。|出版社作者/摘要页|
|B13|[Free open reference implementation of a two-phase PEM fuel cell model](https://arxiv.org/abs/1811.09811)；Vetter, R.; Schumacher, J. O.；2019；Computer Physics Communications 234:223–234|问题1：五层MEA厚度方向守恒与可复现实装；原模型为稳态两相，不能当现成冷启动模型。|作者预印本摘要页与正式期刊信息|
|B14|[AlphaPEM: an open-source dynamic 1D physics-based PEM fuel cell model for embedded applications](https://arxiv.org/abs/2407.12373)；Gass, R.; Li, Z.; Outbib, R.; Jemeï, S.; Hissel, D.；2025；SoftwareX 29；作者预印本arXiv:2407.12373|问题1/4：动态1D建模、参数校准与模块化实现参考；须自行加入冻结物理。|作者预印本摘要页（2024首发、2026修订；页面列正式期刊年2025）|
|B15|[A comprehensive review of cold start in proton-exchange membrane fuel cells: Challenges, strategies, and prospects](https://www.sciencedirect.com/science/article/pii/S0306261925005768)；Yu, Y.; Zheng, W.; Li, B.; Zhang, C.; Ming, P.；2025；Applied Energy 390:125846|问题1–4：近年水管理、热管理和辅助启动路线，用于相关工作与模型边界。|出版社摘要、章节片段及作者贡献栏|

完整元数据见 [B题_文献.json](B题_文献.json)。使用具体公式前仍需检查原文参数、定义和适用条件。
