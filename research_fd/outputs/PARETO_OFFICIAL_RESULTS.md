# 正式附件：共同质量约束下的运输能耗与工期双目标

锚点来自实际执行的 official_transport_s7/best_plan.json：27 趟、工期 8310.169077 秒、能耗 75.069164118 kWh，软/硬迟到均为 0。

所有试验固定同一 600 条路线池、60 秒启动网格、共同加权软迟到上限 0（数值容差 1e-5）和原硬截止，保留全部箱覆盖、共享机身/电池容量。cap=锚点工期×倍率。此锚点特意使用同网格方案；没有用稍快的连续/整秒方案改写实验上限。

|实际后端与预算|cap倍率|能量阶段状态|独立运输检查|实际工期/s|能耗/kWh|能量界/kWh|界差距|
|---|---:|---|---|---:|---:|---:|---:|
|HiGHS 60s|1|1|invalid/80箱未交付|无 incumbent|无 incumbent|—|—|
|HiGHS 60s|1.1|1|invalid/80箱未交付|无 incumbent|无 incumbent|—|—|
|HiGHS 60s|1.25|1|invalid/80箱未交付|无 incumbent|无 incumbent|—|—|
|HiGHS 60s|1.5|1|invalid/80箱未交付|无 incumbent|无 incumbent|—|—|
|HiGHS 精确预删120s|1|1|invalid/80箱未交付|无 incumbent|无 incumbent|—|—|
|HiGHS 精确预删120s|1.1|1|invalid/80箱未交付|无 incumbent|无 incumbent|—|—|
|HiGHS 精确预删120s|1.25|1|invalid/80箱未交付|无 incumbent|无 incumbent|—|—|
|HiGHS 精确预删120s|1.5|1|invalid/80箱未交付|无 incumbent|无 incumbent|—|—|
|CP-SAT 30s/30s|1|FEASIBLE|通过|8237.190525|71.245007450|69.968850|1.791%|
|CP-SAT 30s/30s|1.1|FEASIBLE|通过|8237.190525|71.435370640|67.204267|5.923%|
|CP-SAT 30s/30s|1.25|FEASIBLE|通过|8237.190525|71.286982875|64.470695|9.562%|
|CP-SAT 30s/30s|1.5|FEASIBLE|通过|9847.271255|71.834316772|61.705788|14.100%|
|CP-SAT warm180s/30s|1.5|FEASIBLE|通过|8237.190525|71.245007450|68.762715|3.484%|

## 失败与修复的实际结论

首次 HiGHS 四点均在能量阶段限时退出、没有 incumbent；共同质量精确预删后加到 120 秒的四点也没有 incumbent，均完整保留原空计划、求解状态和 80 箱未交付的独立导出。原 CSV 中空计划的能耗/工期为 0，是空集合求和，不参与成绩排序。

baseline_witness.json 逐项直接核验了同网格基线满足覆盖、迟到、资源与工期约束，且原池与预删修复池的所有路线一致，因此这些无 incumbent 结果是搜索失败，不是正式物理问题不可行。

CP-SAT 使用同一个池和同一网格的可选占用区间，并提供真实可行方案提示；这些点只有后端实际返回 FEASIBLE/OPTIMAL 才写为求解候选。已核验基线另存 known_baseline_plan.json，未冒充 CP-SAT incumbent。能量目标量化至 1e-9 kWh，次级工期至 1 微秒；本例所有有效启动的迟到均为 0，没有正迟到近似表。

初轮更宽 cap 的能耗反而略差，已保留全部负结果。更宽 cap 包含更窄 cap 的可行域，但限时 incumbent 不必单调，不能把这些点连线称为全局连续 Pareto 前沿。warm180 仅改变提示和能量阶段预算，原锚点、候选池与共同质量保持不变。

## 已观察到的取舍

当前最低能耗的已验证候选为 [official_pareto_cpsat/energy_cap_1.json](official_pareto_cpsat/energy_cap_1.json)：71.245007450 kWh、8237.190525 秒，较锚点节能 5.094%。

本次实际候选中有 1 个不同的未被其他已验证候选支配的目标坐标（相同坐标去重，但不删除原候选）：

- [official_pareto_cpsat/energy_cap_1.json](official_pareto_cpsat/energy_cap_1.json)：8237.190525 秒，71.245007450 kWh。

目前仅发现一个非支配点，不能据此画出“工期越长能耗越低”的趋势，也未证明更长工期不可能节能。
最大 cap 的180秒能耗修复仍返回 71.245007450 kWh；该受限模型的能量界为 68.762715228 kWh，剩余相对差距 3.484%。这量化了搜索尚未完成，不能据此宣布不存在更好的能耗—工期取舍。

全部可行点均已逐箱、机身/电池库存、释放与硬截止、载荷、路线能量及充电周转独立复核；各 export_cap*/ 中保留 CSV 与 validation.json。所有这些点仅完成运输检查，通信需另行联验；本报告没有把运输能耗或工期冒称运输—中继联合值。

原始日志在 logs/official_pareto*.log/json；各 cap 的阶段状态、bound、gap 和候选本体在对应目录，失败与较差方案均未覆盖或删除。
