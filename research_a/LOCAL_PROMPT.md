# 本地提示词：只运行 A 实验

你在 Windows 本机的 model_competition 仓库中。现在请实际运行 A 题实验，不要只给命令或计划，不要再次核验整个仓库。

## 环境和范围

使用 `D:\python\python.exe`（Python 3.12.5）。不使用 WSL，不创建 Conda 环境，不安装 CUDA/PyTorch；RTX 3060 不参与计算。默认同时2个CPU评估进程，若内存不足改1个。不要假设已知CPU型号或内存容量。

只操作 A 题实验输出。GitHub的清理已完成，不处理其他题，不做数据盘点、哈希比对、安全测试、冒烟或单元测试。不要删除本地ZIP、旧结果、用户改动，不使用force/reset/clean。不要改原题、100个计算图、config或原评估器。

## 更新代码

在现有仓库根目录，用PowerShell执行以下代码；临时跳过自动LFS下载，只更新main代码。若有用户改动导致更新失败，不覆盖它，说明实际冲突。

```powershell
$PreviousSkipSmudge = $env:GIT_LFS_SKIP_SMUDGE
try {
    $env:GIT_LFS_SKIP_SMUDGE = '1'
    git switch main
    if ($LASTEXITCODE -ne 0) { throw 'git switch main failed' }
    git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) { throw 'git pull failed' }
} finally {
    $env:GIT_LFS_SKIP_SMUDGE = $PreviousSkipSmudge
}
```

不要额外执行全量 `git lfs pull` 或旧的数据恢复脚本。

## 实际运行

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a\experiments.ps1 all -Workers 2
```

`all`按顺序执行dev→main→cross。不要在同一输出目录并行启动多个阶段。配置、随机种子和预算采用脚本默认值，覆盖A的三个问题。已有数据直接用；缺少输入时启动器会从仓库根目录`A题.zip`补齐，ZIP在别处时加`-Archive "实际路径\A题.zip"`。没有ZIP才由启动器下载A的LFS文件，不下载其他题。

此前若有非本轮结果，使用新 `-OutRoot "research_a\runs_windows"`；同一环境和同一配置中断后则重复原命令续跑。不要为“通过”实验删除失败图、换成模拟评估器，或只运行问题1。不要运行未要求的额外修正搜索。

持续读取进程和日志，有实际进展才报告。遇到Windows路径、编码、参数或进程启动错误，定位真实堆栈并做最小兼容性修复；不要改变算法目标、硬件参数或官方评分规则。内存不足优先改`-Workers 1`续跑。阶段程序失败时不要声称后续已完成；原评估候选失败按原流程保留。

## 交付

完成后读取实际输出，分别汇总问题1/2/3在1–5核的加速比、最差图、有效/缺失作业、真实Spill和缓存指标；查看`dev_report`与`cross_report`解释消融和缓存/重新优化收益。不完整结果明确标注，不虚构、不用合成结果填空。

告诉我结果根目录、关键CSV位置和真实错误。只压缩汇总/日志/所需方案，不把原始数据或ZIP混入结果包；不要未经要求提交生成结果或修改到GitHub。
