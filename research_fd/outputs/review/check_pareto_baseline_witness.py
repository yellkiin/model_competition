"""Verify that a saved baseline is a feasible binary witness of the fixed grid model."""
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]
data = json.loads((OUT/'d_official.json').read_text(encoding='utf-8'))
plan = json.loads((OUT/'official_transport_s7/best_plan.json').read_text(encoding='utf-8'))
pool0 = json.loads((OUT/'official_pareto/route_pool.json').read_text(encoding='utf-8'))
pool1 = json.loads((OUT/'official_pareto_repair_exact/route_pool.json').read_text(encoding='utf-8'))
step = 60.
cap = plan['metrics']['makespan_s']
quality = plan['metrics']['weighted_tardiness_s']

def key(route):
    return route['kind'], tuple(route['boxes']), tuple(route['stops'])

pool = {key(r): r for r in pool1['routes']}
counts = Counter()
occupied = defaultdict(Counter)
errors = []
total_tardiness = 0.
chosen = []
for j in plan['jobs']:
    r = j['route']
    k = key(r)
    if k not in pool:
        errors.append('Baseline route missing: '+str(k))
        continue
    q = pool[k]
    s = j['start']
    if abs(s/step-round(s/step)) > 1e-8:
        errors.append('Baseline start is off grid')
    latest = math.inf if q['latest'] is None else q['latest']
    if s < q['release']-1e-8 or s > min(latest, cap-q['duration'])+1e-8:
        errors.append('Baseline route/start option outside allowed domain')
    for field in ('duration', 'aircraft_hold', 'battery_hold', 'energy'):
        if abs(r[field]-q[field]) > 1e-8:
            errors.append('Physical route mismatch: '+field)
    counts.update(q['boxes'])
    for i in q['boxes']:
        b = data['boxes'][i]
        total_tardiness += b['weight']*max(0., s+q['delivery'][str(i)]-b['due'])
    for label, hold in [('aircraft', q['aircraft_hold']), ('battery', q['battery_hold'])]:
        for tick in range(round(s/step), math.ceil((s+hold-1e-8)/step)):
            occupied[(q['kind'], label)][tick] += 1
    chosen.append(dict(route_id=q['id'], start_s=s))
for i in range(len(data['boxes'])):
    if counts[i] != 1:
        errors.append('Box coverage inequality: '+str(i))
fleets = {f['id']: f for f in data['fleet']}
resource_peaks = {}
for (kind, label), ticks in occupied.items():
    peak = max(ticks.values(), default=0)
    resource_peaks[kind+'_'+label] = peak
    if peak > fleets[kind]['count' if label=='aircraft' else 'batteries']:
        errors.append('Discrete resource capacity exceeded: '+kind+'_'+label)
if total_tardiness > quality+1e-5:
    errors.append('Common quality ceiling exceeded')
result = dict(baseline_is_feasible_discrete_model_witness=not errors, errors=errors,
              original_and_repair_route_pools_identical=pool0['routes']==pool1['routes'],
              cap_s=cap, weighted_tardiness_s=total_tardiness, resource_peaks=resource_peaks,
              selected_route_start_columns=chosen,
              conclusion='This is a directly checked feasible witness, not an incumbent returned by an unexecuted solver.')
(OUT/'official_pareto_repair_exact/baseline_witness.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k!='selected_route_start_columns'}, ensure_ascii=False))
