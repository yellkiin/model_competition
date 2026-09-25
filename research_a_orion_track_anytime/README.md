# ORION Anytime Wu — 独立研究实现

PR #34，分支`orion/track-anytime_wu`，起点main`b513a98f86183a8c1b41d67a547f06fa9d578e2a`。只新增本目录；原公共求解器、官方文件、其他研究线不改。完整代码可直接导入，不需要运行materialize/apply来源脚本。

## 入口

- `plugin.propose(...)`：只改变已有子图的合法同核顺序及联合自然错峰，保留分组/核归属。
- `selector.select_candidate(...)`：候选族首评、本机成本准入、收缩校准；返回候选索引。
- `runner.py`：旧/新、冷/暖、硬截止、逐前缀、Q3相同计划无L2对照、自动CPU workers与分片。
- `prepare.py`：从原始最终记录找到正式计划，重新目标问题/核数评估，并保存真实FIFO事件诊断。
- `trace.py` / `diagnose.py` / `event_audit.py`：读取原记录与原官方执行时间线；不是LRU或替代官方模拟器。
- `collect_results.py` / `plot_trajectories.py`：从已经存在的原始结果生成表和曲线，不调用求解器。

运行器依赖`psutil==7.0.0`；绘图另需matplotlib。本轮实际Linux/Python3.13.5及Ubuntu/Python3.12 CPU-only。Windows入口`run_windows.ps1`和本地步骤见`LOCAL_AGENT_PROMPT.md`，优先已有`D:\python\python.exe`。启动检查之后直接真实图，不做单元/烟雾/指纹测试。

## 版本不能混用

`--revision v1.1`用于复现七图30秒/16次上限实验，保留已发现的gap归一化差异。

`--revision v2`对齐原solver的U/L阈值，并在incumbent变化后刷新局部流，避免旧FIFO和未充分评估的新邻域触发停滞。该版有独立120秒五图复测；083仍有负结果。

`--revision v3`再加现有8个固定阶段候选的有限前瞻排序，先评估代理较好的代表，昂贵DP仍惰性生成。这是对084候选被时间准入错过的修正，不是新划分算法。它仅有后续小规模冷启动验证，不将其局部结果替换进v1.1完整表。

目录默认并未自动替换公共ORION，脚本显示指定版本。除非同条件结果支持，不声称统一算法全面更好。

## 数据与结果

主数据：day01/combined_final五张表与两机最终原始包，读取与解释都注明源阶段。输入导出run36104651803/artifact10850846702不是实验。现存最新PR31/32摘要中的更好计划有原文件缺口，不能由分数重造，本轮不覆盖这些最新成果。

本轮结果根：`results/wu_20260925_0649/`。`ci_primary`为七图三问二/五核warm+cold old/combined共168臂；`ci_revision`为v2独立复测；`ci_revision3`为小规模v3纠错。各run保留来源提交和真实artifact IDs。完整原始计划/响应/错误/轨迹在所列GitHub artifacts，本地消融/长轨迹另提供会话原始ZIP。

完整解释、负结果和均值在该目录REPORT.md及表中。临时Actions工作流最终删除；不自动合并PR，不做百图扩张或三线最终集成。
