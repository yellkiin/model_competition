# A 三问性能测试计划与效果不佳时的修正操作

2026-09-23。目的不是检验系统安全，而是回答“算法是否更快、为什么、在哪些图上失效、怎样修正”。无需文件哈希校验或冒烟阶段。运行入口、环境与输出约定见 [README](README.md)，公式见 [THEORY](THEORY.md)。正式附件和三个原评估器保持不变。

## 0. 首先回答：能覆盖三问吗？

|赛题问题|要回答的实际问题|直接运行的实现|必要实验证据|当前交付范围|
|---|---|---|---|---|
|问题1|子图如何切分、分核和排序，才能在Task等待及全DDR边界下缩短总时间？|`solver.search(question=1)`＋原 `multicore_cut_evaluate_problem_1.py`|E1通信口径、E2各核主表、E3公平预算、E4粒度、E7小图/关键路|已实现独立优化及结果输出，不是借问题2的分数代替|
|问题2|允许同核驻留后，怎样平衡通信、Spill、并行和优先级？|同一search的question=2＋原问题2评估器|E1跨核成对复制、E2、E3内存消融、E5驻留、E6同方案Q1/Q2|已实现核心级Task计费、跨子图驻留代理和Spill修正|
|问题3|加FIFO Cache后如何调优，并量化Cache与重新优化各自贡献？|同一search的question=3＋原问题3评估器|E2、E3缓存消融、E6完整3×3、E7缓存时序、E8修正|已实现FIFO时序代理、实际缓存指标、缓存定向修正和同方案回放|

统一的是决策变量、候选操作、调用预算和统计协议，不是强迫三个问题使用同一份最优方案。每问都会生成独立 `best_plan.json`；交叉回放则专门固定方案。**这些实验能产生三问的数值答案和论文证据，但尚未运行的正式成绩不能预先保证，更不等于全局最优证明。**

## 1. 数据、比较与预算协议

用原始100个 `case_*.json`。`prepare`按图规模/并行度确定性分层选择20图开发集，剩余80图用于配置冻结后的留出描述；原比赛主表仍包含全部100图。不同种子、核数、问题不得重新挑一套“好看”的图。

所有问题的分母均是同图原版 `singlecore_evaluate.py` 时间Tsingle，不随策略或Cache改变。逐图加速比为S=Tsingle/Tq，主指标是先算各图比值再平均，不是总单核时间/总多核时间。多种子先在同图内平均，再对图平均；另报最差图、几何均值、搜索秒数和不完整项。配对消融使用相同图、核数、种子与原评估次数，失败调用同样计预算。

RR只是一份确定性工作量分块＋轮转分核基线，消耗1次评估。full主实验每作业至多32次；full相对RR提升属于**追加优化收益**，不是同预算算法优越性。公平预算结论来自E3的common/full/消融对照。所有权重只改变候选评分，不改变官方config。

```bat
git switch main
git pull --ff-only origin main
git lfs install --local
git lfs pull
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a\setup_windows.ps1 -SkipPull
D:\python\python.exe -m research_a.run prepare --out research_a\runs\cases.json
```

如果已经用脚本生成 `cases.json`，无需重复prepare。数据、算法、Python或评估器改变后使用新输出根目录；原样中断可用 `--resume`。

## E1. 通信公式与性能指标口径：三问共同的基准

**假设/应答：** THEORY中的前置复制公式与三个真实构图函数一致；`scheduled−spill`应等于Dpre；Q3字节命中率与次数命中率分别统计。

执行数学检验：

```bat
python -m unittest -v research_a.test_theory
```

在完整仓库内，最后的原程序集成项会对同一小图实际调用三个原评估器，并核对前置字节数。正式运行后的 `proxy_calibration.csv` 将这个公式检验扩展到所有取得结果的最好方案。缓存命中字节预测不要求等于真实值，那是代理误差，不是计数恒等式。

**预期判据：** 前置字节公式误差0；`DDR_accounted + hit_bytes = scheduled`；所有比率的分子/分母含义明确。由于不同Pipe/DDR可以重叠，不检验“各Pipe时间相加等于makespan”。

