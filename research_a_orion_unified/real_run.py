"""One real official case or a short list; no synthetic graph or test harness."""
from pathlib import Path
import argparse,time
from .io import official_root,write,read
from .pool import run_jobs


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--official');p.add_argument('--out',required=True)
    p.add_argument('--cases',nargs='+',default=['044:1:2','044:3:2'])
    p.add_argument('--seconds',type=float,default=45.)
    p.add_argument('--seed');p.add_argument('--workers',type=int,default=1)
    p.add_argument('--calls',type=int,default=128)
    a=p.parse_args()
    if not 0<a.seconds<=600: p.error('seconds must be in (0,600]')
    root,cfg=official_root(a.official);out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    jobs=[]
    for item in a.cases:
        c,q,n=map(int,item.split(':'));case=f'case_{c:03d}'
        if q not in (0,1,2,3) or n not in range(1,6) or (q==0 and n!=1):p.error('invalid question/core count')
        key=f'{case}_q{q}_n{n}'
        jobs.append(dict(case=case,q=q,n=n,out=str(out/'jobs'/key),official=str(root),config=str(cfg),
            graph=str(root/'data'/f'{case}.json'),components='smf',source_policy='work_adaptive',
            mode='warm' if a.seed else 'cold',seed_plan=str(Path(a.seed).resolve()) if a.seed else None,
            pair_inline=q==3,pair_reserve_seconds=min(60.,a.seconds*.2),
            job_seconds=a.seconds,seconds=a.seconds,max_evaluations=a.calls,keep_all_responses=False))
    rs=run_jobs(jobs,out,time.time()+a.seconds*len(jobs)+30.,a.workers,.25)
    report={'records':rs,'scope':'actual original graph evaluations; not a 100-case campaign',
            'complete':len(rs)==len(jobs) and all(r['status']=='ok' and r.get('optimization_complete',False) and (r['q']!=3 or r.get('pair_status')=='ok') for r in rs)}
    write(out/'RUN_REPORT.json',report)
    print('Actual configurations:',len(rs),'complete:',report['complete'],flush=True)
    return 0 if report['complete'] else 1
if __name__=='__main__':raise SystemExit(main())
