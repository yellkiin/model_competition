"""Optional paper figures from real CSV observations; one figure per plot."""
import argparse
from collections import defaultdict
from pathlib import Path
from .io import csv_read

def main():
    p=argparse.ArgumentParser();p.add_argument('root');a=p.parse_args();root=Path(a.root)
    import matplotlib.pyplot as plt
    out=root/'paper_data/figures';out.mkdir(parents=True,exist_ok=True)
    groups=defaultdict(list)
    for r in csv_read(root/'trajectory.csv'):
        if r['best_makespan']:groups[r['case'],r['q'],r['n']].append(r)
    for (case,q,n),rows in groups.items():
        rows.sort(key=lambda r:float(r['cutoff_seconds']))
        fig,ax=plt.subplots();ax.step([float(r['cutoff_seconds']) for r in rows],
            [float(r['best_makespan']) for r in rows],where='post')
        ax.set(xlabel='Shared graph solve time (seconds)',ylabel='Best paired/validated makespan (cycles)',title=f'{case} Q{q} / {n} cores')
        fig.tight_layout();fig.savefig(out/f'{case}_q{q}_n{n}.svg');plt.close(fig)
    rows=csv_read(root/'paper_data/curves_1_to_5.csv')
    for q in ('1','2','3'):
        rs=[r for r in rows if r['q']==q]
        if not rs:continue
        fig,ax=plt.subplots();ax.plot([int(r['n']) for r in rs],[float(r['arithmetic_mean']) for r in rs],marker='o')
        ax.set(xlabel='NPU cores',ylabel='Mean original single-core speedup',title=f'Question {q}')
        fig.tight_layout();fig.savefig(out/f'question_{q}.svg');plt.close(fig)
if __name__=='__main__':main()