**效果/结果不符时：** 用 `unranked` 停止按代理筛选候选，仍按原评估器保留最优；检查 `model.copy_accounting` 与 THEORY第2节对应分支。若只有Q2/Q3扇出错误，重点查“每源核—目标核一对COPY”；若仅直接边错误，查 `data_size`；若Q3误差来自把scheduled当DDR，查 `evaluator.metrics`。已有可运行修正命令见E8。此类差异不能用调参消除，必须先纠正口径。

## E2. 100图×三问×五核数主实验

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a\experiments.ps1 main
```

每问n=1…5，RR与full，seed0、full预算32。输出每问5行核心主结果，并保留每图所有方案。默认最多49,600次原CLI调用：100单核＋100×3×5×(1+32)；实际重复候选可能提前耗尽，按真实调用数报告。

**回答问题1：** 划分优化能否抵消Task等待与新增DDR，哪个核数的代价收益更合适？

**回答问题2：** 同核驻留模型下是否获得不同的方案与加速曲线，Spill和跨核复制怎么变化？

**回答问题3：** Cache模型下独立优化效果如何，命中字节与加速是否一致？仅凭本实验还不能分离Cache与调参作用，须接E6。

**主要观察：** `summary.csv`、`summary_by_split.csv`、`per_job.csv`；不能只看平均值，列出最差若干图和T/LB、Spill占比、实际用核数。`complete=false`时不输出全图平均分。

**效果不好时：**
- 高n反而慢、划分复制多：E4粗化或`locality`，允许在n个虚拟核中只用部分核心。
- 计算负载偏斜而通信不高：`fine`细分/迁移；检查细分增加的边界是否超过负载收益。
- 单核到多核几乎不变但T接近计算LB：`critical`，接受关键路解释，不强求线性加速。
- 大量候选无法执行：`coarse`减少过细跨核交互；保留真实错误，不能把超时视作性能差或不可行的证明。此处是方案可执行性，不是安全测试。

## E3. 公平预算消融、种子稳定性和预算收敛

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a\experiments.ps1 dev
```

20开发图、n=2/4、seeds=0/1/2、每个方法24次原评估。Q1/Q2比较common、full、no_memory；Q3再加入no_cache。common、full、两个消融保留相同的候选操作集合，只改变评分项；轨迹因选择不同而分叉是算法预期，不强称每次候选完全相同。最多28,820次调用。

|比较|要证实/否定的命题|效果不好后的操作|
|---|---|---|
|full vs common|驻留/缓存代理是否值得额外计算？|common更好时冻结common；不能保留full只因模型更复杂|
|full vs no_memory|生命周期惩罚是否减少实际Spill并缩短时间？|转E5扫权重；过强惩罚会损害并行|
|full vs no_cache，仅Q3|FIFO时序代理是否改善真实缓存/时间？|no_cache更好时关闭代理但仍调用问题3，真实Cache仍生效|
|full vs portfolio，另行运行|局部改进优于纯候选组合吗？|portfolio更好或停滞时用explore提高新拓扑比例|

可选同预算局部搜索对照：

```bat
D:\python\python.exe -m research_a.run run --manifest research_a/runs/cases.json --split dev --questions 1 2 3 --cores 2 4 --variants full portfolio --seeds 0 1 2 --budget 32 --out research_a/runs/local_ablation --workers 2
D:\python\python.exe -m research_a.report analyze --source research_a/runs/local_ablation --out research_a/runs/local_ablation_report
```

`paired.csv`给同图配对差值和图级重采样区间；区间是图集敏感性，不是对新图总体的保证。种子波动大时，增加种子并比较均值/差例，不挑最佳seed。

`convergence.csv`给每次调用的incumbent，直接比较第4/8/16/24或32次；前缀与最终预算独立。若16之后仍明显下降，扩大预算是合理实验；若早停滞，先比较portfolio/explore，而不是盲目加十倍预算。主表扩预算需统一重跑，不只给最差图增加预算后混表。

