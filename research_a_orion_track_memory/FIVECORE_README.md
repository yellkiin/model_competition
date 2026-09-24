# 五核内存修复第二轮

见 `results/fivecore_final_20260924/REPORT.md`。当前实验从day01正式方案暖启动，遵照用户指令不重跑旧指标。原方案及分数是信任前提；只对新候选调用原评估器。结果不是完整Anytime的冷启动替代品。

- `reuse_repair.propose`：固定核归属复用分带、凸Task合并和局部释放修复；COMMON候选接口。
- `local_repair.propose`：固定分区的张量端点亲和及合法顺序窗口；COMMON候选接口。
- `trusted_run.py`：图清单、三问、1–5核、自动workers、预算/总截止、三机分片、旧种子成本及独立续优化。
- `pair_selected.py`：新Q3方案的同方案无L2对照；保留父方案时复用现有配对，不重评旧成绩。
- `fivecore_report.py`：本轮八图三问五核专用分阶段汇总，不是三线最终整合器。

## 输入与执行

完整仓库根目录应有原路径A数据（问题与附件之间两个空格）、官方code/config，以及day01 `combined_final/per_case.csv` 和 `selected_plans.zip`。后者已有发布；本程序只提取请求的方案。图未下载时按tools/A_DATA_ACCESS.md从PR25修复分支获取，不能读LFS指针、手工抄改base64或重建缩小图。

Windows默认使用D:\python\python.exe，3.12.x/CPU-only；不同环境交本地Agent适配，不更改现有正在运行的目录。Linux可使用已有Python3.13。旧run.py的冷启动对照入口仍保留，不是这次的默认入口。

```powershell
.\research_a_orion_track_memory\run_fivecore_windows.ps1 -Cases 5,51,59,67,73,83,90,92 -Questions 1,2,3 -Cores 5 -Seconds 120 -Workers auto -Out research_a_orion_track_memory\results\local_epochs
.\research_a_orion_track_memory\run_fivecore_windows.ps1 -Cases 5,51,73,83,90,92 -Questions 1,2,3 -Cores 5 -Seconds 120 -Workers auto -Proposal local -SeedRun research_a_orion_track_memory\results\local_epochs -Out research_a_orion_track_memory\results\local_tensor
& D:\python\python.exe -m research_a_orion_track_memory.pair_selected --run research_a_orion_track_memory/results/local_epochs --workers auto
& D:\python\python.exe -m research_a_orion_track_memory.pair_selected --run research_a_orion_track_memory/results/local_tensor --workers auto
```

新目录已存在manifest时拒绝覆盖。--seed-run指向同机器当前路径的父run，检查case/q/n/config；改变原输入图后不允许继续信任该父记录。祖先图的真实性是显式信任前提，不做指纹测试。每次local续跑是新阶段，种子成本包含之前阶段的时间；不得把多个版本冒称同一固定策略轨迹。raw和request含执行时绝对路径，移动证据包后不要直接重新执行旧request；使用新CLI请求来定位当前仓库。

## 范围与配对解释

默认目标是原配置Makespan最小，额外搬运仅平分时次级；Q3同时报告同方案cache加速比，不能为了比值更大故意恶化无L2方案。mean(T1/T5)与mean(noL2/L2)不同；此次后者下降，报告已保留。

本轮未执行新的1–4核。hybrid_100_curves仅是旧表+已改五核方案的记账，不是新方法100图跑分。下一批先固定小清单补核数，或另选未参与调参的少量差图；shards=3按同一排序图清单互斥分片，不能三台分别跑相同100图。
