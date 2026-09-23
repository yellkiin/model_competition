"""Energy/makespan tradeoff under ONE fixed baseline tardiness ceiling.

Derived from research_fd.d_schedule.integrated_milp (read-only original).
Changes: build and freeze one candidate pool for every cap; impose baseline
weighted tardiness as a constraint; minimize energy then makespan (no independent
tardiness minimization at each cap). Only outputs/ is writable by this script.
This is a restricted-pool, discrete-start model, not a global VRP Pareto proof.
"""
from __future__ import annotations
import argparse
import csv
from dataclasses import asdict, replace
import importlib
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix, csr_matrix, vstack

ROOT = Path(__file__).resolve().parents[3]
QUALITY_TOLERANCE = 1e-5


def solver_number(result, name):
    value = getattr(result, name, None)
    return None if value is None or not math.isfinite(float(value)) else float(value)


def validate_baseline(p, jobs, metrics):
    if not jobs:
        raise ValueError('Baseline is empty; fixed quality requires a feasible baseline')
    m = metrics(p, jobs)
    if any(m[k] for k in ('unserved', 'duplicated', 'resource_overlaps', 'hard_violations')):
        raise ValueError(f'Baseline is not transport feasible: {m}')
    for j in jobs:
        f = p.fleet[j.route.kind]
        if not isinstance(j.aircraft, int) or not 0 <= j.aircraft < f.count:
            raise ValueError('Baseline aircraft index exceeds declared inventory')
        if not isinstance(j.battery, int) or not 0 <= j.battery < f.batteries:
            raise ValueError('Baseline battery index exceeds declared inventory')
        r = p.route(j.route.boxes, j.route.kind, j.route.stops)
        if r is None:
            raise ValueError('Baseline contains a physically infeasible route')
        if j.start < r.release-1e-6 or j.start > r.latest+1e-6:
            raise ValueError('Baseline violates route release/hard deadline')
        for field in ('duration', 'energy', 'aircraft_hold', 'battery_hold'):
            if not math.isclose(getattr(r, field), getattr(j.route, field), abs_tol=1e-6, rel_tol=1e-9):
                raise ValueError('Baseline belongs to different physical input: '+field)
        if set(r.delivery) != set(j.route.delivery):
            raise ValueError('Baseline box/delivery fields are inconsistent')
        if any(abs(r.delivery[i]-j.route.delivery[i]) > 1e-6 for i in r.delivery):
            raise ValueError('Baseline delivery offsets differ from current physical input')
    return m


def freeze_pool(p, baseline, generated, max_routes):
    def key(route):
        return route.kind, tuple(route.boxes), tuple(route.stops)
    chosen = {}
    # Keep the actual baseline visit orders; do not regenerate only shortest ones.
    for j in baseline:
        chosen[key(j.route)] = j.route
    baseline_keys = set(chosen)
    for route in generated:
        if len(route.boxes) == 1:
            chosen.setdefault(key(route), route)
    required = len(chosen)
    for route in sorted(generated, key=lambda r: (r.aircraft_hold/len(r.boxes), r.energy, r.kind, r.boxes)):
        if len(chosen) >= max_routes:
            break
        chosen.setdefault(key(route), route)
    pool = [replace(route, id=i) for i, route in enumerate(chosen.values())]
    if not baseline_keys <= {key(route) for route in pool}:
        raise AssertionError('Fixed pool lost a baseline route')
    covered = {i for route in pool for i in route.boxes}
    if covered != set(range(len(p.boxes))):
        raise AssertionError('Fixed pool does not cover exactly the input box set')
    return pool, dict(generated_routes=len(generated), fixed_pool_routes=len(pool), required_routes=required,
                     baseline_routes=len(baseline_keys), max_routes_requested=max_routes,
                     required_exceeds_limit=required > max_routes,
                     policy='Keep all baseline routes and feasible singleton routes; fill remaining slots by per-box aircraft occupation.')