## E4. 切分粒度：两个场景的含义不能混淆

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a\experiments.ps1 granularity
```

20开发图、三问、n=2/4/5、块数约为0.25n、n、2n、4n、8n，其他规则固定为同一拓扑序、等工作量块和轮转分核。实际块数、makespan、分区新增字节、Spill、Pipe占用与内存峰值记录于 `granularity.json`。

Q1重点看U形关系：粗块的并行损失与细块的等待/DDR成本。Q2/Q3细分不重置Task驻留，观察到Spill下降也必须归因于分核/优先序变化，不能写成“子图结束释放缓存”。

当前粒度实验改变块边界后RR分核也改变，所以其结果是**整个确定性切分策略**的效果，不能将差异完全当成块数的独立因果效应。同核驻留不重置的更严格反例由单元测试固定归属后只改子图标签检验。

**修正：** 细分明显更差→coarse；粗块导致单Pipe偏斜→fine；通信骤升→locality。三问分别看结果，不跨问强行选择同一块数。

## E5. 生命周期/Spill定量验证与权重扫描

从开发集有Spill的图定位机制；正式分数仍保留所有图。对所有开发图做统一权重扫描，避免只挑能获益的图拟合：

```powershell
foreach ($w in 0, 0.05, 0.15, 0.5, 1) {
    & "D:\python\python.exe" -m research_a.run run `
        --manifest "research_a\runs\cases.json" --split dev --questions 1 2 3 `
        --cores 2 4 --variants full --seeds 0 1 2 --budget 24 `
        --memory-weight $w --workers 2 --out "research_a\runs\memory_w$w"
    & "D:\python\python.exe" -m research_a.report analyze `
        --source "research_a\runs\memory_w$w" --out "research_a\runs\memory_w$($w)_report"
}
```

记录λ、代理excess、真实Spill、真实峰值、内存复用依赖数、时间、搜索开销。代理峰值不是真实物理上界，不强求两者完全相等。峰值贴近容量并不等于发生Spill，必须看真实Spill字段。

**负面结果及修正：**

- 预测excess高但实际无Spill，强惩罚拖慢：λ降低，或`no_memory`。说明参考序列代理过度保守。
- Spill下降但时间上升：并行/通信被牺牲，降低λ并比较`critical`，不把“Spill最小”作为最终目标。
- Spill仍高：`spill`倾向最后使用者和迁移；若只在Q2/3拆小但仍同核，理论上不应期待任务释放，转`locality`或迁移而非继续纯切分。
- 某操作所需同时驻留的输入/输出自身就超过固定容量：不允许增大官方容量或修改原图；保留原评估错误并核对附件/构图语义，当前划分代码不承诺能修复本质装载困难。

权重扫描结果用于冻结统一算法；不将每图挑最好λ的结果当作一个固定算法。

## E6. 第三问专项：3×3同方案、并发填充与收益分解

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a\experiments.ps1 cross
```

对每图/核数，从P1、P2、P3三个来源各取一个已选方案，用三个原评估器回放。保持原方案JSON中的ID和顺序，不在回放时重新优化或重新编号。对角线复用原成绩，另外6个格子真实评估；默认最多3,000次额外调用。

`cache_decomposition.csv`包含T2(P2)、T3(P2)、T2(P3)、T3(P3)，分别计算固定P2/P3的缓存收益、在Q3下换方案收益和总收益；逐图检验乘法恒等式。跨场景不能执行的格子保持失败，而不是删图后只统计好结果。

额外观察：字节命中率、次数命中率、`overlapping_miss_bytes`、Cache/DDR服务下界、四Pipe占用及实际makespan。`overlapping_miss_bytes`只表示同键读仍在飞时又发生未命中，不断言一定是首次冷读，也不自动等于“可消除浪费”。

**负面结果与现成代码：**

|现象|解释假设|可执行修正|怎样反证修正方向|
|---|---|---|---|
|重复输入多但命中少，同键未完成读重叠|首次填充尚未完成|cache重排独立子图，改变自然请求时序|重排后重叠未命中不降、时间更差，则不用该配置|
|命中更多但时间不降|关键路/Cache读池取代DDR瓶颈|critical或no_cache候选评分；原Q3Cache仍开启|若DDR服务量仍主导，重新查请求代理与真实顺序|
|缓存代理误差很大|Step3、Spill和争用改变请求轨迹|no_cache或unranked|同预算下关闭后仍更差则代理尚有排序价值|
|P3在Q3不如P2|有限预算搜索没有找到跨问已有好方案|从P2的精确JSON作为Q3额外候选，见下方跨问修正|追加候选不改善也保留阴性结果，不保证P3一定优于P2|

