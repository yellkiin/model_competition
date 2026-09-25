# 本地Agent接续：Anytime Wu / PR #34

先读取本轮REPORT、METHOD.md、LITERATURE.md、CI_EVIDENCE_INDEX.json和各版本结果。分支是新建的`orion/track-anytime_wu`，不是旧`orion/track-anytime`。开始前检查最新PR/分支，勿覆盖其他Agent或正在运行的目录；需要继续独立研究可再建唯一后缀分支。公共solver/campaign和官方图/config/evaluator、其他研究线不得修改。

## 先取真实输入和本轮原始证据

原输入导出：GitHub Actions run **36104651803**，artifact **10850846702**，名`orion-anytime-wu-frozen-inputs`。外层ZIP中有`orion_anytime_wu_frozen.zip`。其中`raw_day01/`保存两片原包的七图记录，官方原图/config/code在原附件目录，原文档和源码基线也有来源。不要把导出动作算成实测，不要运行源代码materialize脚本覆盖当前v2。

完整仓库已经有当前官方输入时，只将内层ZIP的`raw_day01/`解压到自己的仓库根，保持原始包不动；不要覆盖已有公共代码或原图。原图获取困难先看tools/A_DATA_ACCESS.md，不把LFS指针/截断JSON当输入。

本轮主七图实测run **36106285863**，每图原始artifact含preparation、paired30、source和EXECUTION_COMMIT。v2修正独立复测run **36107422408**。先读实际artifact索引，不混淆启动失败36106178564与取消的重复36106800532。

## Windows准备与真实小批次

优先已有`D:\python\python.exe`、Python3.12.x、CPU-only。依赖`psutil==7.0.0`用于进程RSS和可用资源；只在缺少时安装。绘图可选matplotlib。不做烟雾、哈希/指纹、pytest/unittest或全仓审计。

从正式原记录建立本机路径并重新原评估，不复制外机/tmp路径：

```powershell
& 'D:\python\python.exe' -u -m research_a_orion_track_anytime.prepare --cases 083,086 --workers 1 --out research_a_orion_track_anytime/results/wu_next_prepare
```

该动作会实际验证两图的三问/二核五核正式方案并取得Q3同方案无L2对照，输出seed_manifest.json。它使用day01正式种子，不是不存在原计划的“最新摘要最优解”。若有后来更好的完整plan/response，先明确新来源并重新目标q/n评估，另建清单保留其成本；未知历史成本不填0。

先验证本轮仍有负结果的083，以及修正有改善的086：

```powershell
& .\research_a_orion_track_anytime\run_windows.ps1 -Cases '083,086' -Questions '3' -Cores '5' -Methods 'old,combined' -Modes 'warm' -Revision 'v2' -Seconds 120 -MaxEvaluations 128 -TotalSeconds 700 -PairSeconds 30 -Workers 'auto' -SeedManifest 'research_a_orion_track_anytime/results/wu_next_prepare/seed_manifest.json' -Out 'research_a_orion_track_anytime/results/wu_next_negative_gate'
```

输出目录须为新目录。不要默认扩100图。只有该批次通过后，再在**另一个run_id**进行`queue,fifo,budget,combined`消融或冷启动；新增预算不能倒填早期轨迹。本轮建议解决083选择偏置、保留旧解，而不是继续增加候选数量或把上限统一加大。

## 验收要求

逐项检查完整原响应的合法性、首个可行解的父进程可用时刻、计划/响应一致性、原q0基准来源和Q3同方案no-L2。新结果不够好就保留已有种子，不能用本轮较弱day01实验覆盖更晚强解。old/combined每组合保持相同种子、时间和次数上限；历史质量/运行时差异单列。

`--revision v2`对齐原solver的U/L gap语义并刷新incumbent邻域。v1.1保留仅用于复现其七图原实验，不应把两者曲线拼接。启发式停滞不是最优证明；固定持续时间slack不是精确缓存因果收益。命中率上升但Makespan退步的案例必须保留。

workers是CPU并发进程数，与NPU核数不同；本版按已完成比较块的内存/CPU/RSS反馈调整，块内不变。三台机器使用同一排序图清单与`--shards 3 --shard-index 0/1/2`分片，不各跑完整清单。跨机器墙钟不得直接当公平对照。

每条轨迹记录30/60/120/300秒已有合法解，早停后标明持有；保留重复/剪枝/错误/无收益尝试。seed取得/新验证/追加搜索/Q3配对成本分开。旧solver仍沿用只保存improver全文的策略，不声称拥有所有旧版拒绝响应。

最终交付本轮自己的代码、真实方案/响应、轨迹、负结果和来源索引，新PR，不自动合并。正式一至五核和百图曲线要求仍在；小样本不能冒称完成它们。
