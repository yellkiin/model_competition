# A 三问实验：Windows 直接运行

本目录覆盖问题 1、2、3，分别调用原评估器、分别输出方案和成绩。统一算法、[理论](THEORY.md)和[详细实验设计](TEST_PLAN.md)不变。当前操作以本页为准，直接运行真实实验，不需要先完成审计、哈希、安全测试、冒烟或单元测试。

## 一条命令

在仓库根目录的 Windows CMD 中：

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a\experiments.ps1 all
```

默认解释器 `D:\python\python.exe`（用户当前 Python 3.12.5），默认并发 2。只用 CPU 和 Python 标准库，无需 CUDA、GPU、Conda 环境或安装机器学习库。参数 `-Workers` 是本机进程数，赛题 `--cores` 是模拟硬件核数，两者不同。

已有附件直接使用；缺少输入时，`launch.py` 优先从本地 `A题.zip` 补齐缺失文件或 LFS 指针；没有可用本地压缩包时才执行限定 A 的 `git lfs pull`。不读取其他题的数据，不恢复其他题的分片。真实输入不因 ZIP 存在就被覆盖。准备动作只为加载必需输入，不做内容比对、哈希或完整数据盘点。

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a\experiments.ps1 all -Archive "D:\你的目录\A题.zip" -Workers 2
```

不在根目录的 ZIP 用 `-Archive` 指定。根目录下的 ZIP 无需该参数。`setup_windows.ps1` 仅是补齐 A 输入的可选入口，**不用先运行它**；保留 `-SkipPull` 参数只为旧命令兼容，不再自动更新 Git 或下载全部题目。

## 阶段和固定参数

|命令末尾的阶段|执行内容|
|---|---|
|`all`|依次 dev → main → cross，前一阶段正常返回后进入下一阶段|
|`dev`|20 开发图、问题1/2/3、2/4核、3种子；每个方法最多24次调用|
|`main`|100图、问题1/2/3、1–5核，RR与full；full最多32次调用，seed=0|
|`cross`|主实验三个来源方案的3×3同方案评分及收益分解|
|`granularity`|开发集粒度扫描，单独运行，不包含在all中|

主实验最多49,600次原评估调用，开发阶段最多28,820次，交叉回放最多额外3,000次。这里是调用预算，不是耗时承诺。默认不自动追加修正预算，不根据开发结果自行改变主实验配置。

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a\experiments.ps1 dev
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a\experiments.ps1 main
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a\experiments.ps1 cross
```

## 输出、续跑与失败

结果默认 `research_a/runs/`。阶段日志为 `dev.log / main.log / cross.log`，运行时同步显示原始输出；Python 子进程统一启用 UTF-8，避免 Windows 中文输出按其他编码解码。每图作业仍保存原评估器的完整结果和错误。

`dev_report/diagnosis.csv` 解释差例，`main_report/summary.csv` 给三问主表，`cross_report/cache_decomposition.csv` 分解缓存/重新优化收益。实际无效候选不被当成性能成绩；不完整主表保留缺项。

输入、算法、配置和环境不变时，重复相同命令可复用已完成作业；失败中断的作业按原运行器规则另存旧attempt后重跑。不要将“复用完成状态”当作文件变更检测。Windows与旧Linux输出不要混用：改 `-OutRoot "research_a\runs_windows"`。

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a\experiments.ps1 all -Workers 1 -OutRoot "research_a\runs_windows"
```

原评估候选失败会进入原日志；若阶段程序本身退出失败，启动器停止后续阶段并显示日志位置。修正入口/解释仍见 TEST_PLAN，追加预算另存，不能覆盖主表或改变官方评分器。

## 本地 Agent

直接复制 [LOCAL_PROMPT.md](LOCAL_PROMPT.md)。它要求实际启动 A，而不是生成另一份核验计划。生成结果留在本地，不自动提交 Git，不运行其他题流程。

此前26项理论检验通过、1项原程序集成检验跳过的记录仍见 `results/local_tests.txt`；那是历史开发记录，不是本次Windows实机或100图性能结果。新启动器不把该记录作为运行前置条件。
