"""Small, deterministic Q3 candidate family; all scores require official replay.

Band-local connected components are kept intact, so every inter-subgraph edge
goes to a later band.  The new placer balances each execution pipe and charges
new source-core/consumer-core tensor copies by bytes.  Its FIFO/readiness model
is deliberately only a placement proxy, not an alternative evaluator.
"""

from __future__ import annotations

import heapq
import math
import sys
from collections import OrderedDict, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CODE = ROOT / "数据/原始/A题官方附件/code"
for _path in (ROOT / "求解", CODE):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_3 import read_cache_config, read_scene_b_config
from solve_bands import build_plan as original_band_plan
from stub_multicore_cut_and_schedule import (
    _build_op_adjacency,
    _contract_excluded_copy_nodes,
    validate_multicore_plan,
)


def _settings(cache_config):
    config_path = str(ROOT / "数据/原始/A题官方附件/data/config.txt")
    settings = read_evaluation_config(config_path)
    settings.update(read_scene_b_config(config_path))
    settings.update(read_cache_config(config_path))
    settings.update(cache_config or {})
    return settings


def _signature(plan):
    positions = {
        sg: (core, index)
        for core, order in enumerate(plan["core_schedules"])
        for index, sg in enumerate(order)
    }
    return tuple(sorted((int(op), *positions[sg])
                        for op, sg in plan["node_to_subgraph"].items()))


def _views(graph):
    ops = {op["id"]: op for op in graph["ops"]
           if op["op"] not in {"COPY_IN", "COPY_OUT"}}
    _, full_succ = _build_op_adjacency(graph)
    pred, succ = _contract_excluded_copy_nodes(sorted(ops), full_succ)
    indegree = {u: len(pred[u]) for u in ops}
    depth = {u: 0 for u in ops}
    ready = [u for u in ops if not indegree[u]]
    heapq.heapify(ready)
    topo = []
    while ready:
        u = heapq.heappop(ready)
        topo.append(u)
        for v in sorted(succ[u]):
            depth[v] = max(depth[v], depth[u] + 1)
            indegree[v] -= 1
            if not indegree[v]:
                heapq.heappush(ready, v)
    if len(topo) != len(ops):
        raise ValueError("contracted operation graph has a cycle")
    bottom = {}
    for u in reversed(topo):
        bottom[u] = max(1, ops[u]["cycles"]) + max(
            (bottom[v] for v in succ[u]), default=0)

    # Virtual tensors also represent original direct op-op edges; they cannot
    # accidentally acquire reuse from an unrelated edge with equal byte size.
    tensors = {t["id"]: {"size": t["size"], "producers": set(), "consumers": set()}
               for t in graph["tensors"]}
    for index, edge in enumerate(graph["edges"]):
        src, dst = edge["source"], edge["target"]
        if src in ops and dst in tensors:
            tensors[dst]["producers"].add(src)
        elif src in tensors and dst in ops:
            tensors[src]["consumers"].add(dst)
        elif src in ops and dst in ops:
            tensors[("direct", index)] = {
                "size": max(0, int(edge.get("data_size", 0))),
                "producers": {src}, "consumers": {dst},
            }
    incoming = defaultdict(set)
    for tid, tensor in tensors.items():
        for op in tensor["consumers"]:
            incoming[op].add(tid)
    return ops, pred, succ, depth, bottom, tensors, incoming


