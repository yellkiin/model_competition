# A三问：松弛界引导的无环构造与定向整数改进

这不是原来大规模随机候选搜索的加预算版。主流程是**解析松弛取界 → 阶段/张量边界感知构造 → 有限定向代理改进 → 原评估确认 → 小候选集合保留最好解**。覆盖三问，独立目录，不改已有实验、原始数据或原评估器。

先读：[题面逐项对齐](REQUIREMENTS.md)｜[统一理论与上下界](THEORY.md)｜[5篇文献迁移](LITERATURE.md)｜[小实验及修正](TEST_PLAN.md)｜[给本地Agent的完整指令](LOCAL_AGENT.md)。本次实际验证范围见 `results/VALIDATION.md`；不把合成验证当100图正式成绩。

## 方法与源码

|文件|已实现内容|
|---|---|
|`core.py`|严格二部输入；参考计算依赖；分数负载LP解析解、全局CP下界、方案相关通信路径界、后验解析上界；统一多Pipe/DDR/FIFO/驻留代理|
|`construct.py`|弱连通组件、非均匀阶段切分、数据就绪/多Pipe分核；论文描述基线；定向迁移/合并/顺序改进；3块整数B&B窗口|
|`solve.py`|真正的通用单图入口，不依赖case文件名；fast不经性能搜索，refined只做代理改进，失败时最多一次单核恢复|
|`official.py`|子进程调用**未改动**的原公开evaluate函数，省去每个候选的Trace字符串生成；原完整结果仍保留|
|`run.py` / `report.py`|小面板、每例分母、三问、Q3同方案配对、明确硬时限、分机、完整性受控表格与SVG曲线|
|`repair.py` / `sensitivity.py`|至多2图针对性修正；Q3五轴点固定/适配方案比较；新目录记录不混旧成绩|
|Windows脚本|沿用D:\python\python.exe，符合条件直接跑；不符时交本地Agent适配，不强装CUDA或Conda|

当前阶段化构造不是A39完整多层FM，窗口也不是COSMA的地址ILP。分数LP只用于下界，不把均匀x=1/n直接当可执行解。所有正式方案必须原评估成功；“代理得分下降”没有被冒充“官方时间下降”。

## Windows开始：不需要GPU、额外包或新Conda

