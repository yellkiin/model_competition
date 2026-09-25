"""Plot observed feasible incumbents; never invent later improvements. Requires matplotlib."""
from pathlib import Path
import argparse,json

def draw_jobs(path,out,case,q,n,title,name,end_to_end=False,horizon=None):
    import matplotlib.pyplot as plt
    rows=[r for r in json.loads(path.read_text(encoding='utf-8-sig')) if str(r['case']).removeprefix('case_').zfill(3)==case and r['q']==q and r['n']==n]
    if not rows:return
    fig,ax=plt.subplots(figsize=(8.2,4.7))
    for method in ('old','published','corrected'):
        rs=[r for r in rows if r['method']==method]
        if not rs:continue
        r=rs[0];events=r.get('observations',[])
        shift=0
        if end_to_end:
            if r.get('seed_solve_seconds') is None:continue
            shift=r.get('seed_solve_seconds',0)+r.get('seed_validation_seconds',0)
        x=[];y=[];best=None
        for e in events:
            if best is None or e['makespan']<best:
                best=e['makespan'];x.append(shift+e['elapsed_seconds']);y.append(best)
        stopped=r.get('solve_seconds',0)<r['seconds']
        label=method+(' [stopped early]' if stopped else '')
        if x:
            # A plateau after early stopping is carry-forward, not continued search.
            stop=shift+min(r.get('solve_seconds',0),r['seconds'])
            ax.step(x+[max(x[-1],stop)],y+[y[-1]],where='post',label=label,marker='x',markevery=[-1])
        else:ax.plot([],[],label=method+' [no feasible incumbent]')
    ax.set_xlabel('Historical seed + validation + added seconds' if end_to_end else 'Observed elapsed seconds')
    ax.set_ylabel('Official makespan (cycles; lower is better)');ax.set_title(title)
    ax.grid(True,alpha=.2);ax.legend(fontsize=8);ax.ticklabel_format(axis='y',style='plain');ax.set_xlim(left=0)
    fig.text(.01,.01,'Crosses mark actual stopping. Later carry-forward values remain in CSV, not invented search.',fontsize=7)
    fig.tight_layout(rect=(0,.04,1,1));out.mkdir(parents=True,exist_ok=True);fig.savefig(out/(name+'.png'),dpi=150);plt.close(fig)


def main():
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,default=Path(__file__).parent/'results');p.add_argument('--out',type=Path)
    a=p.parse_args();root=a.results;out=a.out or root/'recheck_20260925_review/figures';ci=root/'recheck_20260925_run_36085958693'
    for c in ('001','016','024','044','048','059','064'):
        draw_jobs(ci/f'case_{c}/cold30_cap8/all_jobs.json',out,c,2,5,f'Case {c} Q2, n=5 — same-machine cold30 / cap8 (v2b)',f'cold30_q2_n5_{c}',horizon=30)
    for c in ('024','044','059','064'):
        draw_jobs(ci/f'case_{c}/cold300_q2/all_jobs.json',out,c,2,5,f'Case {c} Q2, n=5 — one trajectory, maximum 300s (v2b)',f'cold300_q2_n5_{c}',horizon=300)
    for c in ('016','024'):
        path=ci/f'case_{c}/warm30/all_jobs.json'
        draw_jobs(path,out,c,1 if c=='016' else 2,5,f'Case {c} — same validated seed, additional time (v2b)',f'warm_added_{c}')
        draw_jobs(path,out,c,1 if c=='016' else 2,5,f'Case {c} — end-to-end cost ledger; seed from prior machine',f'warm_end_to_end_{c}',end_to_end=True)
    draw_jobs(root/'recheck_local_v4_300_064/all_jobs.json',out,'064',2,5,'Case 064 Q2 n=5 — v4 vs old/published; maximum 300s','v4_064_q2_long')
    import matplotlib.pyplot as plt
    ratios=[];cases=[]
    for c in ('001','016','024','044','048','059','064'):
        rows=json.loads((ci/f'case_{c}/cold30_cap8/all_jobs.json').read_text())
        r=next(r for r in rows if r['q']==3 and r['n']==5 and r['method']=='published')
        if r.get('no_l2',{}).get('status')=='ok':cases.append(c);ratios.append(r['no_l2']['makespan']/r['makespan'])
    fig,ax=plt.subplots(figsize=(8.2,4.7));ax.bar(cases,ratios);ax.axhline(1,linestyle=':');ax.set_ylim(0,max(ratios)*1.15)
    for i,v in enumerate(ratios):ax.text(i,v,f'{v:.4f}',ha='center',va='bottom')
    ax.set_title('Published policy: Q3 n=5 exact-plan no-L2 / L2 ratio');ax.set_xlabel('Selected real case');ax.set_ylabel('Same-plan cache speedup');fig.tight_layout();fig.savefig(out/'q3_same_plan_cache_ratio.png',dpi=150);plt.close(fig)
    print('Plots saved:',out)

if __name__=='__main__':main()
