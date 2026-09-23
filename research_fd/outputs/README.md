# D 题实际执行档案

入口：[本轮总报告](REPORT_D_EXECUTED.md)。本目录保存真实运行的输入映射、适配代码、成功与失败候选、求解状态、校验 CSV、日志和 PNG/PDF。正式数据与合成实例分开记录。

- 正式 Q2 最佳已验证候选：80 箱、26 趟、8237.190525 s、71.245007 kWh，硬迟到和加权软迟到均为 0，尚未证明全局最优。
- 正式中继累计 10 次尝试仍没有联合可行解；Q3 联合值及 Q4 两/三分组资源是 `null`，没有以合成结果补齐。
- 原始实验基于 `4012819`，保存的 `runtime/research_fd/` 包含本轮正式物理适配。发布分支基于更新的 main，不改写原始实验的版本、路径和哈希证据。

优先阅读 [运输结果](TRANSPORT_EXECUTION_REPORT.md)、[能耗—工期实验](PARETO_OFFICIAL_RESULTS.md)、[通信负对照](COMMUNICATION_BASELINE_PRECISION.md)、[中继命令台账](official_radio_runs.md) 和 [参数来源](official_parameter_sources.md)。选用方案及逐箱/资源导出在 `official_pareto_cpsat/energy_cap_1.json` 和 `official_pareto_cpsat/export_cap1/`。机器入口是 `execution_summary.json`、`execution_inventory.json`、`final_artifact_check.json`。

## 在其他电脑复核

原始 `d_official.json` 中的 DEM 路径，以及日志与 validation 中的工作目录，保留执行时的本机绝对路径。**不要覆盖这些历史文件来伪装成新运行。** 用实际附件映射重新规范化，生成适合当前检出路径的新输入；它的哈希会因路径改变而不同。原始附件仍在仓库 `题目/D题/`，DEM 由 Git LFS 管理。

从仓库根目录，在 Windows PowerShell 中执行（本轮使用 Python 3.12）：

```powershell
git lfs pull --include="题目/D题/**"
py -3.12 -m venv research_fd/.venv
& research_fd/.venv/Scripts/python.exe -m pip install -r research_fd/outputs/logs/environment_freeze.txt
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONIOENCODING = 'utf-8'
New-Item -ItemType Directory -Force research_fd/outputs/replay, research_fd/outputs/tmp | Out-Null

& research_fd/.venv/Scripts/python.exe research_fd/outputs/normalize_official.py --mapping research_fd/outputs/official_mapping.json --out research_fd/outputs/replay/d_official.json
& research_fd/.venv/Scripts/python.exe research_fd/outputs/run_logged.py replay_validate -- research_fd/outputs/review/export_validate_plan.py --input research_fd/outputs/replay/d_official.json --plan research_fd/outputs/official_pareto_cpsat/energy_cap_1.json --out research_fd/outputs/replay/export_cap1 --runtime research_fd/outputs/runtime --skip-radio
```

`--skip-radio` 只复核已有 Q2 运输方案，不代表通信已通过。要重新求解，使用总报告及 `logs/*.json` 中的实际参数，通过 `run_official.py` 导入此目录的适配 runtime，并给每次新运行使用新的输出目录和日志标签。`run_logged.py` 会拒绝覆盖已存在的日志。限时、多线程优化的 incumbent 不保证每次完全相同，不能把历史 FEASIBLE 写成新一轮 OPTIMAL。

虚拟环境、安装缓存、临时文件和字节码不属于发布档案。`research_fd/.gitignore` 继续默认忽略新输出；本轮仅显式提交经审查的档案文件。本目录 `.gitattributes` 禁用行尾自动转换，保持历史文件和校验哈希一致。
