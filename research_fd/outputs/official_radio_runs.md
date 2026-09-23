# 正式中继实验实际命令台账

actual log/result files only; no future runs are listed

|实际目录|阶段预算秒|状态|阶段记录|
|---|---:|---|---|
|official_radio_fixed|30|no_incumbent|tardiness:2|
|official_radio_repair_fixed_pool30000|30|no_incumbent|tardiness:1|
|official_radio_repair_fixed_untruncated|60|no_incumbent|tardiness:1|
|official_radio_repair_retime600|60|external_wall_clock_limit||
|official_radio_repair_cpsat_fixed60|60|no_incumbent|joint_makespan:UNKNOWN|
|official_radio_repair_cpsat_reduced60|60|no_incumbent|joint_makespan:INFEASIBLE|
|official_radio_repair_cpsat_retime1200|60|no_incumbent|joint_makespan:UNKNOWN|
|official_radio_repair_cpsat_retime2400_soft|90|no_incumbent|weighted_tardiness_milliseconds:UNKNOWN|
|official_radio_repair_witness_coarse|90|no_incumbent|feasibility_seed:UNKNOWN|
|official_radio_repair_witness_dense_sessions|90|no_incumbent|feasibility_seed:UNKNOWN|

所有时限、候选集和方法范围以JSON为准。无 incumbent / UNKNOWN 不等于原问题不可行；INFEASIBLE 仅指该有限候选与窗口模型。早期浮点容差删列不声称严格保持原连续目标最优；后续CP-SAT按实际整数系数比较。horizon只约束运输返回，不是联合返回硬上限。

## official_radio_fixed

运输输入：`research_fd/outputs/official_transport_s7/best_plan.json`

```powershell
research_fd/.venv/Scripts/python.exe research_fd/outputs/run_official.py d_experiments radio --input research_fd/outputs/d_official.json --plan research_fd/outputs/official_transport_s7/best_plan.json --out research_fd/outputs/official_radio_fixed --mode fixed --grid 3 --sample-step 60 --seconds 30 --max-sessions 6000
```

日志：`research_fd/outputs/logs/official_radio_fixed.log`。

## official_radio_repair_fixed_pool30000

运输输入：`research_fd/outputs/official_transport_s7/best_plan.json`

```powershell
research_fd/.venv/Scripts/python.exe research_fd/outputs/run_official.py d_experiments radio --input research_fd/outputs/d_official.json --plan research_fd/outputs/official_transport_s7/best_plan.json --out research_fd/outputs/official_radio_repair_fixed_pool30000 --mode fixed --grid 3 --sample-step 60 --seconds 30 --max-sessions 30000
```

日志：`research_fd/outputs/logs/official_radio_repair_fixed_pool30000.log`。

## official_radio_repair_fixed_untruncated

运输输入：`research_fd/outputs/official_transport_s7/best_plan.json`

```powershell
research_fd/.venv/Scripts/python.exe research_fd/outputs/run_radio_dominance.py d_experiments radio --input research_fd/outputs/d_official.json --plan research_fd/outputs/official_transport_s7/best_plan.json --out research_fd/outputs/official_radio_repair_fixed_untruncated --mode fixed --grid 3 --sample-step 60 --seconds 60 --max-sessions 1000000
```

日志：`research_fd/outputs/logs/official_radio_repair_fixed_untruncated.log`。

## official_radio_repair_retime600

运输输入：`research_fd/outputs/official_transport_s7/best_plan.json`

```powershell
research_fd/.venv/Scripts/python.exe research_fd/outputs/run_radio_dominance.py d_experiments radio --input research_fd/outputs/d_official.json --plan research_fd/outputs/official_transport_s7/best_plan.json --out research_fd/outputs/official_radio_repair_retime600 --mode retime --grid 3 --sample-step 60 --shift-window 600 --horizon 10800 --seconds 60 --max-sessions 1000000
```

日志：`research_fd/outputs/logs/official_radio_repair_retime600.log`。

外部终止记录：`{"elapsed_s": 449.3352491, "reason": "Large untruncated retiming MILP exceeded total experiment budget; no mathematical infeasibility claim", "last_known_demands": 4933, "status": "external_wall_clock_limit", "wall_clock_limit_s": 360, "last_known_sessions": 44963}`。

## official_radio_repair_cpsat_fixed60

运输输入：`research_fd/outputs/official_transport_s7/best_plan.json`

