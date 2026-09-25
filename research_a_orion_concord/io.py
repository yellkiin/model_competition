"""Portable records. No input fingerprints, synthetic scores, or silent overwrites."""
from __future__ import annotations
import csv
import gzip
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = Path(__file__).resolve().parent

def read(path):
    p = Path(path)
    with (gzip.open(p, 'rt', encoding='utf-8-sig') if p.suffix == '.gz' else p.open(encoding='utf-8-sig')) as f:
        return json.load(f)

def write(path, obj):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_name(p.name + '.tmp')
    if p.suffix == '.gz':
        with gzip.open(t, 'wt', encoding='utf-8', compresslevel=1) as f:
            json.dump(obj, f, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    else:
        t.write_text(json.dumps(obj, ensure_ascii=False, allow_nan=False, indent=2), encoding='utf-8')
    t.replace(p)

def csv_write(path, rows, fields=None):
    rows = list(rows)
    fields = fields or list(dict.fromkeys(k for r in rows for k in r))
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fields, extrasaction='ignore'); w.writeheader(); w.writerows(rows)

def csv_read(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def key(plan):
    # Preserve IDs: the official builder may use them in deterministic ties.
    return (tuple(sorted((int(u), s) for u, s in plan['node_to_subgraph'].items())),
            tuple(tuple(v) for v in plan['core_schedules']))

def score(response):
    r = response['official_result']
    return r['makespan'], r['data_movement_bytes']['added_copy_bytes']

def resolve(base, name):
    p = Path(name)
    return p if p.is_absolute() else Path(base) / p

def utc():
    return datetime.now(timezone.utc).isoformat()

def attachment(value=None):
    dirs = [Path(value)] if value else list((ROOT/'题目'/'A题').glob('*附件'))
    if len(dirs) != 1:
        raise FileNotFoundError('Supply --official with the original A attachment')
    return dirs[0].resolve()
