"""Structure-aware memory proposals for ORION A.

This module is deliberately additive: it only emits legal-looking plan candidates.
It never evaluates a candidate, never changes the graph/config/official evaluator,
and never owns the global time/FIFO controller. Official Makespan remains the only
acceptance gate in the host runner.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from copy import deepcopy
import math
import time

from research_a_orion_unified.vendor.orion.core import (
    bounds,
    make_plan,
    memory_proxy,
    plan_view,
    planned_traffic,
    topological,
)

VERSION = "memory-coherent-4.4"


@dataclass(frozen=True)
class Options:
    """Case-agnostic structural switches.

    These values describe graph shapes and candidate budgets, not graph IDs.
    The host may override them when combining research tracks.
    """

    stop_ratio: float = 1.04
    allow_core_migration: bool = True
    enable_micro_waves: bool = True
    enable_depth_bands: bool = True
    enable_tensor_transactions: bool = True
    enable_release_cuts: bool = True
    enable_logical_convex: bool = False
    max_candidates: int = 28
    max_hull_groups: int = 10
    max_tensor_stars: int = 20
    max_release_cuts: int = 8


def semantic_key(plan: dict) -> tuple:
    """Plan identity independent of arbitrary subgraph integer labels."""
    groups = defaultdict(list)
    for u, s in plan["node_to_subgraph"].items():
        groups[s].append(int(u))
    return tuple(
        tuple(tuple(sorted(groups[s])) for s in seq)
        for seq in plan["core_schedules"]
    )


def _raw(incumbent: dict) -> dict:
    result = incumbent.get("official_result") or {}
    return result.get("official_result", result)


def retain_best(incumbent: dict, candidate: dict, response: dict) -> dict:
    """Return the old object on failure/tie/regression.

    response must be an OfficialSession response. This helper is intentionally
    conservative for composition: a lower Makespan wins; equal Makespan needs
    fewer official added COPY bytes. A plugin proxy never accepts a plan.
    """
    if response.get("status") != "ok" or response.get("audit", {}).get("ok") is not True:
        return incumbent
    raw = response["official_result"]
    old = _raw(incumbent)
    new_key = (
        int(raw["makespan"]),
        int(raw["data_movement_bytes"]["added_copy_bytes"]),
    )
    old_key = (
        int(old["makespan"]),
        int(old["data_movement_bytes"]["added_copy_bytes"]),
    )
    if new_key >= old_key:
        return incumbent
    return {"plan": deepcopy(candidate["plan"]), "official_result": deepcopy(raw)}


def _expired(deadline: float | None) -> bool:
    return deadline is not None and time.monotonic() >= deadline


def _parts(g, plan):
    mapping, groups, owner, order = plan_view(g, plan)
    pred = {s: set() for s in groups}
    for u in g.topo:
        pred[mapping[u]].update(
            mapping[v] for v in g.pred[u] if mapping[v] != mapping[u]
        )
    return mapping, groups, owner, order, pred


def assess(g, n, cfg, q, incumbent: dict) -> dict:
    """Cheap shape diagnostics; memory numbers here are not feasibility proofs."""
    plan = incumbent["plan"]
    mapping, groups, owner, _, _ = _parts(g, plan)
    if n != len(plan["core_schedules"]):
        raise ValueError("NPU core count differs from plan")

    component_of = {u: i for i, comp in enumerate(g.components) for u in comp}
    shared_input_bytes = 0
    private_input_bytes = 0
    for t, tensor in g.tensors.items():
        consumers = g.tc[t]
        if g.tp[t] or not consumers:
            continue
        size = int(tensor["size"])
        if len({component_of[u] for u in consumers}) > 1:
            shared_input_bytes += size
        else:
            private_input_bytes += size

    tiny = [comp for comp in g.components if len(comp) <= 32]
    tiny_fraction = sum(map(len, tiny)) / max(1, len(g.ops))
    raw = _raw(incumbent)
    movement = raw.get("data_movement_bytes", {})
    lower = float(bounds(g, cfg, n, q)["global_lower"])
    upper = float(raw.get("makespan", math.inf))

    private_islands = (
        len(g.components) >= 8
        and tiny_fraction >= 0.75
        and shared_input_bytes < 0.10 * max(1, private_input_bytes)
    )

    loads = []
    for core in range(n):
        nodes = [u for u in g.ops if owner[mapping[u]] == core]
        loads.append(g.loads(nodes))

    return {
        "ops": len(g.ops),
        "groups": len(groups),
        "components": len(g.components),
        "dominant_component_fraction": max(map(len, g.components), default=0) / max(1, len(g.ops)),
        "tiny_island_fraction": tiny_fraction,
        "shared_input_bytes": shared_input_bytes,
        "private_input_bytes": private_input_bytes,
        "private_islands": private_islands,
        "spill_bytes": int(movement.get("spill_added_copy_bytes", 0) or 0),
        "global_lower": lower,
        "upper": upper,
        "ratio": upper / lower if lower else math.inf,
        "core_loads": loads,
    }


def candidate_advice(g, n, cfg, q, incumbent: dict, plan: dict) -> dict:
    """Optional warning for an external mixed candidate pool.

    It is only advice. High projected memory may still be a legal, useful plan
    because official Spill is allowed. Never treat this result as a certificate.
    """
    features = assess(g, n, cfg, q, incumbent)
    parent = memory_proxy(g, incumbent["plan"], cfg, q)["predicted_peak"]
    proposed = memory_proxy(g, plan, cfg, q)["predicted_peak"]
    old_ratio = max(
        (parent.get(pos, 0) / cfg.capacity[pos] for pos in cfg.capacity),
        default=0,
    )
    new_ratio = max(
        (proposed.get(pos, 0) / cfg.capacity[pos] for pos in cfg.capacity),
        default=0,
    )
    risky = (
        features["private_islands"]
        and features["spill_bytes"] == 0
        and new_ratio > max(1.5, old_ratio * 1.15)
    )
    return {
        "recommendation": "defer" if risky else "evaluate_if_budget",
        "reason": "private_island_frontier_expansion" if risky else "no_structural_warning",
        "parent_projected_peak": parent,
        "candidate_projected_peak": proposed,
        "capacity_certificate": False,
        "features": features,
    }


def _component_live_peak(g, component: set[int]) -> dict[str, int]:
    """Peak live bytes of one compute component in its topological order.

    The estimate has no inserted COPY lifetime and is used only to size batches.
    Official Step2/Step3 remains authoritative.
    """
    seq = [u for u in g.topo if u in component]
    index = {u: i for i, u in enumerate(seq)}
    events = defaultdict(lambda: defaultdict(int))
    touched = set().union(*(g.inputs[u] | g.outputs[u] for u in seq)) if seq else set()
    for t in touched:
        tensor = g.tensors[t]
        pos = tensor.get("pos")
        if pos not in ("L1", "UB"):
            continue
        pins = (g.tp[t] | g.tc[t]) & component
        if not pins:
            continue
        a = min(index[u] for u in pins)
        b = max(index[u] for u in pins)
        size = int(tensor["size"])
        events[a][pos] += size
        events[b + 1][pos] -= size
    live = defaultdict(int)
    peak = defaultdict(int)
    for i in sorted(events):
        for pos, delta in events[i].items():
            live[pos] += delta
            peak[pos] = max(peak[pos], live[pos])
    return dict(peak)


def _balanced_component_owners(g, plan, n: int) -> dict[int, int]:
    """Assign whole independent components to cores by pipe load.

    The old owner majority is a deterministic tie-break only. No case IDs.
    """
    mapping, _, owner, _, _ = _parts(g, plan)
    component_owner = {}
    loads = [defaultdict(int) for _ in range(n)]
    components = sorted(g.components, key=lambda c: (-g.weight(c), min(c)))
    for comp in components:
        work = g.loads(comp)
        old_work = defaultdict(int)
        for u in comp:
            old_work[owner[mapping[u]]] += g.duration[u]

        def score(core: int):
            trial = [dict(x) for x in loads]
            for pipe, value in work.items():
                trial[core][pipe] = trial[core].get(pipe, 0) + value
            bottleneck = max(
                (max(v.values(), default=0) for v in trial),
                default=0,
            )
            return (bottleneck, -old_work[core], core)

        dest = min(range(n), key=score)
        component_owner[min(comp)] = dest
        for pipe, value in work.items():
            loads[dest][pipe] += value
    return component_owner


def micro_wave_plan(g, plan, cfg, n: int, envelope: float, stages: int = 2) -> dict:
    """Close independent micro-components, then execute capacity-bounded waves.

    Each weak compute component moves as a whole, so no inter-core dependency is
    introduced inside it. Components are independent by definition. A wave opens
    only a bounded number of components; stage 0 of the batch runs before stage 1,
    preserving compute overlap without the all-components-live failure of global
    depth bands. envelope is a proposal-size heuristic, not a capacity proof.
    """
    if stages < 1:
        raise ValueError("stages must be positive")
    components = sorted(g.components, key=min)
    if not components:
        return deepcopy(plan)
    owner_by_component = _balanced_component_owners(g, plan, n)

    peaks = [_component_live_peak(g, comp) for comp in components]
    max_peak = {pos: max((p.get(pos, 0) for p in peaks), default=0) for pos in cfg.capacity}
    safe = min(
        (cfg.capacity[pos] / max(1, max_peak[pos]) for pos in cfg.capacity),
        default=1.0,
    )
    width = max(1, int(max(1.0, safe * envelope)))

    assigned = [[] for _ in range(n)]
    for comp in components:
        assigned[owner_by_component[min(comp)]].append(comp)

    groups: list[set[int]] = []
    cores: list[int] = []
    for core in range(n):
        comps = assigned[core]
        for start in range(0, len(comps), width):
            batch = comps[start : start + width]
            depth_by_comp = {}
            for comp in batch:
                depth = {}
                for u in g.topo:
                    if u in comp:
                        depth[u] = 1 + max((depth[p] for p in g.pred[u] if p in comp), default=-1)
                depth_by_comp[min(comp)] = depth
            for stage in range(stages):
                part = set()
                for comp in batch:
                    depth = depth_by_comp[min(comp)]
                    levels = max(depth.values(), default=0) + 1
                    for u, d in depth.items():
                        bucket = min(stages - 1, d * stages // max(1, levels))
                        if bucket == stage:
                            part.add(u)
                if part:
                    groups.append(part)
                    cores.append(core)
    return make_plan(groups, cores, n)


def fixed_owner_bands(g, plan, bins: int) -> dict:
    """Depth bands for shared-parameter / connected regimes, keeping core owners."""
    mapping, _, owner, _, _ = _parts(g, plan)
    op_owner = {u: owner[mapping[u]] for u in g.ops}
    depth = {}
    for u in g.topo:
        depth[u] = 1 + max((depth[v] for v in g.pred[u]), default=-1)
    levels = sorted(set(depth.values()))
    rank = {d: i for i, d in enumerate(levels)}
    bins = max(1, min(bins, len(levels)))
    band = {u: rank[depth[u]] * bins // max(1, len(levels)) for u in g.ops}

    switch = {}
    parts = defaultdict(set)
    for u in g.topo:
        switch[u] = max(
            (
                switch[v] + int(op_owner[u] != op_owner[v])
                for v in g.pred[u]
                if band[v] == band[u]
            ),
            default=0,
        )
        parts[band[u], switch[u], op_owner[u]].add(u)
    keys = sorted(parts)
    return make_plan(
        [parts[key] for key in keys],
        [key[2] for key in keys],
        len(plan["core_schedules"]),
    )


def producer_release_cuts(g, n, cfg, q, incumbent, deadline, limit: int):
    """Q1: split a producer down-set from a long Task to expose data earlier."""
    if q != 1:
        return
    plan = incumbent["plan"]
    raw = _raw(incumbent)
    mapping, groups, owner, order, _ = _parts(g, plan)
    op_end = {}
    task_end = {}
    for core in raw.get("per_core_timeline", []):
        for op in core.get("ops", []):
            op_end[op["op_id"]] = op["end"]
        for task in core.get("tasks", []):
            task_end[task["task_id"]] = task["end"]

    ranked = []
    for t in g.tensors:
        ps = {mapping[u] for u in g.tp[t]}
        cs = {mapping[u] for u in g.tc[t]}
        for sg in ps:
            if len(groups[sg]) < 3 or not any(owner[x] != owner[sg] for x in cs):
                continue
            producers = g.tp[t] & groups[sg]
            prefix = set(producers)
            stack = list(producers)
            while stack:
                u = stack.pop()
                for parent in g.pred[u] & groups[sg]:
                    if parent not in prefix:
                        prefix.add(parent)
                        stack.append(parent)
            suffix = groups[sg] - prefix
            if not suffix:
                continue
            gap = max(
                0,
                task_end.get(sg, 0)
                - max((op_end.get(u, 0) for u in producers), default=0),
            )
            if gap > cfg.same_a:
                ranked.append((gap, t, sg, prefix, suffix))

    ranked.sort(key=lambda x: (-x[0], x[1], x[2]))
    for gap, t, sg, prefix, suffix in ranked[:limit]:
        if _expired(deadline):
            return
        groups_new = []
        cores_new = []
        for old in order:
            pieces = [prefix, suffix] if old == sg else [groups[old]]
            for piece in pieces:
                groups_new.append(piece)
                cores_new.append(owner[old])
        trial = make_plan(groups_new, cores_new, n)
        plan_view(g, trial)
        yield trial, f"producer_release_{t}_{sg}", {
            "kind": "producer_downset_split",
            "tensor": t,
            "split_group": sg,
            "potential_release_cycles": gap,
            "cores_unchanged": True,
        }


def _logical_hull(seeds, pred, succ, position, limit):
    lo = min(position[x] for x in seeds)
    hi = max(position[x] for x in seeds)

    def reach(adjacency):
        seen = set(seeds)
        stack = list(seeds)
        while stack:
            u = stack.pop()
            for v in adjacency[u]:
                if lo <= position[v] <= hi and v not in seen:
                    seen.add(v)
                    stack.append(v)
        return seen

    hull = reach(succ) & reach(pred)
    return hull if len(hull) <= limit else None


def _move_hull(g, plan, selected: set[int], dest: int) -> dict:
    """Move a logical-convex Task hull to one core, preserving old groups."""
    mapping, groups, owner, order, pred = _parts(g, plan)
    for seq in plan["core_schedules"]:
        for a, b in zip(seq, seq[1:]):
            pred[b].add(a)
    rank = {s: i for i, s in enumerate(order)}
    new_owner = {s: (dest if s in selected else owner[s]) for s in groups}
    new_order = topological(groups, pred, key=lambda s: rank[s])
    return make_plan([groups[s] for s in new_order], [new_owner[s] for s in new_order], len(plan["core_schedules"]))


def tensor_transactions(g, n, cfg, q, incumbent, deadline, opt: Options):
    """Move complete producer/consumer Task sets, not individual graph edges."""
    plan = incumbent["plan"]
    mapping, groups, owner, order, pred = _parts(g, plan)
    position = {s: i for i, s in enumerate(order)}
    succ = {s: set() for s in groups}
    for s, parents in pred.items():
        for parent in parents:
            succ[parent].add(s)

    ranked = []
    for t, tensor in g.tensors.items():
        ps = {mapping[u] for u in g.tp[t]}
        cs = {mapping[u] for u in g.tc[t]}
        if not ps or not cs or len(ps | cs) < 2:
            continue
        if q == 1:
            copies = len(cs - ps) + sum(bool(cs - {p}) for p in ps)
        else:
            pc = {owner[s] for s in ps}
            cc = {owner[s] for s in cs}
            copies = 2 * sum(a != b for a in pc for b in cc)
        if copies:
            ranked.append((int(tensor["size"]) * copies, t, ps, cs))
    ranked.sort(key=lambda x: (-x[0], x[1]))

    seen = set()
    for _, t, ps, cs in ranked[: opt.max_tensor_stars]:
        if _expired(deadline):
            return
        seed_sets = [ps | cs]
        for a in sorted(ps, key=position.get)[:2]:
            near = sorted(cs - {a}, key=lambda s: abs(position[s] - position[a]))[:3]
            seed_sets.extend({a, b} for b in near)
            if near:
                seed_sets.append({a, *near})
        for seeds in seed_sets:
            hull = _logical_hull(seeds, pred, succ, position, opt.max_hull_groups)
            if not hull:
                continue
            for dest in sorted({owner[s] for s in hull}):
                key = (tuple(sorted(hull)), dest)
                if key in seen:
                    continue
                seen.add(key)
                if _expired(deadline):
                    return
                try:
                    trial = _move_hull(g, plan, hull, dest)
                    plan_view(g, trial)
                except ValueError:
                    continue
                yield trial, f"tensor_hull_{t}_{dest}_{len(hull)}", {
                    "kind": "tensor_transaction",
                    "tensor": t,
                    "hull_groups": len(hull),
                    "destination": dest,
                    "whole_subgraphs_only": True,
                }


def _decorate(g, n, cfg, q, incumbent, plan, name, mechanism):
    plan_view(g, plan)
    bd = bounds(g, cfg, n, q, plan)
    raw = _raw(incumbent)
    if bd["candidate_lower"] > raw["makespan"]:
        return None
    old_bytes = sum(planned_traffic(g, incumbent["plan"], q))
    new_bytes = sum(planned_traffic(g, plan, q))
    peak = memory_proxy(g, plan, cfg, q)["predicted_peak"]
    pressure = max(
        (peak.get(pos, 0) / cfg.capacity[pos] for pos in cfg.capacity),
        default=0,
    )
    score = (
        bd["candidate_lower"]
        + 0.08 * max(0, new_bytes - old_bytes) / cfg.bandwidth
        + 0.005 * max(0, pressure - 1) * raw["makespan"]
    )
    return {
        "name": name,
        "family": "memory/" + mechanism["kind"],
        "plan": plan,
        "proxy": {
            "score": score,
            "pre_spill_bytes": new_bytes,
            "pre_spill_saved_bytes": old_bytes - new_bytes,
            "predicted_peak": peak,
            "peak_is_heuristic": True,
        },
        "bounds": bd,
        "mechanism": mechanism,
        "version": VERSION,
    }


def propose_with_options(g, n, cfg, q, incumbent=None, feedback=None, deadline=None, options=None):
    """COMMON-compatible generator with configurable composition switches."""
    if incumbent is None or _expired(deadline):
        return
    if q not in (1, 2, 3):
        raise ValueError("q must be 1, 2 or 3")
    opt = options or Options()
    features = assess(g, n, cfg, q, incumbent)
    if features["ratio"] <= opt.stop_ratio:
        return

    seen = {semantic_key(incumbent["plan"])}
    pool = []

    def add(plan, name, mechanism):
        if _expired(deadline):
            return
        try:
            key = semantic_key(plan)
            if key in seen:
                return
            seen.add(key)
            candidate = _decorate(g, n, cfg, q, incumbent, plan, name, mechanism)
            if candidate is not None:
                pool.append(candidate)
        except ValueError as exc:
            if feedback is not None:
                feedback.append({"name": name, "status": "structural_rejected", "error": str(exc)})

    if opt.enable_micro_waves and features["private_islands"]:
        if q in (2, 3) and opt.allow_core_migration:
            for envelope in (1.0, 1.5, 2.0, 2.5):
                for stages in (2, 3):
                    add(
                        micro_wave_plan(g, incumbent["plan"], cfg, n, envelope, stages),
                        f"micro_wave_e{envelope:g}_s{stages}",
                        {
                            "kind": "coherent_micro_wave",
                            "envelope": envelope,
                            "stages": stages,
                            "component_closed": True,
                            "case_id_used": False,
                        },
                    )
        # Measured regression guard: never run all-graph depth bands here.
    else:
        if opt.enable_depth_bands:
            for bins in (16, 32, 64, 8):
                add(
                    fixed_owner_bands(g, incumbent["plan"], bins),
                    f"fixed_owner_bands_{bins}",
                    {"kind": "reuse_bands", "bins": bins, "cores_unchanged": True},
                )

        if opt.enable_release_cuts and q == 1:
            for plan, name, mechanism in producer_release_cuts(
                g, n, cfg, q, incumbent, deadline, opt.max_release_cuts
            ):
                add(plan, name, mechanism)

        if opt.enable_tensor_transactions and opt.allow_core_migration:
            for plan, name, mechanism in tensor_transactions(
                g, n, cfg, q, incumbent, deadline, opt
            ):
                add(plan, name, mechanism)
                if len(pool) >= 4 * opt.max_candidates:
                    break

    families = defaultdict(list)
    for candidate in pool:
        families[candidate["family"]].append(candidate)
    for values in families.values():
        values.sort(key=lambda c: (c["proxy"]["score"], c["name"]))

    emitted = 0
    while families and emitted < opt.max_candidates:
        empty = []
        for family in sorted(families):
            if _expired(deadline) or emitted >= opt.max_candidates:
                return
            values = families[family]
            if not values:
                empty.append(family)
                continue
            emitted += 1
            yield values.pop(0)
            if not values:
                empty.append(family)
        for family in empty:
            families.pop(family, None)


def propose(g, n, cfg, q, incumbent=None, feedback=None, deadline=None):
    """Default COMMON entry point."""
    yield from propose_with_options(
        g, n, cfg, q, incumbent, feedback, deadline, Options()
    )
