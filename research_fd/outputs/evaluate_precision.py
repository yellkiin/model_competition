"""Actual radio time/ray precision comparison on one unchanged joint plan."""
import argparse
import csv
from functools import lru_cache
import json
from pathlib import Path
import sys
import time

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT/'runtime'))
from research_fd.d_model import Problem
from research_fd.d_experiments import load_plan, save
from research_fd.d_radio import evaluate_radio, route_samples, margin, ground

pa = argparse.ArgumentParser()
pa.add_argument('--input', required=True)
pa.add_argument('--plan', required=True)
pa.add_argument('--out', required=True)
pa.add_argument('--rays', default='30,15,7.5')
pa.add_argument('--times', default='60,20,5')
args = pa.parse_args()
p = Problem.load(args.input)
jobs, sessions = load_plan(args.plan)
folder = Path(args.out)
folder.mkdir(parents=True, exist_ok=True)
original_blocked = p.terrain.blocked
@lru_cache(maxsize=200000)
def blocked(a, b, step):
    return original_blocked(a, b, step)
p.terrain.blocked = lambda a, b, step=30: blocked(tuple(a), tuple(b), float(step))
rays = list(map(float, args.rays.split(',')))
times = list(map(float, args.times.split(',')))
summary = []
for ray in rays:
    p.data['radio']['ray_step_m'] = ray
    for dt in times:
        began = time.monotonic()
        result = evaluate_radio(p, jobs, sessions, dt)
        result.update(ray_step_m=ray, elapsed_s=time.monotonic()-began)
        save(folder/f'ray_{ray:g}_time_{dt:g}.json', result)
        summary.append({k:v for k,v in result.items() if k != 'details'})
        save(folder/'summary.json', {'plan': args.plan, 'input': args.input, 'rows': summary,
             'limitation': 'Finite numerical samples, including phase boundaries; no claim of an all-continuous-time proof.'})
        print(json.dumps(summary[-1], ensure_ascii=False), flush=True)
with (folder/'summary.csv').open('w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(summary[0]))
    w.writeheader()
    w.writerows(summary)
p.data['radio']['ray_step_m'] = min(rays)
base = ground(p)
cfg = p.data['radio']
rows = []
for job in jobs:
    for t, xyz in route_samples(job.route, job.start, min(times)):
        direct = margin(p, xyz, base, cfg['direct_budget_db'])
        best = direct
        provider = 'G01' if direct >= -1e-7 else 'disconnected'
        relay_index = None
        for idx, session in enumerate(sessions):
            if session.ready-1e-7 <= t <= session.stop+1e-7:
                m = min(margin(p, xyz, session.xyz, cfg['access_budget_db']), margin(p, session.xyz, base, cfg['backhaul_budget_db']))
                if m > best:
                    best = m
                    if direct < -1e-7 and m >= -1e-7:
                        provider = 'relay'
                        relay_index = idx
        rows.append({'route_id': job.route.id, 'time_s': t, 'x_m': xyz[0], 'y_m': xyz[1],
                     'z_m': xyz[2], 'direct_margin_db': direct, 'best_margin_db': best,
                     'provider': provider, 'relay_session_index': relay_index})
with (folder/'finest_samples.csv').open('w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ['route_id','time_s'])
    w.writeheader()
    w.writerows(rows)
