# 正式输入图件：本次已执行的运输结果

后续能耗实验得到更优已知 Q2 计划，另存 `q2_selected_aircraft_battery_gantt.png/.pdf`、`q2_selected_routes.png/.pdf` 和 `q2_selected_figure_provenance.json`：26 趟、8237.190525 s、71.245007 kWh，来源为 `official_pareto_cpsat/energy_cap_1.json` 和 `export_cap1/`。两张 PNG 已查看。原 `q2_*` 图保留为首轮时间优先组的结果。新方案未配置中继时的九精度通信负对照在 `official_radio_baseline_no_relay_precision/`，最细 5 s/7.5 m 共 7075 样本、2601 断联；不能把 Q2 图当成联合通信已通过。

所有图均只读取本次 `outputs/` 的实际结果，采用 `d_official.json` 的正式附件映射与已声明的物理模型解释；没有借用合成参数或旧实验数字。当前图件是 **Transport only / Q2**，不能作为 Q3 通信可行性证明。

- `transport_method_comparison.png` / `.pdf`：11 项结果，来自 `official_transport_s7`、`official_transport_cpsat`、`official_retime_grids`。静态贪心、静态集合划分、对偶扩列与资源派单的硬截止违约分别为 15、18、16、1；橙色斜线明确表示不可行。完整 HiGHS 与 10 s 网格重排限时无 incumbent，用 N/A 表示，不画零值优胜柱。完整 CP-SAT 保存前阶段可行解，工期阶段 UNKNOWN，10,354.50972 s、90.31621 kWh，劣于 ALNS。
- `q2_aircraft_battery_gantt.png` / `.pdf`：当前固定路线 CP-SAT 计划，27 趟、8,258.19052 s、75.06916 kWh。图中 U01—U08 与附件机身 ID 一致；A-B01 等电池标签是导出编号，不是官方序列号。机身灰段为准备，彩段为飞行/服务；电池彩段包含准备至返仓的占用，斜线段为充电。虚线是运输全部返仓，末次充电可晚于此线。CP-SAT 最优状态仅适用于该固定路线与整秒向上取整模型，不能作为完整路线问题的全局最优声明。
- `q2_routes.png` / `.pdf`：依据验证后的航段 CSV 绘制水平投影，按全部/机型 A/B/C 分图；各实体机身使用相同颜色。箭头表示巡航方向，相同机身的重复边合并显示。路线表仍保留每架次与三维高度，平面图不能证明地形净空或通信连续性。
- `transport_method_comparison.json`、`q2_figure_provenance.json`：保留原始数值、求解阶段、N/A 映射、计划、来源 SHA256、runtime 模型路径及 job→图标签映射。

制图调用 `official_best_transport_export/` 的现有 CSV；其 validation 状态为 `transport_valid_radio_not_checked`。未重写或重算运输物理模型。三个 PNG 已逐张查看，确认标签、N/A、实体编号与图注可见。

重建当前图：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
& research_fd/.venv/Scripts/python.exe -B research_fd/outputs/official_summary/plot_official.py
```

脚本内将 MPLCONFIGDIR、TEMP、TMP 固定到 `official_summary/`，结果只写该目录。后续联合计划必须先导出 CSV 并取得 `joint_valid=true`，再调用：

```powershell
& research_fd/.venv/Scripts/python.exe -B research_fd/outputs/official_summary/plot_official.py --scope q3 --prefix q3 --plan research_fd/outputs/实际联合目录/joint_plan.json --export research_fd/outputs/对应联合导出目录 --skip-comparison
```

Q3 接口拒绝 radio 未通过的导出，运行后另存 Q3 图件；当前尚未生成 Q3 图或 Pareto 图。
