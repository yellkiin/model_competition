"""Plot actual parent-observed feasible prefixes, one figure per comparison.

No solver invocation, no final score backfill. Requires matplotlib only for plots.
"""
import argparse,json
from collections import defaultdict
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--jobs',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--cases');p.add_argument('--questions',default='1,2,3');p.add_argument('--cores',default='2,3,5');p.add_argument('--title',default='Anytime Wu');p.add_argument('--end-to-end',action='store_true');a=p.parse_args()
    import matplotlib.pyplot as plt
    data=json.loads(a.jobs.read_text(encoding='utf-8-sig'));groups=defaultdict(list)
    allowed=None if not a.cases else {'case_'+f'{int(x):03d}' for x in a.cases.split(',')}
    qs=set(map(int,a.questions.split(',')));ns=set(map(int,a.cores.split(',')))
    for r in data:
        if r['q'] not in qs or r['n'] not in ns or (allowed is not None and r['case'] not in allowed):continue
        groups[r['case'],r['q'],r['n'],r['mode']].append(r)
    a.out.mkdir(parents=True,exist_ok=True)
    for (case,q,n,mode),rows in groups.items():
        fig,ax=plt.subplots(figsize=(9,5));drawn=False
        for r in rows:
            if a.end_to_end and r.get('seed_solve_seconds') is None:continue
            offset=(r.get('seed_solve_seconds') or 0.) if a.end_to_end else 0.
            cap=r['seconds'];stop=min(cap,r.get('solve_seconds',cap));obs=sorted((o for o in r.get('observations',[]) if o['elapsed_seconds']<=cap),key=lambda o:o['elapsed_seconds'])
            if not obs:continue
            xs=[];ys=[];best=float('inf')
            for o in obs:
                best=min(best,o['makespan']);xs.append(offset+o['elapsed_seconds']);ys.append(best)
            if xs[-1]<offset+stop:xs.append(offset+stop);ys.append(best)
            ax.step(xs,ys,where='post',label=r['method']+' / '+r['status']);ax.scatter([offset+stop],[best],marker='x',s=45)
            if stop<cap:ax.plot([offset+stop,offset+cap],[best,best],linestyle=':',linewidth=1)
            drawn=True
        ax.set_title(f'{a.title}: {case}, Q{q}, n={n}, {mode}')
        ax.set_xlabel('Historical seed cost + current elapsed seconds' if a.end_to_end else 'Additional elapsed seconds (parent observed)')
        ax.set_ylabel('Best feasible makespan (cycles; smaller is better)');ax.ticklabel_format(axis='y',style='plain');ax.grid(alpha=.2)
        if drawn:ax.legend(fontsize=8)
        else:ax.text(.5,.5,'No feasible result within budget',ha='center',transform=ax.transAxes)
        note='Crosses mark stops; dotted segments retain an existing plan, not further search.'
        if a.end_to_end:note+=' Seed seconds come from historical machines, not a cold runtime comparison.'
        fig.text(.01,.01,note,fontsize=7);fig.tight_layout(rect=(0,.055,1,1))
        suffix='_end_to_end' if a.end_to_end else '_additional'
        fig.savefig(a.out/f'{case}_q{q}_n{n}_{mode}{suffix}.png',dpi=140);plt.close(fig)
    print('Saved',len(groups),'trajectory figures in',a.out)
if __name__=='__main__':main()
