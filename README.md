# 数学建模竞赛资料与 A 题实验

当前保留 A、B、C、D、F 题。E 题目录及其专用调研资料已从当前分支移除；A 不依赖其他题目的数据。原题、A 官方评估器和其他保留题目的原始附件不修改。

## 直接运行 A（Windows）

在本地仓库根目录更新代码，暂不下载其他题目的 LFS 数据。以下是 **CMD** 命令：

```bat
set GIT_LFS_SKIP_SMUDGE=1
git switch main
git pull --ff-only origin main
set GIT_LFS_SKIP_SMUDGE=
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a\experiments.ps1 all
```

默认使用 `D:\python\python.exe`（用户当前为 Python 3.12.5），CPU-only，`Workers=2`。不需要 WSL、Conda 激活、CUDA 或 GPU。CPU 型号和内存容量未知，因此默认并发不是对本机性能的测量结果。

`all` 在前台顺序执行 **dev → main → cross**，分别生成开发消融、100 图三问主结果、同方案跨场景结果。不会自动更改参数或把事后修正混入主结果。单独跑主实验可将 `all` 改为 `main`。

已有 A 官方附件直接使用；输入缺失时，优先从仓库根目录的 `A题.zip`（或 `题目/A题/A题.zip`）补齐缺失/LFS 指针文件，不比较、不覆盖现有真实输入。没有本地压缩包时才下载 **A 题** 的 LFS 文件。不会调用全仓库数据盘点、分片恢复、哈希比对或单元测试。

压缩包在其他位置时：

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a\experiments.ps1 all -Archive "D:\你的目录\A题.zip"
```

降低并发：`-Workers 1`。另存一轮实验：`-OutRoot "research_a\runs_v2"`。不要同时向同一个输出目录启动多轮实验；算法、数据或环境改变后用新目录，不与旧结果混用。

## A 的入口与输出

- [本地执行提示词](research_a/LOCAL_PROMPT.md)：直接交给本地 Agent 执行，不再做仓库核验。
- [运行说明](research_a/README.md)、[详细测试计划](research_a/TEST_PLAN.md)、[统一理论](research_a/THEORY.md)。
- `research_a/runs/dev_report/`：开发实验与诊断。
- `research_a/runs/main_report/`：三个问题、1–5 核的结果汇总。
- `research_a/runs/cross_report/`：缓存与重新优化收益分解。
- 每个作业的 `best_plan.json`、`best_result.json`：方案和原评估器输出。

A 的数据是官方自带的 100 个计算图和固定配置，不是“无数据”，但不需要外部训练数据集。正式成绩以本地实际完成的原评估结果为准。

## 其他保留资料

[调研入口](调研/README.md) · [A 基础调研](调研/A题_基础调研与写作方向.md) · [B 基础调研](调研/B题_基础调研与写作方向.md) · [C 基础调研](调研/C题_基础调研与写作方向.md) · [D 基础调研](调研/D题_基础调研与写作方向.md) · [F 基础调研](调研/F题_基础调研与写作方向.md)

`research_ac/`、`research_fd/` 和通用建模 Agent 保留；A 当前执行入口是 `research_a/`。各题按需获取数据，不再要求先完成全仓库下载或恢复。过期的全库大小、分片恢复说明和旧全库文件快照不再作为当前状态发布。[数据使用说明](调研/数据清单说明.md)

历史提交不重写。本次删除不等于清除历史提交或远端 LFS 对象，也不承诺立即减少托管存储计费。原始 ZIP 留在本地即可，不提交生成结果或压缩包。
