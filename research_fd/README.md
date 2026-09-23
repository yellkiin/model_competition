# F / D 深度研究与可复现验证原型

2026-09-23。新增目录，不修改原始题目、数据、既有调研或 `research_ac/`。基线提交与证据边界见 [REPOSITORY_STATE.md](REPOSITORY_STATE.md)。

## 先看结论，再看代码

建议优先推进 **F：可信度分层的质量—独立数据量—重复训练资源配置**，把“哪些关系能识别、假设改变会不会改变推荐配置”作为主线。D 的建议主线是 **地形保守验证—通信区间证书—能源资源调度—冻结计划独立资源代价**；需要团队持续维护几何与调度两条工程链。这是本轮方法判断，不是正式算例成绩比较。

|文档|内容|
|---|---|
|[REPORT_F.md](REPORT_F.md)|Q与配比不可辨识性、混合律参考系、独立数据供给、条件优化及能力前沿回测设计|
|[REPORT_D.md](REPORT_D.md)|全部相交像元、连续通信充分条件、可交换电池占用、合法反馈割和冻结分区|
|[LITERATURE.md](LITERATURE.md)|16组原始论文/官方资料，逐项标明版本、用途、局限与实际阅读范围|
|[results/local_validation.json](results/local_validation.json)|实际执行的合成实验及34行附件审计的原始数值|
|[results/pytest.txt](results/pytest.txt)|39项测试全部通过的运行记录|
|[results/resource_cli_smoke.json](results/resource_cli_smoke.json)|故意设置的电池复用冲突被检测出的CLI结果|

本材料是辅助研究和可运行原型，**不是可直接提交的竞赛论文，也没有求出正式F最优配置或D联合可行调度**。题面具体要求仍须团队逐项对照原文；既有调研转述的AI使用限制和披露要求也应独立核验、遵守。

## 已验证到什么程度

|项目|本轮状态|不能据此声称|
|---|---|---|
|B1前34行五列投影|真实附件摘录：34个逐行不同run_id，但只有一个N规模|完整B1已核源、run_id是独立轨迹、五参数可由单规模识别|
|五参数标度拟合|合成真值恢复；规模/时间切分入口通过合成模式集成测试|完整真实B1已拟合、质量因果效应已识别|
|RegMix读取与回归|真实路径/表头对齐；配方分组、索引连接在合成模式上测试|LightGBM完整复现、真实测试误差已得到|
|质量成本与供给|9组成本×预算；3种供给×3种子；全部是条件合成实验|表内Q/N是题目正式最优解|
|D几何|304例与独立矩形裁剪oracle一致；合成GeoTIFF入口测试|真实DEM坐标、节点或全部航段已验证|
|D通信|仿射运动、题给最坏遮挡代理下的单链路区间充分证书|完整运输—中继网络连续可用|
|D资源|半开区间着色、指定电池冲突、冻结超边缩并|完整能耗、时限、逐箱交付与联合调度可行|

关键合成结果：Q与配比设计矩阵4列、秩3；经典预算解析/数值最优N相对差小于6.1e-8；窄峰反例中五点采样最高0m、全部相交像元最高100m；两个不重叠飞行区间只需1架机，但其充电占用需2组电池。数值来源均在JSON中，不能与官方附件结论混用。

## 拉取与环境

在已有仓库内执行。若当前有未提交改动，先自行保存，不要使用强制切换。

```bash
git fetch origin
git switch --track origin/research/fd-deep-validation-20260923
# 若本地已经存在该分支，改用：
# git switch research/fd-deep-validation-20260923

python -m venv .venv-fd
source .venv-fd/bin/activate
python -m pip install -r research_fd/requirements.txt
```

Windows PowerShell 激活命令为 `.venv-fd\Scripts\Activate.ps1`。以下命令都在**仓库根目录**运行，不要直接运行目录内某个依赖相对导入的 `.py` 文件。

本轮实际测试环境为 Python 3.13.5、NumPy 2.3.5、SciPy 1.17.0、pandas 2.2.3、pytest 9.0.2、rasterio 1.5.0，详见 [environment.txt](results/environment.txt)。依赖范围不等于每个组合都经过测试。所有本轮实验使用CPU，无PyTorch、无GPU依赖。

## 1. 先复跑测试和机制实验

```bash
python -m pytest -q research_fd/test_fd.py
python -m research_fd.experiments --out research_fd/outputs/local_validation.json
python -m research_fd.run_data d-resources \
  --input research_fd/examples/d_inputs.synthetic.json \
  --out research_fd/outputs/resource_smoke.json
```

