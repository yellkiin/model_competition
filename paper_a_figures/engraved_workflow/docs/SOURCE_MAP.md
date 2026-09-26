# 论文—机制—图形对照

## 依据与版本

主要依据用户上传的 `网页端论文编辑包_20260926(1).zip` 中 `workshop_v1/` 的论文与已绑定理论，而不是旧总流程图。题面对象来自 `题目/A题_20260925T204725662983Z.docx`。原图对象经本项目重新绘制，没有复制原图像素或矢量路径。

仓库核对点：`main` 基准提交 `118260f9978d9668b03ed2a5fc76cc7847eceee2`。仓库 `paper_a_theory/ALGORITHM.md` 与上传包 `求解/论文理论/bindings/20260925T204725662983Z/ALGORITHM.md` 的 Git blob 均为 `4bc2e98e334847dccaea6a207e116c4b2f64adcf`。输入 SHA-256 见 `PROVENANCE.json`。

以下路径以 `workshop_v1/` 为根。图中的“依据”不等于本次重新执行实验。

| 图层 / 表达 | 依据 | 保留的语义 |
| --- | --- | --- |
| 01 二部图、张量、算子、子图包络 | `论文/章节内容/04_问题一.tex`；`求解/THEORY_ALIGNMENT.md` §1 | G=(T∪O,E)，仅对非边界算子分组，覆盖且互不相交，不修改原始算子与依赖 |
| 01 子图块与核心泳道 | 同上；绑定 `ALGORITHM.md` | x=(𝒫,a,π)，同时表示子图划分、核心归属、核内顺序；不提交自行指定的执行起止时刻 |
| 01 初始状态 | `求解/THEORY_ALIGNMENT.md` §4；实际 `solve.py` 流程 | 基础构造或历史方案须在目标配置下完整验证，维护一个当前最好可行方案及执行记录 |
| 02 每轮来源选择 | `求解/THEORY_ALIGNMENT.md` §4；实际 `selector.py:choose` | 初次覆盖、近期收益/成本、失败比例、访问间隔、剩余预算准入；是启发式，不绘成置信上界算法 |
| 02a 基础构造 | 绑定 `ALGORITHM.md`；`论文/章节内容/04_问题一.tex` | 粒度、关键性排序、负载映射提供候选，不是独立并行求解器 |
| 02b 结构与负载 | 绑定 `ALGORITHM.md` | 迁移、交换、拓扑拆分、依赖相关联合迁移；以 B 的跨核迁移和 B 的拆分示意 |
| 02c 驻留重组 | `论文/章节内容/05_问题二.tex`；`求解/THEORY_ALIGNMENT.md` §2–4 | 分组/顺序改变生产消费距离和存活区间；代理提出候选，自动 Spill 仍由固定执行器决定 |
| 02d FIFO 窗口 | `论文/章节内容/06_问题三.tex`；`缓存事件补充.tex` | 只在 Q3，固定 𝒫 和 a，改变合法 π；旧记录提出填充后、淘汰前的读取窗口，新时序完整重演，同刻遵守事件先后 |
| 02 结构预检 | `求解/THEORY_ALIGNMENT.md` §1、4 | 覆盖、唯一归核、商图加每核顺序边所得合图无环、去重；不是充分可行性证明 |
| 02 有效下界 | `求解/THEORY_ALIGNMENT.md` §3–4；`方法补充.tex` | U=Cq(x)，有效候选下界 L(y)>U 才筛去；等号保留，周期持平仍可能改善 COPY 字节 |
| 03 Step1/2/3 与全局模拟 | `求解/THEORY_ALIGNMENT.md` §2；题面附录 | Task/COPY 根据候选重建；核内顺序→驻留/Spill→Pipe 排布→全局离散事件模拟，不能沿用局部参考周期 |
| 03 核心剖面 | 题面；`求解/THEORY_ALIGNMENT.md` §2 | 每核 M、V、MTE2、MTE3 分别串行；L1、UB 为私有存储；图中活动块仅为机制示意 |
| 03 DDR 和 L2 | 题面；`求解/THEORY_ALIGNMENT.md` §2 | DDR 共享 60 B/周期；Q3 只读 L2，1 MiB、250 B/周期，为独立读池，不是所有流量串行穿过的层次 |
| 03 FIFO 查询 / 填充 | 同上；`缓存事件补充.tex` | COPY_IN 发射时查询；命中不刷新 FIFO；未命中读 DDR，完成后尝试填充 |
| 03 三问差异 | `求解/THEORY_ALIGNMENT.md` §2 | Q1 子图级 Task、跨子图经 DDR（同核亦然）、同核切换 100 与跨核前驱完成后 1000；Q2/3 核心级 Task、跨核 COPY_OUT 完成后 500 周期 |
| 04 实际评价 / 严格接受 | `求解/THEORY_ALIGNMENT.md` §3–4；绑定 `ALGORITHM.md` | “总体任务执行时间（Makespan）” Cq=max f；可行且 (Cq,Dq) 字典序严格改善才替换。Dq 是额外 COPY 字节，不等于实际 DDR 流量 |
| 04 反馈 | `求解/THEORY_ALIGNMENT.md` §4 | 同步更新方案和执行记录；刷新依赖父状态的局部流，独立全局构造保留进度 |
| 05 停止与保存 | `求解/THEORY_ALIGNMENT.md` 主审补充、§4、§6 | 预算、质量界、耗尽、经验停滞；仅输出截止前已经验证并可用的最好结果 |
| 05 Q3 配对 | `论文/章节内容/06_问题三.tex` | 对同一个 x3=(𝒫,a,π) 再执行无 L2 对照，C2(x3)/C3(x3)；不拿独立 Q2 最优方案作分子，不参与搜索接受 |

## 示例的一致性

`assets/example_case.json` 中六个算子形成分叉汇合 DAG。A={o1}，B={o2,o4}，C={o3,o5}，D={o6}。父方案为 k1:[A,B,D]，k2:[C]；迁移候选为 k1:[A,D]，k2:[B,C]。右侧硬件上方的候选块与该迁移一致。

驻留图只展开 o2–o5 这四个算子的局部生产消费顺序。FIFO 图使用抽象事件窗口，不为它捏造实际命中率或周期收益。单元测试检查图中示例的覆盖、唯一归属、合图无环、依赖保持和窗口事件次序；这些测试不是官方评估器的可行性或性能认证。

## 视觉参考来源

用户参考目录中的线条方向被转译为本项目原创图形。实际查看的参考：

- Delaware Art Museum，Aubrey Beardsley，*The Peacock Skirt*：https://emuseum.delart.org/objects/14093/the-peacock-skirt 。借鉴黑白对比与连续曲线节奏，不复制人物、纹样或画面布局。
- The Metropolitan Museum of Art，Albrecht Dürer，*Melencolia I*：https://www.metmuseum.org/art/collection/search/336228 。借鉴轮廓、剖面与密排线的组织方式，不复制版画内容。
- Dao 等，*FlashAttention*，Figure 1，PDF 第 2 页：https://arxiv.org/pdf/2205.14135 。仅借鉴将读写动作画在数据块和存储对象上的机制表达，没有导入其算法或配色。

未把参考网页、艺术作品原图、字体文件或外部位图打入交付。所有成图线条、节点、文字由本项目源代码生成。
