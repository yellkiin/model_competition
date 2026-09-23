"""Official single-node safety capacities and exact count-state batching.

Q1 has no aircraft/battery scheduling or delivery deadlines.  Each action is one
out-and-back trip to a single service node; every physical term comes from the
archived official runtime and the unchanged DEM.
"""
from __future__ import annotations

import csv
from functools import lru_cache
from itertools import product
import json
import math
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ARCHIVE = OUT.parent
sys.path.insert(0, str(ARCHIVE / "runtime"))
from research_fd.d_model import Problem


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def leg(p, node):
    outward = p.arc(p.depot, node)
    returning = p.arc(node, p.depot)
    return outward, returning


def trip(p, kind, node, mass, volume, boxes):
    f = p.fleet[kind]
    if mass > f.payload + 1e-8 or volume > f.volume + 1e-8:
        return None
    outward, returning = leg(p, node)
    energy = f.energy(outward[0], outward[2], mass) + f.energy(returning[0], returning[2], 0)
    service = f.service + boxes * f.service_per_box
    energy += f.hover_kw * service / 3600
    time = f.prepare + boxes * f.loading_per_box + service
    for arc in (outward, returning):
        time += arc[2] / f.climb_speed + arc[0] / f.speed + arc[3] / f.descend_speed
    return energy, time


def capacity(p, kind, node, reserve):
    f = p.fleet[kind]
    usable = f.usable_kwh * (1 - reserve)
    def energy(mass):
        return trip(p, kind, node, mass, 0., 1)[0]
    empty = energy(0.)
    if empty > usable + 1e-10:
        return 0., empty, energy(f.payload), "empty_trip_exceeds_reserve"
    full = energy(f.payload)
    if full <= usable + 1e-10:
        return f.payload, empty, full, "rated_mass_binding"
    low, high = 0., f.payload
    for _ in range(70):
        mid = (low + high) / 2
        if energy(mid) <= usable:
            low = mid
        else:
            high = mid
    return low, empty, full, "round_trip_energy_binding"


def group_types(p, node):
    classes = {}
    for index, box in enumerate(p.boxes):
        if box.node == node:
            classes.setdefault((box.mass, box.volume), []).append(index)
    return [(mass, volume, tuple(indices)) for (mass, volume), indices in sorted(classes.items())]


def exact_batch(p, node, reserve):
    classes = group_types(p, node)
    total = tuple(len(indices) for _, _, indices in classes)
    choices = []
    for counts in product(*(range(n + 1) for n in total)):
        if not any(counts):
            continue
        mass = sum(c * cls[0] for c, cls in zip(counts, classes))
        volume = sum(c * cls[1] for c, cls in zip(counts, classes))
        n = sum(counts)
        for kind, fleet in p.fleet.items():
            if mass > fleet.payload + 1e-8 or volume > fleet.volume + 1e-8:
                continue
            result = trip(p, kind, node, mass, volume, n)
            if result and result[0] <= fleet.usable_kwh * (1 - reserve) + 1e-9:
                choices.append((counts, kind, result[0], result[1], mass, volume))
    if not choices:
        return None, [], {"count_states": math.prod(x + 1 for x in total), "actions": 0}

    @lru_cache(None)
    def solve(state):
        if not any(state):
            return (0, 0., 0.), ()
        best = None
        for index, (counts, kind, energy, time, mass, volume) in enumerate(choices):
            if any(c > s for c, s in zip(counts, state)):
                continue
            remainder = tuple(s - c for s, c in zip(state, counts))
            tail, actions = solve(remainder)
            rank = (tail[0] + 1, tail[1] + energy, tail[2] + time)
            if best is None or rank < best[0]:
                best = (rank, (index, *actions))
        return best

    objective, picked = solve(total)
    used = [0] * len(classes)
    batches = []
    for sequence, index in enumerate(picked, 1):
        counts, kind, energy, time, mass, volume = choices[index]
        ids = []
        for j, count in enumerate(counts):
            original = classes[j][2]
            ids.extend(p.boxes[i].id for i in original[used[j]:used[j] + count])
            used[j] += count
        batches.append(dict(node=node, reserve=reserve, batch=sequence,
                            kind=kind, boxes="|".join(ids), box_count=len(ids),
                            mass_kg=mass, volume_m3=volume,
                            round_trip_energy_kwh=energy,
                            cumulative_work_s=time))
    assert tuple(used) == total
    return objective, batches, {"count_states": solve.cache_info().currsize,
                                 "feasible_action_types": len(choices),
                                 "box_types": len(classes)}


def main():
    p = Problem.load(ARCHIVE / "d_official.json")
    nodes = sorted(node for node in p.nodes if node != p.depot)
    reserves = (.20, .25, .30)
    rows = []
    for node in nodes:
        for kind, fleet in p.fleet.items():
            result = {reserve: capacity(p, kind, node, reserve) for reserve in reserves}
            record = dict(node=node, kind=kind, rated_mass_kg=fleet.payload,
                          rated_volume_m3=fleet.volume,
                          round_trip_energy_empty_kwh=result[.20][1],
                          round_trip_energy_rated_mass_kwh=result[.20][2])
            for reserve, (load, _, _, binding) in result.items():
                code = int(100 * reserve)
                record[f"max_safe_mass_r{code}_kg"] = load
                record[f"binding_r{code}"] = binding
            rows.append(record)
    assert len(rows) == 45
    write_csv(OUT / "q1_capacity_45.csv", rows, list(rows[0]))

    all_batches, reserve_rows, details = [], [], {}
    for reserve in reserves:
        totals = [0, 0., 0.]
        details[str(reserve)] = {}
        for node in nodes:
            objective, batches, stats = exact_batch(p, node, reserve)
            if objective is None:
                raise RuntimeError(f"Q1 node has no feasible single-node batch: {node}, reserve={reserve}")
            for index, value in enumerate(objective):
                totals[index] += value
            details[str(reserve)][node] = stats
            all_batches.extend(batches)
        reserve_rows.append(dict(reserve=reserve, trips=int(totals[0]),
                                 transport_energy_kwh=totals[1],
                                 cumulative_work_s=totals[2],
                                 status="exact_count_state_dp"))
    write_csv(OUT / "q1_batches.csv", all_batches, list(all_batches[0]))
    write_csv(OUT / "q1_reserve_sensitivity.csv", reserve_rows, list(reserve_rows[0]))
    summary = dict(source="research_fd/outputs/d_official.json", terrain="official DEM",
                   interpretation="Q1 independent per-node trips; fleet scheduling and delivery deadlines excluded by design",
                   lexicographic_objectives=["minimum trips", "minimum transport energy kWh", "minimum cumulative work seconds"],
                   capacities=45, reserve_sensitivity=reserve_rows, exact_search=details,
                   comparison_candidates={"reserve_20": {"trips":18,"energy_kwh":59.130423},
                                          "reserve_25_trips":19,"reserve_30_trips":20,
                                          "B_S008_kg":28.80179,"C_S008_kg":58.90535},
                   comparison_status="candidate numbers above are references only; observed records are the reserve_sensitivity CSV and capacity table")
    (OUT / "q1_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status":"completed", "capacity_rows":len(rows),
                      "reserve_rows":reserve_rows,
                      "B_S008_kg":next(r["max_safe_mass_r20_kg"] for r in rows if r["kind"]=="B" and r["node"]=="S008"),
                      "C_S008_kg":next(r["max_safe_mass_r20_kg"] for r in rows if r["kind"]=="C" and r["node"]=="S008")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
