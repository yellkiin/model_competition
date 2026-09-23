# A / C 深度调研与可验证原型

日期：2026-09-23。阅读顺序：[A 方法报告](REPORT_A.md) → [C 方法报告](REPORT_C.md) → [文献核验表](LITERATURE.md) → [实验原始结果](results/synthetic_summary.json)。本目录是对既有基础调研的增补，不替换原题或官方程序。

## 结论与阅读边界

**偏工程优化、希望尽快形成可评分闭环，优先 A；偏统计建模、愿意认真处理不可辨识性，C 有更鲜明的方法论切口。** 这不是根据尚未取得的正式成绩做的排名。A 的第一关是官方评估器的全流程可执行性，C 的第一关是事件编码、任务映射和记录身份审计。

本轮新增的重点不是堆模型名字，而是：A 的张量级通信去重、保序切分与真实评估局部搜索；C 的刺激/按钮重叠校正、保形与分类目标冲突，以及 E–I 参数等价族的解析反例。

核验范围：既有 A/C 调研、C 结构审计、A 附件 README、方案格式、CLI、单核入口及部分校验/Spill 源代码。**没有重新解码原始题面 DOCX 的全部公式/图片，也没有在本环境拉取正式 LFS 数据实体；题面解释仍需队内对照原文复核。** 当前 `main` 的数据提交为 `312b950cdd5879995365b488978a16a9dada10d4`；新版根 README 已改为 Git/Git LFS 管理附件，不能沿用旧版“数据只留本地”的描述。获取附件按根 README 执行 `git lfs pull`；本目录读取器会明确拒绝把 LFS 指针当作 JSON/MAT 数据。

## 已运行与未运行

|项目|本环境状态|不能据此声称什么|
|---|---|---|
|Python 单元/集成测试|31 项通过，详见 `results/pytest.txt`|不是官方评测全部通过|
|A 候选结构检查|20 个合成 DAG，1–5 核、三问题，共 3,600 个候选；另测 200 次连续局部变异|未检查官方 Step3/Pipe/跨核 COPY 的完整执行图|
|A CLI / 批处理|使用明确标注的 mock 评估器，测试成功、失败、超时、基准缓存、同方案 Cache 对照|mock 的数值不是赛题成绩|
|C MAT 读取、分类与反卷积 CLI|以自行生成的 MAT-v5 文件端到端验证；分类为四记录嵌套留出|没有读取四份真实记录的 EEG 样本|
|C 方法反例|10 个固定随机种子的重叠实验和降秩实验；扩散守恒、网格细化；E–I 等价族|不是疾病诊断、真实 SNR 或神经源定位结果|
|正式 A 100 图、正式 C 四记录|未运行；交付下列可执行入口|不提供虚构的正式加速比/分类准确率|

验证环境：Python 3.13.5、NumPy 2.3.5、SciPy 1.17.0、scikit-learn 1.8.0、pytest 9.0.2。依赖文件给出兼容范围，范围内其他组合未全部测试。无需 GPU。

## 先复现本轮验证

以下均从仓库根目录运行，输出目录必须不存在，避免覆盖旧实验：

```sh
python -m pip install -r research_ac/requirements.txt
python -m pytest -q research_ac/test_ac.py
python research_ac/experiments.py --out research_ac/runs/synthetic_rerun.json
```

合成结果记录随机种子、环境和全部 Python 源文件的 SHA-256。数值线性代数环境变化可能影响末位数字及优化器轨迹。`runs/` 和 MAT/NPZ 不纳入本目录版本管理；正式输出应放在 `runs/`，不要放回原始数据目录。

## A：连接原版评估器

附件目录名在“问题”和“附件”之间有**两个空格**。下面是 POSIX shell 示例；PowerShell 用 `$A = '...'` 赋值并将参数置于同一行即可。

```sh
A='题目/A题/通用神经网络处理器下的多核调度问题  附件'
# 先把下面的 <实际图名> 换成 data 中的一张真实 JSON，做低预算冒烟测试。
python research_ac/a_search.py "$A/data/<实际图名>.json" --code "$A/code" --config "$A/data/config.txt" --problem 1 --cores 2 --budget 6 --timeout 120 --out research_ac/runs/a_smoke
# 冒烟成功、确认单次评估开销后，再启动正式全量。
python research_ac/a_batch.py "$A/data" --code "$A/code" --config "$A/data/config.txt" --expected-count 100 --cores 1 2 3 4 5 --problems 1 2 3 --budget 24 --timeout 120 --out research_ac/runs/a_full
```

`a_search.py` 先保留整图单核式候选，再做多尺度拓扑切分、轮转/张量亲和分核；后半预算穿插基于当前官方最好方案的合并、拆分、迁移。仅按官方 makespan、再按实际搬运字节字典序选优。基础合法不等于最终可执行，官方拒绝的方案会保留错误记录。

