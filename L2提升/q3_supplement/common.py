from __future__ import annotations
import csv, gzip, json, os, time, uuid
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
PROPOSAL = ROOT/'L2提升/proposals/20260926_workshop_v1_q3_portfolio'

def read(p):
    p=Path(p)
    with (gzip.open(p,'rt',encoding='utf-8-sig') if p.suffix=='.gz' else p.open(encoding='utf-8-sig')) as f:
        return json.load(f)

def write(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        handle=gzip.open(tmp,'wt',encoding='utf8',compresslevel=1) if p.suffix=='.gz' else tmp.open('w',encoding='utf8')
        with handle as f:json.dump(value,f,ensure_ascii=False,separators=(',',':'),allow_nan=False)
        for attempt in range(6):
            try:os.replace(tmp,p);break
            except PermissionError:
                if attempt==5:raise
                time.sleep(.02*(attempt+1))
    finally:
        tmp.unlink(missing_ok=True)

def csv_read(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def csv_write(p,rows,fields=None):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    fields=fields or list(dict.fromkeys(k for r in rows for k in r)) or ['status']
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

def plan_key(p):
    # Do not identify unequal subgraph labels as equivalent: they may break ties.
    return tuple(sorted((int(u),s) for u,s in p['node_to_subgraph'].items())),tuple(map(tuple,p['core_schedules']))

def engine(name):
    if name=='trident':
        from research_a_orion_trident.vendor.orion.engine import OfficialSession
        from research_a_orion_trident.vendor.orion import core,worker
    elif name=='unified':
        from research_a_orion_unified.vendor.orion.engine import OfficialSession
        from research_a_orion_unified.vendor.orion import core,worker
    else:raise ValueError('Explicit backend must be trident or unified')
    return OfficialSession,core,worker

def valid(response,q):
    audit=response.get('audit',{})
    raw=response.get('official_result',{})
    return response.get('status')=='ok' and audit.get('ok') is True and not audit.get('errors') and (raw.get('problem')==q or (q==2 and raw.get('scene')=='B'))

def score(r):
    raw=r['official_result'];return int(raw['makespan']),int(raw['data_movement_bytes']['added_copy_bytes'])
