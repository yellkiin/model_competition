# A 三问统一实验与修正工具

日期：2026-09-23。此目录是 A 的新实验入口；`research_ac/` 的历史 A 原型不再作为本轮运行入口，C 文件不变。

**覆盖问题 1、2、3，而不只是问题 1。** 同一套划分/分核/排序算法分别调用三个原评估器；各问有独立最优方案、分数、诊断和修正。另提供同一方案的三场景交叉评分。代码解决的是可计算的方案搜索与验证，不承诺全局最优，也不将尚未运行的正式数据结果写成已完成答案。

先读 [TEST_PLAN.md](TEST_PLAN.md) 的逐问实验表，再读 [THEORY.md](THEORY.md) 的推导。主程序仅使用 **Python 标准库和仓库原评估器，CPU-only**。不需要 CUDA、RTX 3060、PyTorch、NumPy、SciPy、Conda 或编译器。

## 本轮纠正了旧原型的四个关键问题

1. 官方 `config.txt` 是 `[section]` 加 `key value`，不是带等号的标准 INI。新 `model.settings()` 按真实文件格式读取。
2. 第一问每个输出 Task 可写回一次供多个 Task 使用；第二/三问源码却为每个源核—目标核连接分别生成一对 COPY。不能把第一问的“一写多读”代价直接套到第二问。
3. 第三问查询缓存的是所有符合条件的 COPY_IN，包括跨核中间量和 Spill 换入；键使用 `logical_tid`（存在时）。不是仅对原始输入查询缓存。
4. 当前第三问结果未显式给出 `physical_ddr_bytes`。不能用 `scheduled_copy_bytes` 假装实际 DDR；本程序按该构图规则，用 `scheduled_copy_bytes - cache_stats.hit_bytes` 作字节口径推导，并保留推导来源。官方 `hit_rate` 是字节命中率；另计算次数命中率。

这些结论来自实际评估源码。公式、适用边界及源码位置见 THEORY.md。原始题面 DOCX 的全部图/公式未在本环境重新解码；本轮严格对齐仓库当前三个可执行评估模型。

## 1. WSL 环境

在 WSL Ubuntu/Debian 内进入已拉取本 PR 的仓库根目录。尽量把仓库放在 `~/...`，而不是 `/mnt/c/...`，减少跨文件系统 I/O；这是 Microsoft WSL 文档的建议。

```sh
bash research_a/setup_wsl.sh
source research_a/.venv/bin/activate
git lfs install --local
git lfs pull --include="题目/A题/**" --exclude=""
```

已有 Python >=3.10、venv、Git LFS 时，第一行可加 `--no-apt`。不安装 GPU 驱动，不运行旧目录的依赖安装脚本。本地数学检验使用 Python 3.13.5；其他支持版本尚未在此环境逐个验证。

`--cores` 是**赛题虚拟处理器核数**；`--workers` 是**电脑同时运行几个 Python 评估进程**。二者不要混淆。默认 `WORKERS=2` 是保守起点，不是性能最优结论；内存不足改为 1，确认 CPU/内存余量后可增大。完整 JSON 与官方 Trace 序列化也会占用 CPU/内存。

## 2. 开发实验、三问主实验与交叉实验

```sh
# 开发集：20 图，三问，2/4 核，3 个随机种子，固定预算的评分项消融。
bash research_a/experiments.sh dev

# 主实验：100 图，三问各 1–5 核，RR 基线和 full，seed=0，每个搜索最多 32 次原评估。
bash research_a/experiments.sh main

# 在同一批主实验方案上做 3×3 原评估器交叉回放。
bash research_a/experiments.sh cross

# 切分粒度实验：开发集、三问、2/4/5 核，其他生成规则固定。
bash research_a/experiments.sh granularity
```

每条命令在前台完成后返回，不自动进入下一阶段。开发集用图规模和并行度作确定性分层选择，不读取成绩；剩余 80 图另报结果。主表仍覆盖正式 100 图，但开发集结果不作为未见数据泛化证据。

输出默认在 `research_a/runs/`。换一个实验根目录或并发度：

```sh
OUT_ROOT=research_a/runs_v2 WORKERS=1 bash research_a/experiments.sh main
```

修改算法/数据/原评估器后用新 `OUT_ROOT`。`--resume` 只供**输入和代码不变**时续跑，已经完成的任务不重算；不对源文件做哈希或变更检测。未完成任务保留为 `_attemptN` 后从头重跑。新增 Trace 是独立回放，不计入搜索预算。

主实验候选调用上限：`100 + 100×3×5×(1+32) = 49,600`，分别是单核、RR 与 full；候选重复或空间耗尽时会提前停止。交叉回放额外至多 3,000 次，开发消融至多 28,820 次。这里是**调用数而不是耗时承诺**；每次默认超时 300 秒，是单次上限而非整批时限。默认只保留最优方案/原结果、候选摘要与轨迹，不保留所有大 Trace。

