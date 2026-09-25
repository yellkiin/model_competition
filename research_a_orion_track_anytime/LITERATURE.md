# v4 文献依据与迁移边界

资料来自仓库 `调研/A题_文献库/` 与 `调研/A题_文献.json`；主阅读顺序仍为 A49/A02/A39/A16/A42，另用 A12 Ansor 支持有限预算搜索。所有文献只提供候选/搜索思想，最终分数均由原官方 evaluator 给出。

## Ansor / A12

迁移：有限调优预算、先让不同候选族获得观测，再根据真实改善与评估成本分配后续预算。v4 的 family-first、收缩校准、estimated-eval admission 与“近界停止”属于这个思路。

不迁移：Ansor 的 learned cost model、代码生成、tile/fusion 搜索及其任务目标函数。

## A42

迁移：从强 incumbent 周围做有限局部窗口，接受改善后刷新搜索邻域；这直接支持 v4 丢弃 stale incumbent-specific candidates。不迁移BSP分阶段通信/NUMA分数，本题共享DDR、Pipe、FIFO依旧按官方事件模型执行。

## A49 / A39 / A02

只迁移“结构异常时局部再平衡/细化”的思想。024 的尾核过载由实际 per-core timeline + schedule长度触发，不由 case ID 触发；候选移动后仍经完整合法性和官方 Makespan 评估。不把 cut/connectivity/minimax proxy 当作官方目标或最优性证明。

## COSMA / A16

迁移：tensor create/preserve/spill/retrieve 生命周期说明“减少访存/提高命中”与“缩短最终 Makespan”不是同一目标。024 是直接例证：命中约45.9%，同方案 cache收益只有约0.12%，结构调度才是主要收益。

不迁移：自由地址分配、主动spill/retrieve、ILP地址互斥；这些不是赛题接口。

## CADE / A40（降级背景）

论文使用LRU、inclusive层次和周期DAG reuse profile，与本题FIFO、单次执行、issue lookup/completion fill不一致。v4只保留“复用发生的相对时机重要”这一直觉，所有fill/eviction都从真实官方event定位；不使用LRU reuse distance，也不插入主动延迟。

048冷启动负结果再次说明：文献中的“更多结构候选/更聪明排序”不能自动推出端到端更好；当前版本因此明确定位为continuation。059近界停止说明预算本身也是算法变量。