在**新代码所在仓库根目录**执行。旧实验正在运行时不要切换它使用的工作树；为本次PR建立独立工作树/克隆即可。原本机配置优先CPython3.12.5 x64、`D:\python\python.exe`；stdlib-only。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a_next\configure_windows.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a_next\run_windows.ps1 prepare -Out research_a_next\runs\pilot
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a_next\run_windows.ps1 run -Out research_a_next\runs\pilot -Workers 2 -Minutes 30
```

另一台已有兼容Python的机子可显式传 `-Python 'C:\实际路径\python.exe'`；configure同时加`-AllowCompatible`可接受CPython3.10–3.14 x64并记录差异。主用户不需要WSL，不使用RTX3060。不存在合适解释器时返回`local_agent_action_needed`，按LOCAL_AGENT配置而非强制覆盖现有环境。

输入不全时沿用仓库最新A专用启动器，只从A题.zip恢复缺少内容或下载A的LFS；本地ZIP在别处用prepare的`-Archive`。数据准备不是计算预算的一部分，不要在下载耗时上承诺30分钟。

### 初轮规模和时间上限

6个诊断案例：001、002、044、059、062、083；2核和5核；**三个问题全部**。默认每例40次原评估硬上限、每次20秒、整例600秒、整机30分钟。一般没有去重时最多33次/例，恢复额外最多6次；重复方案复用。到时保留已有结果，未完成明确列missing，不删除难例来给出“完整均值”。

`fast` 和 `refined` 各自真实评分；最后另有 `guarded` 选择可用基线+新方案的最好者。这最多是每配置2–3个基线和2个新候选，不是每配置再调用24/32次搜索。保留基线只能保证不劣于**成功重评的该基线**，不保证严格提升。

## 真正通用的单图求解

```powershell
$A = '题目/A题/通用神经网络处理器下的多核调度问题  附件'
& 'D:\python\python.exe' -X utf8 -m research_a_next.solve "$A/data/case_002.json" --code "$A/code" --config "$A/data/config.txt" --question 2 --cores 5 --method fast --seconds 60 --out research_a_next/runs/single_q2
```

`--question 1/2/3`统一入口；`--method refined`增加最多16个代理改进、3秒，仍只对最终提出的方案作一次原性能评估；`--method window`使用最多3块、200状态/2秒的整数窗口。失败时最多再评估一次整图单核恢复，并明确 `recovery_used`。输出题定 `<case>_multicore_res.json`、原响应、证书、求解时间；整体截止会停止子进程树。新的任意符合格式图也能输入，不限六个案例。

## 原论文方案对照

默认 `draft_components/draft_bands8/draft_batches800` 是按上传论文重实现，缺少的亲和系数0.1是我们明确标注的假设，不能称完全复现原作者。

更严格：准备CSV（路径相对CSV或绝对路径）：

```csv
case,question,cores,plan_path
case_002,1,5,author_results/q1/n5/case_002_multicore_res.json
case_002,2,5,author_results/q2/n5/case_002_multicore_res.json
case_002,3,5,author_results/q3/n5/case_002_multicore_res.json
```

prepare加`-BaselineCatalog 'baseline.csv'`。真实原方案先重评再比较，不能拿PDF的均值伪造逐图基线；缺少的组合明确退回描述重实现。

## 结果不好：执行修正，不盲目加大网格

```powershell
& 'D:\python\python.exe' -X utf8 -m research_a_next.repair --source research_a_next/runs/pilot --out research_a_next/runs/repair_spill --profile spill --limit 2 --workers 1 --minutes 15
```

`components`：执行环/大量超时，减少复杂分组；`locality`：跨核等待/字节高；`spill`：参考驻留惩罚及顺序；`cache`：独立子图读序；`window`：小整数约束窗口。repair重新计分父方案作为基线，追加预算单独标明。超时默认将单次上限20秒改60秒，但整例/整机上限仍在；不把超时视为性能被击败。公式、源码错误不能靠换profile掩盖。

第三问容量/带宽单独跑：

```powershell
& 'D:\python\python.exe' -X utf8 -m research_a_next.sensitivity --source research_a_next/runs/pilot --out research_a_next/runs/pilot_sensitivity --minutes 10
```

默认两例、5个轴点、每点固定默认方案+适配构造，最多20调用。只改输出区配置副本，原config不动。默认锚点必须复现；非默认点绝不混入正式分数。

## 多机：相同manifest，不同case分片

协调机prepare一次，将实验根里的`manifest.json`和可选`baseline_plans/`复制到每台机相应根目录。代码版本一致；两台分别：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a_next\run_windows.ps1 run -Out research_a_next/runs/pilot -ShardIndex 0 -ShardCount 2 -Workers 2 -Minutes 30
# 另一台用 -ShardIndex 1，其余实验manifest相同。
```

收回各机结果到不同目录后：

```powershell
& 'D:\python\python.exe' -X utf8 -m research_a_next.report --out research_a_next/runs/merged --merge returned/pc0 returned/pc1
```

不同manifest或重叠案例会停止，不从重复试验里默默择优。各机器的CPU/解释器/实际墙钟单独记录；官方模拟周期与实机CPU速度不同，不能混淆。慢机触发时限导致候选没评完时，要标记比较不完整。

## 必看输出

`report/appendix_per_case.csv`：题定时间、原始新增COPY字段、推导DDR新增字段、Q3无L2/有L2、字节命中、上下界；`summary.csv`：完整组才给均值；`new_vs_baseline.csv`：fast/refined独立比较；`diagnosis.csv`、`missing.csv`：修正与缺失；`q1/q2/q3_curves.svg`：正式或PILOT明确标题。每个有效q/n目录有题定格式方案和原完整响应，每次评估响应单独保留。

全量只在方法确定后显式创建：

```powershell
& 'D:\python\python.exe' -X utf8 -m research_a_next.run prepare --full --profile balanced --out research_a_next/runs/full100 --eval-seconds 60 --case-seconds 900 --max-calls 100
# 按所需分机数使用 run，不自动启动。
```

全量包含100图、1–5核、三问。Q1/2的n1=1按题面；Q3一核真实L2收益不硬写1。最终“超越论文”需全量同口径比较；六图胜出只能决定是否值得继续，不能证明超过3.5093/3.5456/3.6104。
