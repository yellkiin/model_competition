"""Adapt the original normalizer to explicit row blocks in a multi-header sheet.
Only output files are written. No source values or research modules are changed.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent/'runtime'))
from research_fd import d_data

def table_rows(repo, spec):
    if 'blocks' in spec:
        return [row for block in spec['blocks'] for row in table_rows(repo, block)]
    rows = d_data.workbook(Path(repo)/spec['file'])[spec['sheet']]['rows']
    head = rows[spec['header_row']-1]
    headers = [str(v).strip() if v is not None else f'__empty_{i}' for i, v in enumerate(head)]
    if len(headers) != len(set(headers)):
        raise ValueError('Duplicate headers in specified block')
    result = []
    start, end = spec.get('row_start', spec['header_row']+1), spec.get('row_end', len(rows))
    for rownum in range(start, end+1):
        values = rows[rownum-1]
        if not any(v is not None for v in values):
            continue
        row = {k: values[i] if i < len(values) else None for i, k in enumerate(headers)}
        if spec.get('skip_if_empty') and row[spec['skip_if_empty']] is None:
            continue
        result.append({field: d_data.mapped(rule, row) for field, rule in spec['fields'].items()})
    return result

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mapping', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    d_data.table_rows = table_rows
    print(json.dumps(d_data.normalize(ROOT, a.mapping, a.out), ensure_ascii=False))
