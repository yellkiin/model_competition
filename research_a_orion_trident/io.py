"""Small portable records; no file fingerprints or environment benchmark."""
from __future__ import annotations
import csv, gzip, json, re, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    p = Path(path)
    with (gzip.open(p, 'rt', encoding='utf-8-sig') if p.suffix == '.gz'
          else p.open(encoding='utf-8-sig')) as f:
        return json.load(f)


def write(path, value):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + '.tmp')
    op = gzip.open if p.suffix == '.gz' else open
    with op(tmp, 'wt', encoding='utf8', **({'compresslevel': 1} if p.suffix == '.gz' else {})) as f:
        json.dump(value, f, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    tmp.replace(p)


def csv_read(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def csv_write(path, rows, fields=None):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fields, extrasaction='ignore'); w.writeheader(); w.writerows(rows)


def plan_key(plan):
    # Exact official labels and order; no unproved equivalence of ID renamings.
    return (tuple(sorted((int(u), s) for u,s in plan['node_to_subgraph'].items())),
            tuple(tuple(seq) for seq in plan['core_schedules']))


def score(response):
    raw = response.get('official_result', response)
    return int(raw['makespan']), int(raw['data_movement_bytes']['added_copy_bytes'])


def official_root(value=None):
    root = Path(value).resolve() if value else next((ROOT / '题目/A题').glob('*附件'))
    config = root / 'data/config.txt'
    if not config.is_file() or not (root / 'code/evaluation_validation.py').is_file():
        raise FileNotFoundError(f'Original A attachment incomplete: {root}')
    return root, config


def required_keys(case):
    return [(case, 0, 1)] + [(case, q, n) for q in (1, 2, 3) for n in range(2, 6)] + [(case, 3, 1)]


def key_name(case, q, n):
    return f'{case}_q{q}_n{n}'


def install_plan_archive(archive, destination):
    """Extract only official two-field plans, preserving q/n/case path layout."""
    dest = Path(destination); count = 0
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            m = re.search(r'(?:^|/)q([0-3])/n([1-5])/(case_\d{3})_multicore_res\.json$', info.filename)
            if not m: continue
            p = json.loads(z.read(info).decode('utf-8-sig'))
            if set(p) != {'node_to_subgraph', 'core_schedules'}:
                raise ValueError(f'Not an official plan: {info.filename}')
            q, n, case = m.groups()
            write(dest / f'q{q}' / f'n{n}' / f'{case}_multicore_res.json', p); count += 1
    if not count: raise ValueError('No plans with qN/nN/case_NNN_multicore_res.json layout')
    return count


def plan_path(root, case, q, n):
    return Path(root) / f'q{q}' / f'n{n}' / f'{case}_multicore_res.json'
