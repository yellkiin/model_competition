"""Small immutable-run I/O helpers; no source/input fingerprint checks."""
from __future__ import annotations
import gzip
import json
from pathlib import Path


def read(path):
    p = Path(path)
    with (gzip.open(p, 'rt', encoding='utf-8-sig') if p.suffix == '.gz'
          else p.open(encoding='utf-8-sig')) as stream:
        return json.load(stream)


def write(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + '.tmp')
    if p.suffix == '.gz':
        with gzip.open(tmp, 'wt', encoding='utf-8', compresslevel=3) as stream:
            json.dump(obj, stream, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    else:
        tmp.write_text(json.dumps(obj, ensure_ascii=False, allow_nan=False, indent=2), encoding='utf-8')
    tmp.replace(p)


def plan_key(plan):
    # Exact equality only; do not assume arbitrary subgraph-ID renaming preserves
    # every official implementation tie-break. This is an in-run duplicate key.
    return (tuple(sorted((int(u), s) for u, s in plan['node_to_subgraph'].items())),
            tuple(tuple(seq) for seq in plan['core_schedules']))


def incumbent_from_job(folder):
    folder = Path(folder)
    state = read(folder/'progress.json')
    meta = state.get('incumbent')
    if not meta:
        return None, state
    plan_path = Path(meta['plan_file'])
    result_path = Path(meta['result_file'])
    plan_path = plan_path if plan_path.is_absolute() else folder/plan_path
    result_path = result_path if result_path.is_absolute() else folder/result_path
    result = read(result_path)
    if result.get('status') != 'ok' or not result.get('audit', {}).get('ok'):
        raise ValueError('Seed incumbent lacks a successful original evaluation and audit')
    return dict(plan=read(plan_path), response=result, official_result=result['official_result'],
                meta=meta, plan_file=str(plan_path), result_file=str(result_path)), state
