"""Deterministic component-balanced multicore plan for official A graphs.

Connected components of the contracted non-COPY operation DAG have no data
dependencies between them.  They can be assigned independently.  Grouping all
components assigned to one core into one subgraph avoids scene-A Task handoff
cost.  The plan is validated with the official checker before it is saved.
"""

from __future__ import annotations

import argparse
import json
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


def build_plan(graph: dict, num_cores: int) -> tuple[dict, dict]:
    if not 1 <= num_cores <= 5:
        raise ValueError("num_cores must be in 1..5")
    eligible_ops = {
        op["id"]: op
        for op in graph["ops"]
        if op["op"] not in {"COPY_IN", "COPY_OUT"}
    }
    _, full_succ = _build_op_adjacency(graph)
    _, succ = _contract_excluded_copy_nodes(sorted(eligible_ops), full_succ)
    parent = {u: u for u in eligible_ops}

    def find(u: int) -> int:
        while parent[u] != u:
            parent[u] = parent[parent[u]]
            u = parent[u]
        return u

    for u, destinations in succ.items():
        for v in destinations:
            parent[find(v)] = find(u)
    groups = defaultdict(list)
    for op_id in eligible_ops:
        groups[find(op_id)].append(op_id)

    # Cycles dominate compute work, while a small per-op term prevents groups
    # of zero-cycle operations from becoming costless in list scheduling.
    weighted_groups = []
    for members in groups.values():
        weight = sum(eligible_ops[u]["cycles"] + 1 for u in members)
        weighted_groups.append((weight, min(members), members))
    weighted_groups.sort(key=lambda item: (-item[0], item[1]))
    loads = [0] * num_cores
    members_by_core = [[] for _ in range(num_cores)]
    for weight, _, members in weighted_groups:
        core = min(range(num_cores), key=lambda i: (loads[i], i))
        loads[core] += weight
        members_by_core[core].extend(members)

    # One subgraph per active core.  Empty cores are represented by [].
    active = [i for i, members in enumerate(members_by_core) if members]
    sgid_for_core = {core: rank for rank, core in enumerate(active)}
    mapping = {
        str(op_id): sgid_for_core[core]
        for core, members in enumerate(members_by_core)
        for op_id in members
    }
    plan = {
        "node_to_subgraph": mapping,
        "core_schedules": [
            [sgid_for_core[core]] if core in sgid_for_core else []
            for core in range(num_cores)
        ],
    }
    validate_multicore_plan(graph, plan)
    metadata = {
        "method": "contracted_components_lpt",
        "num_cores": num_cores,
        "components": len(groups),
        "component_size_max": max((len(x) for x in groups.values()), default=0),
        "estimated_loads": loads,
        "active_cores": len(active),
        "subgraphs": len(active),
    }
    return plan, metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("graph", type=Path)
    parser.add_argument("-n", "--num-cores", type=int, required=True)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--metadata", type=Path)
    args = parser.parse_args()
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    plan, metadata = build_plan(graph, args.num_cores)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    if args.metadata:
        args.metadata.parent.mkdir(parents=True, exist_ok=True)
        args.metadata.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
