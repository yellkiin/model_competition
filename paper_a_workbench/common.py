"""Small UTF-8/path helpers; source snapshots are immutable, not experiment runs."""
from __future__ import annotations
import csv, gzip, json, re
from pathlib import Path
from datetime import datetime, timezone


def read(path):
    p=Path(path)
    with (gzip.open(p,'rt',encoding='utf-8-sig') if p.suffix=='.gz' else p.open(encoding='utf-8-sig')) as f:
        return json.load(f)


def write(path, value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_name(p.name+'.tmp')
    t.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    t.replace(p)


def csv_write(path, rows):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def within(root, relative):
    root=Path(root).resolve();p=Path(relative)
    if p.is_absolute() or '..' in p.parts or re.match(r'^[A-Za-z]:',str(relative)):
        raise ValueError(f'Expected a relative path: {relative}')
    out=(root/p).resolve();out.relative_to(root)
    return out


def stamp():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')


def fresh(path):
    p=Path(path);p.mkdir(parents=True,exist_ok=False);return p
