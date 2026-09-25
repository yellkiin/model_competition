"""Rebuild paired tables from real per-case records; does not run experiments.

All comparisons are separated by experiment/source version and seed. Uses stdlib.
"""
from pathlib import Path
import argparse,csv,json
from collections import Counter,defaultdict


def readcsv(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def csvwrite(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--results',type=Path,default=Path(__file__).parent/'results');parser.add_argument('--out',type=Path)
    a=parser.parse_args();root=a.results.resolve();out=a.out or root/'recheck_20260925_review';out.mkdir(parents=True,exist_ok=True)
    studies=[]
    ci=root/'recheck_20260925_run_36085958693'
    for p in sorted(ci.glob('case_*/**/per_case.csv')):
        studies.append(('ci_v2b',p.parent.parent.name,p.parent.name,p))
    for directory,version in [('recheck_local_v3_warm_20260925','local_v3'),('recheck_local_v4_cold_20260925','local_v4'),('recheck_local_v4_q1_064','local_v4'),('recheck_local_v4_300_064','local_v4')]:
        p=root/directory/'per_case.csv'
        if p.exists():studies.append((version,'local_machine',directory,p))
    rows=[];trajectory=[];summaries=[];pairs=[];stops=[]
    for version,machine,phase,p in studies:
        common={'source_version':version,'machine_group':machine,'experiment_phase':phase,'source_table':str(p.relative_to(root))}
        for row in readcsv(p):
            row={'case':row.get('case','').removeprefix('case_').zfill(3),**{k:v for k,v in row.items() if k!='case'}}
            rows.append({**common,**row})
        t=p.with_name('trajectory.csv')
        if t.exists():
            for row in readcsv(t):
                row['case']=row['case'].removeprefix('case_').zfill(3);trajectory.append({**common,**row})
        s=p.with_name('run_summary.json')
        if s.exists():summaries.append({**common,**json.loads(s.read_text())})
    grouped=defaultdict(dict)
    for row in rows:
        key=tuple(row.get(k,'') for k in ('source_version','machine_group','experiment_phase','case','q','n','mode','seed_id','rep'))
        grouped[key][row['method']]=row
    compare=[]
    for key,arms in sorted(grouped.items()):
        row=dict(zip(('source_version','machine_group','experiment_phase','case','q','n','mode','seed_id','rep'),key))
        for method,r in arms.items():
            for k in ('new_makespan','status','actual_route','solve_seconds','winning_name','new_added_copy_bytes','no_l2_makespan','pair_status','stopped','seed_solve_seconds','seed_validation_seconds','total_solve_seconds'):
                row[method+'_'+k]=r.get(k,'')
        old=arms.get('old',{}).get('new_makespan');new=arms.get('corrected',{}).get('new_makespan')
        if old and new:
            old,new=float(old),float(new)
            row['corrected_makespan_reduction_vs_old_pct']=100*(old-new)/old
            row['corrected_outcome']='improved' if new<old else ('equal' if new==old else 'regressed')
        else:row['corrected_outcome']='incomplete_pair'
        compare.append(row)
    csvwrite(out/'per_case.csv',rows);csvwrite(out/'trajectory.csv',trajectory);csvwrite(out/'paired_compare.csv',compare)
    count={'arms':len(rows),'statuses':dict(Counter(r['status'] for r in rows)),'source_versions':dict(Counter(r['source_version'] for r in rows)),'pair_requests':sum(s.get('q3_pairs_requested',0) for s in summaries),'pair_started':sum(s.get('q3_pairs_started',0) for s in summaries),'pair_completed':sum(s.get('q3_pairs_completed',0) for s in summaries),'pair_valid':sum(s.get('q3_pairs_valid',0) for s in summaries),'completed_evaluations_within_budget':sum(int(r.get('completed_evaluations') or 0) for r in rows),'stopped':dict(Counter(r.get('stopped','') for r in rows)),'formal_complete':False,'scope':'Independent real selected-case studies. Versions, phases and seeds must not be pooled as equivalent arms.'}
    csvwrite(out/'experiment_counts.csv',[{k:v for k,v in s.items() if not isinstance(v,(dict,list))} for s in summaries])
    (out/'COUNTS.json').write_text(json.dumps(count,ensure_ascii=False,indent=2))
    print(json.dumps(count,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