## 3. 输出怎样对应三个问题

以 `research_a/runs/main/case_001/q2_n4_full_s0/` 为例：

- `best_plan.json`：符合官方输入格式的候选最优方案；`q1/q2/q3` 各自独立产生。
- `best_result.json`：原评估器完整返回，含时间线、搬运量、内存统计等；第三问另含 Cache 事件。
- `best_metrics.json`、`best_proxy.json`：实际指标与代理预测分开保存。
- `trajectory.json`、`search.json`：每次实际调用、失败/超时、当前最好时间、搜索开销及使用核数。

`main_report/summary.csv` 给三问各核数的平均加速比、最差图和完整性；`summary_by_split.csv` 分开发/留出图；`paired.csv` 作图级配对对照；`proxy_calibration.csv` 核对边界流量恒等式与缓存预测；`convergence.csv` 用同一次搜索的前缀画预算收益曲线。失败或缺例不悄悄删除，表格不会对不完整图集冒报完整平均分。

`cross_report/cache_decomposition.csv` 给 `T2(P2), T3(P2), T2(P3), T3(P3)`，拆开缓存收益与重新优化收益。`cross_matrix.csv` 保留三问所有同方案交叉成绩及失败原因。

## 4. 效果不好时，直接运行已写好的修正代码

先看 `dev_report/diagnosis.csv`。自动修正默认只选开发集最弱的 12 个非 RR 作业，保留原结果，重评原最优方案作为起点：

```sh
python -m research_a.report repair --source research_a/runs/dev --out research_a/runs/dev_repairs --budget 96 --limit 12 --workers 2
```

也可指定修正方向，例如 Spill：

```sh
python -m research_a.report repair --source research_a/runs/dev --out research_a/runs/spill_repairs --profile spill --budget 96 --limit 12 --workers 2
```

可选：`coarse`（过度切分/等待）、`fine`（负载偏斜）、`locality`（通信）、`spill`（驻留/溢出）、`cache`（并发未命中/时序）、`critical`（关键路/少用核心）、`explore`（局部最优）、`unranked`（停用代理筛选）。这些都是实际实现的候选生成/排序配置，不是空的 TODO。修正仍由原评估器评分；不能保证每种病因诊断正确，具体反证与下一步见 TEST_PLAN.md。

`--split all` 可对主实验做事后诊断，但这属于追加预算探索，不能把逐图事后最好值直接混入原主表。开发阶段选择一个统一配置后，应在所有正式图上重跑。例如：

```sh
MAIN_VARIANT=spill OUT_ROOT=research_a/runs_spill bash research_a/experiments.sh main
```

## 5. 控制机制实验与小图参照

这不是正式 100 图成绩，也不是启动检查，而是检验带宽、关键路、扇出、驻留和缓存时序的因果构造。

```sh
python -m research_a.fixtures --out research_a/runs/mechanism_data
python -m research_a.run prepare --data research_a/runs/mechanism_data --expected 8 --dev-count 2 --out research_a/runs/mechanism_cases.json
python -m research_a.run run --manifest research_a/runs/mechanism_cases.json --questions 1 2 3 --cores 1 2 4 --variants rr full --budget 16 --workers 2 --out research_a/runs/mechanisms
```

限制模型枚举：第八个生成图有四个计算操作。两核、固定拓扑序连续切分的候选数为 `2×3³=54`，三问可分别运行：

```sh
for q in 1 2 3; do
  python -m research_a.run oracle --graph research_a/runs/mechanism_data/case_008.json --question "$q" --cores 2 --out "research_a/runs/oracle_q$q"
done
```

这不是任意划分/任意拓扑序下的全局最优证书。全部调用和失败方案保存在 `oracle_trials.jsonl`；超时、内部异常不能当作数学不可行，所以输出保守地称“枚举族中已观察到的最好值”。

## 6. 本环境实际完成的验证

```sh
python -m unittest -v research_a.test_theory
```

本次实际运行 **26 项通过，1 项因本容器没有原评估器实体而跳过**；共 27 项。检验涵盖三问通信规则差异、FIFO 完成时插入/命中不刷新/容量反例、驻留不重置、计算下界、候选保序、预算前缀与统计口径。跳过项会在完整仓库内调用**未改动的三个原评估器**验证小图公式。没有把跳过项当成通过，也没有运行正式 100 图或报告虚构正式成绩。

记录：[results/local_tests.txt](results/local_tests.txt)。没有安排安全测试、文件哈希校验或冒烟阶段；本目录只服务于模型性能、机制和数值推导的验证。
