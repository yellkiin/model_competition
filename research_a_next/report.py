"""Coverage-aware required outputs, diagnostic directions, portable shard merging."""
from __future__ import annotations
import argparse
import csv
from pathlib import Path
import shutil
import statistics
from .official import write
from research_a.model import read_json

# SOURCE: uploaded 35-page draft, pp11/18/26. Claims, not independently verified results.
DRAFT = {1:[1.,1.7789,2.4477,3.0384,3.5093],
         2:[1.,1.7850,2.4605,3.0644,3.5456],
         3:[1.0086,1.8026,2.4873,3.1044,3.6104]}


def csv_write(path, rows, fields=None):
    fields=fields or sorted({k for row in rows for k in row})
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def _curve(path, title, series):
    from html import escape
    values=[y for _,points in series for _,y in points]
    if not values: return
    maximum=max(1.,max(values))*1.08
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="760" height="440" viewBox="0 0 760 440">',
         '<rect width="760" height="440" fill="white"/>',
         f'<text x="60" y="30" font-size="17">{escape(title)}</text>',
         '<path d="M60 65 V365 H700" fill="none" stroke="black"/>']
    for x in range(1,6):
        px=60+(x-1)*155;svg.append(f'<text x="{px}" y="390">{x}</text>')
    for y in range(int(maximum)+1):
        py=365-280*y/maximum;svg.append(f'<text x="20" y="{py:.1f}">{y}</text>')
    for i,(label,points) in enumerate(series):
        xy=' '.join(f'{60+(x-1)*155:.1f},{365-280*y/maximum:.1f}' for x,y in sorted(points))
        dash=' stroke-dasharray="7 5"' if i else ''
        svg.append(f'<polyline points="{xy}" fill="none" stroke="black" stroke-width="2"{dash}/>')
        svg.append(f'<text x="80" y="{415+i*18}" font-size="12">{escape(label)}</text>')
    svg.append('</svg>');Path(path).write_text('\n'.join(svg),encoding='utf-8')


