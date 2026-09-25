"""Aggregate existing experiment artifacts only; never start or rescore a solver."""
import argparse,csv,json,shutil
from pathlib import Path
from collections import Counter,defaultdict

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
def table(p,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with Path(p).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    jobs=[];traj=[];replays=[];diagnostics=[];sources=[]
    for folder in sorted(a.input.glob('wu-real-case-*')):
        case=folder.name.rsplit('-',1)[-1];rec=folder/'paired30/all_jobs.json'
        if not rec.exists():sources.append(dict(case=case,status='missing_all_jobs'));continue
        local=read(rec);jobs.extend(local)
        dst=a.out/('case_'+case);dst.mkdir(exist_ok=True)
        for rel in ['paired30/per_case.csv','paired30/trajectory.csv','paired30/manifest.json','paired30/run_summary.json','paired30/worker_waves.json','preparation/replay_compare.csv','preparation/prepare_errors.json','EXECUTION_COMMIT.txt']:
            f=folder/rel
            if f.exists():shutil.copy(f,dst/Path(rel).name)
        with (folder/'paired30/trajectory.csv').open(encoding='utf-8-sig',newline='') as f:traj.extend(csv.DictReader(f))
        with (folder/'preparation/replay_compare.csv').open(encoding='utf-8-sig',newline='') as f:replays.extend(csv.DictReader(f))
        for d in (folder/'preparation/seeds').glob('*q3*/diagnostics/diagnostics.json'):
            r=read(d);base=dict(case=case,scene=d.parent.parent.name,makespan=r['makespan'],hit_rate=r['cache_stats']['hit_rate'],no_l2_makespan=r['same_plan_pair']['no_l2_makespan'],frozen_diagnostic_not_causal=True)
            for k,v in r['categories'].items():
                for metric,val in v.items():base[k+'_'+metric]=val
            diagnostics.append(base)
        sources.append(dict(case=case,status='read_raw_artifact',arm_count=len(local),manifest=read(folder/'paired30/manifest.json'),runtime_commit=(folder/'EXECUTION_COMMIT.txt').read_text().strip()))
    rows=[{k:v for k,v in r.items() if not isinstance(v,(dict,list))} for r in jobs]
    table(a.out/'per_case.csv',rows);table(a.out/'trajectory.csv',traj);table(a.out/'replay_compare.csv',replays);table(a.out/'cache_diagnostics.csv',diagnostics)
    pairs=[{k:r.get(k) for k in ('case','q','n','mode','method','makespan','no_l2_makespan','cache_hit_rate','pair_status','pair_exact_plan','pair_seconds','pair_plan_file','pair_result_file')} for r in jobs if r['q']==3]
    table(a.out/'cache_pairs.csv',pairs)
    grouped=defaultdict(dict)
    for r in jobs:grouped[r['case'],r['q'],r['n'],r['mode']][r['method']]=r
    compare=[]
    for (c,q,n,mode),arms in sorted(grouped.items()):
        old=arms.get('old',{});new=arms.get('combined',{});u=old.get('makespan');v=new.get('makespan')
        compare.append(dict(case=c,q=q,n=n,mode=mode,old=u,combined=v,old_seconds=old.get('solve_seconds'),combined_seconds=new.get('solve_seconds'),old_status=old.get('status'),combined_status=new.get('status'),outcome=('win' if v<u else 'loss' if v>u else 'tie') if u is not None and v is not None else 'missing_feasible_side',reduction_pct=100*(1-v/u) if u and v is not None else None,base=old.get('baseline'),old_stop=old.get('stopped'),new_stop=new.get('stopped')))
    table(a.out/'comparison.csv',compare)
    means=[]
    for mode in ('warm_start','cold_start'):
        for q in (1,2,3):
            for n in (2,5):
                rs=[r for r in compare if r['mode']==mode and r['q']==q and r['n']==n];complete=[r for r in rs if r['old'] is not None and r['combined'] is not None]
                means.append(dict(mode=mode,q=q,n=n,expected_cases=7,observed_cases=len(rs),paired_feasible_cases=len(complete),old_mean=sum(r['base']/r['old'] for r in complete)/len(complete) if complete else None,new_mean=sum(r['base']/r['combined'] for r in complete)/len(complete) if complete else None,complete_seven_cases=len(complete)==7,missing_not_dropped_from_count=True))
    table(a.out/'means.csv',means)
    stats=dict(source_run=36106285863,executed_code='ff326e037312bec791efb465d7c0d161df84b8e3',policy='wu-v1.1',expected_arms=168,actual_rows=len(jobs),status_counts=dict(Counter(r['status'] for r in jobs)),warm_outcomes=dict(Counter(r['outcome'] for r in compare if r['mode']=='warm_start')),cold_outcomes=dict(Counter(r['outcome'] for r in compare if r['mode']=='cold_start')),q3_pairs_requested=len(pairs),q3_pairs_valid=sum(r['pair_status']=='ok' and r['pair_exact_plan'] for r in pairs),formal_replays=len(replays),diagnostic_pairs=len(diagnostics),new_algorithm_100_run=False,normalization_warning='v1.1 gap uses 1-L/U; old uses U/L-1; v2 explicitly aligns these definitions. Do not attribute threshold-crossing early stops only to scheduling.',sources=sources)
    write(a.out/'SUMMARY.json',stats)
    print(json.dumps({k:v for k,v in stats.items() if k!='sources'},indent=2))
if __name__=='__main__':main()
