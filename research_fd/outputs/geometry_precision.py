"""Compare native DEM cell coverage under three projection polyline steps."""
import csv
import json
from itertools import combinations
from pathlib import Path
import sys
import time

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT/'runtime'))
from research_fd.d_model import Problem

p = Problem.load(OUT/'d_official.json')
rows = []
t = time.monotonic()
for a, b in combinations(sorted(p.nodes), 2):
    u, v = p.nodes[a], p.nodes[b]
    peaks = [p.terrain.peak([u.x, u.y], [v.x, v.y], step) for step in (15, 7.5, 3.75)]
    rows.append({'from': a, 'to': b, 'peak_15_m': peaks[0], 'peak_7_5_m': peaks[1],
                 'peak_3_75_m': peaks[2], 'spread_m': max(peaks)-min(peaks)})
folder = OUT/'geometry_precision'
folder.mkdir(exist_ok=True)
with (folder/'arc_peaks.csv').open('w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
result = {'arcs_undirected': len(rows), 'steps_m': [15,7.5,3.75], 'max_peak_spread_m': max(r['spread_m'] for r in rows),
          'changed_arcs': [r for r in rows if r['spread_m']>1e-9], 'elapsed_s': time.monotonic()-t,
          'scope': 'All task-node pairs; relay candidate arcs are separately generated. This is convergence evidence on the supplied raster, not geodetic accuracy.'}
(folder/'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
