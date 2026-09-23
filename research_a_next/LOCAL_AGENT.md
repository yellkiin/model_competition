# 给本地 Agent：运行新 A 方法的小实验，不覆盖正在运行的旧实验

## 先明确工作区与环境

本任务只操作 `research_a_next/` 及明确指定的新结果目录。旧 `research_a/runs*`、用户ZIP、原始100图、config、官方Step1/2/3和其他题不修改、不删除。若旧进程正在运行，不在它使用的工作目录切换版本；使用独立克隆或独立工作树读取新分支。不要force/reset/clean。

用户当前Windows解释器是 `D:\python\python.exe`、CPython3.12.5 x64，CPU-only。RTX3060不用。不转WSL，不建Conda，不装CUDA/PyTorch。新代码及原评估器只需要标准库。

先执行 `configure_windows.ps1`。如果路径不存在，定位本机已有Python，优先3.12.5 x64，传`-Python`。如只有CPython3.10–3.14 x64，可以在用户许可范围内用`-AllowCompatible`显式确认并记录版本；不可声称与指定3.12.5完全同环境。没有可用解释器则配置一个独立解释器或询问必要的安装权限，保留现有环境。不要因GPU型号不同而安装驱动。

环境脚本只做是否能运行的必要检查，不是全仓库审计；不把单元测试、哈希、安全测试、冒烟作为启动前提。已有A数据直接使用；缺失数据由原 `research_a.launch.ensure_inputs` 从本地A题.zip补齐，否则只拉A题LFS。

## 必须实际执行的小面板

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a_next\configure_windows.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a_next\run_windows.ps1 prepare -Out research_a_next\runs\pilot
powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a_next\run_windows.ps1 run -Out research_a_next\runs\pilot -Workers 2 -Minutes 30
```

不要追加旧 `experiments.ps1 all`。默认只有6图、2/5核、三问，单次20秒、每图40次原评估上限、每图600秒、整机30分钟。先读取 `report/status.json`、`new_vs_baseline.csv`、`diagnosis.csv`。遇内存紧张用workers1，不擅自跳过大图而把均值标完整。

如已有论文原方案，先整理CSV `case,question,cores,plan_path` 并在prepare时加 `-BaselineCatalog`；文件路径相对CSV或绝对路径均可。不得根据PDF均值反推伪造逐例成绩。没有原方案时，默认基线只是按论文描述重实现，特别是bands8的亲和系数并未由原文给出。

需要尝试修正时只挑一个对应方向、至多两张图，另写目录：

```powershell
& 'D:\python\python.exe' -X utf8 -m research_a_next.repair --source research_a_next/runs/pilot --out research_a_next/runs/repair_spill --profile spill --limit 2 --workers 1 --minutes 15
```

候选超时与性能差是不同问题。20秒不足时用repair的默认60秒，每图/总时限仍生效。官方环/容量错误要保留，优先components/少跨核恢复；禁止改原评估器、删依赖、减少tensor size。任何certificate不等式失败都须定位，不允许裁剪界或取消断言后称证明成立。

## 第三问容量与带宽

在已有pilot结果后单独运行，不与旧流程同时写目录：

```powershell
& 'D:\python\python.exe' -X utf8 -m research_a_next.sensitivity --source research_a_next/runs/pilot --out research_a_next/runs/pilot_sensitivity --minutes 10
```

2例×5轴点×固定/适配方案最多20次调用；默认点要与原结果一致，非默认点标NONOFFICIAL。若指定案例因超时无默认方案，明确缺失，不编造曲线。

## 多台电脑

只在协调机器prepare一次。复制整个新实验根中的 `manifest.json` 和可选 `baseline_plans/` 到其它机，不能每台重新随机prepare。代码提交版本相同；数据可位于各自仓库对应路径。2台示例：机器0运行`--shard-index 0 --shard-count 2`，机器1运行`--shard-index 1 --shard-count 2`。不要共享实时可写目录，每台独立结果根。运行参数不改变题目虚拟核数。

合并前复制各机结果到不同文件夹：

```powershell
& 'D:\python\python.exe' -X utf8 -m research_a_next.report --out research_a_next/runs/merged --merge returned/pc0 returned/pc1
```

重叠case或不同manifest须人工决定，不能自动挑最优版本。硬截止会让慢机器产生更多缺失，报告这个事实；不要跨CPU把总墙钟时间作为算法性能对比。

## 汇报与最终门槛

汇报三问分别的成功/失败/缺失、fast/refined相对真实同例基线的比、生成与评估时间、globalLB/feasibleUB/analyticUB、Q3同方案比和命中字节率。pilot不能宣称超过论文100图均值。

只有方法固定后，才prepare `--full` 创建100图1–5核任务；是否启动由用户决定。原题全量表、逐例附录和Q3同方案两条曲线必须完整；任何失败或未跑都保留在missing.csv。结果不自动提交GitHub、不上传赛事平台。
