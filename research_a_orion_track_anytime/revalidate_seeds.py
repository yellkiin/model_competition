"""Re-evaluate a portable existing seed pool with prepare.fixed, not score synthesis.

This delivery helper is not a new algorithm experiment. Original official checks
and exact same-plan Q3/no-L2 replays remain enabled.
"""
import argparse
from pathlib import Path
from .storage import read,write
from .prepare import fixed,csv_write,ROOT

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--cases',required=True);a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);cases={'case_'+f'{int(c):03d}' for c in a.cases.split(',')};records=[]
    chosen=[r for r in read(a.manifest) if r['case'] in cases]
    if {r['case'] for r in chosen}!=cases:raise ValueError('Missing requested real seed')
    for row in chosen:
        src=Path(row['seed_job']);src=src if src.is_absolute() else ROOT/src
        m=read(src/'progress.json')['incumbent']
        spec={**row,'original_plan':str(src/m['plan_file']),'original_response':str(src/m['result_file']),'original_progress':str(src/'progress.json'),'seed_job':str(out/'seeds'/f"{row['case']}_q{row['q']}_n{row['n']}")}
        records.append(fixed(spec));write(out/'partial_seed_manifest.json',records)
    write(out/'seed_manifest.json',records);csv_write(out/'replay_compare.csv',records)
if __name__=='__main__':main()
