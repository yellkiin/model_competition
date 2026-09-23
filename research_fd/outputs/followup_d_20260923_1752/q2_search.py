"""Official Q2 finite-neighborhood search with a continuous resource-order DAG.

No route-by-time discretization is used. Run with research_fd/.venv Python.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import random
import sys
import time
from dataclasses import replace
from itertools import permutations

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research_fd" / "outputs" / "runtime"))
from research_fd.d_model import Problem
from research_fd.d_schedule import Job, metrics
from research_fd.d_experiments import load_plan, save_plan

HERE = Path(__file__).resolve().parent
SOURCE = ROOT / "research_fd" / "outputs"


def keys(p):
    return [(kind, label, ident) for kind, f in p.fleet.items()
            for label, count in (("aircraft", f.count), ("battery", f.batteries))
            for ident in range(count)]


def resource_orders(p, jobs):
    order = {k: [] for k in keys(p)}
    for idx, j in sorted(enumerate(jobs), key=lambda t: (t[1].start, t[0])):
        for label in ("aircraft", "battery"):
            order[(j.route.kind, label, getattr(j, label))].append(idx)
    return order


def dag_schedule(p, routes, order):
    """Longest paths in fixed entity orders; None means cycle/deadline failure."""
    n = len(routes)
    indeg = [0] * n
    succ = [[] for _ in routes]
    owners = [[None, None] for _ in routes]
    for (kind, label, ident), seq in order.items():
        pos = 0 if label == "aircraft" else 1
        for j in seq:
            if j < 0 or j >= n or routes[j].kind != kind or owners[j][pos] is not None:
                return None
            owners[j][pos] = ident
        for a, b in zip(seq, seq[1:]):
            hold = routes[a].aircraft_hold if pos == 0 else routes[a].battery_hold
            succ[a].append((b, hold))
            indeg[b] += 1
    if any(None in pair for pair in owners):
        return None
    starts = [r.release for r in routes]
    queue = [i for i, degree in enumerate(indeg) if degree == 0]
    seen = 0
    while queue:
        i = queue.pop()
        seen += 1
        if starts[i] > routes[i].latest + 1e-6:
            return None
        for j, lag in succ[i]:
            starts[j] = max(starts[j], starts[i] + lag)
            indeg[j] -= 1
            if indeg[j] == 0:
                queue.append(j)
    if seen != n:
        return None
    jobs = [Job(r, starts[i], owners[i][0], owners[i][1]) for i, r in enumerate(routes)]
    m = metrics(p, jobs)
    if any(m[k] for k in ("unserved", "duplicated", "resource_overlaps", "hard_violations")):
        return None
    return jobs, m


def route_choices(p, ids, kind, limit=3):
    ids = tuple(sorted(ids))
    nodes = sorted({p.boxes[i].node for i in ids})
    if not ids or len(nodes) > 4:
        return []
    found = []
    for order in permutations(nodes):
        r = p.route(ids, kind, order)
        if r is not None:
            found.append(r)
    if not found:
        return []
    pool = []
    for r in (min(found, key=lambda x: (x.energy, x.duration)),
              min(found, key=lambda x: (x.duration, x.energy)),
              max(found, key=lambda x: x.latest)):
        if r not in pool:
            pool.append(r)
    return pool[:limit]


def valid_zero(m):
    return (m["weighted_tardiness_s"] <= 1e-6 and m["hard_violations"] == 0
            and m["resource_overlaps"] == 0 and m["unserved"] == 0 and m["duplicated"] == 0)


def rank(m, mode):
    return ((m["energy_kwh"], m["makespan_s"]) if mode == "energy"
            else (m["makespan_s"], m["energy_kwh"]))


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=180)
    parser.add_argument("--seed", type=int, default=20260923)
    a = parser.parse_args()
    rng = random.Random(a.seed)
    p = Problem.load(SOURCE / "d_official.json")
    original, sessions = load_plan(SOURCE / "official_pareto_cpsat" / "energy_cap_1.json")
    assert not sessions and len(original) == 26
    routes = [j.route for j in original]
    order = resource_orders(p, original)
    assert valid_zero(metrics(p, original))
    def state(rr, oo):
        ret = dag_schedule(p, rr, oo)
        if ret is None:
            return None
        jj, mm = ret
        return {"routes": rr, "order": oo, "jobs": jj, "metrics": mm}
    baseline = {"routes": routes, "order": order, "jobs": original, "metrics": metrics(p, original)}
    compressed = state(routes, order)
    assert compressed is not None and valid_zero(compressed["metrics"])
    archives = {"energy": baseline, "fast": baseline}
    for mode in archives:
        if rank(compressed["metrics"], mode) < rank(archives[mode]["metrics"], mode):
            archives[mode] = compressed
    current = compressed
    attempts = {"dag": 1, "pair": 0, "triple": 0, "type_insert": 0, "order_insert": 0}
    feasible = {k: 0 for k in attempts}
    feasible["dag"] = 1
    updates = []
    start_time = time.perf_counter()
    rounds = 0

    def record(cand, op):
        nonlocal current
        if cand is None:
            return
        feasible[op] += 1
        if not valid_zero(cand["metrics"]):
            return
        for mode in archives:
            if rank(cand["metrics"], mode) < rank(archives[mode]["metrics"], mode):
                archives[mode] = cand
                row = {"elapsed_s": round(time.perf_counter()-start_time, 3), "operation": op,
                       "archive": mode, **cand["metrics"]}
                updates.append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
        cm = current["metrics"]
        mm = cand["metrics"]
        if (mm["energy_kwh"] + 0.004 * mm["makespan_s"] < cm["energy_kwh"] + 0.004 * cm["makespan_s"]
                or rng.random() < 0.004):
            current = cand

    def select_pair(rr):
        i = rng.randrange(len(rr))
        ni = set(rr[i].stops)
        candidates = [j for j in range(len(rr)) if j != i and
                      (rr[j].kind == rr[i].kind or ni.intersection(rr[j].stops))]
        if not candidates:
            candidates = [j for j in range(len(rr)) if j != i]
        weights = [6 if ni.intersection(rr[j].stops) else 1 for j in candidates]
        return i, rng.choices(candidates, weights)[0]

    while time.perf_counter() - start_time < a.seconds:
        rounds += 1
        base = archives[rng.choice(["energy", "fast"])] if rounds % 9 == 0 else current
        rr, oo = base["routes"], base["order"]
        mode = rng.choices(["pair", "triple", "type_insert", "order_insert"], [56, 10, 17, 17])[0]
        attempts[mode] += 1
        if mode in ("pair", "triple"):
            i, j = select_pair(rr)
            k = rng.randrange(len(rr))
            if mode == "triple" and k in (i, j):
                continue
            x, y = set(rr[i].boxes), set(rr[j].boxes)
            xi, yj = rng.choice(tuple(x)), rng.choice(tuple(y))
            if mode == "pair":
                option = rng.randrange(3)
                if option == 0 and len(x) >= 2:
                    xx, yy = x-{xi}, y|{xi}
                elif option == 1 and len(y) >= 2:
                    xx, yy = x|{yj}, y-{yj}
                else:
                    xx, yy = x-{xi}|{yj}, y-{yj}|{xi}
                choices1 = route_choices(p, xx, rr[i].kind)
                choices2 = route_choices(p, yy, rr[j].kind)
                if not choices1 or not choices2:
                    continue
                for r1 in choices1:
                    for r2 in choices2:
                        copy = list(rr)
                        copy[i], copy[j] = replace(r1, id=rr[i].id), replace(r2, id=rr[j].id)
                        record(state(copy, oo), mode)
            else:
                z = set(rr[k].boxes)
                zk = rng.choice(tuple(z))
                c1 = route_choices(p, x-{xi}|{zk}, rr[i].kind, 2)
                c2 = route_choices(p, y-{yj}|{xi}, rr[j].kind, 2)
                c3 = route_choices(p, z-{zk}|{yj}, rr[k].kind, 2)
                for r1 in c1:
                    for r2 in c2:
                        for r3 in c3:
                            copy = list(rr)
                            for ix, new in ((i,r1),(j,r2),(k,r3)):
                                copy[ix] = replace(new, id=rr[ix].id)
                            record(state(copy, oo), mode)
        elif mode == "order_insert":
            i = rng.randrange(len(rr))
            label = rng.choice(["aircraft", "battery"])
            copy_order = {k:list(v) for k,v in oo.items()}
            source = (rr[i].kind, label, next(k[2] for k,v in oo.items() if k[0] == rr[i].kind and k[1] == label and i in v))
            copy_order[source].remove(i)
            possible = [k for k in copy_order if k[0] == rr[i].kind and k[1] == label]
            dest = rng.choice(possible)
            copy_order[dest].insert(rng.randrange(len(copy_order[dest])+1), i)
            record(state(rr, copy_order), mode)
        else:
            i = rng.randrange(len(rr))
            possible = [kind for kind in p.fleet if kind != rr[i].kind]
            rng.shuffle(possible)
            for kind in possible:
                variants = route_choices(p, rr[i].boxes, kind, 2)
                if not variants:
                    continue
                for variant in variants:
                    aa = [key for key in oo if key[0] == kind and key[1] == "aircraft"]
                    bb = [key for key in oo if key[0] == kind and key[1] == "battery"]
                    for _ in range(5):
                        copy_order = {key:list(v) for key,v in oo.items()}
                        for seq in copy_order.values():
                            if i in seq:
                                seq.remove(i)
                        ak, bk = rng.choice(aa), rng.choice(bb)
                        copy_order[ak].insert(rng.randrange(len(copy_order[ak])+1), i)
                        copy_order[bk].insert(rng.randrange(len(copy_order[bk])+1), i)
                        copy = list(rr)
                        copy[i] = replace(variant, id=rr[i].id)
                        record(state(copy, copy_order), mode)

    for name, value in (("energy", archives["energy"]), ("fast", archives["fast"])):
        save_plan(HERE / f"q2_candidate_{name}.json", p, value["jobs"],
                  {"source": "official 26-trip plan", "method": "finite neighborhood continuous-time resource DAG",
                   "objective": name, "verified_zero_lateness": True,
                   "global_optimality_proven": False})
    rows = []
    for name, result in (("baseline", baseline), ("dag_compressed", compressed),
                         ("candidate_energy", archives["energy"]), ("candidate_fast", archives["fast"])):
        rows.append({"method": name, "status": "feasible_zero_lateness", "global_optimality_proven": False,
                     **result["metrics"]})
    write_csv(HERE / "q2_comparison.csv", rows)
    (HERE / "q2_search_log.json").write_text(json.dumps({"elapsed_s":time.perf_counter()-start_time,
        "seed":a.seed,"rounds":rounds,"attempts":attempts,"feasible":feasible,"updates":updates,
        "baseline":baseline["metrics"],"compressed":compressed["metrics"]},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(rows, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
