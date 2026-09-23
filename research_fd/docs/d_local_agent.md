# D 本地 Agent 执行手册

目标是运行方法对照、解释失败并接入正式附件，而不是再生成一份待办清单。代码入口全部从仓库根目录以 `python -m research_fd...` 调用。每个实验单独输出目录，不覆盖原始题目和上游 Agent。

## 0. 可直接交给 Agent 的任务文本

> 先读仓库AGENTS.md、research_fd/README.md、REPORT_D.md和本手册。进入research_fd/.venv环境；先跑小规模完整运输—中继—分区，再跑80箱合成对照。之后提取D题DOCX/XLSX，按实际工作表建立显式映射，填齐机型、充电和通信参数；不得将合成实例的参数当作官方值。执行正式数据的资源感知派单、ALNS和固定路线重排，比较完整模型与降阶模型。保留无可行解、超时、劣于基线的结果，并按本手册运行对应修复。输出逐箱交付、机身/电池时间表、中继出返仓任务、不同精度通信结果、两/三分组资源、能耗—工期取舍。所有结果只写research_fd/outputs/。最终给出真实跑过的方法及数值，不预填未执行后端的成绩。

## 1. 一条命令启动

环境见 d_environment.md。小规模端到端：

```bash
python research_fd/scripts/run_d_local.py --size small --seconds 10 --radio
```

它生成4服务点12箱的合成输入、比较运输方法，固定运输时刻解中继，再计算严格/复制口径的两组和三组资源。默认输出 `research_fd/outputs/d_local/`。中继未解出时保存原因，不伪造后续分区。

80箱多种子对照：

```bash
python -m research_fd.d_experiments benchmark \
 --out research_fd/outputs/benchmark80 --seeds 7,17,42,73,101 \
 --boxes 80 --nodes 15 --seconds 10 --trials 500 --backend none
```

`backend none`只关闭完整时间索引/CP-SAT两个昂贵后端，集合划分和ALNS内部仍用HiGHS。正式方法对比应固定实例、候选生成种子、目标顺序和求解预算，再改变一种方法；不能拿不同种子生成的不同需求计划相互评估。

## 2. 正式附件：先提取实际字段，不猜表头

```bash
git lfs pull
python -m research_fd.d_data inspect --repo . \
 --out research_fd/outputs/official_extract
```

输出包括每个Excel的工作表名、全部行、公式和缓存值，以及DOCX的可检索文本、含公式的原始document.xml。读取 `index.json` 找工作表；公式文本或高程基准难理解时由agent查看原文，不需要OCR替代原始文本。

复制 `configs/d_official_mapping.template.json` 到 `outputs/official_mapping.json` 后填：实际表名、1起算表头行、准确列名、单位比例；模板中的尖括号和null全部是待补字段。这个模板不是声称已经适配真实附件。机型列名与字段对应见 `configs/d_fleet_field_reference.json`，其中示范数值**全部是合成值**，只看字段含义。

映射规则支持：`{"column":"实际列名","scale":60}`分钟转秒，`{"const":0}`固定值，`{"when":{"column":"标记","in":["是",1]},"then":...}`条件字段，`{"min":[...,...]}`取医疗/首批多个非空硬期限的较早者。Excel日期序列不自动猜测时间原点，应显式 scale=86400 并设置 offset。体积若为升则乘0.001；速度若为km/h则除3.6。

模板 `template.fleet` 填三类机型的实际字段；也可在 `tables` 新增fleet工作表映射，由同一通用入口读取，不必改代码。通信三个budget字段分别为运输—地面、运输—中继、中继—地面在两方向中较小的允许路径损耗：`Ptx+Gtx+Grx−系统损耗−接收灵敏度−裕量`，不要将不同接口功率混用。中心天线高度与无人机起飞地面高度是两个字段，代码已分开处理。

充电原题与两阶段参数不同则设置 `charge_table`。每行是 `[SOC, 从空电充至该SOC的累计秒数]`，首尾SOC为0和1；支持精确分段线性或对原函数高精度采样，需比较采样分辨率。该表存在时覆盖默认两段公式。relay也可使用同样的charge_table。

```bash
python -m research_fd.d_data normalize --repo . \
 --mapping research_fd/outputs/official_mapping.json \
 --out research_fd/outputs/d_official.json
```

经纬度由O01为中心建立米制局部坐标，再查询原DEM；已有米制节点则移除lonlat转换项并提供一致local_crs。节点z为空时从DEM取值，有附件高度则显式保留并比较差异。正式参数整理完成后，应核对箱数、总质量体积、库存包含初装电池的口径与原题；代码输出这些总量，但不会替代读题。

## 3. 运输：先取得可用解，再做精确局部优化

```bash
python -m research_fd.d_experiments transport \
 --input research_fd/outputs/d_official.json \
 --out research_fd/outputs/official_transport_s7 \
 --seed 7 --trials 1000 --rounds 3 --lns-iterations 500 \
 --max-stops 3 --max-boxes 12 --max-routes 600 \
 --seconds 30 --step 60 --backend highs
```

输出逐方法JSON、comparison.csv/json和best_plan.json；每个plan包含完整逐箱交付偏移、路线段、实体编号、电池编号与开始时刻。评分先检查覆盖、硬截止和资源冲突。无可行解的空计划，在CSV中即使某些和指标为0也不能当成更好结果。

