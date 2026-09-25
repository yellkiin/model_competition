# 下一轮本地 Agent：固定规则后继续小批次，不扩大

在 `yellkiin/model_competition` 的 `orion/track-memory` 独立工作树继续。先读本目录 README、METHOD、LITERATURE、`results/memory_v13_six_graphs/REPORT.md`、`results/fivecore_final_20260924/REPORT.md` 与 PR #24 COMMON。不要切换或修改其他运行中的工作树。

当前事实同时保留：
- 第一轮六图暖启动只有 5胜/15平/16负，说明“整套内存插件替代 Anytime”没有成立。
- 后续固定到五核、采用 incumbent-safe 选择后，八图×三问共24配置为 19改善、5保留、0选中退步。
- 用户明确要求信任 day01 已发布旧指标，不再把预算浪费在旧方案复现；**新候选仍必须由未修改官方评估器验证**。
- 五核改善不是正式1–5核完整新曲线；未通过迁移验证前不得扩大100图或写三线最终汇总代码。

## 环境、输入与正式种子

Windows 优先沿用 `D:\python\python.exe`、Python 3.12.x、CPU-only。只检查启动必需文件和解释器；不跑 smoke、pytest、unittest、哈希/指纹/checksum、全仓审计或额外 benchmark。环境不符由本地 Agent 在独立目录显式适配，不装 CUDA/Conda/PyTorch，不影响现有实验；实际解释器写入 manifest。

原路径 `题目/A题/通用神经网络处理器下的多核调度问题  附件/data/` 中“问题”和“附件”之间有两个空格。只从已含 PR #25 的 main 或明确修复分支取得真实 JSON。大图网页接口为空时按 `tools/A_DATA_ACCESS.md`、`tools/a_input_payloads/MANIFEST.json` 和 `tools/restore_a_inputs.py` 取齐分片并无损还原；不手抄、不改写载荷，不把数据恢复与算法实验混成一件事。

先核对 `research_a_orion_anytime/team_results/day01/latest.json` 与最新 PR/分支/发布索引。旧指标直接使用 `combined_final/per_case.csv`、`lower_tail.csv`、`improvements.csv`、`budget_prefixes.csv`、`cache_pairs.csv`。需要正式旧方案作为暖启动时，从 `selected_plans.zip` 或 shard 原包取得实际选中 plan；种子获取成本按原记录保留，不把其他图耗时均摊进来。

## 已冻结的通用规则

算法不得按 case 编号分支。五核已验证机制只以**方案与官方响应特征**触发：

1. **近下界停止**：若当前可行 Makespan / 可信 global lower ≤ 1.04，直接保留 incumbent，不继续烧官方评估预算。
2. **Spill/驻留修复**：存在官方 Spill、长驻留或共享参数跨多个深度阶段时，优先保持 op 核归属不变，尝试 dependency-depth / parameter-capacity epochs；候选仍需完整官方评估。不能用平均内存代替 L1/UB 峰值。
3. **Q1 Task 边界修复**：同核跨子图仍是 Task 边界。零 Spill 也允许尝试 critical Task release、合法凸拆/并、tensor endpoint affinity；目标不是“Task越少越好”。
4. **Q2/Q3 tensor locality**：同核合并不代表无 Spill。优先基于生产者/消费者集合做整子图迁移或局部合法顺序调整；共享 DDR 与 COPY 排队必须结合官方时间线判断。
5. **接受门槛**：只要官方 Makespan 严格改善才替换 incumbent；Makespan 相同时才用 added-copy bytes 作次级目标。任何代理、预测 Spill、搬运字节下降都不能单独接受。
6. **Q3约束**：FIFO 算法、缓存容量/带宽、张量和操作均不改。每个最终 Q3 新方案都做同方案 no-L2 对照并单列成本；不故意恶化 no-L2 来放大缓存比值。
7. **保留负结果**：少搬运但变慢、Spill更多却变快、候选非法、穷尽、硬超时、无收益都保留。不能按 Spill 字节大小决定优先级。

## 下一步：先迁移验证，再补核数

先选**未参与规则调参**的一小批新差图与好图，重点五核 Q1/Q2，必要时补 Q3。旧 Makespan 直接读 day01，不复现；新方法只跑自己的追加候选。差图/好图编号只用于实验清单，不进入策略分支。

每个新样本先给 60–120 秒或约20次官方评估；若至少两张新差图出现真实改善且好图无明显退步，再补同一条轨迹的 30/60/120/300 秒前缀。困难图才单独放宽600秒。早停后的前缀标记 stopped carry-forward，不能用最终值回填以前时间点。

迁移通过后，在原小清单补 2/3/4 核，保持同一规则与预算：

```powershell
.\research_a_orion_track_memory\run_fivecore_windows.ps1 -Cases 5,51,73,90,92,83 -Questions 1,2,3 -Cores 2,3,4 -Seconds 120 -MaxEvaluations 20 -TotalSeconds 1800 -Workers auto -Out research_a_orion_track_memory\results\small_core_extension
& D:\python\python.exe -m research_a_orion_track_memory.pair_selected --run research_a_orion_track_memory/results/small_core_extension --total-seconds 600 --workers auto
```

未来三机分片必须给三机**同一个排序后的完整清单**，仅 `-ShardIndex 0/1/2` 不同，并给各机独立 Out；不允许三台各自重复完整100图。workers 由实际 RAM/CPU/作业 RSS 自适应，不能与题目 NPU 核数混淆。

## 证据与提交

分别记录构造、候选生成、原评估、输出/失败和总耗时；冷启动与续优化分开。阶段B从阶段A种子继续时，seed成本包含实际取得种子的原 solve + added 时间，不能清零。30/60/120/300 秒必须来自同一持续轨迹。

最终只提交 `research_a_orion_track_memory/` 的代码、Markdown、CSV和原响应位置索引，不重复提交原图、config或论文。大响应按仓库已有结果传输方式处理，不把整个工作区二次打包当作研究前置条件。不自动合并 PR，不上传赛事平台。
