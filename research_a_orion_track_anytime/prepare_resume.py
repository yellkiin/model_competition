"""Publish a complete seed manifest only after actual original-evaluator replays.

Questions and core counts are configurable; absent formal reference keys fail
explicitly. This imports prepare.fixed without changing the official evaluator.
"""
import argparse,csv,traceback
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from .storage import read,write
from .prepare import fixed,csv_write,ROOT

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--cases',default='001,024,044,059,083,084,086');p.add_argument('--workers',type=int,default=2);p.add_argument('--questions',default='1,2,3');p.add_argument('--cores',default='2,5');a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    cases={'case_'+f'{int(x):03d}' for x in a.cases.split(',')};day=ROOT/'research_a_orion_anytime/team_results/day01/combined_final'
    allrows=list(csv.DictReader((day/'per_case.csv').open(encoding='utf-8-sig')));todo=[]
    for row in allrows:
        case=row['case'];q=int(row['q']);n=int(row['n'])
        if case not in cases or q not in {int(x) for x in a.questions.split(',')} or n not in {int(x) for x in a.cores.split(',')}:continue
        candidates=[]
        for path in (ROOT/'raw_day01').glob(f'**/{case}_q{q}_n{n}/progress.json'):
            s=read(path);meta=s.get('incumbent')
            if meta and int(meta['makespan'])==int(row['makespan']):
                pp=path.parent/meta['plan_file'];rp=path.parent/meta['result_file']
                if pp.exists() and rp.exists():candidates.append((path,pp,rp))
        if not candidates:raise FileNotFoundError('No raw matching final plan '+str((case,q,n)))
        candidates.sort(key=lambda x:('refinement' not in str(x[0]),str(x[0])))
        pg,pp,rp=candidates[0]
        todo.append(dict(case=case,q=q,n=n,recorded_makespan=int(row['makespan']),baseline=int(row['baseline']),seed_solve_seconds=float(row['solve_seconds']),seed_cost_source='day01 per_case solve_seconds; historical machine, not same-host speed comparison',original_plan=str(pp),original_response=str(rp),original_progress=str(pg),seed_job=str(out/'seeds'/f'{case}_q{q}_n{n}'),recorded_no_l2=int(row['no_l2_makespan']) if row['no_l2_makespan'] else None))
    expected={(c,int(q),int(n)) for c in cases for q in a.questions.split(',') for n in a.cores.split(',')}
    missing=expected-{(s['case'],s['q'],s['n']) for s in todo}
    if missing:raise ValueError('No formal records for '+repr(sorted(missing))+'; day01 Q1/Q2 one-core reference is q0, not a fabricated warm seed.')
    write(out/'original_sources.json',todo);records=[];errors=[]
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futures={ex.submit(fixed,s):s for s in todo}
        for f in as_completed(futures):
            try:records.append(f.result())
            except Exception as exc:errors.append(dict(spec=futures[f],error=str(exc),traceback=traceback.format_exc()))
            write(out/'partial_seed_manifest.json',records);write(out/'prepare_errors.json',errors)
    csv_write(out/'replay_compare.csv',records)
    if errors:raise SystemExit('Actual replay errors: '+str(len(errors)))
    write(out/'seed_manifest.json',records)
if __name__=='__main__':main()
