"""Substantive Q1 checks: delivered boxes, physical limits, and exact mask DP."""
from __future__ import annotations

import csv
from functools import lru_cache
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import q1_exact


def rows(name):
    with (HERE / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def full_mask_reference(p, node, reserve):
    ids = [i for i, b in enumerate(p.boxes) if b.node == node]
    n = len(ids)
    assert n <= 8  # Independent comparison stays small; S001 is proven by count-state enumeration.
    options = []
    for mask in range(1, 1 << n):
        selected = [ids[i] for i in range(n) if mask >> i & 1]
        mass = sum(p.boxes[i].mass for i in selected)
        volume = sum(p.boxes[i].volume for i in selected)
        for kind, fleet in p.fleet.items():
            result = q1_exact.trip(p, kind, node, mass, volume, len(selected))
            if result and result[0] <= fleet.usable_kwh * (1 - reserve) + 1e-9:
                options.append((mask, result[0], result[1]))

    @lru_cache(None)
    def dp(mask):
        if mask == 0:
            return (0, 0., 0.)
        target_bit = mask & -mask
        best = None
        for subset, energy, time in options:
            if subset & target_bit and subset & mask == subset:
                tail = dp(mask ^ subset)
                value = (1 + tail[0], energy + tail[1], time + tail[2])
                if best is None or value < best:
                    best = value
        return best

    return dp((1 << n) - 1)


def main():
    p = q1_exact.Problem.load(HERE.parent / "d_official.json")
    batches = rows("q1_batches.csv")
    caps = rows("q1_capacity_45.csv")
    totals = rows("q1_reserve_sensitivity.csv")
    by_id = {b.id: b for b in p.boxes}
    checks = []
    for record in totals:
        reserve = float(record["reserve"])
        subset = [row for row in batches if abs(float(row["reserve"]) - reserve) < 1e-9]
        ids = [ident for row in subset for ident in row["boxes"].split("|")]
        assert len(ids) == len(by_id) == 80 and set(ids) == set(by_id)
        for row in subset:
            kind, node = row["kind"], row["node"]
            bs = [by_id[ident] for ident in row["boxes"].split("|")]
            assert all(b.node == node for b in bs)
            mass = sum(b.mass for b in bs)
            volume = sum(b.volume for b in bs)
            actual = q1_exact.trip(p, kind, node, mass, volume, len(bs))
            assert actual is not None
            assert actual[0] <= p.fleet[kind].usable_kwh * (1 - reserve) + 1e-8
            assert math.isclose(actual[0], float(row["round_trip_energy_kwh"]), abs_tol=1e-8)
            assert math.isclose(actual[1], float(row["cumulative_work_s"]), abs_tol=1e-8)
        assert len(subset) == int(record["trips"])
        assert math.isclose(sum(float(row["round_trip_energy_kwh"]) for row in subset), float(record["transport_energy_kwh"]), abs_tol=1e-8)
        exact_nodes = {}
        for node in ("S002", "S003", "S008"):
            benchmark = full_mask_reference(p, node, reserve)
            node_rows = [row for row in subset if row["node"] == node]
            observed = (len(node_rows), sum(float(row["round_trip_energy_kwh"]) for row in node_rows), sum(float(row["cumulative_work_s"]) for row in node_rows))
            assert benchmark[0] == observed[0]
            assert math.isclose(benchmark[1], observed[1], abs_tol=1e-8)
            assert math.isclose(benchmark[2], observed[2], abs_tol=1e-8)
            exact_nodes[node] = dict(boxes=sum(b.node == node for b in p.boxes), trips=benchmark[0], energy_kwh=benchmark[1])
        checks.append(dict(reserve=reserve, all_80_boxes_once=True, batches=len(subset), independent_mask_dp_nodes=exact_nodes))
    assert len(caps) == 45
    for row in caps:
        fleet = p.fleet[row["kind"]]
        for reserve in (.20, .25, .30):
            cap = float(row[f"max_safe_mass_r{int(100*reserve)}_kg"])
            assert 0 <= cap <= fleet.payload + 1e-8
            if row[f"binding_r{int(100*reserve)}"] != "empty_trip_exceeds_reserve":
                e, _ = q1_exact.trip(p, row["kind"], row["node"], cap, 0., 1)
                assert e <= fleet.usable_kwh * (1-reserve) + 1e-8
    result = dict(status="passed", scope="80-box exact coverage and physical limits for all three reserves; independent full-mask DP at three representative nodes per reserve", capacity_rows=45, checks=checks)
    (HERE / "q1_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
