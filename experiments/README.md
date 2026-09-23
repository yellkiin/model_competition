# A/C 深度调研与实验脚本

本目录对应 2026-09-23 的 A/C 二次深挖。

- `调研/A_C_深度调研_20260923.md`：方法论、近期文献和实验设计。
- `experiments/a_search.py`：A 题官方 evaluator 驱动的 ε-constraint 初始分配 + 局部搜索骨架。
- `experiments/c_pipeline.py`：C 题事件解析、RPCA 基线及合成验证。

## C 合成验证

```bash
python experiments/c_pipeline.py --synthetic
```

当前合成配置可复现“重复 ERP + Gaussian noise + 漂移 + 稀疏大幅脉冲”条件下的 RPCA 恢复检查。合成实验只验证算法性质，不代表正式数据效果。

## C 正式数据

```bash
python experiments/c_pipeline.py /path/to/VisualCogA_Task-1.mat --out outputs/c_a1
```

输出 trial table、epoch、RPCA 分解和摘要。Task 2 的正确/错误映射仍需按题面规则补充，脚本不会把 cue 符号等同 response 符号。

## A 正式数据

```bash
python experiments/a_search.py /path/to/graph.json --problem 2 --cores 4 --block-size 32 --eps 0.15 --budget 300
```

A 正式 100 图未随 Git 提交，因此无法在云端仓库环境完成官方批量验证。脚本调用仓库自带官方 evaluator；建议本地先选 5–10 张不同规模图做 smoke test，再跑全量。

当前 A 搜索脚本是“可运行研究骨架”，不是最终强算法。下一步最值得加的是：
1. tensor lifetime / L1-UB pressure proxy；
2. merge/split 邻域；
3. scene 3 FIFO reuse-window reorder；
4. evaluator 日志训练 pairwise ranking surrogate。