`a_batch.py` 每图只计算一次固定单核分母；基准按图、配置、评估器源码哈希核对后复用。问题 3 另外将其最优方案交给问题 2 评估，得到**固定方案**的有/无 Cache 比值。全量默认候选调用上限约为 `100×5×3×24`，另有 100 次单核和至多 500 次 Cache 配对调用；`--timeout` 是单次子进程上限，不是全批次墙钟上限。先测开销，不要未经估算直接开大预算。

输出包括 `best_plan.json`、逐候选 `manifest.json`、原评估器 result/trace/log、逐例 CSV/JSON 和完整性受控的汇总。正式实例失败或基准缺失时，不输出“完整平均加速比”；问题 3 配对失败也标为不完整。生成器、局部搜索与基准调用开销应分别解释。当前没有实现完整缓存驻留代理、冲突学习、前沿动态规划或 CP-SAT，它们在报告中明确列为下一层研究方向。

## C：真实 MAT 的审计与方向预测

```sh
python research_ac/c_pipeline.py '题目/C题' --out research_ac/runs/c_baseline
# 固定短窗敏感性；不得从所有结果中挑最高者再称为独立测试。
python research_ac/c_pipeline.py '题目/C题' --window 0.2 --out research_ac/runs/c_short_window
```

程序递归寻找 `VisualCog*.mat`。若 DataLabel 不能确认前三行是 Fz/F3/F4，会停止；**人工核实后**才允许加 `--trust-channel-order`，不能用该参数掩盖通道顺序错误。只支持 MAT-v5，时间戳不递增或存在明显缺口时要求先分段，不静默修复。读取实际 `SampleRate`，不把采样点数直接当秒。

`audit.json` 记录单位/身份尚未核实、试次数、无应答/重复点击、边界丢弃和特征窗内应答比例；`events.csv` 不擅自判定答对/答错。`cv.json` 为嵌套留记录预测，训练折内选“不投影/PCA1/ERP 偏置投影1或2”，并报告未投影对照。输入是刺激后的固定窗口，采用固定因果滤波；这仍不证明信息不是眼动/动作造成的。超过应答的窗口会单独计数，不称作纯认知信号。首次真实验证还应补记录内时间块验证、有效置换和人工伪迹审查；这些没有冒充已实现。

## C：重叠校正与机制内核

```sh
# 将路径替换为真实文件；通常位于 C 题附件的下级目录。
python research_ac/c_deconvolve.py '实际路径/VisualCogA_Task-1.mat' --out research_ac/runs/c_deconvolution
```

输出 `kernels.npz` 与 `report.json`。模型同时拟合左右刺激、左右按钮的 FIR 核，含截距/趋势；前 70% 时间块训练、后 30% 留出，中间留支持区间缓冲。按钮核允许负时间滞后，**这是已知应答时刻的回顾性解释，不是在线预测**。模板默认 0–0.8 秒和按钮 ±0.3 秒；真实事件慢于此尺度时须预注册更长支持，不能将默认值视作题面规定。

`c_models.py` 还提供 `ei_basis` / `fit_ei` 和含右删失的扩散似然。`fit_ei(..., fixed_tau_i=0.10)` 可固定一个时间常数作敏感性分析；0.10 秒仅是示例假设，不是测得生理常数。真实 ERP 若经过滤波，前向模型必须包含同一观测滤波链，或改为拟合未滤波数据加趋势；本轮 E–I 内核不自动完成这一拼接。

扩散拟合输入 CSV 必须显式具有 `time,choice,cue`：time 是秒，choice 为 -1/+1；未应答用 choice=0、time=可观察截止时刻，cue 为 -1/+1。它是**点击边界**编码，不是正确/错误编码。依据 `events.csv` 转换时，有应答取 `rt_seconds` 与 `action/2`，无应答取 `observation_seconds` 与 0。项目二的正确性仍须另外按任务映射判断。

```sh
python research_ac/c_models.py 'behavior.csv' --out research_ac/runs/ddm_fit.json --memory-tau 0.3 --nondecision 0
```

该命令比较恒定漂移和指数衰减驱动，包含遗漏试次，输出 NLL/AIC/收敛标志；**这是样本内拟合，不是“证实记忆作用”**。需要目标出现标记、不同记忆时间尺度/非决策时间敏感性，以及独立块上的似然和选择/反应时联合检验。`--nondecision 0` 是描述性基线，不能解读为人类没有感知与运动耗时。

## 推荐先看什么

A 先检查失败日志和 `best_plan.json` 的官方复评，再看平均加速比；C 先看 `audit.json` 的事件与应答窗污染，再看分类。最有论文价值的增量是能被反例约束、能由消融验证的结论，而不是最复杂的模型。原始附件、原评估器、已有调研及数据管理脚本在本次提交中保持不变。

补充验证：`results/ddm_cli_smoke.json` 保存 80 个合成行为观测的认知模型 CLI 冒烟测试，两个优化器均返回收敛；样本由同一数值模型族生成，仅验证接口，不是独立精度检验或真实记忆证据。
