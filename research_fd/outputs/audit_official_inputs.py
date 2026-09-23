import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
sys.path.insert(0, str(OUT/'runtime'))
from research_fd.d_data import workbook

p = json.loads((OUT/'d_official.json').read_text(encoding='utf-8'))
folder = ROOT/'题目/D题/数据/无人机应急物资运输基础数据'
wb = workbook(folder/'物资需求与配送时限.xlsx')
raw = wb['逐箱货箱清单']['rows']
header = raw[0]
byid = {r[0]: dict(zip(header, r)) for r in raw[1:]}
expected = {(r[0], r[1]): int(r[2]) for r in wb['数据']['rows'][1:] if r and r[0] and r[1]}
actual = Counter((v['服务区编号'], v['物资类型']) for v in byid.values())
issues = []
if dict(actual) != expected:
    issues.append({'demand_aggregation_mismatch': {'actual': str(actual), 'expected': str(expected)}})
first = medical = 0
for box in p['boxes']:
    r = byid[box['id']]
    deadlines = []
    if r['是否首批保障'] == '是':
        first += 1
        deadlines.append(r['首批截止时间（s）'])
    if r['物资类型'] == '医疗物资':
        medical += 1
        deadlines.append(r['期望送达时间（s）'])
    hard = min(deadlines) if deadlines else None
    assert box['hard_due'] == hard
    assert box['due'] == r['期望送达时间（s）']
    assert box['mass'] == r['单箱质量（kg）'] and box['volume'] == r['单箱体积（m³）']
    assert box['node'] == r['服务区编号'] and box['weight'] == r['应急优先系数']
assert len(p['nodes']) == 16 and len(p['boxes']) == len(byid) == 80
assert all('loading_per_box' in f and f['loading_per_box'] == 30 for f in p['fleet'])
paths = [q for q in (ROOT/'题目/D题').rglob('*') if q.is_file() and q.suffix in ('.docx', '.xlsx', '.tif') and not q.name.startswith('~$')]
sources = [{'path': q.relative_to(ROOT).as_posix(), 'bytes': q.stat().st_size, 'sha256': hashlib.sha256(q.read_bytes()).hexdigest()} for q in paths]
result = {'status': 'valid' if not issues else 'invalid', 'nodes': len(p['nodes']), 'boxes': len(p['boxes']), 'mass_kg': sum(b['mass'] for b in p['boxes']), 'volume_m3': sum(b['volume'] for b in p['boxes']), 'first_batch_boxes': first, 'medical_boxes': medical, 'hard_deadline_boxes': sum(b['hard_due'] is not None for b in p['boxes']), 'first_batch_count_by_node': dict(Counter(r['服务区编号'] for r in byid.values() if r['是否首批保障']=='是')), 'issues': issues, 'source_files': sources, 'input_sha256': hashlib.sha256((OUT/'d_official.json').read_bytes()).hexdigest()}
(OUT/'official_input_audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ('source_files','first_batch_count_by_node')}, ensure_ascii=False))
if issues:
    raise SystemExit(1)
