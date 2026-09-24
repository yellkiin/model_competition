"""Render measured step curves. Matplotlib is optional; solving needs only stdlib."""
from __future__ import annotations
import argparse
import csv
from pathlib import Path


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True)
    parser.add_argument('--case',type=int,required=True)
    parser.add_argument('--q',type=int,required=True)
    parser.add_argument('--n',type=int,required=True)
    parser.add_argument('--mode',choices=['warm_start','cold_start'],default='warm_start')
    parser.add_argument('--clock',choices=['additional','end_to_end'],default='additional')
    parser.add_argument('--horizon',type=float,default=300)
    a=parser.parse_args(argv)
    if a.horizon<=0:parser.error('positive horizon required')
    import matplotlib.pyplot as plt
    root=Path(a.run)
    def table(name):
        with (root/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
    case=f'case_{a.case:03d}'
    choose=lambda r:r['case']==case and int(r['q'])==a.q and int(r['n'])==a.n and r['mode']==a.mode
    raw=[r for r in table('trajectory.csv') if choose(r)]
    per=[r for r in table('per_case.csv') if choose(r)]
    fig,ax=plt.subplots(figsize=(9,5.3))
    for method in ['old','memory']:
        m=next((r for r in per if r['method']==method),None)
        if not m:continue
        seq=sorted((r for r in raw if r['method']==method),key=lambda r:float(r['elapsed_seconds']))
        uncertainty=float(m.get('legacy_clock_uncertainty_seconds') or 0)
        seed=float(m['seed_solve_seconds']) if a.clock=='end_to_end' else 0
        xx=[];yy=[];previous=None
        for r in seq:
            score=int(r['best_makespan'])
            t=float(r['elapsed_seconds'])+seed
            # The frozen v1.3 source clock excludes process startup. Defer by
            # its conservative residual bound, never backfill a final result.
            if r['phase']!='imported_seed_pre_recheck':t+=uncertainty
            if previous==score or t>a.horizon:continue
            xx.append(t);yy.append(score);previous=score
        if not xx:continue
        stop=float(m['added_solve_seconds'])+seed
        if stop>xx[-1] and stop<a.horizon:xx.append(stop);yy.append(yy[-1])
        ax.step(xx,yy,where='post',label=f'{method}; stop={stop:.2f}s')
        ax.scatter([xx[-1]],[yy[-1]],marker='x')
        if stop<a.horizon:
            ax.plot([max(stop,xx[-1]),a.horizon],[yy[-1],yy[-1]],linestyle=':',label=f'{method}: stopped carry-forward')
    ax.set(xlim=(0,a.horizon),xlabel='Additional solver seconds' if a.clock=='additional' else 'Seed acquisition + additional solver seconds',
           ylabel='Best feasible official Makespan (cycles)',
           title=f'{case} | Q{a.q} | {a.n} NPU cores | {a.mode}')
    ax.grid(True,alpha=.3);ax.legend(fontsize=8)
    fig.text(.02,.015,'Completed saved incumbents only. Legacy source clocks shifted conservatively; no search was rerun. Pair cost is separate.',fontsize=8)
    fig.tight_layout(rect=(0,.045,1,1))
    out=root/'curves';out.mkdir(exist_ok=True)
    name=f'{case}_q{a.q}_n{a.n}_{a.mode}_{a.clock}_{int(a.horizon)}s.png'
    fig.savefig(out/name,dpi=180);plt.close(fig)
    print(out/name)
if __name__=='__main__':main()