def optimize_cap(p, pool, cap, step, tardiness_ceiling, seconds, recolor, metrics):
    """Binary route/start columns, exact coverage, shared resource capacities."""
    start_clock = time.perf_counter()
    n = len(p.boxes)
    kinds = list(p.fleet)
    kind_index = {kind: i for i, kind in enumerate(kinds)}
    options = []
    for route in pool:
        last = min(route.latest, cap-route.duration)
        lo_tick = max(0, math.ceil(route.release/step))
        hi_tick = math.floor((last+1e-8)/step)
        options.extend((route, tick*step) for tick in range(lo_tick, hi_tick+1))
    detail = dict(backend='scipy-highs', routes=len(pool), options=len(options), step_s=step, cap_s=cap,
                  weighted_tardiness_ceiling_s=tardiness_ceiling, quality_tolerance_s=QUALITY_TOLERANCE,
                  energy_lock_tolerance_kwh=1e-5,
                  stage_order=['energy', 'makespan'], time_limit_per_stage_s=seconds,
                  scope='Fixed candidate pool, zero-anchored discrete starts, cap, hard deadlines and shared resources.', stages=[])
    if not options:
        detail.update(status='no_route_start_options', all_stages_optimal=False, elapsed_s=time.perf_counter()-start_clock)
        return [], detail
    nvar = len(options)+1
    z = nvar-1
    tail = max(max(route.aircraft_hold, route.battery_hold) for route in pool)
    ticks = math.ceil((cap+tail)/step)+1
    resource_rows = 2*len(kinds)*ticks
    quality_row = 2*n+resource_rows
    rows, cols, values = [], [], []
    tardiness = np.zeros(nvar)
    energy = np.zeros(nvar)
    makespan = np.zeros(nvar)
    makespan[z] = 1.

    def add(row, col, value=1.):
        rows.append(row)
        cols.append(col)
        values.append(value)

    for col, (route, start) in enumerate(options):
        for i in route.boxes:
            add(i, col)
            # Exactly one covering column per box makes its return <= makespan.
            add(n+resource_rows+i, col, start+route.duration)
            tardiness[col] += p.boxes[i].weight*max(0., start+route.delivery[i]-p.boxes[i].due)
        if tardiness[col]:
            add(quality_row, col, tardiness[col])
        energy[col] = route.energy
        for resource, hold in enumerate((route.aircraft_hold, route.battery_hold)):
            row0 = n+(2*kind_index[route.kind]+resource)*ticks
            for tick in range(round(start/step), math.ceil((start+hold-1e-8)/step)):
                add(row0+tick, col)
    for i in range(n):
        add(n+resource_rows+i, z, -1.)
    matrix = coo_matrix((values, (rows, cols)), shape=(quality_row+1, nvar)).tocsc()
    lower = np.r_[np.ones(n), np.full(resource_rows+n+1, -np.inf)]
    capacities = []
    for kind in kinds:
        capacities.extend([p.fleet[kind].count]*ticks)
        capacities.extend([p.fleet[kind].batteries]*ticks)
    upper = np.r_[np.ones(n), capacities, np.zeros(n), tardiness_ceiling+QUALITY_TOLERANCE]
    bounds = Bounds(np.zeros(nvar), np.r_[np.ones(z), cap])
    integrality = np.r_[np.ones(z), 0.]
    incumbent = None
    for name, objective in [('energy', energy), ('makespan', makespan)]:
        stage_clock = time.perf_counter()
        fit = milp(objective, integrality=integrality, bounds=bounds,
                   constraints=LinearConstraint(matrix, lower, upper),
                   options={'time_limit': float(seconds), 'mip_rel_gap': 1e-5})
        detail['stages'].append(dict(stage=name, status=int(fit.status), message=fit.message,
                                    objective=solver_number(fit, 'fun'), gap=solver_number(fit, 'mip_gap'),
                                    bound=solver_number(fit, 'mip_dual_bound'),
                                    has_incumbent=fit.x is not None, elapsed_s=time.perf_counter()-stage_clock))
        if fit.x is None:
            break
        incumbent = fit.x
        # Preserve the actual energy incumbent if a later stage times out.
        matrix = vstack([matrix, csr_matrix(objective[None, :])], format='csc')
        lower = np.r_[lower, -np.inf]
        upper = np.r_[upper, float(objective@incumbent)+1e-5]
    detail.update(all_stages_optimal=len(detail['stages'])==2 and all(s['status']==0 for s in detail['stages']),
                  elapsed_s=time.perf_counter()-start_clock,
                  status='no_incumbent' if incumbent is None else 'feasible_incumbent')
    if incumbent is None:
        return [], detail
    selected = [options[i] for i in np.flatnonzero(incumbent[:z] > .5)]
    jobs = recolor(p, selected)
    m = metrics(p, jobs)
    violations = []
    for key in ('unserved', 'duplicated', 'resource_overlaps', 'hard_violations'):
        if m[key]:
            violations.append(key)
    if m['weighted_tardiness_s'] > tardiness_ceiling+QUALITY_TOLERANCE+1e-6:
        violations.append('common_tardiness_ceiling')
    if m['makespan_s'] > cap+1e-5:
        violations.append('makespan_cap')
    detail['postcheck_violations'] = violations
    if violations:
        detail['status'] = 'invalid_incumbent'
    return jobs, detail


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--runtime')
    parser.add_argument('--seconds', type=float, default=30.)
    parser.add_argument('--step', type=float, default=60.)
    parser.add_argument('--trials', type=int, default=200)
    parser.add_argument('--max-routes', type=int, default=600)
    parser.add_argument('--ratios', default='1,1.1,1.25,1.5')
    parser.add_argument('--seed', type=int, default=7)
    args = parser.parse_args()
    if args.seconds <= 0 or args.step <= 0 or args.trials < 0 or args.max_routes < 1:
        parser.error('Require seconds/step/max-routes > 0 and trials >= 0')
    ratios = [float(value) for value in args.ratios.split(',')]
    if not ratios or any(not math.isfinite(value) or value <= 0 for value in ratios):
        parser.error('Ratios must be finite positive numbers')
    out = Path(args.out).resolve()
    out.relative_to((ROOT/'research_fd/outputs').resolve())
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT))
    if args.runtime:
        runtime = Path(args.runtime).resolve()
        if not (runtime/'research_fd/d_model.py').is_file():
            parser.error('--runtime must contain the adapted research_fd package')
        sys.path.insert(0, str(runtime))
    from research_fd.d_model import Problem
    from research_fd.d_routes import build_pool
    from research_fd.d_schedule import metrics, recolor
    from research_fd.d_experiments import load_plan, save, save_plan
    p = Problem.load(args.input)
    baseline, _ = load_plan(args.plan)
    bm = validate_baseline(p, baseline, metrics)
    baseline_off_grid = [dict(job=i, route_id=j.route.id, start_s=j.start)
                         for i, j in enumerate(baseline) if abs(j.start/args.step-round(j.start/args.step)) > 1e-8]
    pool_clock = time.perf_counter()
    generated = build_pool(p, args.seed, trials=args.trials)
    pool, pool_info = freeze_pool(p, baseline, generated, args.max_routes)
    pool_info['pool_generation_elapsed_s'] = time.perf_counter()-pool_clock
    save(out/'route_pool.json', dict(info=pool_info, routes=[asdict(r) for r in pool]))
    contract = dict(input=str(Path(args.input).resolve()), baseline_plan=str(Path(args.plan).resolve()),
                    runtime_model=str(Path(importlib.import_module('research_fd.d_model').__file__).resolve()),
                    metadata=p.data.get('metadata', {}), baseline_metrics=bm,
                    common_weighted_tardiness_ceiling_s=bm['weighted_tardiness_s'], quality_tolerance_s=QUALITY_TOLERANCE,
                    pool=pool_info, stage_order=['energy', 'makespan'], step_s=args.step, ratios=ratios,
                    seed=args.seed, trials=args.trials, seconds_per_stage=args.seconds,
                    baseline_starts_outside_grid=baseline_off_grid,
                    grid_warning='Containing baseline routes does not contain its continuous start times. Off-grid starts and the finite cap can exclude that baseline; no incumbent does not prove the physical problem infeasible.',
                    comparison_scope='Transport-only energy and return makespan at one common baseline soft-tardiness ceiling. No relay energy optimization.',
                    code_origin='Copied/modified time-index logic of research_fd.d_schedule.integrated_milp; original/runtime modules unchanged.')
    save(out/'experiment_contract.json', contract)
    rows = []
    for ratio in ratios:
        cap = bm['makespan_s']*ratio
        jobs, detail = optimize_cap(p, pool, cap, args.step, bm['weighted_tardiness_s'], args.seconds, recolor, metrics)
        detail['ratio'] = ratio
        detail['baseline_starts_outside_grid'] = len(baseline_off_grid)
        detail['pool_file'] = 'route_pool.json'
        metric = metrics(p, jobs)
        feasible = bool(jobs) and detail['status']=='feasible_incumbent'
        row = dict(ratio=ratio, cap_s=cap, feasible=feasible, status=detail['status'],
                   common_tardiness_ceiling_s=bm['weighted_tardiness_s'], options=detail['options'],
                   elapsed_s=detail['elapsed_s'], all_stages_optimal=detail['all_stages_optimal'], **metric)
        save_plan(out/f'energy_cap_{ratio:g}.json', p, jobs, detail)
        save(out/f'energy_cap_{ratio:g}_solver.json', detail)
        rows.append(row)
        save(out/'pareto.json', dict(contract=contract, records=rows))
        with (out/'pareto.csv').open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(json.dumps(row, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
