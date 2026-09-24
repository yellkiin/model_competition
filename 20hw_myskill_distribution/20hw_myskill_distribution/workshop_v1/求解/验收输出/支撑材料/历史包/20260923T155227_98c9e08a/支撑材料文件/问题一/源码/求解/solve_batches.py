"""Bounded-size Task candidate for graphs with many independent components.

Each weak component of the contracted non-COPY DAG stays intact.  The
component-balanced core assignment is inherited from solve_components; only
independent components already on the same core are packed into consecutive
subgraphs.  This limits the quadratic work of the official scene-A Task
scheduler on very wide graphs without changing any evaluator code.
"""

from __future__ import annotations

from collections import defaultdict

from solve_components import build_plan as component_plan
from stub_multicore_cut_and_schedule import (
    _build_op_adjacency,
    _contract_excluded_copy_nodes,
    validate_multicore_plan,
)


def build_plan(graph: dict, num_cores: int, target_ops: int = 800) -> tuple[dict, dict]:
    base, base_meta = component_plan(graph, num_cores)
    eligible = {op["id"] for op in graph["ops"] if op["op"] not in {"COPY_IN", "COPY_OUT"}}
    _, full_succ = _build_op_adjacency(graph)
    _, succ = _contract_excluded_copy_nodes(sorted(eligible), full_succ)
    parent = {u: u for u in eligible}

    def find(u: int) -> int:
        while parent[u] != u:
            parent[u] = parent[parent[u]]
            u = parent[u]
        return u

    for u, destinations in succ.items():
        for v in destinations:
            parent[find(v)] = find(u)
    groups = defaultdict(list)
    for u in eligible:
        groups[find(u)].append(u)
    core_by_base_sgid = {
        sgid: core for core, schedule in enumerate(base["core_schedules"])
        for sgid in schedule
    }
    by_core = defaultdict(list)
    for members in groups.values():
        core = core_by_base_sgid[base["node_to_subgraph"][str(members[0])]]
        by_core[core].append(sorted(members))

    mapping: dict[str, int] = {}
    schedules: list[list[int]] = [[] for _ in range(num_cores)]
    batch_sizes: list[int] = []
    sgid = 0
    for core in range(num_cores):
        current: list[int] = []
        for members in sorted(by_core[core], key=lambda group: group[0]):
            if current and len(current) + len(members) > target_ops:
                schedules[core].append(sgid)
                batch_sizes.append(len(current))
                mapping.update((str(u), sgid) for u in current)
                sgid += 1
                current = []
            current.extend(members)
        if current:
            schedules[core].append(sgid)
            batch_sizes.append(len(current))
            mapping.update((str(u), sgid) for u in current)
            sgid += 1
    plan = {"node_to_subgraph": mapping, "core_schedules": schedules}
    validate_multicore_plan(graph, plan)
    return plan, {
        "method": "independent_component_batches",
        "num_cores": num_cores,
        "target_ops": target_ops,
        "subgraphs": sgid,
        "max_batch_ops": max(batch_sizes, default=0),
        "components": base_meta["components"],
        "component_size_max": base_meta["component_size_max"],
    }