最后一个输入**故意让两趟任务共用尚未充满的B1**，预期 `valid_occupancy=false`，并报告 `A: overlapping battery B1`。它不是程序运行失败。把第二个任务改用B2，资源占用检查才应通过；仍不代表其他物理约束通过。

记录结果时可在Linux命令前加 `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1` 控制数值库线程。优化器和线性代数版本差异可能导致最后几位与运行耗时变化，重点核查误差阈值和可行性。不要覆盖提交内的 `results/`，个人运行输出写 `outputs/`（已忽略）。

## 2. F：在你们的完整附件上运行

```bash
python -m research_fd.run_data f-scaling \
  --repo . --starts 6 --bootstrap 0 --seed 20260923 \
  --out research_fd/outputs/f_scaling.json

python -m research_fd.run_data f-mixtures \
  --repo . --seed 20260923 \
  --out research_fd/outputs/f_mixtures.json
```

`f-scaling`读取 `题目/F题/real_attachments/B_scaling_laws/pythia_training_log_existing.csv`。输出每规模留出、同规模时间前推、随机行诊断、全部数据拟合，以及同名 `.predictions.csv`。确认输入/分组语义后，可以把 `--bootstrap 0` 改成 `--bootstrap 200` 得到规模块重采样诊断；这不是独立模型族验证或因果区间。

`f-mixtures`读取 `题目/F题/real_attachments/A_data_value/regmix_tables/` 的train_1m及test_1m/60m/1B配方与Loss表。固定13个连续目标，按index严格一对一连接，记录配比舍入归一化量与重合配方数，输出全部测试/新配方子集。超出0.01的配比闭合误差、无效值、重复或不匹配索引会停止，不静默删数据。

对60M/1B的结果是**未校准尺度迁移诊断**，优先检查排名；代码没有用大规模测试标签调参，也没有用估算10B/70B数据充当真实验证。入口只实现线性/CLR ridge，不是RegMix作者的完整LightGBM方案。

目前未实现：A1—A3全量Q、跨来源质量校准、带来源层的广义标度拟合、C8聚合与能力前沿。报告给出研究设计，但不能把它们写入“已经跑通的代码”清单。

## 3. D：原始附件接入前先确定坐标和参数

大文件需有Git LFS并下载实体：

```bash
git lfs pull
```

读取函数会识别LFS指针并停止。只有取得实体，才能核验坐标、高程基准、NoData、节点高程和工作高度；本轮未完成这一步。

`d-arcs`要求**投影米制CRS**。将实际Excel中的节点转换为与GeoTIFF同CRS的x/y，保存为以下结构；示例数值不得当作正式节点：

```json
{
  "nodes": [
    {"id": "O01", "x": 500015, "y": 3499985, "work_height_m": 0},
    {"id": "S001", "x": 500105, "y": 3499895, "work_height_m": 30}
  ]
}
```

```bash
python -m research_fd.run_data d-arcs \
  --dem "/实际路径/已核验米制DEM.tif" \
  --nodes "/实际路径/已核验节点.json" \
  --out research_fd/outputs/d_arcs.json
```

若原DEM为经纬度，本原型会拒绝。不能只修改CRS标签，也不能未经误差评估做普通插值重投影；报告讨论了需补充的保守映射。当前没有自动读取D题Excel的适配器。

固定资源检查输入为 `tasks` 和 `capacities`，字段示例见 [examples/d_inputs.synthetic.json](examples/d_inputs.synthetic.json)。所有时间须使用同一原点、同一单位；`aircraft_end`包含所采用的实体周转约定，`battery_ready`须由独立核验的充电规则计算。不同机型分别计数，初装电池包含在库存内的口径须对题。

本轮仅交付单链路证书、载荷能耗内核、一般两阶段充电函数、区间资源与超边分量。未交付Q1装箱、Q2完整调度、Q3中继候选优化/全网络检查、Q4完整分组搜索，也未填结果模板。一般充电示范参数不等于题面参数。

## 文件结构与后续实验顺序

`f_models.py`负责统计/优化内核，`d_core.py`负责几何/通信/资源内核，`run_data.py`负责只读附件入口，`experiments.py`生成机制实验，`test_fd.py`提供39项测试。输入文件有SHA256，测试代码Git哈希见 [code_manifest.json](results/code_manifest.json)。

下一步建议先执行F的两个真实附件入口，用得到的误差、重合配方和参数边界决定是否继续复杂化；D先把实际DEM/节点/充电参数口径固定，再接正式逐箱调度。对任何无法验证的步骤保留“未验证”，不要用合成通过替代附件通过。
