"""Build the Chinese Markdown report from finalized, audited experiment data."""
from collections import Counter
import json
import statistics as st
from optimize_q3 import HERE, ROOT, read


def main():
    rows = read(HERE / "selected_results.json")
    summary = read(HERE / "summary.json")
    audit = read(HERE / "final_audit.json")
    assert audit["status"] == "PASS" and len(rows) == 500
    old = {(r["case"], int(r["cores"])): r for r in read(HERE / "baseline_snapshot.json")["rows"]}
    statuses = Counter()
    receipts = []
    for path in (HERE / "evaluations").glob("case_*/n*/*/q3.receipt.json"):
        r = read(path)
        statuses[r["status"]] += 1
        if r["status"] == "PASS":
            receipts.append((path, r))
    main_table, cache_table = [], []
    for n in range(1, 6):
        s = summary["cores"][str(n)]
        g = [r for r in rows if r["cores"] == n]
        main_table.append(f"| {n} | {s['baseline_speedup']:.6f} | {s['speedup']:.6f} | {s['improved']} / 100 | {s['worse']} | {s['time_reduction_pct']:.4f}% |")
        faster = sum(r["no_l2_makespan"] > r["makespan"] for r in g)
        slower = sum(r["no_l2_makespan"] < r["makespan"] for r in g)
        reduction = st.mean((1-r["makespan"]/r["no_l2_makespan"])*100 for r in g)
        cache_table.append(f"| {n} | {s['baseline_cache_gain']:.6f} | {s['cache_gain']:.6f} | {reduction:.4f}% | {faster} / {100-faster-slower} / {slower} | {st.mean(r['cache_hit_rate'] for r in g)*100:.3f}% |")
    five = [r for r in rows if r["cores"] == 5]
    selected_cases = {"case_001", "case_002", "case_003", "case_044", "case_046", "case_049", "case_050", "case_056", "case_062", "case_075", "case_080", "case_083", "case_090"}
    examples = []
    for r in five:
        if r["case"] not in selected_cases:
            continue
        o = old[r["case"], 5]
        pure = (1-r["makespan"]/r["no_l2_makespan"])*100
        examples.append(f"| {r['case'][5:]} | {int(o['q3_matched_no_l2_cycles']):,} | {r['baseline_makespan']:,} | {r['no_l2_makespan']:,} | {r['makespan']:,} | {r['time_reduction_pct']:.2f}% | {pure:.2f}% | `{r['candidate']}` |")
    ablation = []
    for label, allowed in [("原问题三候选", ()), ("原候选 + 多尺度/加权切分", ("bands",)), ("原候选 + 缓存感知组件候选", ("cache",)), ("完整新组合", ("bands", "cache"))]:
        best = {r["case"]: r["baseline_makespan"] for r in five}
        for path, receipt in receipts:
            if receipt["cores"] == 5 and path.parent.name.startswith(allowed) and allowed:
                best[receipt["case"]] = min(best[receipt["case"]], receipt["makespan"])
        avg_s = st.mean(r["baseline_speedup"]*r["baseline_makespan"]/best[r["case"]] for r in five)
        avg_delta = st.mean((1-best[r["case"]]/r["baseline_makespan"])*100 for r in five)
        improved = sum(best[r["case"]] < r["baseline_makespan"] for r in five)
        ablation.append(f"| {label} | {avg_s:.6f} | {avg_delta:.4f}% | {improved} |")
    changed = sum(r["makespan"] < r["baseline_makespan"] for r in rows)
    avg5 = summary["cores"]["5"]
    cache_drop5 = st.mean((1-r["makespan"]/r["no_l2_makespan"])*100 for r in five)
    cache_median5 = st.median((1-r["makespan"]/r["no_l2_makespan"])*100 for r in five)
    top_cache = sorted(five, key=lambda r: 1-r["makespan"]/r["no_l2_makespan"], reverse=True)[:3]
    cache_examples = "、".join(f"{r['case'][5:]}（{100*(1-r['makespan']/r['no_l2_makespan']):.2f}%）" for r in top_cache)
    protected = audit["protected_files"]
    report = rf"""# 问题三 L2 作用分析与算法改进实测报告

日期：2026-09-26。对象：题给 100 个算例，每例 1—5 核，共 500 个配置。官方图、硬件参数和评估器保持不变。

主要依据：[题面](../../题目/通用神经网络处理器下的多核调度问题.docx)、[官方配置](../../数据/原始/A题官方附件/data/config.txt)、[问题三官方评估器](../../数据/原始/A题官方附件/code/multicore_cut_evaluate_problem_3.py)、[原逐例实验记录](../正式实验/逐例分析.csv)。

## 1. 先回答你的问题

**L2 不应被预设为对所有算例都带来很大的提高；但原算法确实还有可改善的空间，本次已经完成代码修改和全量验证。**

新算法使五核问题三平均加速比从 **{avg5['baseline_speedup']:.6f} 提高到 {avg5['speedup']:.6f}**，逐例执行时间平均减少 **{avg5['time_reduction_pct']:.4f}%**。五核 **{avg5['improved']} / 100** 例严格改善，**0 例退步**；全部 500 个配置有 **{changed}** 个严格改善，0 个退步。问题一、问题二的原方案、已选结果及原求解器保留，受保护文件核查通过。

这次改善并不全部来自 L2。我们同时测了新方案关闭 L2 的时间：新方案五核的同方案 L2 平均时间降幅为 **{cache_drop5:.4f}%**。应把“切分、分核与调度的改善”和“缓存本身的作用”分开写，不能把前者包装成缓存硬件收益。

## 2. 从题意和实际数据看，L2 是否应该大幅提高成绩

### 2.1 带宽提高不等于整个图同比提速

官方配置为 DDR 60 B/cycle、L2 250 B/cycle、L2 容量 1 MiB，跨核释放延迟 500 cycle。带宽比 250/60≈4.17 只描述两个带宽参数，不能当作全图加速比。

官方模型中：

- 只有 `COPY_IN` 查询 L2；写回仍走 DDR，普通计算周期不变。
- 首次未命中读取完成后才填入缓存。多个核心若在首读完成前同时请求同一张量，会各自未命中；没有合并冷启动缺失请求。
- FIFO 命中不刷新淘汰顺序，工作集大于 1 MiB 或复用距离过长会丢失复用；单张量超过容量不缓存。
- L2 命中既能加速本次读，也能减轻 DDR 争用，但仍不消除原有依赖、写回和跨核同步。
- MTE2、MTE3、计算流水线可重叠，因此命中字节占比不能直接替换为“总时间中可以缩短的占比”。

所以，大收益通常同时需要：**足够多的重复读取、读取能在驻留期间命中、这些读或它们造成的竞争确实影响最终完工时间。** 只增加命中率，并不保证 Makespan 下降。

### 2.2 本题确有一批图，理论上就很难靠 L2 大幅提速

只统计普通计算操作，对任意合法 n 核方案都有下界：

$$
L_{{global}}=\max\left(\max_p\frac{{\sum_{{v:\,pipe(v)=p}}d(v)}}{{n}},\quad \max_{{P\in DAG}}\sum_{{v\in P,\,v\text{{非COPY}}}}d(v)\right).
$$

它乐观地忽略全部搬运及很多等待。用旧同方案无 L2 时间 $T_0$ 作分母，$1-L_{{global}}/T_0$ 是可降时幅度的乐观上限，不是可实现承诺。五核中 **18 / 100** 个图即使允许重新分核、理想化消除搬运，也无法比旧无 L2 成绩再降时超过 5%；固定旧核心归属时有 **31** 个这样的图。

例如旧算例 001 的无 L2 / 有 L2 均为 47,502 周期，计算下界为 46,560；所有优化合计的乐观降时上限也只有约 1.98%。其原方案除首次读取外的重复读量仅占约 0.56%。这一类图 L2 没有显著提升是合理的。

但不能据此认为所有图都没有空间。旧五核方案的理想重复读字节比例逐例均值约 **41.67%**，实际字节命中率均值只有 **21.29%**。前者假设理想复用，不是可达命中率，也不能直接换算成速度；它说明部分图仍值得检查访问顺序和驻留问题。详细计算见 [理论边界与逐例诊断](./analysis_potential/结论.md)。

## 3. 原算法为什么开启 L2 后效果不明显

### 3.1 原方案生成对缓存的适配有限

原候选主要是完整连通块平衡、以 8 个深度带为目标的切分和 800 操作分批，再由问题三评估器重选最优。候选生成没有系统使用 L2 容量、带宽、共享输入、驻留次序及并发首次读取信息。因此，原结果反映的是有限候选集下的成绩，不能证明已经利用完 L2 潜力。

### 3.2 算法瓶颈与缓存瓶颈混在一起

粗切分可能导致核心计算负载不均衡，跨核依赖、私有缓存换入和读写竞争也可能拉长执行。L2 只能改善其中一部分，不能自动修复切图不佳或核心分配不均。

旧算例 056 就很典型：读流水线累计忙时从 3,409 降到 3,182 周期，但总时间只从 219,090 降到 219,072。读确实变快，收益却没有等量传递到最终终点。本次改变切分方案后的改善，应首先归因于整个方案变好，而不是说“原来的 L2 没启用”。

旧算例 083 则相反：从 442,480 降到 310,731，执行时间减少约 29.78%。其 386 次缓存命中全部属于同核重复读取，主要对应私有缓存不足后的再次换入。这已说明 L2 并没有白引入，只是受益集中在特定访存结构。

### 3.3 还要避免两个误判

- 官方 `data_movement_bytes` 统计的是缓存路由前的计划搬运量。有无 L2 时相同，不能证明 L2 未工作。
- 固定方案不等于固定实际发射时刻。旧算例 002 开启 L2 后提前的 DDR 读取改变了读写竞争，使最终时间增加 3 周期；这有时间线证据，不能简单归因于计算误差。

原始逐例数字与时间线核查见 [此前的 L2 核查总结](../问题三_L2结果核查总结.md)。该文件描述的是优化前版本。

## 4. 已实现的算法改动

本次在独立目录增加问题三改进器，不替换问题一、问题二入口。

| 改动 | 具体内容 | 目的与限制 |
|---|---|---|
| 多尺度切分 | 在原目标 8 个深度带之外，搜索目标带数 2、4、16、32、64 | 改善粗切分导致的不平衡与私有缓存压力；过细可能增加同步，须实测取舍 |
| 按流水线及通信代价分配 | 分别估计各 Pipe 工作量，考虑唯一跨核张量搬运字节、DDR 读写与 500 周期同步 | 避免只平衡操作总数；估计值只用于生成候选 |
| 保守估计 L2 复用 | 对先前深度带的可能复用给予折扣估计，限制容量 | 不把同批并发读取直接假定为命中；仍非精确缓存模拟 |
| 缓存感知组件候选 | 保留或重平衡独立组件；搜索正序、逆序、跨核旋转次序及按输入工作集分组 | 改善共享输入次序与私有缓存压力；不保证实际发射一定错峰 |
| 官方评估择优及回退 | 保留旧问题三方案；比较 `(Makespan, added_copy_bytes)`，只有更优才替换 | 时间持平时才比较搬运量；失败、超时和变差候选不替换基线 |

需要特别说明：官方 Step2 和 Step3 会继续重排与处理私有缓存。候选名中的 `stagger` 是输入给评估器的次序策略，**不是已经保证消除并发冷启动的证明**。最终是否有效，以官方全局事件模拟为准。

最终批量实验对全部 100 图的 2—5 核配置补齐 band/refine 候选；所有 1—5 核配置均尝试适用的组件候选。切分尺度与分配规则不依赖具体算例编号，属于有限通用候选搜索。并未针对每个编号硬编码答案。

## 5. 题定配置下的全量结果

### 5.1 最终问题三成绩

每行均有 100 个算例。平均加速比使用原实验相同的单核参考时间 $T_1$，逐例算 $T_1/T_{{Q3}}$ 再取算术平均；没有重设分母来放大收益。“平均降时”是逐例 $1-T_{{new}}/T_{{old}}$ 的平均值，不是平均加速比的倒数。

这里的 $T_1$ 保持原参考方案，未改成新算法重新优化后的单核结果。因此该指标衡量相对原单核参考的速度；同时改善调度和搬运时，个别值或平均值可以超过核数，不能直接解释成新算法自身的纯并行扩展效率。

| 核数 | 原平均加速比 | 新平均加速比 | 严格改善 | 退步 | 平均执行时间减少 |
|---|---:|---:|---:|---:|---:|
{chr(10).join(main_table)}

这里报告的是题给数据和官方固定配置下的性能改善；有限候选搜索没有证明全局最优。

### 5.2 五核候选家族对照

下面从已完成的候选回执重新取各组最优，所有组均保留原方案作为回退。它用于区分候选家族的贡献，**不是关闭 L2 的硬件消融**；“缓存感知组件候选”也同时改变分组和顺序，不能将其全部收益视为纯 L2 收益。

| 可选候选集合 | 平均加速比 | 相对原方案平均降时 | 改善图数 |
|---|---:|---:|---:|
{chr(10).join(ablation)}

## 6. 固定新方案，重新检查 L2 自身的作用

定义四个时间：A=旧方案无 L2，B=旧方案有 L2，C=新方案无 L2，D=新方案有 L2。

- 算法改进：$B/D$；时间降幅为 $1-D/B$。
- 新方案缓存收益：$C/D$；时间降幅为 $1-D/C$。
- $A/D$ 同时包含方案变化与缓存作用，不能叫作“纯 L2 加速比”。

每个新选方案均补跑官方问题二评估器，作为同方案无 L2 对照；原方案保留的条目使用原对应无 L2 完整结果。该对照仅用于归因，**没有替换问题二原有提交方案**。

| 核数 | 旧同方案平均 L2 加速比 | 新同方案平均 L2 加速比 | 新同方案平均时间降幅 | 新方案变快 / 持平 / 变慢 | 新平均字节命中率 |
|---|---:|---:|---:|---:|---:|
{chr(10).join(cache_table)}

五核新方案的纯 L2 时间降幅中位数为 **{cache_median5:.4f}%**，明显低于均值，说明收益仍有较强的实例差异。较大的三个缓存降时实例为 **{cache_examples}**。这几例适合展示缓存适配的正面作用，同时保留 083 这类计算瓶颈案例作对照。独立复算见 [最终统计复核](./final_statistics_review.md)。

这个表与上一节回答不同问题。即使缓存加速比提升不大，绝对 Makespan 降低仍然是有效优化。如果新方案消除原先会被缓存命中的多余换入，命中率或缓存加速比还可能下降。评价改进时应以最终 Makespan 为主，并用命中率和同方案缓存收益解释原因。

### 五核代表算例的四格对照

周期越小越好；算法降时与新方案缓存降时的分母不同。

| 算例 | A 旧无 L2 | B 旧有 L2 | C 新无 L2 | D 新有 L2 | 算法降时 | 新方案 L2 降时 | 最终候选 |
|---|---:|---:|---:|---:|---:|---:|---|
{chr(10).join(examples)}

**083 是“成绩更好，但有无 L2 总时间持平”的直接例子。** 新方案保持计算操作的核心归属不变，把 SPILL 新增搬运从 11,336,448 B 降到 0；有 L2 总时间从 310,731 降到 185,314，降幅约 40.36%。新方案仍有 49 次命中、930,112 个命中字节，缓存正常生效。瓶颈 core0 的读流水线占用从同方案无 L2 的 53,049 周期降到 8,095，但该核所有计算操作的起止时间完全相同，计算主导的整体终点仍为 185,314。此时总时间只比固定归属计算下界 183,092 高约 1.21%，继续放大缓存收益的空间已经很小。

这说明本次优化应追求的是：**减少不必要搬运，并让剩余访存尽可能与计算重叠。** 缓存收益比应结合瓶颈变化解释。上述 083 结论来自新同方案两套完整时间线的逐操作核对，详见下述机制报告。

完整数据位于 [500 配置结果](./selected_results.csv) 和 [包含原问题一、二指标的对照表](./all_questions_comparison.csv)。代表例的负载、搬运及子图变化见 [代表算例改进机制](./代表算例改进机制.md)。后者记录具体方案哈希，应与最终计划对应核对。

## 7. 如何确保问题一、问题二不变差

本次采用按问题分别输出方案的方式：原问题一和问题二使用原算法和原已选计划，问题三使用新组合择优。**没有要求三问必须共享同一个新切图计划。** 新问题三计划的无 L2 对照，可能不如原问题二独立最优计划，这不影响原问题二交付成绩。

验证实际完成情况：

1. 100 图 × 1—5 核共 500 个键完整且唯一。
2. 全部最终计划通过官方结构校验，并从完整官方结果重查依赖、流水线冲突、容量等不变量。
3. 全部 500 个最终 Q3 时间不高于各自原 Q3 时间。
4. 同方案无 L2 对照逐项校验计划、输入、配置、官方源码和结果 SHA-256。
5. **{protected:,} 个**快照中列明的受保护文件哈希不变，涵盖原已选 Q1/Q2 计划及结果、原求解器、官方代码与输入等；不是对整个项目每个文件都做了哈希审计。
6. 5 个代表例的原 Q3 方案在本次 Python 环境中重新运行，周期、命中统计、搬运量与原记录完全一致。

新候选 Q3 回执状态：`{json.dumps(dict(statuses), ensure_ascii=False)}`。这是 `evaluations` 下保存的候选回执数，可能含相同语义方案的不同命名候选，不等于不同计划总数；不包括原有基线与独立 CLI 冒烟测试。失败或超时候选若存在，均不进入最终选择。

可核查文件：[最终审计](./final_audit.json)、[原方案重放审计](./baseline_replay_audit.json)、[文件保护快照](./baseline_snapshot.json)、[各核改善分布](./gain_distribution.json)。

## 8. 交付文件及复现

所有新代码和结果均在 `求解/q3_l2_optimization_20260926`：

- [通用问题三改进器](./solve_q3_optimized.py)：接收任意图、核数和已知可行基线，在有限预算内寻找更好的问题三方案；见 [调用说明](./README_通用Q3改进器.md)。
- [批量复现实验入口](./optimize_q3.py)：复现本次 100 图组合搜索、同方案无 L2 对照及汇总。
- [切分候选](./band_candidates.py)、[细粒度候选](./refine_candidates.py)、[缓存感知组件候选](./cache_candidates.py)。
- [最终 500 份问题三计划](./final_plans/)：按 `n1` 至 `n5` 分目录，文件名 `case_XXX_multicore_res.json`。
- [最终问题三计划压缩包](./问题三_优化计划_500组.zip)：同一批 500 份计划，附逐例指标及计划校验清单。
- [逐例新旧指标](./all_questions_comparison.csv)、[最终结果 JSON](./selected_results.json)、[汇总](./summary.json)。
- `evaluations/case_XXX/nN/`：保留候选计划、评价回执及被保留候选的完整压缩结果。

从项目根目录运行（PowerShell）：

```powershell
$py = '.\.venv\Scripts\python.exe'
$opt = '.\求解\q3_l2_optimization_20260926'
& $py -X utf8 -B "$opt\optimize_q3.py" init
& $py -X utf8 -B "$opt\optimize_q3.py" search --cases 1-100 --cores 1,2,3,4,5 --families cache,band,refine --workers 4 --timeout 60
& $py -X utf8 -B "$opt\optimize_q3.py" finalize --workers 4 --timeout 180
& $py -X utf8 -B "$opt\audit_and_export.py" export
& $py -X utf8 -B "$opt\build_report.py"
```

这是完整组合的等价复现命令；本次实际按 band、cache、refine 分阶段运行，阶段超时为 45 或 60 秒，先前试跑的个别候选已缓存。运行记录见 `run_history.jsonl`，早于该日志功能加入的首轮 band 仍有逐候选回执。不要把此日志误称为覆盖全部历史调用。

全量搜索覆盖由 `final_audit.json` 的 `search_coverage` 核实。补测按区间并行完成，覆盖全部 400 个多核配置后停止了已进入重复缓存重放的作业，详见 [搜索完成记录](./search_completion_note.json)。

搜索需要额外离线时间，官方评价模拟的执行周期与求解器在电脑上的运行秒数是两个指标。当前保证针对已核验的基线及本次数据；遇到未知图，通用入口重新评价后才能决定是否改进。没有通过独立未见数据证明泛化最优。

原论文 PDF、正文表格和原正式提交打包目录尚未替换。本目录已经交付新版算法、最终计划与核验结果；将新成绩写入论文时，应同步更新算法描述、表格、图、复现实验说明及提交文件，避免论文和计划版本不一致。

## 9. 建议写进论文的结论

> 在题定硬件配置下，L2 的收益依赖于可复用读取、缓存驻留以及访存对全局执行的约束程度，不能从其带宽优势推断所有计算图均获得明显提速。针对原候选生成对切分粒度、不同计算流水线负载及数据访问顺序考虑不足的问题，本文增加多尺度切分、通信与缓存代价引导的核心分配及组件次序候选，并以未修改的官方评估器择优，保留原方案作为回退。在 100 个测试图的五核配置上，平均加速比从 {avg5['baseline_speedup']:.4f} 提高到 {avg5['speedup']:.4f}，逐例完成时间平均减少 {avg5['time_reduction_pct']:.2f}%，其中 {avg5['improved']} 例改善且无例退化。进一步固定新方案对比有无 L2，五核平均时间收益为 {cache_drop5:.2f}%，说明整体方案优化与缓存加速应分别评价。问题一和问题二保持原方案及结果。
"""
    (HERE / "问题三_L2分析与算法改进报告.md").write_text(report, encoding="utf-8")
    print(json.dumps({"report": str(HERE / "问题三_L2分析与算法改进报告.md"), "improved": changed,
                      "candidate_receipts": dict(statuses)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
