"""Dependency-band partition with independent subgraphs per core and band."""

from __future__ import annotations

import argparse
import heapq
import json
import math
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "数据/原始/A题官方附件/code"
sys.path.insert(0, str(CODE))
from stub_multicore_cut_and_schedule import (  # noqa: E402
    _build_op_adjacency,
    _contract_excluded_copy_nodes,
    validate_multicore_plan,
)


def build_plan(graph: dict, num_cores: int, target_bands: int = 8) -> tuple[dict, dict]:
    if not 1 <= num_cores <= 5:
        raise ValueError("num_cores must be in 1..5")
    if target_bands < 1:
        raise ValueError("target_bands must be positive")
    ops = {op["id"]: op for op in graph["ops"] if op["op"] not in {"COPY_IN", "COPY_OUT"}}
    _, full_succ = _build_op_adjacency(graph)
    pred, succ = _contract_excluded_copy_nodes(sorted(ops), full_succ)
    indegree = {u: len(pred[u]) for u in ops}
    depth = {u: 0 for u in ops}
    ready = [u for u, d in indegree.items() if d == 0]
    heapq.heapify(ready)
    count = 0
    while ready:
        u = heapq.heappop(ready)
        count += 1
        for v in succ[u]:
            depth[v] = max(depth[v], depth[u] + 1)
            indegree[v] -= 1
            if indegree[v] == 0:
                heapq.heappush(ready, v)
    if count != len(ops):
        raise ValueError("contracted operation graph has a cycle")
    max_depth = max(depth.values(), default=0)
    band_width = math.ceil((max_depth + 1) / target_bands)
    band_of = {u: depth[u] // band_width for u in ops}
    by_band = defaultdict(list)
    for u, band in band_of.items():
        by_band[band].append(u)

    core_of = {}
    assignment = defaultdict(list)
    loads = [0] * num_cores
    band_records = []
    for band in sorted(by_band):
        members = by_band[band]
        parent = {u: u for u in members}

        def find(u: int) -> int:
            while parent[u] != u:
                parent[u] = parent[parent[u]]
                u = parent[u]
            return u

        for u in members:
            for v in succ[u]:
                if v in parent:
                    parent[find(v)] = find(u)
        components = defaultdict(list)
        for u in members:
            components[find(u)].append(u)
        weighted = [
            (sum(ops[u]["cycles"] + 1 for u in group), min(group), group)
            for group in components.values()
        ]
        weighted.sort(key=lambda item: (-item[0], item[1]))
        band_loads = [0] * num_cores
        for weight, _, group in weighted:
            # Prefer a predecessor's core when it keeps a tensor local, but
            # never sacrifice substantial work balance for that preference.
            affinity = [0] * num_cores
            for u in group:
                for p in pred[u]:
                    if p in core_of:
                        affinity[core_of[p]] += 1
            best = min(
                range(num_cores),
                key=lambda c: (band_loads[c] + weight - min(affinity[c], weight // 8), loads[c], c),
            )
            assignment[band, best].extend(group)
            band_loads[best] += weight
            loads[best] += weight
            for u in group:
                core_of[u] = best
        band_records.append({"band": band, "components": len(components), "loads": band_loads})

    mapping = {}
    schedules = [[] for _ in range(num_cores)]
    for band, core in sorted(assignment):
        group = assignment[band, core]
        if not group:
            continue
        sgid = len(mapping) + 1  # unique, deterministic, nonnegative
        schedules[core].append(sgid)
        for u in group:
            mapping[str(u)] = sgid
    plan = {"node_to_subgraph": mapping, "core_schedules": schedules}
    validate_multicore_plan(graph, plan)
    meta = {
        "method": "dependency_bands",
        "num_cores": num_cores,
        "target_bands": target_bands,
        "actual_bands": len(by_band),
        "band_width": band_width,
        "max_depth": max_depth,
        "subgraphs": sum(map(len, schedules)),
        "estimated_loads": loads,
        "bands": band_records,
    }
    return plan, meta


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("graph", type=Path)
    parser.add_argument("-n", "--num-cores", type=int, required=True)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--bands", type=int, default=8)
    args = parser.parse_args()
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    plan, meta = build_plan(graph, args.num_cores, args.bands)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    if args.metadata:
        args.metadata.parent.mkdir(parents=True, exist_ok=True)
        args.metadata.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in meta.items() if k != "bands"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
