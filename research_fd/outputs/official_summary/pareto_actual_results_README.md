# 正式运输能耗取舍图

`pareto_actual_results.png/.pdf` 是一张两面板图，读取本次13次真实运行总表。A面板仅画5个独立运输校验通过的结果和两个背景参考；cap1与warm180结果共用同一目标坐标。B面板画各工期上限下的求解下界和实际候选能耗，两者之间不是统计置信区间。

8次HiGHS无incumbent保留在来源JSON中，不绘制空计划的零值。所有数据只代表运输/Q2、不含中继。仅观察到一个不同的非支配坐标，因此没有拟合或连接任何平滑Pareto前沿。

来源路径、SHA256、全部13次状态、排除记录和作图数值保存在 `pareto_actual_results_sources.json`。脚本为 `pareto_actual_results.py`，运行结果只写本目录。未修改 `plot_official.py` 或既有图件。
