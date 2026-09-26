"""Rebuild representative Q3 mechanism evidence from selected official traces.

Example after the final search and finalize:
    python -B analyze_representative.py --selection-source finalized --no-evaluate

This script never modifies solver code, original results, or selected.json.
An absent matched Q2 may be evaluated in the candidate's own folder unless
--no-evaluate is supplied. Earlier representative snapshots are retained.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import time

from optimize_q3 import HERE, ROOT, DATA, read, run_eval, baseline_folder, digest


CASES = ("case_003", "case_056", "case_044", "case_083")
JSON_PATH = HERE / "representative_mechanisms.json"
MARKDOWN_PATH = HERE / "代表算例改进机制.md"


def _live_selections(cases):
    return {case: read(HERE / "evaluations" / case / "n5/selected.json")
            for case in cases}


def load_selections(cases, source):
    live = _live_selections(cases)
    final_path = HERE / "selected_results.json"
    final = {}
    if final_path.exists():
        final = {row["case"]: row for row in read(final_path)
                 if row["cores"] == 5 and row["case"] in cases}
    mismatches = [case for case in cases if case not in final or
                  final[case]["plan_path"] != live[case]["plan_path"]]
    if source == "finalized":
        if mismatches:
            raise RuntimeError(
                "Finalized selections are absent or stale for: " + ", ".join(mismatches)
                + ". Run finalize first or explicitly use --selection-source live.")
        return final, "finalized", mismatches
    if source == "live":
        return live, "live_snapshot", mismatches
    if not mismatches:
        return final, "finalized", []
    return live, "live_snapshot", mismatches


def _variant(graph, folder):
    plan = read(folder / "plan.json")
    result = read(folder / "q3.json.gz")
    owner = {sg: core for core, order in enumerate(plan["core_schedules"])
             for sg in order}
    coremap = {int(op): owner[sg] for op, sg in plan["node_to_subgraph"].items()}
    ops = {op["id"]: op for op in graph["ops"]
           if op["op"] not in {"COPY_IN", "COPY_OUT"}}
    loads = [Counter() for _ in plan["core_schedules"]]
    for op_id, op in ops.items():
        loads[coremap[op_id]][op["pipe"]] += max(1, op["cycles"])
    global_work = Counter()
    for load in loads:
        global_work.update(load)
    movement, cache = result["data_movement_bytes"], result["cache_stats"]
    read_bytes = cache["hit_bytes"] + cache["miss_bytes"]
    per_core = []
    for core in result["per_core_timeline"]:
        cid, counts = core["core_id"], Counter()
        for event in result["cache_events"]:
            if event["core_id"] == cid and event["event"] in {"hit", "miss"}:
                counts[event["event"] + "_count"] += 1
                counts[event["event"] + "_bytes"] += event["size_bytes"]
        reads = [op for op in core["ops"] if op["op"] == "COPY_IN"]
        per_core.append({
            "core_id": cid, **counts,
            "copy_in_pipe_busy_cycles": sum(op["duration"] for op in reads),
            "ddr_read_op_duration_sum": sum(op["duration"] for op in reads
                                             if op.get("memory_path") == "DDR"),
            "cache_read_op_duration_sum": sum(op["duration"] for op in reads
                                               if op.get("memory_path") == "CACHE_READ"),
        })
    record = {
        "plan_path": str((folder / "plan.json").relative_to(ROOT)),
        "plan_sha256": digest(folder / "plan.json"),
        "q3_result_path": str((folder / "q3.json.gz").relative_to(ROOT)),
        "q3_result_sha256": digest(folder / "q3.json.gz"),
        "makespan": result["makespan"],
        "subgraph_count": sum(map(len, plan["core_schedules"])),
        "subgraph_count_by_core": list(map(len, plan["core_schedules"])),
        "internal_op_count_by_core": [sum(core == cid for core in coremap.values())
                                      for cid in range(len(loads))],
        "compute_pipe_cycles_by_core": [dict(load) for load in loads],
        "fixed_assignment_compute_lower_bound": max(
            (cycles for load in loads for cycles in load.values()), default=0),
        "global_compute_lower_bound": max(global_work.values(), default=0) / len(loads),
        "core_finish_times": [max((op["end"] for op in core["ops"]), default=0)
                              for core in result["per_core_timeline"]],
        "data_movement_bytes": movement,
        "cache_stats": cache,
        "copy_in_bytes": read_bytes,
        "copy_out_bytes_inferred": movement["scheduled_copy_bytes"] - read_bytes,
        "ddr_copy_bytes_inferred": movement["scheduled_copy_bytes"] - cache["hit_bytes"],
        "copy_in_count": sum(op["op"] == "COPY_IN" for core in result["per_core_timeline"]
                             for op in core["ops"]),
        "copy_out_count": sum(op["op"] == "COPY_OUT" for core in result["per_core_timeline"]
                              for op in core["ops"]),
        "cross_core_transfer_count": len(result["cross_core_transfers"]),
        "memory_peak_by_core": result["memory_peak_by_core"],
        "step3_by_core": result["step3_by_core"],
        "cache_timing_by_core": per_core,
    }
    return record, coremap


def mechanism_text(record):
    old, new = record["old"], record["new"]
    pieces = []
    same_loads = old["compute_pipe_cycles_by_core"] == new["compute_pipe_cycles_by_core"]
    if record["core_reassigned_op_count"] == 0 and same_loads:
        pieces.append("原始计算操作没有换核，各核心各计算Pipe工作量完全不变；改善不能归因于计算负载均衡。")
    else:
        pieces.append(
            f"{record['core_reassigned_op_count']:,}个原始计算操作改变核心归属。固定归属计算下界从"
            f"{old['fixed_assignment_compute_lower_bound']:,}变为{new['fixed_assignment_compute_lower_bound']:,}周期，"
            "可据此评估重分核改善；下界之外的收益仍包含依赖顺序与通信时序变化。")
    reduction = record["no_l2_reduction_pct"]
    if reduction >= 0:
        pieces.append(f"新方案在无L2时也缩短{reduction:.2f}%，而有L2的总改善为"
                      f"{record['q3_reduction_pct']:.2f}%；两者不能都称为缓存收益。")
    else:
        pieces.append(f"新方案若关闭L2反而变慢{-reduction:.2f}%，有L2却缩短"
                      f"{record['q3_reduction_pct']:.2f}%；该方案的收益依赖缓存及其引起的访问时序变化。")
    ddr_change = new["ddr_copy_bytes_inferred"] - old["ddr_copy_bytes_inferred"]
    pieces.append(f"估算DDR总搬运{'增加' if ddr_change > 0 else '减少' if ddr_change < 0 else '不变'}"
                  + (f"{abs(ddr_change):,}B。" if ddr_change else "。"))
    if ddr_change > 0:
        pieces.append("因此不能把提速解释为减少总DDR流量；需看计算分配、关键链和共享带宽请求时序。")
    old_spill = old["data_movement_bytes"]["spill_added_copy_bytes"]
    new_spill = new["data_movement_bytes"]["spill_added_copy_bytes"]
    if old_spill > 0 and new_spill == 0:
        pieces.append(f"SPILL新增搬运从{old_spill:,}B清零，说明新执行顺序与驻留安排消除了此类换出/换入开销。")
    cid = max(range(len(old["core_finish_times"])), key=lambda c: old["core_finish_times"][c])
    old_t = {row["core_id"]: row for row in old["cache_timing_by_core"]}[cid]
    new_t = {row["core_id"]: row for row in new["cache_timing_by_core"]}[cid]
    pieces.append(f"原最晚核心{cid}的COPY_IN Pipe占用从{old_t['copy_in_pipe_busy_cycles']:,}"
                  f"变为{new_t['copy_in_pipe_busy_cycles']:,}周期，其核完工从"
                  f"{old['core_finish_times'][cid]:,}变为{new['core_finish_times'][cid]:,}周期。")
    pieces.append(f"同方案L2节省的绝对周期由{record['cache_saving_cycles_old']:,}变为"
                  f"{record['cache_saving_cycles_new']:,}；这是各方案自己的有/无L2差值，不能据此做唯一因果归因。")
    if new["makespan"] == new["matched_no_l2_makespan"] and new["cache_stats"]["hits"]:
        critical_core = max(range(len(new["core_finish_times"])), key=lambda c: new["core_finish_times"][c])
        timing = next(row for row in new["matched_timing_by_core"] if row["core_id"] == critical_core)
        pieces.append(f"当前有/无L2总时间相同，但仍有{new['cache_stats']['hits']}次命中、"
                      f"{new['cache_stats']['hit_bytes']:,}B命中数据。关键核心{critical_core}的COPY_IN占用"
                      f"由无L2的{timing['no_l2']['copy_in_pipe_busy_cycles']:,}降至"
                      f"有L2的{timing['l2']['copy_in_pipe_busy_cycles']:,}周期。")
        if timing["non_copy_operation_timings_equal"]:
            pieces.append("这个关键核心的全部原始计算操作起止时间却完全一致，直接表明更快的读入未缩短计算关键路径。")
        lower_bound = new["fixed_assignment_compute_lower_bound"]
        if lower_bound:
            pieces.append(f"总完工仅高于该固定归属计算下界{100*(new['makespan']/lower_bound-1):.2f}%，"
                          "缓存的局部加速被计算瓶颈遮蔽，不能解释为缓存未启用。")
    return "".join(pieces)


def _matched_timing(no_l2, l2):
    result = []
    no_l2_cores = {core["core_id"]: core for core in no_l2["per_core_timeline"]}
    for core in l2["per_core_timeline"]:
        cid = core["core_id"]
        old_core = no_l2_cores[cid]
        before = {op["op_id"]: op for op in old_core["ops"]}
        after = {op["op_id"]: op for op in core["ops"]}
        if set(before) != set(after):
            raise RuntimeError("Matched no-L2/Q3 operation IDs differ")
        changed = Counter()
        for op_id, old_op in before.items():
            new_op = after[op_id]
            if (old_op["start"], old_op["end"]) != (new_op["start"], new_op["end"]):
                changed[old_op["op"]] += 1
        stats = {}
        for label, trace in (("no_l2", old_core), ("l2", core)):
            pipe_stats = {}
            for pipe in sorted({op["pipe"] for op in trace["ops"]
                                if op["op"] not in {"COPY_IN", "COPY_OUT"}}):
                ops = [op for op in trace["ops"] if op["pipe"] == pipe
                       and op["op"] not in {"COPY_IN", "COPY_OUT"}]
                start, end = min(op["start"] for op in ops), max(op["end"] for op in ops)
                busy = sum(op["duration"] for op in ops)
                pipe_stats[pipe] = {"start": start, "end": end, "busy": busy,
                                    "idle_between_first_last": end - start - busy}
            stats[label] = {
                "finish": max((op["end"] for op in trace["ops"]), default=0),
                "copy_in_pipe_busy_cycles": sum(op["duration"] for op in trace["ops"] if op["op"] == "COPY_IN"),
                "compute_pipe_timing": pipe_stats,
            }
        result.append({"core_id": cid, "changed_operations_by_type": dict(changed),
                       "non_copy_operation_timings_equal": not any(
                           kind not in {"COPY_IN", "COPY_OUT"} for kind in changed), **stats})
    return result


def analyze_case(case, selected, baseline, args):
    old_folder = baseline_folder(baseline)
    new_folder = (ROOT / selected["plan_path"]).parent
    receipt_path = new_folder / "q2.receipt.json"
    if args.no_evaluate:
        if not receipt_path.exists():
            raise RuntimeError(f"Missing matched Q2 receipt: {receipt_path}")
        q2 = read(receipt_path)
    else:
        q2 = run_eval(case, new_folder, 2, args.timeout, 10**30)
    if q2.get("status") != "PASS":
        raise RuntimeError(f"Matched Q2 did not pass: {case}: {q2}")
    # This also accepts original Q2 receipts for an unchanged baseline winner.
    q2_plan_hash = q2.get("plan_sha256", q2.get("fingerprint", {}).get("plan_sha256"))
    if q2_plan_hash != digest(new_folder / "plan.json"):
        raise RuntimeError(f"Matched Q2 plan hash mismatch: {case}")
    graph = read(DATA / f"{case}.json")
    old, old_map = _variant(graph, old_folder)
    new, new_map = _variant(graph, new_folder)
    if new["makespan"] != selected["makespan"]:
        raise RuntimeError(f"Selected Q3 time mismatch: {case}")
    old["matched_no_l2_makespan"] = int(baseline["q3_matched_no_l2_cycles"])
    new["matched_no_l2_makespan"] = q2["makespan"]
    new["matched_no_l2_receipt_path"] = str(receipt_path.relative_to(ROOT))
    new["matched_no_l2_result_path"] = q2.get("result_path", str((new_folder / "q2.json.gz").relative_to(ROOT)))
    new["matched_timing_by_core"] = _matched_timing(
        read(ROOT / new["matched_no_l2_result_path"]), read(new_folder / "q3.json.gz"))
    record = {
        "case": case, "cores": 5, "selection_snapshot": selected,
        "old": old, "new": new,
        "core_reassigned_op_count": sum(old_map[u] != new_map[u] for u in old_map),
        "q3_reduction_pct": 100 * (1 - new["makespan"] / old["makespan"]),
        "no_l2_reduction_pct": 100 * (1 - new["matched_no_l2_makespan"] / old["matched_no_l2_makespan"]),
        "cache_saving_cycles_old": old["matched_no_l2_makespan"] - old["makespan"],
        "cache_saving_cycles_new": new["matched_no_l2_makespan"] - new["makespan"],
    }
    record["analysis_summary"] = mechanism_text(record)
    return record


def _retain_history(previous, current):
    current_keys = {(row["case"], row["new"]["plan_sha256"]) for row in current}
    historical = {}
    for row in previous.get("historical_candidate_comparisons", []) + previous.get("cases", []):
        key = row["case"], row["new"]["plan_sha256"]
        if key not in current_keys:
            historical[key] = row
    return list(historical.values())


def render_markdown(data):
    scope = "已完成finalize且与当前选择一致" if data["selection_source"] == "finalized" else "当前搜索选择快照，尚不称为最终方案"
    lines = ["# 代表算例改进机制核查", "", f"分析时间：{data['created_at']}。选择来源：{scope}。",
             "", "本报告使用5核方案的完整事件轨迹和原始图。后续若继续搜索，以候选名和完整plan SHA-256标识本报告版本。",
             "", "总改善指新Q3相对旧Q3的时间下降；同方案L2节省指该方案Q2时间减Q3时间，二者不能混称。",
             "", "|算例|当前候选|旧Q3→新Q3|总时间下降|旧无L2→新同方案无L2|新方案L2节省|",
             "|---|---|---:|---:|---:|---:|"]
    for row in data["cases"]:
        old, new = row["old"], row["new"]
        lines.append(f"|{row['case']}|{row['selection_snapshot']['candidate']}|{old['makespan']:,}→{new['makespan']:,}|"
                     f"{row['q3_reduction_pct']:.2f}%|{old['matched_no_l2_makespan']:,}→{new['matched_no_l2_makespan']:,}|"
                     f"{row['cache_saving_cycles_new']:,} cycles|")
    for row in data["cases"]:
        old, new = row["old"], row["new"]
        om, nm = old["data_movement_bytes"], new["data_movement_bytes"]
        lines.extend(["", f"## {row['case']} / {row['selection_snapshot']['candidate']}", "", row["analysis_summary"], "",
                      "|指标|旧方案|当前方案|", "|---|---:|---:|"])
        metrics = [
            ("子图数", old["subgraph_count"], new["subgraph_count"]),
            ("固定归属计算下界/cycles", old["fixed_assignment_compute_lower_bound"], new["fixed_assignment_compute_lower_bound"]),
            ("不限制归属计算下界/cycles", old["global_compute_lower_bound"], new["global_compute_lower_bound"]),
            ("额外COPY/B", om["added_copy_bytes"], nm["added_copy_bytes"]),
            ("切分新增COPY/B", om["partition_added_copy_bytes"], nm["partition_added_copy_bytes"]),
            ("SPILL新增COPY/B", om["spill_added_copy_bytes"], nm["spill_added_copy_bytes"]),
            ("所有路径计划COPY/B", om["scheduled_copy_bytes"], nm["scheduled_copy_bytes"]),
            ("COPY_IN/B", old["copy_in_bytes"], new["copy_in_bytes"]),
            ("推算COPY_OUT/B", old["copy_out_bytes_inferred"], new["copy_out_bytes_inferred"]),
            ("推算DDR COPY/B", old["ddr_copy_bytes_inferred"], new["ddr_copy_bytes_inferred"]),
            ("跨核传输连接数", old["cross_core_transfer_count"], new["cross_core_transfer_count"]),
            ("COPY_IN指令数", old["copy_in_count"], new["copy_in_count"]),
            ("COPY_OUT指令数", old["copy_out_count"], new["copy_out_count"]),
        ]
        lines.extend(f"|{name}|{a:,}|{b:,}|" for name, a, b in metrics)
        lines.append(f"|字节命中率|{old['cache_stats']['hit_rate']:.4%}|{new['cache_stats']['hit_rate']:.4%}|")
        lines.extend(["", "每核原始计算操作的Pipe工作量与完工时间（cycles，核心编号从0开始）：", "",
                      "|核心|旧PIPE_M|新PIPE_M|旧PIPE_V|新PIPE_V|旧完工|新完工|",
                      "|---|---:|---:|---:|---:|---:|---:|"])
        for core in range(row["cores"]):
            a, b = old["compute_pipe_cycles_by_core"][core], new["compute_pipe_cycles_by_core"][core]
            lines.append(f"|{core}|{a.get('PIPE_M', 0):,}|{b.get('PIPE_M', 0):,}|{a.get('PIPE_V', 0):,}|"
                         f"{b.get('PIPE_V', 0):,}|{old['core_finish_times'][core]:,}|{new['core_finish_times'][core]:,}|")
        lines.extend(["", f"旧plan SHA-256：`{old['plan_sha256']}`。", f"新plan SHA-256：`{new['plan_sha256']}`。", "",
                      f"[旧完整Q3结果]({(ROOT / old['q3_result_path']).as_posix()}) · "
                      f"[当前完整Q3结果]({(ROOT / new['q3_result_path']).as_posix()}) · "
                      f"[当前同方案无L2结果]({(ROOT / new['matched_no_l2_result_path']).as_posix()})"])
    history = data["historical_candidate_comparisons"]
    if history:
        lines.extend(["", "## 历史候选对照（不代表当前最终选择）", "",
                      "这些方案来自先前代表例快照，保留用于比较机制；不得把其周期或解释替代当前选择。", "",
                      "|算例|历史候选|历史Q3周期|该候选无L2周期|plan SHA-256前12位|",
                      "|---|---|---:|---:|---|"])
        for row in history:
            lines.append(f"|{row['case']}|{row['selection_snapshot']['candidate']}|{row['new']['makespan']:,}|"
                         f"{row['new']['matched_no_l2_makespan']:,}|{row['new']['plan_sha256'][:12]}|")
        lines.append("\n历史候选完整负载、轨迹路径与当时解释保存在JSON的historical_candidate_comparisons。")
    lines.extend(["", "## 口径与边界", "",
                  "固定归属下界对每个核心每条独占计算Pipe累计原始非COPY操作的max(1, cycles)，再取最大值；全局下界对同Pipe总工作量除以5后取最大值。下界不包含依赖与通信，其与实际时间之差不能全部称为通信开销。", "",
                  "推算DDR量=scheduled_copy_bytes−hit_bytes；推算写回量=scheduled_copy_bytes−hit_bytes−miss_bytes。这是官方COPY字节口径，不含真实硬件协议开销。", "",
                  "COPY_IN占用由轨迹end−start累加，包含共享带宽竞争的延长，不是纯数据传输工作量。不同核心占用时长不可相加后当作全局完工时间。", "",
                  "这些统计验证分核、数据量和访问时序变化；尚未逐条还原全部关键依赖与FIFO事件，不能把周期差唯一归因于某一个机制，不能推广成真实芯片上的普遍规律。", "",
                  "完整逐核缓存读时长、内存峰值、Step3信息、结果SHA-256与选择快照详见representative_mechanisms.json。"])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection-source", choices=("auto", "finalized", "live"), default="auto")
    parser.add_argument("--no-evaluate", action="store_true")
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    selected, source, mismatches = load_selections(CASES, args.selection_source)
    snapshot = read(HERE / "baseline_snapshot.json")
    baseline = {(row["case"], int(row["cores"])): row for row in snapshot["rows"]}
    records = [analyze_case(case, selected[case], baseline[case, 5], args) for case in CASES]
    current = _live_selections(CASES)
    changed = [case for case in CASES if current[case]["plan_path"] != selected[case]["plan_path"]]
    if changed:
        raise RuntimeError("Selections changed during analysis; output not overwritten: " + ", ".join(changed))
    previous = read(JSON_PATH) if JSON_PATH.exists() else {}
    payload = {
        "schema_version": 2,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "selection_source": source,
        "finalized_live_mismatches_at_start": mismatches,
        "scope": "Five-core representative selections, unchanged official evaluator/config; selected.json and original outputs unchanged.",
        "official_config": snapshot["official_config"],
        "analysis_source_sha256": digest(Path(__file__)),
        "cases": records,
        "historical_candidate_comparisons": _retain_history(previous, records),
    }
    if previous:
        old_bytes = JSON_PATH.read_bytes()
        token = hashlib.sha256(old_bytes).hexdigest()[:12]
        archive = HERE / "representative_snapshots" / token
        archive.mkdir(parents=True, exist_ok=True)
        shutil.copy2(JSON_PATH, archive / JSON_PATH.name)
        if MARKDOWN_PATH.exists():
            shutil.copy2(MARKDOWN_PATH, archive / MARKDOWN_PATH.name)
    JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    MARKDOWN_PATH.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "PASS", "selection_source": source,
                      "cases": [{"case": row["case"], "candidate": row["selection_snapshot"]["candidate"],
                                 "makespan": row["new"]["makespan"], "plan_sha256": row["new"]["plan_sha256"]}
                                for row in records],
                      "historical_candidates": len(payload["historical_candidate_comparisons"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