def collect(root):
    root=Path(root);m=read_json(root/'manifest.json');out=root/'report';out.mkdir(exist_ok=True)
    appendix,comparisons,missing,diagnostics,curve_rows=[],[],[],[],[]
    formal=m['formal_scope'] and m['cases']==[f'case_{i:03d}' for i in range(1,101)] and m['cores']==[1,2,3,4,5]
    for name in m['cases']:
        state_path=root/'cases'/name/'case.json'
        state=read_json(state_path) if state_path.exists() else {}
        by_key={(r['question'],r['cores'],r['variant']):r for r in state.get('rows',[])}
        single=state.get('singlecore',{}).get('makespan')
        if state and not single:
            diagnostics.append(dict(case=name,question=0,cores=1,reason='singlecore_'+state.get('singlecore',{}).get('status','missing'),profile='components'))
        for trial in state.get('rows',[]):
            if trial.get('status') not in ('ok',None):
                diagnostics.append(dict(case=name,question=trial['question'],cores=trial['cores'],reason=trial['status'],profile='components'))
        for q in (1,2,3):
            for n in m['cores']:
                job=root/'cases'/name/f'q{q}'/f'n{n}'
                if n==1 and q in (1,2) and single:
                    appendix.append(dict(**state['singlecore'],case=name,question=q,cores=n,speedup=1.,
                                         source_variant='baseline_by_definition',singlecore=single))
                    continue
                if not (job/'selected.json').exists():
                    missing.append(dict(case=name,question=q,cores=n,reason='no_selected_official_result'));continue
                best=read_json(job/'selected.json')
                row={k:v for k,v in best.items() if isinstance(v,(int,float,str,bool)) or v is None}
                row.update(case=name,question=q,cores=n,singlecore=single,
                           formal_configuration=True,
                           lower_bound=best['certificate']['global_lower'],upper_bound=best['certificate']['feasible_upper'],
                           analytic_upper=best['certificate']['analytic_upper'],ratio_bound=best['certificate']['ratio_bound'])
                appendix.append(row)
                if not single: missing.append(dict(case=name,question=q,cores=n,reason='singlecore_missing'))
                base_rows=[r for (rq,rn,label),r in by_key.items() if rq==q and rn==n and label.startswith(('draft_','supplied_')) and r['status']=='ok']
                baseline=min((r['makespan'] for r in base_rows),default=None)
                for variant in ('fast','refined'):
                    r=by_key.get((q,n,variant),{})
                    comparisons.append(dict(case=name,question=q,cores=n,variant=variant,status=r.get('status','missing'),
                        baseline_makespan=baseline,new_makespan=r.get('makespan'),
                        baseline_over_new=baseline/r['makespan'] if baseline and r.get('status')=='ok' else None,
                        baseline_kind=m['baseline_kind']))
                if best['source_variant'].startswith(('draft_','supplied_')):
                    profile='locality' if best.get('partition_added_copy_bytes',0)>best.get('spill_added_copy_bytes',0) else 'spill'
                    diagnostics.append(dict(case=name,question=q,cores=n,reason='new_candidates_not_better',profile=profile))
                if best.get('overlapping_miss_bytes',0)>0 and q==3:
                    diagnostics.append(dict(case=name,question=q,cores=n,reason='overlapping_cache_misses',profile='cache'))
                if q==3:
                    paired=read_json(job/'same_plan_cache.json') if (job/'same_plan_cache.json').exists() else {}
                    if paired.get('status')!='ok':
                        missing.append(dict(case=name,question=q,cores=n,reason='same_plan_no_L2_missing'))
                    else:
                        off,on=paired['off_metrics'],paired['on_metrics']
                        row.update(no_l2_makespan=paired['off'],cache_ratio=paired['cache_ratio'],
                                   no_l2_extra_ddr_bytes=off.get('extra_ddr_accounted_bytes'),
                                   no_l2_official_added_copy_bytes=off.get('official_added_copy_bytes'),
                                   cache_byte_hit_rate=on.get('cache_byte_hit_rate'),
                                   no_l2_speedup=single/paired['off'] if single else None)
    csv_write(out/'appendix_per_case.csv',appendix)
    csv_write(out/'new_vs_baseline.csv',comparisons)
    csv_write(out/'missing.csv',missing,['case','question','cores','reason'])
    csv_write(out/'diagnosis.csv',diagnostics,['case','question','cores','reason','profile'])
    summary=[]
    for q in (1,2,3):
        for n in m['cores']:
            rows=[r for r in appendix if r['question']==q and r['cores']==n]
            complete=len(rows)==len(m['cases']) and all(r.get('speedup') is not None for r in rows)
            if q==3: complete=complete and all(r.get('cache_ratio') is not None for r in rows)
            mean=statistics.mean(r['speedup'] for r in rows) if complete else None
            summary.append(dict(question=q,cores=n,expected=len(m['cases']),completed=len(rows),complete=complete,
                mean_speedup=mean,worst_speedup=min((r['speedup'] for r in rows),default=None) if complete else None,
                mean_cache_ratio=statistics.mean(r['cache_ratio'] for r in rows) if complete and q==3 else None,
                mean_same_plan_no_l2_speedup=statistics.mean(r['no_l2_speedup'] for r in rows) if complete and q==3 else None,
                draft_reported_mean=DRAFT[q][n-1],
                exceeds_reported_number=(mean>DRAFT[q][n-1]) if formal and complete else None,
                comparison_scope='full100_reported_number_not_independent_paper_reproduction' if formal else 'pilot_only_do_not_compare_to_full100_mean'))
    csv_write(out/'summary.csv',summary)
    complete=not missing and len(appendix)==len(m['cases'])*len(m['cores'])*3
    write(out/'status.json',dict(complete=complete,formal_full100_complete=formal and complete,
          reported_numbers_independently_verified=False,
          local_panels_do_not_establish_full100_improvement=True,
          expected=len(m['cases'])*len(m['cores'])*3,available=len(appendix),missing=len(missing)))
    for q in (1,2,3):
        points=[(r['cores'],r['mean_speedup']) for r in summary if r['question']==q and r['complete']]
        series=[('with L2' if q==3 else f'question {q}',points)]
        if q==3: series.append(('same plan without L2',[(r['cores'],r['mean_same_plan_no_l2_speedup']) for r in summary if r['question']==3 and r['complete']]))
        _curve(out/f'q{q}_curves.svg',('FULL 100' if formal and complete else 'PILOT / INCOMPLETE')+f' - Question {q}',series)
    print(out/'status.json')
    return dict(complete=complete,rows=appendix,summary=summary)


def merge(destination, sources):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    manifests=[read_json(Path(s)/'manifest.json') for s in sources]
    if any(m!=manifests[0] for m in manifests): raise ValueError('Shard manifests differ; never merge different algorithms/budgets/configs')
    if (destination/'manifest.json').exists() and read_json(destination/'manifest.json')!=manifests[0]:
        raise ValueError('Destination belongs to another experiment')
    write(destination/'manifest.json',manifests[0])
    if (Path(sources[0])/'baseline_plans').exists() and not (destination/'baseline_plans').exists():
        shutil.copytree(Path(sources[0])/'baseline_plans',destination/'baseline_plans')
    for source in map(Path,sources):
        for machine in source.glob('machine_*.json'):
            dst=destination/(source.name+'_'+machine.name)
            if not dst.exists(): shutil.copyfile(machine,dst)
        for name in manifests[0]['cases']:
            src=source/'cases'/name
            if not src.exists(): continue
            dst=destination/'cases'/name
            if dst.exists(): raise FileExistsError(f'Overlapping case {name}: resolve duplicate shards explicitly')
            shutil.copytree(src,dst)
    return collect(destination)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--merge',type=Path,nargs='+');a=p.parse_args()
    merge(a.out,a.merge) if a.merge else collect(a.out)

if __name__=='__main__':main()
