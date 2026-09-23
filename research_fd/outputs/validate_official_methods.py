"""Recompute all actual official transport candidates, including failures."""
import json
from collections import Counter
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT / 'review'))
from export_validate_plan import validate_export

target = OUT / 'official_method_validation'
if target.exists():
    raise FileExistsError(target)
target.mkdir()
records = []
for parent, names in [
    ('official_transport_s7', ['greedy', 'route_milp', 'dual_route_milp', 'resource_dispatch', 'alns', 'fixed_route_retime', 'integrated_highs']),
    ('official_transport_cpsat', ['integrated_cpsat']),
    ('official_retime_grids', ['highs_step_30', 'highs_step_10', 'cpsat_seconds']),
]:
    for name in names:
        result = validate_export(OUT / 'd_official.json', OUT / parent / (name + '.json'),
                                 target / (parent + '__' + name), skip_radio=True,
                                 runtime=OUT / 'runtime')
        record = dict(source=f'{parent}/{name}.json', status=result['status'],
                      transport_valid=result['transport_valid'],
                      metrics=result['independently_recomputed_metrics'],
                      issues=len(result['issues']),
                      issue_types=dict(Counter(x.get('code', x.get('message', 'unknown')) for x in result['issues'])))
        records.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
(target / 'summary.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
