r"""Read existing Q3 evidence only; never import or invoke an evaluator.

Usage (PowerShell, from the repository root):
  & '<PYTHON312>' -X utf8 `
    .\research_a_orion_unified\l2_refine_20260926\evidence_audit.py

Input roots can be relocated with --local-raw and --unified-root. The only
written file is --output (default: EVIDENCE_AUDIT.md beside this script).
No hashes, file fingerprints, tests, performance probes, or new solves.
"""

from __future__ import annotations

import argparse
import collections
import gzip
import json
import statistics
from pathlib import Path


CASES = ("001", "026", "030", "033", "080", "083")
RUN_RELS = (
    "host0/records/run",
    "host1/records/research_a_orion_trident/runs/round01/shard_1",
    "host2/records/research_a_orion_trident/runs/round01/shard_2",
)
RECOVERY_REL = (
    "host1/records/research_a_orion_trident/runs/save_recovery_20260925/"
    "shard_1/attempt_001/jobs/case_049_q3_n1"
)


def read_json(path: Path):
    with path.open(encoding="utf-8-sig") as stream:
        return json.load(stream)


def read_response(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def pair_record(job: Path, provenance: str):
    summary = read_json(job / "summary.json")
    files = {name: (job / name).is_file() for name in (
        "plan.json", "result.json.gz", "same_plan_no_l2_plan.json",
        "same_plan_no_l2_result.json.gz",
    )}
    equal = False
    if files["plan.json"] and files["same_plan_no_l2_plan.json"]:
        equal = read_json(job / "plan.json") == read_json(job / "same_plan_no_l2_plan.json")
    complete = bool(
        summary.get("status") == "ok" and summary.get("pair_status") == "ok"
        and all(files.values()) and equal and summary.get("makespan")
        and summary.get("no_l2_makespan")
    )
    return {
        "case": summary["case"], "n": int(summary["n"]), "summary": summary,
        "files": files, "same_plan": equal, "complete": complete,
        "provenance": provenance, "job": job,
    }


def fifo_counts(progress_paths):
    count = collections.Counter()
    family = collections.defaultdict(collections.Counter)
    examples = []
    for path in progress_paths:
        progress = read_json(path)
        for attempt in progress.get("attempts", []):
            name = str(attempt.get("family", ""))
            if not name.startswith("fifo/"):
                continue
            count["evaluated"] += 1
            family[name]["evaluated"] += 1
            if attempt.get("status") == "ok":
                count["valid"] += 1
                family[name]["valid"] += 1
        previous = None
        for event in progress.get("improvement_events", []):
            name = str(event.get("family", ""))
            if name.startswith("fifo/"):
                count["accepted"] += 1
                family[name]["accepted"] += 1
                if previous is not None and event["makespan"] < previous:
                    count["makespan_improvements"] += 1
                    family[name]["makespan_improvements"] += 1
                if path.parent.name == "case_033_q3_n5":
                    examples.append((path.parent.name, previous, event))
            previous = event.get("makespan", previous)
    return count, family, examples


def aggregate(rows, n):
    ratios = [r["summary"]["no_l2_makespan"] / r["summary"]["makespan"]
              for r in rows if r["n"] == n and r["complete"]]
    return (
        len(ratios), statistics.mean(ratios), statistics.median(ratios),
        sum(x > 1 for x in ratios), sum(x == 1 for x in ratios), sum(x < 1 for x in ratios),
    )


def pipe_rows(response):
    result = []
    for core in response["per_core_timeline"]:
        operations = core["ops"]
        busy = collections.Counter()
        for operation in operations:
            busy[operation["pipe"]] += operation["duration"]
        result.append({
            "core": core["core_id"], "end": max(o["end"] for o in operations),
            "m_busy": busy["PIPE_M"],
            "copy_in_busy": sum(o["duration"] for o in operations if o["op"] == "COPY_IN"),
            "last_copy_in_end": max([o["end"] for o in operations if o["op"] == "COPY_IN"] or [0]),
        })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-raw", type=Path, default=Path(r"<LOCAL_RAW_ROOT>"))
    parser.add_argument("--unified-root", type=Path, default=Path(r"<STOPPED_UNIFIED_RUN_ROOT>"))
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("EVIDENCE_AUDIT.md"))
    args = parser.parse_args()
    roots = [args.local_raw / rel for rel in RUN_RELS]
    original = []
    progress = []
    shard_counts = []
    for shard, root in enumerate(roots):
        records = [pair_record(p.parent, f"original shard {shard}")
                   for p in sorted((root / "jobs").glob("*_q3_n*/summary.json"))]
        original.extend(records)
        progress.extend((r["job"] / "progress.json") for r in records)
        shard_counts.append((shard, len(records), sum(r["complete"] for r in records)))
    recovery = pair_record(args.local_raw / RECOVERY_REL, "authorized recovery, not original run")
    selected = [r for r in original if (r["case"], r["n"]) != ("case_049", 1)] + [recovery]
    fifo, families, examples = fifo_counts(progress)
    unified, _, _ = fifo_counts(sorted((args.unified_root / "jobs").glob("*_q3_n*/progress.json")))
    lines = [
        "# Q3/L2 既有证据核对（2026-09-26）", "",
        "本报告只读取已存在的 Trident 原始记录和已停止的 Unified 记录，未调用求解器或官方评估器。"
        "所有周期来自已保存官方评价的 summary；六个诊断点进一步读取原始响应核对。", "",
        "## 版本与附件边界", "",
        "用户附件《问题三_L2结果核查总结.md》明确引用 `workshop_v1/求解/run_official_experiments.py`，"
        "其五核平均同方案收益 1.025957、083 的 442480/310731 和有限候选重选的实现描述，"
        "属于早期 workshop 的方案和结果。它关于缓存语义与瓶颈的解释可作核查线索，"
        "但不能代替或混入下列 Trident/Unified 新版实测，也不能据其第 6.1 节断言新版没有 F 优化。", "",
        "Trident 原始冻结锚点为 `489ec93a4c74683679e6a87a0175e4b8a3e3bbe1`；"
        "shard 0 是 Windows 保存修复 `854d8775ee378e14089fade6e30fd83b0a832842` / "
        "`trident-1.3-win-save.1`，shard 1/2 是 `trident-1.3`。"
        "Unified 已停轮固定提交为 `217444aba097259feb09cac8544279533f670986`，本报告单列其 F 调用。", "",
        "## 输入定位与复现", "",
        "`--local-raw` 指向已解压三个分机资料的共同根；以下均为该根内相对路径：", "",
        *[f"- shard {i}: `{rel}`" for i, rel in enumerate(RUN_RELS)],
        f"- 唯一纳入的后续接续：`{RECOVERY_REL}`；授权选择记录在其上级 shard 目录的 `SELECTED_RECOVERIES.json`。",
        "- `--unified-root` 指向已停止的 Unified shard 0 运行根，只统计已有 Q3 `jobs/*/progress.json`。", "",
        "复现脚本：`evidence_audit.py --local-raw <解压共同根> --unified-root <已停Unified运行根> --output <新报告.md>`。"
        "脚本仅写指定的新报告，不修改任何输入。", "",
        "逐项读取 `jobs/<case>_q3_n<n>/summary.json` 的 `case,n,status,pair_status,makespan,no_l2_makespan`，"
        "检查 `plan.json` 和 `same_plan_no_l2_plan.json` 的 JSON 对象完全相等，以及两份 `result.json.gz` 的存在。"
        "这不是哈希或文件指纹。全量核对没有解压解析 499 对大响应，因此不把存在性检查称作独立重新验证全部官方响应内容。", "",
        "## 同方案配对覆盖", "", "| 分片 | 原始 Q3 数 | 完整配对 |", "|---|---:|---:|",
        *[f"| {sh} | {total} | {complete} |" for sh, total, complete in shard_counts], "",
    ]
    missing = [r for r in original if not r["complete"]]
    lines += [
        f"原始三片共 {len(original)} 个 Q3 主键、{sum(r['complete'] for r in original)} 对完整配对。缺项如下：", "",
        *[f"- `{r['case']}/n{r['n']}`：主结果 {r['summary'].get('makespan')}，"
          f"pair_status={r['summary'].get('pair_status')}，no_l2_makespan={r['summary'].get('no_l2_makespan')}；"
          "缺同方案 no-L2 plan/response。" for r in missing], "",
        f"049/n1 后续接续的 Q3/no-L2 为 {recovery['summary']['makespan']}/{recovery['summary']['no_l2_makespan']}，"
        f"plan 对象一致={recovery['same_plan']}，pair_status={recovery['summary']['pair_status']}。"
        "该接续单项预算记录为 586.344 秒，继承剩余预算；其结果不能回填成原始运行早期轨迹。"
        f"纳入明确选定接续后是 {sum(r['complete'] for r in selected)}/{len(selected)} 对，仅 014/n5 仍缺配对。", "",
        "## 499 对最终汇总（保留接续来源）", "",
        "收益定义为同一最终 plan 的 `no_l2_makespan / makespan`；没有借独立优化的 Q2 方案。", "",
        "| 核数 | 有效数 | 算术平均收益 | 中位数 | >1 | =1 | <1 |", "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for n in range(1, 6):
        valid, mean, median, faster, equal, slower = aggregate(selected, n)
        lines.append(f"| {n} | {valid} | {mean:.9f} | {median:.9f} | {faster} | {equal} | {slower} |")
    o1 = aggregate(original, 1)
    lines += ["", f"纯原始 n1 口径为 {o1[0]} 对，均值 {o1[1]:.9f}、中位数 {o1[2]:.9f}；"
              "其余 n2..n5 与上表一致。缺失项不填 1、不删低分图，也不将 99 对写成完整 100 图。", ""]
    for r in selected:
        s = r["summary"]
        if r["complete"] and s["no_l2_makespan"] < s["makespan"]:
            lines.append(f"唯一低于 1 的已配对结果是 `{r['case']}/n{r['n']}`：无 L2 {s['no_l2_makespan']} / "
                         f"有 L2 {s['makespan']} = {s['no_l2_makespan']/s['makespan']:.12f}。这里保留真实反向差异。")
    lines += ["", "## F 是否实际产生过改善", "",
              "F 定义为已有 `progress.attempts[].family` 或 `improvement_events[].family` 前缀 `fifo/`。"
              "调用数按 attempts 计；接受数按 improvement_events 计；周期改善比较该接受事件与前一真实 incumbent 的 Makespan。"
              "周期相同但 added COPY 变好的接受另计，不冒充周期下降。", "",
              "| 已有数据 | F 调用 | 合法调用 | 接受次数 | 严格周期改善事件 |", "|---|---:|---:|---:|---:|",
              f"| Trident 原始三片 Q3 | {fifo['evaluated']} | {fifo['valid']} | {fifo['accepted']} | {fifo['makespan_improvements']} |",
              f"| 已停 Unified 本片 Q3 | {unified['evaluated']} | {unified['valid']} | {unified['accepted']} | {unified['makespan_improvements']} |", "",
              "Trident 明细（接受事件可与 `report/paper_data/source_yield_and_cost.csv` 的同名字段交叉核对）：", "",
              "| F 来源 | 调用 | 合法 | 接受 | 周期改善 |", "|---|---:|---:|---:|---:|"]
    for name, count in sorted(families.items()):
        lines.append(f"| {name} | {count['evaluated']} | {count['valid']} | {count['accepted']} | {count['makespan_improvements']} |")
    lines += ["", "上述是优化过程中真实增量接受事件，不是独立 F 消融胜率，也不是互相独立的 517 个图。"
              "F 改变子图/访问次序，其收益可能同时改善无 L2 时序；不能把每次 F 接受都归因为 L2 带宽带来的净收益。", ""]
    for key, before, event in examples:
        lines.append(f"直接例证 `{key}/progress.json`：evaluation={event['evaluation']}，"
                     f"elapsed_seconds={event['elapsed_seconds']:.6f}，`{event['name']}` ({event['family']}) "
                     f"使 {before} → {event['makespan']}。该最终方案的同方案有无 L2 工期仍完全相同，"
                     "这直接反驳“F 不运行”，同时约束其缓存专属因果归因。")
    lines += ["", "## 固定六图五核起点", "",
              "这六图预先覆盖零命中、命中被计算隐藏、Spill、显著 L2 收益及反复逐出/重入。"
              "是机制诊断样本，其均值不能代表 100 图。起点均为 shard 0 原始 "
              "`jobs/case_XXX_q3_n5/plan.json`，不是只有分数的虚构种子。", "",
              "| 图 | 有 L2 | 同 plan 无 L2 | 比值 | 字节命中率 | Spill bytes | 重复 insert 的 Tensor 数 / 额外 insert 数 |", "|---|---:|---:|---:|---:|---:|---:|"]
    detailed = {}
    for case in CASES:
        job = roots[0] / "jobs" / f"case_{case}_q3_n5"
        summary = read_json(job / "summary.json")
        response = read_response(job / "result.json.gz")
        no_response = read_response(job / "same_plan_no_l2_result.json.gz")
        official, no = response["official_result"], no_response["official_result"]
        if official["makespan"] != summary["makespan"] or no["makespan"] != summary["no_l2_makespan"]:
            raise ValueError(f"Saved response/summary cycle mismatch at case_{case}")
        if not pair_record(job, "diagnostic starting plan")["complete"]:
            raise ValueError(f"Incomplete exact pair at case_{case}")
        inserts = collections.Counter(e["tensor_id"] for e in official["cache_events"] if e["event"] == "insert")
        stats = official["cache_stats"]
        hit = stats["hit_bytes"] / (stats["hit_bytes"] + stats["miss_bytes"])
        detailed[case] = (official, no, pipe_rows(official), pipe_rows(no))
        lines.append(f"| {case} | {official['makespan']} | {no['makespan']} | {no['makespan']/official['makespan']:.9f} | "
                     f"{hit:.6%} | {summary['spill_added_copy_bytes']} | {sum(v>1 for v in inserts.values())} / {sum(v-1 for v in inserts.values())} |")
    lines += ["", "六图的周期已与保存的原始 `official_result.makespan` 对照；缓存事件来自 "
              "`official_result.cache_events`，命中字节率由 `cache_stats.hit_bytes/(hit_bytes+miss_bytes)` 计算。"
              "重复 insert 按真实 `tensor_id` 计，额外 insert 为每个 Tensor 的 insert 次数减 1 的和；"
              "它不等同于 Spill 次数或 COPY_IN 次数。", "",
              "## 时间线与机制证据", ""]
    for case in ("001", "030", "033", "080"):
        official, no, cores, no_cores = detailed[case]
        lines += [f"### {case}", "", "| 核 | Q3 终点 | no-L2 终点 | Q3 M 忙时 | Q3 COPY_IN 忙时 | no-L2 COPY_IN 忙时 |", "|---|---:|---:|---:|---:|---:|"]
        for core, other in zip(cores, no_cores):
            lines.append(f"| {core['core']} | {core['end']} | {other['end']} | {core['m_busy']} | {core['copy_in_busy']} | {other['copy_in_busy']} |")
        lines.append("")
    lines += [
        "001：Tensor 1000000001 在 t=0 被五核同时 miss，t=100 才首次 insert；该图没有淘汰和重复 insert。"
        "五核 M 忙时都是 46560/47502，现有起点主要受计算限制。仅提高这 4 个跟随读取的命中不能保证降低工期。", "",
        "033：瓶颈 core3 的 M 忙时 346368，Q3 工期 351503；COPY_IN 忙时由 86084 降至 49347，"
        "工期却不变。030 同样 M 忙时已接近 Makespan。原响应支持搬运收益被计算/依赖重叠吸收，"
        "但本报告未完整重建所有关键路径，不声称已经定位每一周期的因果。", "",
        "080：无 L2 时 MTE2 累计忙时约 87–91k，L2 后约 30–38k；M 忙时约 56–60k，"
        "终点从 94963 降至 63001。其局部搬运收益确实传递到全局工期。", "",
        "033 的 Tensor 1054 真实事件如下（不是从 COPY 次数推断）：", "",
        "| 时刻 | 事件 | 核 / 相关 Tensor |", "|---:|---|---|",
    ]
    for event in detailed["033"][0]["cache_events"]:
        if event.get("tensor_id") == 1054:
            lines.append(f"| {event['time']} | {event['event']} 1054 | core{event.get('core_id')} |")
        elif 1054 in event.get("evicted_tensor_ids", []):
            lines.append(f"| {event['time']} | 1054 被逐出 | insert {event['tensor_id']} |")
    lines += ["", "## 对本次小批次的约束", "",
              "- 保留上述已验证强起点，候选仅在官方 `(Makespan, added COPY)` 更优时替换。",
              "- 优先优化真实 critical COPY 终点、消费者落入填充与逐出之间的窗口，以及多次读取的 Tensor 身份；命中率只是辅助指标。",
              "- 高命中计算受限图用于检查无害性与成本准入，不以提高命中率为单独成功目标。",
              "- 每个新最终 plan 必须另做该 plan 的 no-L2 回放；旧 plan 配对只能解释旧起点。",
              "- Q3 专属候选不改变 Q1/Q2 入口、原图、官方配置或评估器。六图改进与 100 图结论严格区分。", ""]
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"report": str(args.output), "original_pairs": sum(r["complete"] for r in original),
                      "selected_pairs": sum(r["complete"] for r in selected), "trident_f": dict(fifo),
                      "unified_f": dict(unified)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
