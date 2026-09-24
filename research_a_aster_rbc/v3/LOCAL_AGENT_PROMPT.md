# 本地 agent：直接执行最新 PR #18 的 best5

请实际执行，不要只给计划。PR #18 的 quality.py 已提交，不再等待旧 ZIP，也不要自行造替代模块。

取得分支 `research/a-aster-v3-wavefront-20260924` 的最新提交；已合并则用包含该版本的 main。版本应为 `aster-v3-release-affinity-4.1`。有其他 agent 修改或正在跑实验时使用独立 worktree，不 reset/clean、不强制切换、不覆盖别人的代码或输出。只改 `research_a_aster_rbc/v3/`。

不做冒烟，不做哈希/指纹，不跑 pytest/unittest、全仓审计、安全测试、环境性能基准。不得把这些换个名称执行。只做启动必需的路径/解释器判断，随后直接运行真实案例。官方操作覆盖、无环、容量和执行合法性检查必须保留，不得关闭。

阅读本目录 README、LOCAL_MEASURED、EXPERIMENT_PLAN 后，在仓库根目录执行：

```powershell
& 'D:\python\python.exe' -X utf8 -u -m research_a_aster_rbc.v3.best5 --workers 2 --wall-seconds 900
```

优先现有 Python。其他机器没有该路径时用已有 Python 3.10+ 的真实路径，缺少才最小配置。CPU和标准库，不装CUDA、PyTorch、Conda、MILP求解器。同机有重实验或内存紧张时改workers为1。缺输入仅恢复A；路径不标准时用 `--official-dir` 指向含code/data的附件目录。

不要另跑fast、原ASTER、ORION、多核数组合、消融、随机种子和预算网格。fast指标从同一full求解的首候选读取，不再单跑一次。固定五核、三问、每作业90秒、单评45秒、8次调用；Q3同方案Q2回放也算一次。原始整图单核分母单独最多120秒，全部计入总窗口。

默认12图003/007/012/020/028/035/047/056/065/076/088/094；不要再先跑6或7张开发图。第一次15分钟窗口结束即汇报，保留complete/partial/failed/not_started和遗留running，不自动续跑、不分档补齐、不扩大100图、不开始第二轮。若窗口未满且程序已经正常结束，也直接汇报。

多机用 `--shards M --shard i`，i=0..M-1，每机独立目录，不重复领取。合并CSV按case/question/cores/variant检查重复/缺项，不做哈希，机器耗时分别报告。

若报错，读取对应result.json、worker_error.json、official_stderr.log，修本目录最小兼容问题并记录原错误。不要因此去补冒烟或全仓测试。确需重跑错误案例须新目录、明确新版本/重试口径；已得到合法incumbent就保留，没有合法结果就记录失败，不填造分数。

所有周期均来自当前官方评估器，分母必须是同图题定配置的原始整图单核；缺分母就留空。第三问固定最终best_plan分别评Q2/Q3；不能拿两问独立优化结果相除。不要用缓存命中率替代完成周期。

交回实际命令、Python/机器、目录、summary.csv、coverage.json、manifest.json、run_receipt.json及精简报告。按三问分别给best的AM、GM、中位数、最低值、超过5倍的例数、有效样本数与缺项；给求解秒数和评估次数。已有旧结果只作同图同核同配置参考，不重新跑旧全量搜索；缺同口径来源就明确没有旧方案对照。

4.5或5倍都不是人为截断、删除低分图或停止记录的理由。没到5倍如实报告，优先定位Q1的Task边界/重复读取，以及Q2/Q3的通信释放、驻留Spill和核心不均衡。不要按case文件名写特殊规则，不把多版本逐图最好值拼成固定算法成绩。

首轮完成后停止实验。提交代码修复或精简结果时只暂存本目录明确文件，不 `git add .`，不提交runs/原始官方响应/大ZIP/他人修改，不自动合并PR或上传赛事平台。
