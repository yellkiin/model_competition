"""Compare fixed route retiming on identical input, route set and horizon."""
import argparse
import json
import math
from pathlib import Path
import sys
import time

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT/'runtime'))
from research_fd.d_model import Problem
from research_fd.d_experiments import load_plan, save_plan, save
from research_fd.d_schedule import metrics, integrated_milp, cpsat

p = argparse.ArgumentParser()
p.add_argument('--input', required=True)
p.add_argument('--plan', required=True)
p.add_argument('--out', required=True)
p.add_argument('--seconds', type=float, default=30)
p.add_argument('--steps', default='60,30,10')
p.add_argument('--cpsat', action='store_true')
a = p.parse_args()
problem = Problem.load(a.input)
jobs, _ = load_plan(a.plan)
base = metrics(problem, jobs)
if not jobs or any(base[k] for k in ('unserved', 'duplicated', 'resource_overlaps', 'hard_violations')):
    raise ValueError('Retiming comparison requires a complete feasible transport baseline')
routes = [j.route for j in jobs]
horizon = math.ceil((base['makespan_s'] + len(jobs)*60)/60)*60
results = [{'method': 'original_continuous_schedule', 'found': True, **base}]
for step in map(float, a.steps.split(',')):
    t = time.monotonic()
    sol, detail = integrated_milp(problem, routes, horizon, step, a.seconds)
    record = {'method': f'highs_step_{step:g}', 'found': bool(sol), 'elapsed_s': time.monotonic()-t,
              **metrics(problem, sol), 'solver': detail}
    results.append(record)
    save_plan(Path(a.out)/f'highs_step_{step:g}.json', problem, sol, detail)
    save(Path(a.out)/'comparison.json', {'baseline': a.plan, 'horizon_s': horizon, 'results': results})
    print(json.dumps(record, ensure_ascii=False), flush=True)
if a.cpsat:
    t = time.monotonic()
    sol, detail = cpsat(problem, routes, horizon, a.seconds, workers=4, seed=7)
    record = {'method': 'cpsat_seconds', 'found': bool(sol), 'elapsed_s': time.monotonic()-t,
              **metrics(problem, sol), 'solver': detail}
    results.append(record)
    save_plan(Path(a.out)/'cpsat_seconds.json', problem, sol, detail)
    save(Path(a.out)/'comparison.json', {'baseline': a.plan, 'horizon_s': horizon, 'results': results})
    print(json.dumps(record, ensure_ascii=False), flush=True)