跨问候选再优化可直接使用已实现的修正接口：将Q3的父方案替换不是手工覆盖原文件，而是使用下面脚本级调用，输出到新目录：

```powershell
@'
from pathlib import Path
from research_a.model import Graph, Plan, read_json, settings
from research_a.run import attachment
from research_a.evaluator import Official
from research_a.solver import search
root = Path('research_a/runs/main/case_001')
source = root / 'q2_n4_full_s0'
graph_path = Path(read_json(source / 'search.json')['graph_path'])
graph = Graph(read_json(graph_path))
plan = Plan.load(read_json(source / 'best_plan.json'), graph)
a = attachment()
out = Path('research_a/runs/q2_seeded_q3_case001_n4')
if out.exists():
    raise FileExistsError(out)
evaluator = Official(a / 'code', a / 'data/config.txt', graph_path, out)
search(graph, settings(a / 'data/config.txt'), lambda p: evaluator.evaluate(p, 3),
       out, question=3, cores=4, variant='cache', budget=96, seed=0, initial=plan)
'@ | & "D:\python\python.exe" -
```

这96次是明确的追加预算。论文可另列“跨场景热启动”，但不可替换原32次主表。该示例路径可改为其他图/核数，`cores`必须与父方案一致。

## E7. 可控机制图与小图枚举：找出为什么有效/无效

```bat
D:\python\python.exe -m research_a.fixtures --out research_a/runs/mechanism_data
D:\python\python.exe -m research_a.run prepare --data research_a/runs/mechanism_data --expected 8 --dev-count 2 --out research_a/runs/mechanism_cases.json
D:\python\python.exe -m research_a.run run --manifest research_a/runs/mechanism_cases.json --questions 1 2 3 --cores 1 2 4 --variants rr full --budget 16 --workers 2 --out research_a/runs/mechanisms
D:\python\python.exe -m research_a.report analyze --source research_a/runs/mechanisms --out research_a/runs/mechanisms_report
```

|生成图|控制机制|预期用途，不是承诺的正式分数|不符时的修正|
|---|---|---|---|
|case_001 chain|长计算关键路|解释不能随核数线性加速|critical、允许空核|
|case_002 independent|相同Pipe独立工作|检验负载均衡与小通信开销|fine、检查工作量而非节点数|
|case_003 mixed|多Pipe工作交错|说明Σ总工作/n不是一般下界|按Pipe计负载，已在代码实现|
|case_004 fanout|一个张量多个消费者|验证Q1/Q2计费差异和核心去重|locality、校验Dpre公式|
|case_005 cache_burst|共同输入的并发请求|并发冷读可能重复未命中|cache时序修正|
|case_006 cache_stagger|加入原图中明确的计算依赖形成错峰|检验填充后复用机会|观察真实Cache事件，不按图名认定一定命中|
|case_007 spill|多个输出驻留后再消费|验证迁移、访问顺序与Spill指标|spill；不能通过改容量消除|
|case_008 tiny_oracle|四操作小DAG|为限制族枚举提供可比对象|explore；检查启发式是否错过明显方案|

构造图不代表正式图分布；burst/stagger改变了依赖与计算，所以不能仅用两图总时间差估计“纯缓存效应”，应在每图内部做Q2/Q3同方案对照。完整回放可用 `run cross --source research_a/runs/mechanisms --cores 1 2 4 ...`。

```powershell
foreach ($q in 1, 2, 3) {
    & "D:\python\python.exe" -m research_a.run oracle `
        --graph "research_a\runs\mechanism_data\case_008.json" `
        --question $q --cores 2 --out "research_a\runs\oracle_q$q"
}
```

每问54个固定拓扑序连续划分/分核候选；若任意调用失败，只称已观察最优。启发式可生成其他拓扑序，若比该枚举值更好并不矛盾。大于枚举值提示遗漏，但不是相对于全局最优的精确差距。

## E8. 统一诊断→修正→复核，不覆盖旧成绩

