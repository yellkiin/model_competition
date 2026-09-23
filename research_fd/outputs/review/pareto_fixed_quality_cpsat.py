"""CP-SAT repair: same frozen pool, common quality and 60 s start grid.

Use optional intervals instead of expanding every route/start binary. Aircraft
and battery lengths are rounded upward in grid ticks; with grid starts this is
exactly the same capacity model. Energy is rounded to 1e-9 kWh and the secondary
return objective to one microsecond. Baseline hints are not solver incumbents.
"""
from __future__ import annotations
import argparse
import csv
import importlib
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
ENERGY_SCALE = 10**9
TIME_SCALE = 10**6
QUALITY_SCALE = 10**9
TOL = 1e-5


def route_key(r):
    return r.kind, tuple(r.boxes), tuple(r.stops)


def solve_cap(p, pool, baseline, ceiling, cap, step, seconds, workers, seed, recolor, metrics):
    from ortools.sat.python import cp_model
    t0 = time.perf_counter()
    model = cp_model.CpModel()
    makespan = model.new_int_var(0, math.ceil(cap*TIME_SCALE), 'return_makespan_us')
    active = {i: [] for i in range(len(p.boxes))}
    body = {k: [] for k in p.fleet}
    battery = {k: [] for k in p.fleet}
    variables, selected, starts, energy_terms, quality_terms = [], [], [], [], []
    baseline_by_key = {route_key(j.route): j for j in baseline}
    remaining_routes, equivalent_options, excluded_routes = [], 0, 0
    for route in pool:
        lo = max(0, math.ceil(route.release/step))
        hi = math.floor((min(route.latest, cap-route.duration)+1e-8)/step)
        qualities = []
        for tick in range(lo, hi+1):
            tard = sum(p.boxes[i].weight*max(0., tick*step+route.delivery[i]-p.boxes[i].due) for i in route.boxes)
            if tard > ceiling+TOL:
                break  # tardiness is monotone nondecreasing in start time
            qualities.append(tard)
        if not qualities:
            excluded_routes += 1
            continue
        hi = lo+len(qualities)-1
        equivalent_options += len(qualities)
        remaining_routes.append(route)
        z = model.new_bool_var(f'r{route.id}')
        start = model.new_int_var(lo, hi, f's{route.id}')
        selected.append(z)
        starts.append(start)
        variables.append((route, z, start, lo, hi))
        for label, hold, target in [('a', route.aircraft_hold, body), ('b', route.battery_hold, battery)]:
            length = math.ceil((hold-1e-8)/step)
            end = model.new_int_var(lo+length, hi+length, f'{label}e{route.id}')
            target[route.kind].append(model.new_optional_interval_var(start, length, end, z, f'{label}{route.id}'))
        model.add(makespan >= start*round(step*TIME_SCALE)+math.ceil(route.duration*TIME_SCALE)).only_enforce_if(z)
        for i in route.boxes:
            active[i].append(z)
        energy_terms.append(round(route.energy*ENERGY_SCALE)*z)
        if max(qualities) > 0:
            # Conservative sub-nanosecond quality rounding; the exact original
            # floating quality is always checked after solving.
            vals = [math.ceil(value*QUALITY_SCALE) for value in qualities]
            offset = model.new_int_var(0, hi-lo, f'offset{route.id}')
            model.add(offset == start-lo)
            raw = model.new_int_var(min(vals), max(vals), f'raw_quality{route.id}')
            model.add_element(offset, vals, raw)
            chosen_quality = model.new_int_var(0, max(vals), f'quality{route.id}')
            model.add(chosen_quality == raw).only_enforce_if(z)
            model.add(chosen_quality == 0).only_enforce_if(z.Not())
            quality_terms.append(chosen_quality)
        hint = baseline_by_key.get(route_key(route))
        model.add_hint(z, int(hint is not None))
        model.add_hint(start, round(hint.start/step) if hint is not None else lo)
    for options in active.values():
        model.add_exactly_one(options)
    for kind, fleet in p.fleet.items():
        model.add_cumulative(body[kind], [1]*len(body[kind]), fleet.count)
        model.add_cumulative(battery[kind], [1]*len(battery[kind]), fleet.batteries)
    model.add(sum(quality_terms) <= math.floor((ceiling+TOL)*QUALITY_SCALE))
    energy = sum(energy_terms)
    model.add_hint(makespan, math.ceil(max(j.start+j.route.duration for j in baseline)*TIME_SCALE))
    detail = dict(backend='ortools-cpsat', routes=len(pool), active_routes=len(variables), excluded_no_start_routes=excluded_routes,
                  equivalent_route_start_options=equivalent_options, step_s=step, cap_s=cap,
                  common_weighted_tardiness_ceiling_s=ceiling, quality_tolerance_s=TOL,
                  time_limit_per_stage_s=seconds, workers=workers, seed=seed,
                  objective_energy_quantum_kwh=1/ENERGY_SCALE, objective_time_quantum_s=1/TIME_SCALE,
                  quality_rounding_s=1/QUALITY_SCALE, positive_quality_tables=len(quality_terms),
                  baseline_hint=True, stages=[],
                  scope='Same frozen route pool and start grid; interval lengths in ticks exactly represent grid-start cumulative capacities.')
    print(json.dumps(dict(event='cpsat_model', cap_s=cap, routes=len(pool), active_routes=len(variables), equivalent_options=equivalent_options), ensure_ascii=False), flush=True)
    incumbent = None
    for label, objective, scale in [('energy', energy, ENERGY_SCALE), ('makespan', makespan, TIME_SCALE)]:
        model.minimize(objective)
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = seconds
        solver.parameters.num_search_workers = workers
        solver.parameters.random_seed = seed
        st = time.perf_counter()
        status = solver.solve(model)
        found = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        objective_value = solver.objective_value/scale if found else None
        bound = float(solver.best_objective_bound)/scale
        gap = abs(objective_value-bound)/max(abs(objective_value), 1e-12) if found else None
        detail['stages'].append(dict(stage=label, status=solver.status_name(status), has_incumbent=found,
                                    objective=objective_value, bound=bound, relative_gap=gap, elapsed_s=time.perf_counter()-st,
                                    response_stats=solver.response_stats()))
        if not found:
            break
        incumbent = [(route, float(solver.value(start)*step)) for route, z, start, _, _ in variables if solver.value(z)]
        value = round(solver.objective_value)
        model.add(objective <= value)
        model.clear_hints()
        for route, z, start, _, _ in variables:
            model.add_hint(z, solver.value(z))
            model.add_hint(start, solver.value(start))
        model.add_hint(makespan, solver.value(makespan))
    detail['elapsed_s'] = time.perf_counter()-t0
    detail['all_stages_optimal'] = len(detail['stages'])==2 and all(s['status']=='OPTIMAL' for s in detail['stages'])
    if incumbent is None:
        detail['status'] = 'no_solver_incumbent'
        return [], detail
    jobs = recolor(p, incumbent)
    m = metrics(p, jobs)
    violations = [key for key in ('unserved','duplicated','hard_violations','resource_overlaps') if m[key]]
    if m['weighted_tardiness_s'] > ceiling+TOL+1e-6:
        violations.append('common_quality')
    if m['makespan_s'] > cap+1e-5:
        violations.append('return_cap')
    detail['postcheck_violations'] = violations
    detail['status'] = 'invalid_incumbent' if violations else 'feasible_solver_incumbent'
    return jobs, detail


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--pool', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--runtime')
    parser.add_argument('--seconds', type=float, default=30.)
    parser.add_argument('--step', type=float, default=60.)
    parser.add_argument('--ratios', default='1,1.1,1.25,1.5')
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--seed', type=int, default=7)
    args = parser.parse_args()
    if args.seconds <= 0 or args.step <= 0 or args.workers <= 0:
        parser.error('seconds, step and workers must be positive')
    ratios = [float(x) for x in args.ratios.split(',')]
    if any(not math.isfinite(r) or r < 1 for r in ratios):
        parser.error('Ratios must be finite and >=1 so the validated baseline hint fits')
    out = Path(args.out).resolve()
    out.relative_to((ROOT/'research_fd/outputs').resolve())
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT))
    if args.runtime:
        sys.path.insert(0, str(Path(args.runtime).resolve()))
    from research_fd.d_model import Problem, Route
    from research_fd.d_schedule import metrics, recolor
    from research_fd.d_experiments import load_plan, save, save_plan
    from pareto_fixed_quality import validate_baseline
    p = Problem.load(args.input)
    baseline, _ = load_plan(args.plan)
    bm = validate_baseline(p, baseline, metrics)
    if any(abs(j.start/args.step-round(j.start/args.step)) > 1e-8 for j in baseline):
        raise ValueError('This repair requires a baseline on the same start grid for valid hints')
    pooldata = json.loads(Path(args.pool).read_text(encoding='utf-8'))
    pool = []
    for entry in pooldata['routes']:
        r = dict(entry)
        r['boxes'], r['stops'] = tuple(r['boxes']), tuple(r['stops'])
        r['delivery'] = {int(i): value for i, value in r['delivery'].items()}
        r['latest'] = math.inf if r['latest'] is None else r['latest']
        pool.append(Route(**r))
    if not {route_key(j.route) for j in baseline} <= {route_key(r) for r in pool}:
        raise ValueError('Supplied frozen pool is missing a baseline route')
    save(out/'route_pool.json', pooldata)
    save_plan(out/'known_baseline_plan.json', p, baseline, dict(source_plan=str(Path(args.plan).resolve()),
              status='previously_executed_and_revalidated_baseline', solver_returned_incumbent=False,
              warning='This saved baseline must not be relabeled as a CP-SAT incumbent.'))
    contract = dict(input=str(Path(args.input).resolve()), baseline_plan=str(Path(args.plan).resolve()),
                    pool_source=str(Path(args.pool).resolve()), runtime_model=str(Path(importlib.import_module('research_fd.d_model').__file__).resolve()),
                    baseline_metrics=bm, common_quality_ceiling_s=bm['weighted_tardiness_s'],
                    ratios=ratios, step_s=args.step, seed=args.seed, seconds_per_stage=args.seconds,
                    model='Fixed-pool common-quality energy and return-makespan biobjective; no relay optimization.',
                    incumbent_policy='Only OPTIMAL/FEASIBLE backend results populate cap plans. Known baseline is stored separately if backend returns UNKNOWN.')
    save(out/'experiment_contract.json', contract)
    records = []
    for ratio in ratios:
        cap = ratio*bm['makespan_s']
        jobs, detail = solve_cap(p, pool, baseline, bm['weighted_tardiness_s'], cap, args.step, args.seconds,
                                args.workers, args.seed, recolor, metrics)
        detail['ratio'] = ratio
        row = dict(ratio=ratio, cap_s=cap, feasible=bool(jobs) and detail['status']=='feasible_solver_incumbent',
                   status=detail['status'], elapsed_s=detail['elapsed_s'], all_stages_optimal=detail['all_stages_optimal'],
                   known_baseline_feasible=True, **metrics(p, jobs))
        records.append(row)
        save_plan(out/f'energy_cap_{ratio:g}.json', p, jobs, detail)
        save(out/f'energy_cap_{ratio:g}_solver.json', detail)
        save(out/'pareto.json', dict(contract=contract, records=records))
        with (out/'pareto.csv').open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
        print(json.dumps(row, ensure_ascii=False), flush=True)


if __name__=='__main__':
    main()
