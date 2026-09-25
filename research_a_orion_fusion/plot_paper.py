"""Optional figures from the exported CSVs; solver itself remains stdlib-only."""
from __future__ import annotations
import argparse
from collections import defaultdict
from pathlib import Path
from statistics import mean
from .io import csv_read,csv_write


def run(data,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    data,out=Path(data),Path(out);out.mkdir(parents=True,exist_ok=True)
    curves=csv_read(data/'mean_speedup_1_to_5_cores.csv')
    def save(name):
        plt.tight_layout();plt.savefig(out/(name+'.svg'));plt.savefig(out/(name+'.png'),dpi=180);plt.close()
    for q in (1,2,3):
        rs=[r for r in curves if int(r['q'])==q and r.get('mean_speedup')]
        if not rs:continue
        plt.figure(figsize=(7,4.5))
        plt.plot([int(r['n']) for r in rs],[float(r['mean_speedup']) for r in rs],marker='o',label='Selected plan')
        if q==3:
            paired=[r for r in rs if r.get('same_plan_no_l2_mean_speedup')]
            if paired:plt.plot([int(r['n']) for r in paired],[float(r['same_plan_no_l2_mean_speedup']) for r in paired],marker='s',label='Same plan, no L2')
        plt.xlabel('NPU cores');plt.ylabel('Mean per-case speedup');plt.xticks(range(1,6))
        plt.title(f'Question {q}; counts per core: '+','.join(r['count'] for r in rs));plt.legend();save(f'q{q}_core_scaling')
    raw=csv_read(data/'per_case_all_metrics.csv');baseline={r['case']:float(r['reference']) for r in raw if r.get('reference')}
    for q in (1,2,3):
        rs=[r for r in raw if r['q']==str(q) and r['n']=='5' and r.get('speedup')]
        if not rs:continue
        vals=sorted(float(r['speedup']) for r in rs)
        plt.figure(figsize=(7,4.5));plt.step(vals,[(i+1)/len(vals) for i in range(len(vals))],where='post')
        plt.xlabel('Five-core speedup');plt.ylabel('Fraction of cases');plt.title(f'Question {q}; {len(vals)} cases');save(f'q{q}_speedup_ecdf')
    rs=[r for r in raw if r['q']=='3' and r['n']=='5' and r.get('same_plan_cache_speedup') and r.get('cache_hit_rate')]
    if rs:
        plt.figure(figsize=(7,4.5));plt.scatter([float(r['cache_hit_rate']) for r in rs],[float(r['same_plan_cache_speedup']) for r in rs])
        plt.xlabel('Official byte hit rate');plt.ylabel('Same-plan no-L2 / L2 makespan');plt.title(f'{len(rs)} paired five-core cases');save('cache_hit_vs_benefit')
    grouped=defaultdict(list)
    for r in csv_read(data/'anytime_30_seconds.csv'):
        if r['time_axis']=='local_total' and r['n']=='5' and r.get('best_makespan') and r['case'] in baseline and float(r['best_makespan'])>0:
            grouped[int(r['q']),int(r['cutoff_seconds'])].append(baseline[r['case']]/float(r['best_makespan']))
    summary=[{'q':q,'seconds':t,'available_cases':len(v),'mean_best_speedup':mean(v)} for (q,t),v in sorted(grouped.items())]
    csv_write(data/'anytime_available_case_means.csv',summary)
    for q in (1,2,3):
        rs=[r for r in summary if r['q']==q]
        if not rs:continue
        plt.figure(figsize=(7,4.5));plt.step([r['seconds'] for r in rs],[r['mean_best_speedup'] for r in rs],where='post')
        plt.xlabel('Local elapsed seconds, including replay');plt.ylabel('Mean best speedup among available cases')
        plt.title(f'Q{q}; available count {min(r["available_cases"] for r in rs)}–{max(r["available_cases"] for r in rs)}; stopped outputs held')
        save(f'q{q}_anytime')
    return str(out)


def main():
    p=argparse.ArgumentParser();p.add_argument('--data',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    print(run(a.data,a.out))
if __name__=='__main__':main()