```powershell
research_fd/.venv/Scripts/python.exe research_fd/outputs/run_radio_cpsat_fixed.py d_experiments radio --input research_fd/outputs/d_official.json --plan research_fd/outputs/official_transport_s7/best_plan.json --out research_fd/outputs/official_radio_repair_cpsat_fixed60 --mode fixed --grid 3 --sample-step 60 --seconds 60 --max-sessions 1000000
```

日志：`research_fd/outputs/logs/official_radio_repair_cpsat_fixed60.log`。

## official_radio_repair_cpsat_reduced60

运输输入：`research_fd/outputs/official_transport_s7/best_plan.json`

```powershell
research_fd/.venv/Scripts/python.exe research_fd/outputs/run_radio_cpsat_fixed.py --site-policy greedy_double d_experiments radio --input research_fd/outputs/d_official.json --plan research_fd/outputs/official_transport_s7/best_plan.json --out research_fd/outputs/official_radio_repair_cpsat_reduced60 --mode fixed --grid 3 --sample-step 60 --seconds 60 --max-sessions 1000000
```

日志：`research_fd/outputs/logs/official_radio_repair_cpsat_reduced60.log`。

## official_radio_repair_cpsat_retime1200

运输输入：`research_fd/outputs/official_transport_s7/best_plan.json`

```powershell
research_fd/.venv/Scripts/python.exe research_fd/outputs/run_radio_cpsat_retime.py --site-policy greedy_double d_experiments radio --input research_fd/outputs/d_official.json --plan research_fd/outputs/official_transport_s7/best_plan.json --out research_fd/outputs/official_radio_repair_cpsat_retime1200 --mode retime --grid 3 --sample-step 60 --shift-window 1200 --horizon 10800 --seconds 60 --max-sessions 1000000
```

日志：`research_fd/outputs/logs/official_radio_repair_cpsat_retime1200.log`。

## official_radio_repair_cpsat_retime2400_soft

运输输入：`research_fd/outputs/official_pareto_cpsat/energy_cap_1.json`

```powershell
research_fd/.venv/Scripts/python.exe research_fd/outputs/run_radio_cpsat_retime.py --site-policy greedy_double --allow-soft-lateness d_experiments radio --input research_fd/outputs/d_official.json --plan research_fd/outputs/official_pareto_cpsat/energy_cap_1.json --out research_fd/outputs/official_radio_repair_cpsat_retime2400_soft --mode retime --grid 3 --sample-step 60 --shift-window 2400 --horizon 15000 --seconds 90 --max-sessions 1000000
```

日志：`research_fd/outputs/logs/official_radio_repair_cpsat_retime2400_soft.log`。

## official_radio_repair_witness_coarse

运输输入：`research_fd/outputs/official_pareto_cpsat/energy_cap_1.json`

```powershell
research_fd/.venv/Scripts/python.exe research_fd/outputs/run_radio_cpsat_retime.py --site-indices-file research_fd/outputs/review/radio_temporal_candidate_pairs.json --allow-soft-lateness --transport-step 300 --cover-blocks --feasibility-first d_experiments radio --input research_fd/outputs/d_official.json --plan research_fd/outputs/official_pareto_cpsat/energy_cap_1.json --out research_fd/outputs/official_radio_repair_witness_coarse --mode retime --grid 3 --sample-step 60 --shift-window 2400 --horizon 15000 --seconds 90 --max-sessions 1000000
```

日志：`research_fd/outputs/logs/official_radio_repair_witness_coarse.log`。

## official_radio_repair_witness_dense_sessions

运输输入：`research_fd/outputs/official_pareto_cpsat/energy_cap_1.json`

```powershell
research_fd/.venv/Scripts/python.exe research_fd/outputs/run_radio_cpsat_retime.py --site-indices-file research_fd/outputs/review/radio_temporal_candidate_pairs.json --allow-soft-lateness --transport-step 300 --cover-blocks --feasibility-first --dense-sessions d_experiments radio --input research_fd/outputs/d_official.json --plan research_fd/outputs/official_pareto_cpsat/energy_cap_1.json --out research_fd/outputs/official_radio_repair_witness_dense_sessions --mode retime --grid 3 --sample-step 60 --shift-window 2400 --horizon 15000 --seconds 90 --max-sessions 1000000
```

日志：`research_fd/outputs/logs/official_radio_repair_witness_dense_sessions.log`。
