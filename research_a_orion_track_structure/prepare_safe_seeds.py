"""Build an explicit seed manifest from the unchanged formal selected-plan archive.

This reads published scores; safe_refine re-evaluates each target seed before use.
Use the supplied measured-history seed bundle to reproduce the reported warm run.
"""
import argparse,csv,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cases',required=True)
    p.add_argument('--day-root',type=Path,default=ROOT/'research_a_orion_anytime/team_results/day01/combined_final')
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();cases={f'case_{int(c):03d}' for c in a.cases.split(',')};out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    rows=[]
    with (a.day_root/'per_case.csv').open(encoding='utf-8-sig',newline='') as f,zipfile.ZipFile(a.day_root/'selected_plans.zip') as z:
        for r in csv.DictReader(f):
            q,n=int(r['q']),int(r['n'])
            if r['case'] not in cases or q==0 or r['status']!='ok':continue
            case=r['case'].removeprefix('case_');member=f'plans/q{q}/n{n}/{r["case"]}_multicore_res.json'
            plan=json.loads(z.read(member));target=out/f'{case}_q{q}_n{n}.json'
            target.write_text(json.dumps(plan,separators=(',',':')),encoding='utf8')
            try:filename=str(target.relative_to(ROOT))
            except ValueError:filename=str(target)
            rows.append(dict(case=case,q=q,n=n,recorded_makespan=int(r['makespan']),recorded_added_copy_bytes=int(r['added_copy_bytes']),plan_file=filename,seed_solve_seconds=float(r['solve_seconds']) if r['solve_seconds'] else None,seed_cost_source='published day01 per_case total solve_seconds; not a fresh timing',source_archive=str(a.day_root/'selected_plans.zip'),source_member=member))
    (out/'seed_manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
    print(out/'seed_manifest.json')
if __name__=='__main__':main()
