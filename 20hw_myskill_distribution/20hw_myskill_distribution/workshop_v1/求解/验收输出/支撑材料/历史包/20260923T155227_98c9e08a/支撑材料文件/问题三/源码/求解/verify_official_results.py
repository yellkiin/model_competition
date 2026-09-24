"""Independent invariants over original graph, submitted plan and official trace."""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path


def read_json(path: Path):
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    return json.loads(path.read_text(encoding="utf-8"))


def verify(graph: dict, plan: dict, result: dict) -> dict:
    n = len(plan["core_schedules"])
    assert result["num_cores"] == n
    internal = {x["id"] for x in graph["ops"] if x["op"] not in {"COPY_IN", "COPY_OUT"}}
    assignment = {int(u): sg for u, sg in plan["node_to_subgraph"].items()}
    assert set(assignment) == internal
    scheduled = [sg for order in plan["core_schedules"] for sg in order]
    assert len(scheduled) == len(set(scheduled)) and set(scheduled) == set(assignment.values())
    core_of_sg = {sg: core for core, order in enumerate(plan["core_schedules"]) for sg in order}
    cores = result["per_core_timeline"]
    assert len(cores) == n
    seen = Counter()
    all_ends = []
    pipe_intervals = defaultdict(list)
    for core in cores:
        c = core["core_id"]
        assert 0 <= c < n
        for op in core["ops"]:
            assert op["start"] >= 0 and op["end"] >= op["start"]
            assert op["duration"] == op["end"] - op["start"]
            all_ends.append(op["end"])
            if op["op_id"] in internal:
                seen[op["op_id"]] += 1
                sgid = op.get("subgraph_id", op["task_id"])
                assert sgid == assignment[op["op_id"]]
                assert core_of_sg[sgid] == c
            pipe_intervals[c, op["pipe"]].append((op["start"], op["end"]))
    assert set(seen) == internal and all(value == 1 for value in seen.values())
    assert result["makespan"] == max(all_ends, default=0)
    for intervals in pipe_intervals.values():
        intervals.sort()
        for (_, end), (next_start, _) in zip(intervals, intervals[1:]):
            assert next_start >= end
    capacity = result["capacity_bytes"]
    for peak in result["memory_peak_by_core"].values():
        for space, used in peak.items():
            assert 0 <= used <= capacity[space]
    movement = result["data_movement_bytes"]
    assert movement["scheduled_copy_bytes"] - movement["original_graph_copy_bytes"] == movement["added_copy_bytes"]
    assert movement["partition_added_copy_bytes"] + movement["spill_added_copy_bytes"] == movement["added_copy_bytes"]
    if result["scene"] == "A":
        tasks = {task["task_id"]: (core["core_id"], task) for core in cores for task in core["tasks"]}
        wait_same = result["task_same_core_wait_cycles"]
        wait_cross = result["task_cross_core_wait_cycles"]
        for core in cores:
            spans = core["tasks"]
            for previous, following in zip(spans, spans[1:]):
                assert following["start"] >= previous["end"] + wait_same
        for dep in result["task_dependencies"]:
            source_core, source = tasks[dep["source"]]
            target_core, target = tasks[dep["target"]]
            if source_core != target_core:
                assert target["start"] >= source["end"] + wait_cross
            else:
                assert target["start"] >= source["end"]
    else:
        wait = result["cross_core_copy_delay_cycles"]
        for transfer in result["cross_core_transfers"]:
            assert transfer["copy_in_release"] >= transfer["copy_out_end"] + wait
            assert transfer["copy_in_start"] >= transfer["copy_in_release"]
        if "cache_stats" in result:
            cache = result["cache_stats"]
            assert cache["hits"] + cache["copy_in_misses"] == cache["accesses"]
            assert cache["hits"] == cache["copy_in_hits"]
            total = cache["hit_bytes"] + cache["miss_bytes"]
            assert abs(cache["hit_rate"] - (cache["hit_bytes"] / total if total else 0)) < 1e-12
    return {
        "status": "PASS",
        "internal_op_count": len(internal),
        "timeline_op_count": len(all_ends),
        "makespan": result["makespan"],
        "num_cores": n,
        "checked_pipe_sequences": len(pipe_intervals),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("graph", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("result", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(read_json(args.graph), read_json(args.plan), read_json(args.result))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
