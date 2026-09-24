"""Direct bounded A experiments. No smoke/unit/hash/audit prerequisite."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
import csv
from datetime import datetime,timezone
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import time
from .job import run_job
from .model import read_json
from .policy import VERSION
from .session import dump

ROOT=Path(__file__).resolve().parents[3]




def aggregate(out,manifest):
    baseline={};states={};coverage=[];rows=[]
    for job in manifest['jobs']:
        path=out/job['id']/'result.json'
        if not path.exists():
            coverage.append(dict(id=job['id'],status='not_started'));continue
        r=read_json(path);states[job['id']]=r
        coverage.append(dict(id=job['id'],status=r['status'],stop_reason=r.get('stop_reason'),official_calls=r.get('official_calls',0)))
        if r['q']==0 and r.get('incumbent'):baseline[r['case']]=r['incumbent']['makespan']
    for key,r in states.items():
        if not r['q']:continue
        t0=baseline.get(r['case'])
        for variant in ('fast','best'):
            score=r.get('fast' if variant=='fast' else 'incumbent')
            if not score:continue
            t=score['makespan'];lb=r.get('global_compute_lower')
            rows.append(dict(case=r['case'],question=r['q'],cores=r['n'],variant=variant,job_status=r['status'],
                makespan=t,original_singlecore=t0,speedup=t0/t if t0 is not None and t>0 else None,
                added_copy_bytes=score.get('added_copy_bytes'),partition_added_copy_bytes=score.get('partition_added_copy_bytes'),
                spill_added_copy_bytes=score.get('spill_added_copy_bytes'),cache_byte_hit_rate=score.get('cache_byte_hit_rate'),
                total_solve_seconds=r.get('solve_seconds'),fast_available_seconds=r.get('fast',{}).get('available_seconds') if r.get('fast') else None,
                official_calls=r.get('official_calls'),global_compute_lower=lb,
                speedup_upper_bound=t0/lb if t0 is not None and lb and not r.get('bound_violation') else None,
                instance_ratio_upper=t/lb if lb and t>=lb else None,
                same_plan_cache_ratio=(r.get('cache_pair') or {}).get('ratio') if variant=='best' else None,
                selected_recipe=json.dumps(score.get('recipe'),ensure_ascii=False),job=key))
    columns=['case','question','cores','variant','job_status','makespan','original_singlecore','speedup','added_copy_bytes','partition_added_copy_bytes','spill_added_copy_bytes','cache_byte_hit_rate','total_solve_seconds','fast_available_seconds','official_calls','global_compute_lower','speedup_upper_bound','instance_ratio_upper','same_plan_cache_ratio','selected_recipe','job']
    temp=out/'summary.csv.tmp'
    with temp.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows(rows)
    temp.replace(out/'summary.csv')
    dump(out/'coverage.json',dict(planned=len(manifest['jobs']),statuses=coverage))
    lines=['# ASTER V3 real-instance results','',f'Protocol: `{VERSION}`. Mode: {manifest["settings"]["mode"]}.',
           'Arithmetic and geometric means below use paired original-singlecore denominators. Counts are mandatory; incomplete cohorts are NOT 100-case results.','',
           '|Question|Cores|Variant|Paired count / selected|Arithmetic speedup|Geometric speedup|',
           '|---|---|---|---|---|---|']
    for q in manifest['settings']['questions']:
        for n in manifest['settings']['cores']:
            for variant in ('fast','best'):
                ratios=[r['speedup'] for r in rows if r['question']==q and r['cores']==n and r['variant']==variant and r['speedup'] is not None]
                if ratios:lines.append(f'|{q}|{n}|{variant}|{len(ratios)} / {len(manifest["settings"]["cases"])}|{statistics.mean(ratios):.6f}|{math.exp(statistics.mean(math.log(x) for x in ratios)):.6f}|')
    counts={s:sum(r['status']==s for r in coverage) for s in ('complete','partial','failed','running','not_started')}
    lines+=['',f'Job coverage: `{counts}`.',
        'A complete job means a valid solution (and, for Q3, the same-plan no-cache replay), not an exhaustive search.',
        'Fast-available time includes the first construction, official validation and I/O. Total solve time is shared by the complete solver, NOT the independent runtime of each variant.',
        'Any changed code, budget or retry belongs to a separate protocol; do not take per-case historical minima.',
        'Official feasibility is retained; no independent repository/timeline audit or hash task was run.']
    formal=(manifest['settings']['cases']==list(range(1,101)) and manifest['settings']['cores']==[1,2,3,4,5] and manifest['settings']['questions']==[1,2,3] and counts['complete']==len(manifest['jobs']))
    lines.append(f'formal_complete={str(formal).lower()}')
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
