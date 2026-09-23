"""Spatial two-site witnesses by active minute; not a physical relay schedule."""
from pathlib import Path
import sys, json, hashlib, math, time
from collections import defaultdict

OUT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OUT / "runtime"))
from research_fd.d_model import Problem
from research_fd.d_experiments import load_plan
from research_fd.d_radio import candidates, demands_for_options, margin

started = time.monotonic()
input_path = OUT / "d_official.json"
plan_path = OUT / "official_transport_s7/best_plan.json"
p = Problem.load(input_path)
jobs, _ = load_plan(plan_path)
sites = candidates(p, 3)
demands = demands_for_options(p, [(j.route, j.start) for j in jobs], 60.)
minutes = defaultdict(list)
for i, d in enumerate(demands):
    minutes[math.floor(d["time"] / 60 + 1e-9)].append(i)

def distance(a, b):
    return math.sqrt(sum((x-y)**2 for x, y in zip(a, b)))

access = []
cache = {}
for site_id, site in enumerate(sites):
    covered = set()
    for demand_id, d in enumerate(demands):
        key = site_id, tuple(d["xyz"])
        if key not in cache:
            cache[key] = margin(p, site, d["xyz"], p.data["radio"]["access_budget_db"]) >= 0
        if cache[key]:
            covered.add(demand_id)
    access.append(covered)
depot = p.nodes[p.depot]
previous = [[depot.x, depot.y, depot.z]] * 2
records = []
selected = set()
uncovered_minutes = []
for minute, ids in sorted(minutes.items()):
    target = (1 << len(ids)) - 1
    masks = [sum(1 << k for k, demand_id in enumerate(ids) if demand_id in cov) for cov in access]
    feasible_count = 0
    best = None
    for i in range(len(sites)):
        for j in range(i, len(sites)):
            if masks[i] | masks[j] != target:
                continue
            feasible_count += 1
            same = distance(previous[0], sites[i]) + distance(previous[1], sites[j])
            swap = distance(previous[0], sites[j]) + distance(previous[1], sites[i])
            if same <= swap:
                ordered, cost = [i, j], same
            else:
                ordered, cost = [j, i], swap
            score = (cost, i, j)
            if best is None or score < best[0]:
                best = score, ordered
    record = {"minute_index": minute, "time_bin_s": [minute*60, (minute+1)*60], "demand_indices": ids,
              "demand_count": len(ids), "feasible_unordered_pairs_with_repetition": feasible_count}
    if best is None:
        uncovered_minutes.append(minute)
        record.update(status="no_two_site_cover", ordered_site_indices=None, movement_proxy_m=None)
    else:
        score, ordered = best
        selected.update(ordered)
        previous = [sites[i] for i in ordered]
        record.update(status="spatial_pair_found", ordered_site_indices=ordered, movement_proxy_m=score[0])
    records.append(record)
result = {
    "scope": "Spatial candidate diagnostic only; no preparation, travel-time, depot-return, charging, or continuous-radio feasibility assertion.",
    "input": str(input_path.relative_to(OUT.parent.parent)),
    "plan": str(plan_path.relative_to(OUT.parent.parent)),
    "source_sha256": {str(path.relative_to(OUT.parent.parent)): hashlib.sha256(path.read_bytes()).hexdigest() for path in [input_path, plan_path]},
    "site_generator": "runtime research_fd.d_radio.candidates(p,3)",
    "sites_meaning": "All original backhaul-qualified candidate xyz points, in the generator's original zero-based index order.",
    "sites": sites,
    "site_count": len(sites),
    "selected_site_indices": sorted(selected),
    "selected_site_count": len(selected),
    "selected_sites": [sites[i] for i in sorted(selected)],
    "demand_sample_step_s": 60,
    "ray_step_m": p.data["radio"]["ray_step_m"],
    "demands_count": len(demands),
    "active_minutes": len(minutes),
    "uncovered_minutes": uncovered_minutes,
    "minute_binning": "floor(time/60 + 1e-9), same as session-pool slot calculation; all sampled demands within the minute must be covered by the union of the chosen pair.",
    "movement_proxy": "At each active minute minimize the sum of two 3D Euclidean distances under the better of two matchings from the previous selected pair. First pair starts at O01 ground. Inactive minutes do not reset positions. This is not a physical travel-energy calculation.",
    "pair_semantics": "Unordered pairs with repetition were enumerated; repeated index means a single spatial candidate covers all demands. Ordered output records the chosen minimum-distance matching, not actual relay IDs.",
    "records": records,
    "elapsed_s": time.monotonic() - started,
}
target_path = OUT / "review/radio_temporal_candidate_pairs.json"
target_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: result[k] for k in ["site_count", "selected_site_indices", "selected_site_count", "demands_count", "active_minutes", "uncovered_minutes", "elapsed_s"]}, ensure_ascii=False, indent=2))