```bat
D:\python\python.exe -m research_a.report analyze --source research_a/runs/dev --out research_a/runs/dev_report
D:\python\python.exe -m research_a.report repair --source research_a/runs/dev --out research_a/runs/dev_repairs --limit 12 --budget 96 --workers 2
```

默认只处理开发集full的12个最弱作业，诊断规则按以下顺序选择一种首要修正。阈值是可解释的工程启发，不是统计显著性标准；多个病因可以同时存在，先验证首个，再试其他profile。

|触发/症状|修正配置|实际代码动作|
|---|---|---|
|没有有效方案|coarse|减少块数、多试少核方案、偏向合并|
|Dpre公式不一致|unranked|停止以代理分数筛选，随机挑候选给原评估|
|Spill/scheduled>15%|spill|提高驻留惩罚，倾向最后使用顺序及迁移/拆分|
|Q3有重叠未命中字节|cache|共享张量优先拓扑、独立块重排、实际评估|
|分区新增字节/scheduled>35%|locality|强化张量亲和、重通信块合并、少用核心|
|T/LB<1.15|critical|关键路优先、降低过度通信/驻留惩罚、扫描少核|
|核心计算负载max/mean>1.4|fine|更细的工作量块并迁移|
|加速比<1.05而无明显单项病因|coarse|降低固定等待/复制开销|
|其他/搜索停滞|explore|提高新拓扑/新划分比例，不只围绕当前局部最优|

显式指定方向：

```bat
D:\python\python.exe -m research_a.report repair --source research_a/runs/dev --out research_a/runs/repair_locality --profile locality --limit 12 --budget 96 --workers 2
```

`repair_summary.csv`报告旧makespan、新makespan、比值、实际追加调用、搜索秒数及失败。每个修正先重评原best_plan，代码保存父目录和原因。若重评失败，不能引用“保留父方案所以一定不差”的论断。

**修正也不好时：** profile无收益就保留原方案，不做结果美化；再在相同追加预算下比较另一profile，或用E7/E6证伪当前瓶颈解释。若多个方向都接近计算下界，则报告上限；若离下界很远而所有代理都失效，用unranked/portfolio作机制对照，保留这一局限。代码不承诺任何单一策略必然提升。

在开发实验选择一个统一配置后，使用新目录重跑全部100图：

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a\experiments.ps1 main -MainVariant locality -OutRoot "research_a\runs_locality"
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a\experiments.ps1 cross -MainVariant locality -OutRoot "research_a\runs_locality"
```

不将逐图不同profile、不同预算事后取最好的集合称为一个公平32次算法；可另外命名为明确预算的组合策略，并对所有图执行同一选择规则。

## 9. 交付与论文验收清单

问题1：每图每核最佳方案与原时间、平均/最差加速、Task等待和粒度差例、搜索开销。问题2：同样主表，加实际Spill/分区流量/核心负载及与Q1的同方案比较。问题3：同样主表，加字节/次数命中、重叠未命中、3×3回放、四格缓存/重优化分解。

三问都有可用输出且100图各核主表完整，才能填写正式三问数值结果；缺失、超时和不可执行必须说明。公平消融和阴性结果也进入论文，不只展示最好图。最后附统一算法伪代码、公式到源码的映射、开发/留出说明和限制族枚举边界。

## 10. 资源与本环境完成情况

主程序和原评估器使用CPU；不需要CUDA/RTX3060。当前 Windows 机器直接使用 `D:\\python\\python.exe`（Python 3.12.5）；Conda 26.3.2 已安装但无需激活环境。`setup_windows.ps1`负责核对 Python/Git/Git LFS，`experiments.ps1 -Workers`控制 Windows 上的 CPU 并行，`--cores`仍是仿真硬件核数。先控制 Workers=1 或 2，过度并发会增加内存峰值而不一定更快；本计划不对未知 CPU/内存配置给耗时估计。

当前容器已跑26项数学/算法/统计检验，1项原评估器三问集成检验因缺源码实体被明确跳过。正式100图未运行。测试记录保存在 `results/local_tests.txt`。本地原程序集成项和真实实验会提供本轮尚缺的数值证据。