def _weighted_plan(graph, num_cores, target_bands, communication_weight,
                   settings, views):
    ops, pred, succ, depth, bottom, tensors, incoming = views
    band_width = max(1, math.ceil((max(depth.values(), default=0) + 1) / target_bands))
    by_band = defaultdict(list)
    for u in sorted(ops):
        by_band[depth[u] // band_width].append(u)
    pipes = sorted({op["pipe"] for op in ops.values()})
    total_load = [{pipe: 0.0 for pipe in pipes} for _ in range(num_cores)]
    assignment, core_of = defaultdict(list), {}
    placed_links = set()
    fifo = OrderedDict()
    fifo_used = 0
    ddr = float(settings["bandwidth"])
    l2 = float(settings["cache_bandwidth_bytes_per_cycle"])
    cache_capacity = int(settings["cache_capacity_bytes"])
    copy_delay = float(settings["cross_core_copy_delay_cycles"])
    predicted_bytes = 0
    predicted_l2_bytes = 0
    band_records = []

    for band in sorted(by_band):
        members = by_band[band]
        parent = {u: u for u in members}

        def find(u):
            while parent[u] != u:
                parent[u] = parent[parent[u]]
                u = parent[u]
            return u

        for u in members:
            for v in sorted(succ[u]):
                if v in parent:
                    parent[find(v)] = find(u)
        groups = defaultdict(list)
        for u in members:
            groups[find(u)].append(u)
        records = []
        for group in groups.values():
            work = {pipe: 0.0 for pipe in pipes}
            for u in group:
                work[ops[u]["pipe"]] += max(1, ops[u]["cycles"])
            records.append((max(work.values(), default=0),
                            max(bottom[u] for u in group), min(group), group, work))
        records.sort(key=lambda item: (-item[0], -item[1], item[2]))
        band_load = [{pipe: 0.0 for pipe in pipes} for _ in range(num_cores)]
        assigned_cost = [0.0] * num_cores

        for _, _, _, group, work in records:
            group_set = set(group)
            input_tensors = sorted(set().union(*(incoming[u] for u in group)), key=str)
            choices = []
            for core in range(num_cores):
                links, cost, read_bytes, reuse_bytes = [], 0.0, 0, 0
                for tid in input_tensors:
                    tensor = tensors[tid]
                    size = tensor["size"]
                    producer_cores = {core_of[p] for p in tensor["producers"]
                                      if p not in group_set and p in core_of}
                    if tensor["producers"] & group_set:
                        producer_cores.add(core)
                    source_cores = sorted(producer_cores - {core})
                    if not tensor["producers"]:
                        source_cores = [None]
                    # Same-band readers may launch concurrently before a fill:
                    # count predicted reuse only from a completed earlier band,
                    # and discount it 50% because actual global timing can differ.
                    cached = tid in fifo and fifo[tid][1] < band and 0 < size <= cache_capacity
                    read_cycles = size / ddr
                    if cached:
                        read_cycles = 0.5 * (size / ddr + size / l2)
                    for source in source_cores:
                        link = (tid, source, core)
                        if link in placed_links:
                            continue
                        links.append(link)
                        read_bytes += size
                        reuse_bytes += size if cached else 0
                        cost += read_cycles
                        if source is not None:
                            cost += size / ddr + copy_delay
                # Current-band balance prevents greedy co-location of an entire
                # chain; cumulative per-pipe balance accounts for earlier bands.
                band_finish = max((band_load[core][p] + work[p] for p in pipes), default=0)
                total_finish = max((total_load[core][p] + work[p] for p in pipes), default=0)
                score = 0.7 * band_finish + 0.3 * total_finish + communication_weight * cost
                choices.append((score, assigned_cost[core], core,
                                links, cost, read_bytes, reuse_bytes))
            _, _, core, links, cost, read_bytes, reuse_bytes = min(choices, key=lambda x: x[:3])
            assignment[band, core].extend(group)
            assigned_cost[core] += cost
            predicted_bytes += read_bytes
            predicted_l2_bytes += reuse_bytes
            placed_links.update(links)
            for u in group:
                core_of[u] = core
            for pipe in pipes:
                band_load[core][pipe] += work[pipe]
                total_load[core][pipe] += work[pipe]
            for tid in sorted({link[0] for link in links}, key=str):
                size = tensors[tid]["size"]
                if not 0 < size <= cache_capacity or tid in fifo:
                    continue
                while fifo and fifo_used + size > cache_capacity:
                    _, (evicted_size, _) = fifo.popitem(last=False)
                    fifo_used -= evicted_size
                fifo[tid] = (size, band)
                fifo_used += size
        band_records.append({"band": band, "components": len(records),
                             "pipe_loads": band_load})

    mapping, schedules = {}, [[] for _ in range(num_cores)]
    for sgid, ((band, core), group) in enumerate(sorted(assignment.items())):
        schedules[core].append(sgid)
        for u in group:
            mapping[str(u)] = sgid
    plan = {"node_to_subgraph": mapping, "core_schedules": schedules}
    validate_multicore_plan(graph, plan)
    metadata = {
        "method": "pipe_byte_affinity_bands", "target_bands": target_bands,
        "actual_bands": len(by_band), "band_width": band_width,
        "communication_weight": communication_weight,
        "num_cores": num_cores, "subgraphs": sum(map(len, schedules)),
        "pipe_loads": total_load, "bands": band_records,
        "placement_read_bytes_proxy": predicted_bytes,
        "placement_cache_eligible_read_bytes_proxy": predicted_l2_bytes,
        "proxy_warning": "Placement estimates only; cache fills, sharing, stalls and makespan require official Q3 evaluation.",
    }
    return plan, metadata


def generate_candidates(graph, num_cores, baseline_plan, cache_config=None):
    """Yield at most seven distinct legal candidates, excluding the baseline.

    ``cache_config`` may supply official cache keys and optionally ``bandwidth``
    and ``cross_core_copy_delay_cycles``. Missing values come from config.txt.
    Official validation here establishes basic plan legality; execution validity
    and all reported performance must still be established by the Q3 evaluator.
    """
    if not 1 <= num_cores <= 5:
        raise ValueError("num_cores must be in 1..5")
    if num_cores == 1:
        return
    seen = {_signature(baseline_plan)} if baseline_plan else set()
    for bands in (2, 4, 16):
        plan, metadata = original_band_plan(graph, num_cores, target_bands=bands)
        signature = _signature(plan)
        if signature not in seen:
            seen.add(signature)
            metadata = dict(metadata, candidate_family="original_band_scale")
            yield f"bands{bands}_scale", plan, metadata
    settings = _settings(cache_config)
    views = _views(graph)
    for bands, weight in ((4, 0.25), (8, 0.25), (16, 0.25), (8, 0.75)):
        plan, metadata = _weighted_plan(graph, num_cores, bands, weight, settings, views)
        signature = _signature(plan)
        if signature not in seen:
            seen.add(signature)
            yield f"bands{bands}_pipebytes_w{int(weight * 100)}", plan, metadata
