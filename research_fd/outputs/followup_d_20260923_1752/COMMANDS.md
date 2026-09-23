# 已执行命令（PowerShell，仓库根目录）

虚拟环境解释器均为 `research_fd/.venv/Scripts/python.exe`；执行前已按任务要求 `git fetch origin`、切换并快进到 `research/d-four-questions-20260923`。

```powershell
& research_fd/.venv/Scripts/python.exe research_fd/outputs/followup_d_20260923_1752/q1_exact.py
& research_fd/.venv/Scripts/python.exe research_fd/outputs/followup_d_20260923_1752/q1_validate.py
& research_fd/.venv/Scripts/python.exe research_fd/outputs/followup_d_20260923_1752/q2_search.py --seconds 180
& research_fd/.venv/Scripts/python.exe research_fd/outputs/review/export_validate_plan.py --input research_fd/outputs/d_official.json --plan research_fd/outputs/official_pareto_cpsat/energy_cap_1.json --out research_fd/outputs/followup_d_20260923_1752/q2_baseline_export --skip-radio --runtime research_fd/outputs/runtime
& research_fd/.venv/Scripts/python.exe research_fd/outputs/review/export_validate_plan.py --input research_fd/outputs/d_official.json --plan research_fd/outputs/followup_d_20260923_1752/q2_candidate_fast.json --out research_fd/outputs/followup_d_20260923_1752/q2_fast_export --skip-radio --runtime research_fd/outputs/runtime
& research_fd/.venv/Scripts/python.exe research_fd/outputs/review/export_validate_plan.py --input research_fd/outputs/d_official.json --plan research_fd/outputs/followup_d_20260923_1752/q2_candidate_energy.json --out research_fd/outputs/followup_d_20260923_1752/q2_energy_export --skip-radio --runtime research_fd/outputs/runtime
& research_fd/.venv/Scripts/python.exe research_fd/outputs/followup_d_20260923_1752/q3_compact.py --seconds 90
& research_fd/.venv/Scripts/python.exe research_fd/outputs/followup_d_20260923_1752/q3_compact.py --seconds 90 --allow-soft
& research_fd/.venv/Scripts/python.exe research_fd/outputs/followup_d_20260923_1752/q3_compact.py --seconds 120 --allow-soft --single-window 1200 --slots-per-aircraft 8
& research_fd/.venv/Scripts/python.exe research_fd/outputs/followup_d_20260923_1752/q3_diagnose.py
& research_fd/.venv/Scripts/python.exe research_fd/outputs/followup_d_20260923_1752/q3_compact.py --seconds 120 --allow-soft --single-window 1200 --slots-per-aircraft 8 --all-sites
& research_fd/.venv/Scripts/python.exe research_fd/outputs/followup_d_20260923_1752/q3_compact.py --seconds 120 --allow-soft --single-window 1200 --slots-per-aircraft 8 --split-blocks
& research_fd/.venv/Scripts/python.exe research_fd/outputs/followup_d_20260923_1752/q3_compact.py --plan research_fd/outputs/followup_d_20260923_1752/q2_candidate_energy.json --seconds 120 --allow-soft --single-window 1200 --slots-per-aircraft 8
& research_fd/.venv/Scripts/python.exe research_fd/outputs/followup_d_20260923_1752/q3_compact.py --seconds 120 --allow-soft --single-window 1200 --slots-per-aircraft 8 --all-sites --split-blocks
```

各命令对应日志和模型状态文件均在本目录；`q3_diagnose.py` 中的资源放松只用于失败定位。没有执行独立 Q4 求解，因为正式 Q3 冻结门槛未达到。
