# F / D 深度调研与可运行实验

本PR只新增/整理 `research_fd/`，沿用仓库 `research_ac/` 的独立工作区命名。F原研究保留；本轮重点把D从方法内核推进到**箱组、机身/电池排程、中继出返仓、联合调时、多目标和固定分区**的完整合成实验。

## 入口

|任务|入口|
|---|---|
|D理论与模型|[REPORT_D.md](REPORT_D.md)|
|D文献与方法对应|[docs/d_literature.md](docs/d_literature.md)|
|D实际结果及失败修复|[docs/d_results.md](docs/d_results.md)|
|本地Agent直接执行|[docs/d_local_agent.md](docs/d_local_agent.md)|
|安装与依赖|[docs/d_environment.md](docs/d_environment.md)|
|F原研究|[REPORT_F.md](REPORT_F.md)、[LITERATURE.md](LITERATURE.md)|

## D快速开始

```bash
bash research_fd/scripts/setup_d.sh
source research_fd/.venv/bin/activate
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python research_fd/scripts/run_d_local.py --size small --seconds 10 --radio
```

Windows提供 `scripts/setup_d.ps1`。环境全部在 `research_fd/.venv/`，个人实验全部在 `research_fd/outputs/`。不需要GPU、商业优化器、Office或API密钥。完整DEM和CP-SAT安装可选依赖。

已运行5个80箱实例的25组方法对照、3个12箱实例的21组对照，以及完整模型超时/固定路线修复、能耗取舍、中继瓶颈修复和分区。派单→ALNS的5例配对平均：加权迟到下降81.81%、工期下降26.19%、能耗下降32.90%。这些是**合成算例结果，不是正式附件成绩**，不能外推为获奖或官方提升保证。

正式附件接入：

```bash
python -m research_fd.d_data inspect --repo . --out research_fd/outputs/official_extract
# Agent读取实际字段，填写 configs/d_official_mapping.template.json 的副本后：
python -m research_fd.d_data normalize --repo . \
 --mapping research_fd/outputs/official_mapping.json \
 --out research_fd/outputs/d_official.json
python research_fd/scripts/run_d_local.py \
 --input research_fd/outputs/d_official.json --out research_fd/outputs/official --seconds 30
```

原始二进制附件本轮未完整取得，因此模板列名明确留待实际读取，并未冒称已经适配官方Excel。充电、能耗和通信口径必须对照原题。完整任务说明在本地Agent手册，不以手填合成值绕过缺失数据。

## 目录约定

`d_model.py/d_geometry.py`：物理与地形；`d_routes.py`：路线池/集合划分/对偶扩列；`d_schedule.py`：派单、ALNS、时间索引MILP、可选CP-SAT；`d_radio.py`：中继会话和联合调时；`d_partition.py`：固定计划分区；`d_uncertainty.py`：情景重放；`d_data.py`：原文/表格提取与映射；`d_experiments.py`：统一CLI。`docs/`放方法手册，`configs/`放输入与映射示例，`scripts/`放安装和一键入口，`results/`只放本次有解释价值的实验记录。

原 `d_core.py/run_data.py` 为上一轮内核保留；新的D完整实验统一使用 `d_experiments.py`，避免混用两套输入格式。现有F代码接口不变。

## F保留的运行入口

F另需原requirements.txt中的pandas等依赖：

```bash
python -m pip install -r research_fd/requirements.txt
python -m research_fd.run_data f-scaling --repo . --starts 6 --bootstrap 0 \
 --out research_fd/outputs/f_scaling.json
python -m research_fd.run_data f-mixtures --repo . \
 --out research_fd/outputs/f_mixtures.json
```

F的全量附件拟合本轮未执行。旧results/local_validation.json记录原先合成机制实验与B1的34行摘录；不把它当全量F验证。新D不增加哈希登记或启动测试流程，把精力放在算法效果和可复现实验。


## 2026-09-23：基于正式实验结果的四问跟进

main 已包含正式 D 输入和执行结果；当前正式 Q2 最佳已验证方案为 26 趟、8237.190525 s、71.245007450 kWh，零硬迟到与零加权软迟到。正式 Q3 的 10 次联合中继尝试尚未取得可行 incumbent，最后一次模型保留约 13.6 万会话，因此下一阶段重点从“继续枚举会话”切换到紧凑中继时空模型。

- [四问深化与下一阶段算法](docs/d_four_questions_followup.md)
- [可直接交给本地 Agent 的提示词](docs/d_followup_agent_prompt.md)
- [结构化跟进结果与待复跑候选](results/d_followup_20260923.json)
- [跟进实验编排器](scripts/run_d_followup.py)

本轮跟进明确不增加哈希登记，也不以冒烟测试作为研究任务。Q1/Q2 的新候选数值需要在本地正式 DEM 与当前 runtime 上复跑确认；Q3/Q4 的正式成绩只在通信联合计划通过加密复核后产生。
