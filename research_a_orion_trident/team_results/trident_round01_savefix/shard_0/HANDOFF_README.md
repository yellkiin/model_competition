# 写作 agent 交接

用户会把 `ORION_Trident_shard0_round01_savefix_FULL_20260926.zip` 复制到目标电脑桌面，并在提示词中提供实际路径。先解压外层ZIP；阅读 `HANDOFF_README.md`、`04_reports/RUN_OUTCOME.md`、`04_reports/ROUND_SUMMARY.json`。不要依赖原机器绝对路径。

`01_actual_run/round01_savefix_shard0_raw.zip` 是完整原始run目录：需要原始证据时再解压它，根目录为run/。`02_initial_failure/round01_shard0_initial_failure.zip` 是保留的初次Windows保存失败轨迹。两段分开计账；不得把失败前和重试后的轨迹拼接成一次连续运行。

`03_inputs/` 是本机本片启动输入、官方代码/config和参考种子；其中部分历史方案档案含100图，仅当前SHARDS.json的34图被执行。`04_reports/` 是易读报告与汇总表；`05_source/` 是实际修复代码与说明；`06_run_control/` 保存命令和执行/发布日志；`07_publication/` 是GitHub报告发布内容。原始请求内的绝对路径只说明原运行位置，不要求在新机器创建同名目录。

审稿口径：476合法主结果≠476正常完成（464正常、12时限）。配对169/170，014 Q3/n5缓存收益缺失。五核每问34图；不得将shard0平均冒充全100图。构造、搜索、诊断和历史成本必须区分；S/M/F接受事件不是独立消融因果证明。全部图号和失败/低分项保留。

本次交接用于已有证据分析和写作；不要仅因找到源码就自行启动solver/evaluator补分。原始包不需任何哈希/指纹检查。
