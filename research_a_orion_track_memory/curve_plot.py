"""Plot saved arithmetic-mean core curves and a real warm trajectory.

Optional matplotlib dependency; no solver, no evaluation, no invented data.
"""
from __future__ import annotations
import argparse,csv
from pathlib import Path


def rows(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True)
    p.add_argument('--case',type=int,default=85);p.add_argument('--question',type=int,default=2);p.add_argument('--cores',type=int,default=5)
    p.add_argument('--out');a=p.parse_args(argv)
    import matplotlib.pyplot as plt
    root=Path(a.run);out=Path(a.out) if a.out else root/'curves';out.mkdir(parents=True,exist_ok=True)
    means=rows(root/'curve_means.csv');cases=rows(root/'per_case.csv');trajectory=rows(root/'trajectory.csv')
    for q in (1,2):
        data=sorted([r for r in means if int(r['q'])==q],key=lambda r:int(r['n']))
        fig,ax=plt.subplots(figsize=(7.5,4.7))
        ax.plot([int(r['n']) for r in data],[float(r['old_mean_speedup']) for r in data],marker='o',label='Published day01 plans')
        ax.plot([int(r['n']) for r in data],[float(r['new_mean_speedup']) for r in data],marker='s',label='Frozen warm repair + incumbent guard')
        ax.set(xlabel='NPU cores',ylabel='Arithmetic mean of T1 / Tn',title=f'Q{q}: seven-graph transfer set; not 100 new runs',xticks=range(1,6))
        ax.grid(True,alpha=.25);ax.legend();fig.tight_layout();fig.savefig(out/f'q{q}_core_curve.png',dpi=170);plt.close(fig)
    data=sorted([r for r in means if r['q']=='3' and r['new_cache_ratio_mean']],key=lambda r:int(r['n']))
    if data:
        fig,ax=plt.subplots(figsize=(7.5,4.7))
        ax.plot([int(r['n']) for r in data],[float(r['old_cache_ratio_mean']) for r in data],marker='o',label='Old plans: same-plan no-L2 / L2')
        ax.plot([int(r['n']) for r in data],[float(r['new_cache_ratio_mean']) for r in data],marker='s',label='Selected plans: same-plan no-L2 / L2')
        ax.set(xlabel='NPU cores',ylabel='Mean same-plan cache speedup',title='Q3: cache ratio is separate from T1 / Tn',xticks=range(1,6))
        ax.grid(True,alpha=.25);ax.legend();fig.tight_layout();fig.savefig(out/'q3_same_plan_cache.png',dpi=170);plt.close(fig)
    label=f'case_{a.case:03d}';ident=lambda r:r['case']==label and int(r['q'])==a.question and int(r['n'])==a.cores
    summary=next(r for r in cases if ident(r));data=sorted([r for r in trajectory if ident(r)],key=lambda r:float(r['elapsed_seconds']))
    for clock in ('additional','end_to_end'):
        field='elapsed_seconds' if clock=='additional' else 'total_elapsed_seconds'
        points=[r for r in data if float(r[field])<=300]
        if not points:continue
        fig,ax=plt.subplots(figsize=(8,4.6));xx=[float(r[field]) for r in points];yy=[float(r['best_makespan']) for r in points]
        stop=float(summary['added_solve_seconds'])+(float(summary['seed_solve_seconds']) if clock=='end_to_end' else 0)
        active_end=min(stop,300.)
        if xx[-1]<active_end:xx.append(active_end);yy.append(yy[-1])
        ax.step(xx,yy,where='post',label='Completed official incumbent')
        if stop<300 and xx[-1]<300:ax.plot([xx[-1],300],[yy[-1],yy[-1]],linestyle='--',label='Stopped; incumbent held (no extrapolation)')
        ax.axhline(float(summary['old_makespan']),linestyle=':',label='Published seed score; not an old solver trajectory')
        ax.set(xlabel=f'{clock.replace("_"," ")} wall seconds',ylabel='Official makespan (cycles)',xlim=(0,300),title=f'{label}, Q{a.question}, {a.cores} cores: one continuous warm run')
        ax.grid(True,alpha=.25);ax.legend(fontsize=8);fig.tight_layout();fig.savefig(out/f'{label}_q{a.question}_n{a.cores}_{clock}.png',dpi=170);plt.close(fig)
    print(out.resolve())


if __name__=='__main__':main()
