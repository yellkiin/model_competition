"""Targeted repair in a NEW root, starting from re-evaluated parent plans.

Extra-budget repairs are separate experiments, never mixed into the original
fixed-budget table. Select a single correction, not a large parameter grid.
"""
from __future__ import annotations
import argparse
import csv
from pathlib import Path
from types import SimpleNamespace
from .official import write
from research_a.model import read_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--profile',choices=['components','locality','spill','cache','window'],default=None)
    p.add_argument('--limit',type=int,default=2);p.add_argument('--workers',type=int,default=1)
    p.add_argument('--minutes',type=float,default=15);p.add_argument('--eval-seconds',type=float,default=60)
    p.add_argument('--archive');a=p.parse_args()
    source=a.source.resolve();m=read_json(source/'manifest.json')
    if a.out.resolve()==source:raise ValueError('Repair requires a NEW output root')
    if min(a.limit,a.workers,a.minutes,a.eval_seconds)<=0:raise ValueError('Positive limits required')
    from .report import collect
    collect(source)
    with (source/'report/diagnosis.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    names=sorted({r['case'] for r in rows})[:a.limit]
    if not names:raise ValueError('No diagnosed cases. Do not automatically expand a successful experiment.')
    suggested=a.profile or next((r['profile'] for r in rows if r['case'] in names),'components')
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    catalog=out/'parent_plans.csv'
    with catalog.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['case','question','cores','plan_path']);writer.writeheader()
        for name in names:
            for q in (1,2,3):
                for n in m['cores']:
                    plan=source/'cases'/name/f'q{q}'/f'n{n}'/f'{name}_multicore_res.json'
                    if plan.exists():writer.writerow(dict(case=name,question=q,cores=n,plan_path=str(plan)))
    from .run import prepare,run
    prepare(SimpleNamespace(out=out,archive=a.archive,cases=names,cores=m['cores'],full=False,profile=suggested,
                            eval_seconds=a.eval_seconds,case_seconds=600,max_calls=40,baseline_catalog=catalog))
    write(out/'repair_scope.json',dict(parent=str(source),cases=names,profile=suggested,
          additional_budget=True,not_a_replacement_for_parent_score=True,
          missing_parent_plan='No feasible parent available; reconstruct baseline under original rules'))
    run(SimpleNamespace(out=out,workers=a.workers,minutes=a.minutes,shard_index=0,shard_count=1))

if __name__=='__main__':main()