长实验建议固定实例，分别用种子7/17/42/73/101生成候选与搜索，输出到不同目录。再比较 `max_stops=1/2/3/4`、`max_boxes=8/12/16`；默认同箱组仅保留一个访问序，多点路线的完整Pareto访问序是后续扩展，不应声称现有池已经穷尽。

|失败现象|原因诊断|已给出的解决代码与运行方式|
|---|---|---|
|架次减少但硬截止更差|静态路线目标没有资源时序|先用 `resource_dispatch`，再 `alns`；两者是transport自动生成的独立结果|
|完整HiGHS无可行解/内存增加|路线×时间选项太大，不等于问题不可行|保留ALNS方案，查看 `fixed_route_retime.json`；减少max_routes或增大step得到起点，再细化|
|30/60秒网格限制导致完工更差|连续启动基线未必落在网格|比较step60/30/10，或安装ORTools后 `--backend cpsat`；最佳已知计划不会被劣解覆盖|
|对偶扩列未改善迟到|定价代理仍是静态占用|保留该负结果，增加资源感知搜索，不把更多列本身当贡献|
|某箱没有任何可行路线|单位/工作高度/机型不符或确实超限制|查看箱、逐段能耗与体积；增加允许机型和合法候选，不能删除该箱或降低题给要求|

## 4. 中继：固定基线、局部调时、位置和精度修复

```bash
python -m research_fd.d_experiments radio \
 --input research_fd/outputs/d_official.json \
 --plan research_fd/outputs/official_transport_s7/best_plan.json \
 --out research_fd/outputs/official_radio_fixed \
 --mode fixed --grid 3 --sample-step 60 --seconds 30 --max-sessions 6000
```

固定时刻失败后运行：

```bash
python -m research_fd.d_experiments radio \
 --input research_fd/outputs/d_official.json \
 --plan research_fd/outputs/official_transport_s7/best_plan.json \
 --out research_fd/outputs/official_radio_retime \
 --mode retime --grid 3 --sample-step 40 --shift-window 1200 \
 --horizon 18000 --seconds 60 --max-sessions 12000
```

horizon单位秒，是明确实验上限而不是题给常数，应据实际初始计划调整。先调小邻域，再尝试600/1200/2400秒窗口；本轮对称双点反例900秒窗口失败、2100秒可行。若 `unreachable` 非空属于空间覆盖问题，比较 grid3/5/7 并加 `--refine-sites 6`；这会调用差分进化搜索位置，预算和最大高度不变。若是stage状态1则先增加求解预算或减小模型；stage状态2也只证明当前候选与窗口的模型不可行。

有解后用 `--mode refine` 自动60/20/5秒重建；还应改变输入radio.ray_step_m为30/15/7.5，比较最差链路裕量与断联点。细化模式可能放大模型，应以已取得方案附近小调时窗口运行。不要把10秒采样通过写成解析的连续通信定理。

多运输候选联合选择：

```bash
python -m research_fd.d_experiments coopt \
 --input research_fd/outputs/d_official.json \
 --plans research_fd/outputs/official_transport_s7/alns.json \
         research_fd/outputs/official_transport_s7/fixed_route_retime.json \
 --out research_fd/outputs/official_coopt --seconds 30 \
 --horizon 18000 --shift-window 1200 --max-sessions 12000
```

只传同一物理输入生成的完整可行计划。coopt逐个计算中继、必要时调时，按软迟到—联合返回—总能量选，不混淆Q2最佳和Q3最佳。当前位置优化、单点悬停会话池都有限，尚不是所有路线、所有连续位置的一次性全局求解。

## 5. 多目标、情景和分区

```bash
python -m research_fd.d_experiments pareto \
 --input research_fd/outputs/d_official.json \
 --plan research_fd/outputs/official_transport_s7/best_plan.json \
 --out research_fd/outputs/official_pareto \
 --ratios 1,1.1,1.25,1.5 --seconds 60 --trials 500 --step 60

python -m research_fd.d_experiments stress \
 --input research_fd/outputs/d_official.json \
 --plan research_fd/outputs/official_transport_s7/best_plan.json \
 --out research_fd/outputs/official_stress.json \
 --seed 20260923 --scenarios 1000 --sigma 0.08

python -m research_fd.d_experiments partition \
 --input research_fd/outputs/d_official.json \
 --plan research_fd/outputs/official_coopt/best_joint_plan.json \
 --out research_fd/outputs/official_partition2.json \
 --groups 2 --policy strict
```

另跑groups3和policy duplicate，分别解释是否允许复制同一中继保障。分区不修改原任务时刻。若连通分量不足，这是冻结计划的结构事实，不应该偷偷改路线凑分组。Pareto当前重建指定种子的有限运输池，不含中继优化；对应每个取舍点再跑radio才得到联合能耗曲线。stress当前不重放通信，方差是假设，不是估计的天气概率。

## 6. 完成一次实验后应交付什么

保留原始comparison、每阶段求解状态、最优可行plan、所有失败候选原因，以及共用输入下的可行方法对照。正式附件结果应单列，不与本提交results/d_results.json中的合成数据拼在同一“官方成绩”表。优先解释三个机制：电池周转改变最优分组；中继移动/充电使空间覆盖变成时序问题；允许更长工期怎样节省能量与独立分区资源。
