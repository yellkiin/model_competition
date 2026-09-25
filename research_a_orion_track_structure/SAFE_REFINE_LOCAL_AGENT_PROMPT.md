# 结构线安全续优化：本地 Agent 交接

目标：保留每张图已经通过官方评估的目标问题/核数好方案，再继续优化。不是丢掉旧解重新构造，也不是把暖启动成绩称为等时间冷启动成绩。

## 先定位本次分支和证据

本次从 main `996d7d11f10ac44ce65fcd361d5a057a5795c0f9` 开独立分支 `orion/structure-safe-refine-20260925-0318`，对应 PR #31。开始时重新核实分支状态，勿覆盖其他 Agent 的提交或正在运行的目录。此前 PR #30 冲突分支保持不动。

所有新增研究代码在 `research_a_orion_track_structure/`。不修改公共 solver/campaign、官方输入/config/evaluator 或另外两条研究线。新入口是 `safe_refine.py`，候选模块是 `safe_refine_plugin.py`。原 `plugin.py`、`run.py`、`worker.py` 不替换。

优先读 `SAFE_REFINE_PLAN.md` 和最终结果目录的 REPORT。`safe_regions.py` 是保留的失败实验，没有接入默认候选策略。不要因为它听起来合理就默认为改进。

## 运行环境与种子

Windows 优先已有 `D:\python\python.exe`、Python3.12.x、CPU-only。只核对启动必需路径；不做冒烟、哈希/指纹测试、pytest/unittest、全仓审计。原官方合法性检查必须保留。

复现本轮历史最优起点，应使用会话交付代码/种子包中的：
`research_a_orion_track_structure/results/safe_refine_20260925/inputs/seed_manifest.json`
把代码/种子包叠放到完整仓库根目录。清单中的 plan 路径相对于仓库根目录；不要使用过期的 `/mnt/data/...` 路径。每个主种子会在本机目标 q/n 重新原评估并要求与记录周期数一致，之后才开始续优化。

没有该历史种子包时，使用 `prepare_safe_seeds.py --cases ... --out ...` 从正式 `selected_plans.zip` 生成清单。它的起点是 day01 正式解，不是本轮跨历史已验证最优池，两者成绩不能混称。

历史池取得成本没有完整追踪时必须保留 unknown，不能用0代替。新取得或新验证种子的成本要保留。

## 下一轮先小批次，不启动三份百图

先在同一机器运行实际退步风险案例和对照图044/048/059/064，三个小问、五核，每臂最大120秒：

```powershell
& 'D:\python\python.exe' -u -m research_a_orion_track_structure.safe_refine --cases 044,048,059,064 --questions 1,2,3 --cores 5 --methods old,safe --seconds 120 --wall-seconds 900 --max-evaluations 128 --workers auto --seed-manifest research_a_orion_track_structure/results/safe_refine_20260925/inputs/seed_manifest.json --out research_a_orion_track_structure/results/safe_next_small
```

输出目录必须是新目录。通过后再以不同 run_id 处理016/024的大图，不把两个阶段当作同一冷启动轨迹。

`run_safe_windows.ps1` 提供相同参数。后续三机共享同一个完整排序图清单，加 `--shards 3 --shard-index 0/1/2` 分片；workers是进程并发数，不是NPU核数。每张图/每个比较块内部保持相同硬件及预算政策。本版 auto 为启动时选择并固定块并发，不冒称运行中自适应。

## 验收规则

1. 比较 `seed_makespan`、`old_warm_makespan`、`safe_warm_makespan` 与最终 `selected_makespan`；失败/超时不能抹掉合法种子。
2. 旧版和结构线都拿同一主种子。结构线还会尝试清单中的较少核和跨问题方案，因此这是带复用信息的组合续优化，不是纯结构候选的等信息消融。
3. 拿旧/新更好的方案要计入两条搜索成本。不得只报获胜臂时间，也不得给旧臂较小预算来制造优势。
4. 较少核方案补空核、跨问题方案迁移都必须在目标q/n调用原官方评估，不能复制源分数。
5. Q3选中方案本身必须完成无L2对照；不是另一个独立优化Q2方案。
6. 只接收Makespan更好，或Makespan相同且额外COPY更少的方案。该保底不承诺所有辅助指标都改善。
7. 30/60/120/300前缀必须来自同一运行，父进程观察到完整合法响应后才算可用。停止后只能标注持有旧解；没有启动的作业不能当成完成。
8. 用 `summarize_safe_refine.py --run <目录>` 计算均值。100图混合账本只替换对应的真实已验证方案、其他图不变；必须写明不是100图新算法重跑，不与内存线等其他更晚方案暗中合并。
9. 本轮只实测五核不意味着正式1—5核曲线完成。不要扩大范围前就宣称全量验收。

最终提交独立可审查PR、原始方案/响应/失败、连续轨迹和明确证据索引，不自动合并，不提交赛事平台。
