"""Lossless publication of already-recorded plans and CSV fields.

The input files contain literal measured strings and integer runs. This module
only expands that storage representation. It never generates candidates,
executes an evaluator, fits a curve, or substitutes later values into a prefix.
"""
from pathlib import Path
from itertools import accumulate
import csv
import io
import json

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent


def expand(parts):
    values = []
    for part in parts:
        if isinstance(part, list):
            values.extend(part)
        else:
            block = part['values'] if 'values' in part else expand(part['parts'])
            values.extend(block * part['repeat'])
    return values


def delta_array(value):
    return list(accumulate([value[0]] + expand(value[1]))) if value else []


def plans():
    receipt = []
    for path in sorted(HERE.glob('seed_data_*.json')):
        for row in json.loads(path.read_text(encoding='utf8'))['plans']:
            target = PACKAGE / 'evidence/available_seeds' / row['path']
            if '..' in Path(row['path']).parts or Path(row['path']).is_absolute():
                raise ValueError('Plan publication path leaves package')
            ids = list(accumulate(expand(row['op_deltas'])))
            labels = delta_array(row['group_labels'])
            lengths = expand(row['group_lengths'])
            if len(labels) != len(lengths):
                raise ValueError('Stored group arrays differ in length')
            groups = [s for s, count in zip(labels, lengths) for _ in range(count)]
            if len(ids) != len(groups) or len(set(ids)) != len(ids):
                raise ValueError('Stored plan coverage sequence is incomplete')
            obj = {'node_to_subgraph':dict(zip(map(str, ids), groups)),
                   'core_schedules':[delta_array(v) for v in row['core_schedules']]}
            payload = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf8')
            if len(payload) != row['bytes']:
                raise ValueError('Plan byte length differs: ' + row['path'])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            receipt.append({'path':str(target.relative_to(PACKAGE)), 'bytes':len(payload),
                            'operations':len(ids), 'source':'literal recorded plan, losslessly expanded'})
    return receipt


def column(c, row_count):
    if 'constant' in c:
        return [c['constant']] * row_count
    if 'values' in c:
        return c['values']
    if 'indices' in c:
        return [c['dictionary'][i] for i in c['indices']]
    return [c['dictionary'][i] for i, count in c['runs'] for _ in range(count)]


def tables():
    receipt = []
    for path in sorted(HERE.glob('table_*.json')):
        data = json.loads(path.read_text(encoding='utf8'))
        cols = list(data.get('columns', []))
        for part in data.get('column_parts', []):
            cols.extend(json.loads((HERE / part).read_text(encoding='utf8'))['columns'])
        if len(cols) != len(data['header']):
            raise ValueError('Missing table columns: ' + data['filename'])
        decoded = [column(c, data['row_count']) for c in cols]
        if any(len(c) != data['row_count'] for c in decoded):
            raise ValueError('Incomplete table rows: ' + data['filename'])
        stream = io.StringIO(newline='')
        writer = csv.writer(stream, lineterminator=data['lineterminator'])
        writer.writerow(data['header'])
        writer.writerows(zip(*decoded))
        payload = stream.getvalue().encode('utf-8-sig' if data['bom'] else 'utf8')
        if len(payload) != data['bytes']:
            raise ValueError('CSV transfer byte length differs: ' + data['filename'])
        if Path(data['filename']).name != data['filename']:
            raise ValueError('Table filename must be a basename')
        target = PACKAGE / 'evidence' / data['filename']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        receipt.append({'path':str(target.relative_to(PACKAGE)), 'bytes_before_git_eol':len(payload),
                        'data_rows':data['row_count'], 'source':'all literal recorded strings; no recomputed time values'})
    return receipt


def main():
    result = {'purpose':'existing evidence publication only', 'new_official_evaluations':0,
              'plans':plans(), 'tables':tables()}
    (HERE / 'EVIDENCE_COPY_RECEIPT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'published_plans':len(result['plans']), 'published_tables':len(result['tables']),
                      'new_official_evaluations':0}), flush=True)


if __name__ == '__main__':
    main()
