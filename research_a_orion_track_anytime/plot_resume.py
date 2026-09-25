"""Draw only observed feasible incumbents, with explicit stopped carry-forward.

Figures use Matplotlib defaults. No final value is backfilled into early prefixes.
"""
from pathlib import Path
import argparse,json

def draw(records,output,title,horizon):
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(9,5))
    plotted=0
    for label,r in records:
        if r.get('makespan') is None:continue
        xs=[];ys=[];best=float('inf')
        for o in sorted(r.get('observations',[]),key=lambda o:o['elapsed_seconds']):
            if o['elapsed_seconds']>r['seconds']:continue
            if o['makespan']<best:
                best=o['makespan'];xs.append(o['elapsed_seconds']);ys.append(best)
        if not xs:continue
        stop=min(r['solve_seconds'],r['seconds']);xs.append(max(xs[-1],stop));ys.append(best)
        ax.step(xs,ys,where='post',label=label)
        ax.plot([xs[-1]],[ys[-1]],marker='x',linestyle='none')
        if stop<horizon:ax.plot([stop,horizon],[best,best],linestyle=':',linewidth=.8)
        plotted+=1
    if plotted:
        ax.set_title(title);ax.set_xlabel('Observed search seconds (pairing costs recorded separately)')
        ax.set_ylabel('Best validated makespan, cycles (lower is better)');ax.set_xlim(0,horizon)
        ax.ticklabel_format(axis='y',style='plain');ax.legend(fontsize=8);ax.grid(alpha=.2)
        fig.text(.01,.01,'Cross = actual stop; dots = held incumbent, not further search. Warm full historical cost remains unknown.',fontsize=7)
        fig.tight_layout(rect=(0,.04,1,1));output.parent.mkdir(parents=True,exist_ok=True);fig.savefig(output,dpi=150)
    plt.close(fig)
    return plotted>0

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--out',type=Path)
    a=p.parse_args();root=a.root;round=root/'research_a_orion_track_anytime/results/wu_resume_20260925_0900';out=a.out or round/'review/figures';made=0
    load=lambda path:json.loads(path.read_text())
    for case in ('001','024','044','059','083','084','086'):
        path=root/f'retrieved/wu_primary_{case}/paired30/all_jobs.json'
        if not path.exists():continue
        rr=load(path)
        for mode in ('cold_start','warm_start'):
            rows=[(r['method']+' (v1.1)',r) for r in rr if r['q']==3 and r['n']==5 and r['mode']==mode]
            made+=draw(rows,out/f'v1_{case}_{mode}.png',f'Case {case}, Q3 n=5, v1.1 {mode}, cap16',30)
    for case in ('044','083','084'):
        path=root/f'retrieved/wu_revision3_{case}/comparison/all_jobs.json'
        if path.exists():made+=draw([(r['method']+' (v3)',r) for r in load(path)],out/f'v3_{case}_cold.png',f'Case {case}, Q3 n=5, v3 cold start, cap16',30)
    for case in ('024','044','083','086'):
        path=round/('ablation_missing_086' if case=='086' else 'ablation_v3')/'all_jobs.json'
        if path.exists():made+=draw([(r['method'],r) for r in load(path) if r['case']=='case_'+case],out/f'ablation_{case}.png',f'Case {case}, Q3 n=5, warm 4-way ablation, cap32',60)
    path=round/'extended_024_086/all_jobs.json'
    if path.exists():
        for case in ('024','086'):made+=draw([(r['method'],r) for r in load(path) if r['case']=='case_'+case],out/f'extended_{case}.png',f'Case {case}, Q3 n=5, one warm trajectory, cap128',300)
    for case in ('024','044','059','084','086'):
        rr=[]
        for rev in ('v3','v4-select'):
            path=round/f'guard_{case}_{rev}/all_jobs.json'
            if path.exists():rr.extend((rev,r) for r in load(path))
        made+=draw(rr,out/f'guard_{case}.png',f'Case {case}, Q3 n=5, negative-evidence guard, cap32',60)
    print(f'{made} observed-trajectory figures saved: {out}')
if __name__=='__main__':main()
