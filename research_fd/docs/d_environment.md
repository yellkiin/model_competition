# 本地环境与依赖

## 1. 推荐：独立 CPU 环境

本轮实际执行版本：Python 3.13.5、NumPy 2.3.5、SciPy 1.17.0。HiGHS 随 SciPy 提供，无商业求解器许可、CUDA、PyTorch、LLM API 或数据库要求。脚本仅在 `research_fd/.venv/` 和 `research_fd/outputs/` 写入环境与输出，不在仓库根目录散放文件。

Linux/macOS 在仓库根执行：

```bash
# Python 解释器明确指定；已有合适 Python 时省略 PYTHON=...
PYTHON=python3.13 bash research_fd/scripts/setup_d.sh
source research_fd/.venv/bin/activate
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
python research_fd/scripts/run_d_local.py --size small --seconds 10 --radio
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File research_fd/scripts/setup_d.ps1
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
& research_fd/.venv/Scripts/python.exe research_fd/scripts/run_d_local.py --size small --seconds 10 --radio
```

PowerShell 脚本默认 `py -3.13`。未安装3.13时，使用已安装且符合依赖要求的 Python 创建同目录 venv，再运行该环境的 pip。不要改系统 Python。3.11/3.12 可作为安装替代，但这两个解释器版本未在本轮执行。

## 2. 正式 DEM 与 CP-SAT 后端

```bash
python -m pip install -r research_fd/requirements_d_optional.txt
# 或一开始：bash research_fd/scripts/setup_d.sh --full
```

GIS 部分使用 rasterio1.5.0、pyproj3.7.2；这两版本在当前环境可导入。合成主实验不依赖它们。OR-Tools 使用9.x兼容范围，**本环境未安装，因此CP-SAT未执行**；其整数时间/可选区间实现已包含在 d_schedule.py。安装后显式跑 `--backend cpsat`，检查 solver.status，不将 import 成功当作成绩。

如 GIS wheel 安装失败，优先用 conda-forge 新环境装 `rasterio pyproj`，再装 NumPy/SciPy；不要混装系统GDAL和不兼容的pip GDAL。macOS/Windows/ARM的轮子可用性需实际安装确认，不能保证每种平台都已验证。pip 无网络时在同架构联网机器执行 `pip download -r ... -d wheelhouse`，再用 `--no-index --find-links wheelhouse` 安装。默认脚本不自动改第三方镜像源。

原始大文件先在有 Git LFS 的环境执行 `git lfs pull`。DOCX/XLSX提取使用 Python ZIP/XML，**不要求 Office、LibreOffice 或 LaTeX**。公式保留缓存值与公式原文；缓存缺失时应读取原题，不凭空算作零。

## 3. 求解预算与并行

`--seconds` 是**每个 MILP 目标阶段**的限制，不是整个程序的总耗时；路线生成、地形/通信矩阵计算和多个阶段还会额外用时。ALNS另有迭代数和内部小MILP限时。结果的 per-method elapsed 也不包含所有共用准备时间，不用它宣称端到端速度排名。

先单进程确定方法有效，再由本地 agent 按 seed 启动独立进程，各写独立输出目录。每进程限制 BLAS 线程，避免外层多进程×内层多线程过度抢核。CP-SAT函数默认8工作线程，跑多进程时应减少其workers参数。无需占用A100。

大量 `路线×开始时刻×通信采样` 会造成内存和建模时间膨胀。先以3×3悬停网格、固定运输时刻、40–60秒通信采样取得解，再细化。不能通过增大允许路径损耗或删除硬截止来“修复”内存问题。详细方法降阶顺序见 d_local_agent.md。
