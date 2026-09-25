"""Plot actual parent-observed warm trajectories; requires matplotlib only for figures."""
from pathlib import Path
import argparse,json
import matplotlib.pyplot as plt


def curve(observations,deadline,stop):
    points=sorted((o['elapsed_seconds'],o['makespan']) for o in observations
                  if o['elapsed_seconds']<=deadline)
    x=[];y=[];best=float('inf')
    for t,m in points:
        best=min(best,m);x.append(t);y.append(best)
    if x:x.append(max(x[-1],min(stop,deadline)));y.append(best)
    return x,y


def plot(run,case,q,n,out):
    out.mkdir(parents=True,exist_ok=True)
    rows=json.loads((run/'all_jobs.json').read_text(encoding='utf-8-sig'))
    rows=[r for r in rows if (r['case'],r['q'],r['n'])==(case,q,n) and r.get('makespan') is not None]
    if not rows:return
    fig,ax=plt.subplots(figsize=(9,5))
    for r in rows:
        x,y=curve(r['observations'],r['seconds'],r['solve_seconds'])
        label='New structure' if r['method']=='safe' else 'Original ORION'
        ax.step(x,y,where='post',label=f"{label}: {r['makespan']:,}")
    ax.set_title(f'Case {case}, Q{q}, {n} cores — common protected starting plan')
    ax.set_xlabel('Additional seconds per arm');ax.set_ylabel('Best validated makespan (cycles; lower is better)')
    ax.ticklabel_format(axis='y',style='plain');ax.legend();ax.grid(alpha=.2)
    fig.text(.01,.01,'Lines end at actual stopping. Historical seed-pool acquisition cost is not fully known.',fontsize=8)
    fig.tight_layout(rect=(0,.04,1,1));fig.savefig(out/f'{case}_q{q}_n{n}_arms.png',dpi=150);plt.close(fig)
    source=run/'selected'/f'{case}_q{q}_n{n}'/'selection.json'
    if not source.exists():return
    s=json.loads(source.read_text());x,y=curve(s['observations'],s['portfolio_seconds'],s['portfolio_seconds'])
    fig,ax=plt.subplots(figsize=(9,5));ax.step(x,y,where='post')
    ax.set_title(f'Case {case}, Q{q}, {n} cores — costed two-arm portfolio')
    ax.set_xlabel('Additional seconds including both searches and selected no-L2 replays')
    ax.set_ylabel('Best validated makespan (cycles; lower is better)')
    ax.ticklabel_format(axis='y',style='plain');ax.grid(alpha=.2)
    fig.text(.01,.01,'Old good plans remain available. Primary seed verification is recorded separately.',fontsize=8)
    fig.tight_layout(rect=(0,.04,1,1));fig.savefig(out/f'{case}_q{q}_n{n}_portfolio.png',dpi=150);plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--case',required=True);p.add_argument('--q',type=int,default=3);p.add_argument('--n',type=int,default=5);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();plot(a.run.resolve(),f'{int(a.case):03d}',a.q,a.n,a.out.resolve())
if __name__=='__main__':main()
