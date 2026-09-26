import json
from pathlib import Path
import statistics as s

d=Path(__file__).parent.parent
rows=json.loads((d/'selected_results.json').read_text(encoding='utf-8'))
summary=json.loads((d/'summary.json').read_text(encoding='utf-8'))
five=[r for r in rows if r['cores']==5]
assert len(rows)==len({(r['case'],r['cores']) for r in rows})==500
assert sum(r['makespan']<r['baseline_makespan'] for r in rows)==353
assert all(r['makespan']<=r['baseline_makespan'] for r in rows)
groups=[]
for n in range(1,6):
    g=[r for r in rows if r['cores']==n]
    data=dict(cores=n,n=len(g),improved=sum(r['makespan']<r['baseline_makespan'] for r in g),
      speedup=s.mean(r['baseline_speedup']*r['baseline_makespan']/r['makespan'] for r in g),
      algorithm_reduction=s.mean(1-r['makespan']/r['baseline_makespan'] for r in g)*100,
      cache_gain=s.mean(r['no_l2_makespan']/r['makespan'] for r in g),
      cache_reduction=s.mean(1-r['makespan']/r['no_l2_makespan'] for r in g)*100,
      cache_fast=sum(r['no_l2_makespan']>r['makespan'] for r in g),
      cache_equal=sum(r['no_l2_makespan']==r['makespan'] for r in g),
      cache_slow=sum(r['no_l2_makespan']<r['makespan'] for r in g))
    assert abs(data['speedup']-summary['cores'][str(n)]['speedup'])<1e-12
    assert abs(data['algorithm_reduction']-summary['cores'][str(n)]['time_reduction_pct'])<1e-10
    assert abs(data['cache_gain']-summary['cores'][str(n)]['cache_gain'])<1e-12
    groups.append(data)
top=sorted(five,key=lambda x:-x['cache_gain'])
delta=sorted(five,key=lambda x:-(x['cache_gain']-x['baseline_cache_gain']))
fields=('case','candidate','baseline_cache_gain','cache_gain','no_l2_makespan','makespan','cache_hit_rate','time_reduction_pct')
result=dict(groups=groups,top_cache=[{k:r[k] for k in fields} for r in top[:15]],
  top_delta=[dict(case=r['case'],delta=r['cache_gain']-r['baseline_cache_gain']) for r in delta[:12]],
  bottom_delta=[dict(case=r['case'],delta=r['cache_gain']-r['baseline_cache_gain']) for r in delta[-10:]],
  median_cache_gain=s.median(r['cache_gain'] for r in five),
  median_cache_reduction=s.median(1-r['makespan']/r['no_l2_makespan'] for r in five)*100,
  exclude_top_cache_mean=s.mean(r['cache_gain'] for r in top[1:]),
  exclude_top2_cache_mean=s.mean(r['cache_gain'] for r in top[2:]),
  top3_excess_contribution=sum(r['cache_gain']-1 for r in top[:3])/sum(r['cache_gain']-1 for r in top),
  top1_excess_contribution=(top[0]['cache_gain']-1)/sum(r['cache_gain']-1 for r in top),
  reductions_over_threshold={str(k):sum((1-r['makespan']/r['no_l2_makespan'])*100>k for r in five) for k in (1,5,10)},
  case083=next(r for r in five if r['case']=='case_083'),
  negative_cache=[r for r in five if r['cache_gain']<1],
  audit_present=(d/'final_audit.json').exists())
print(json.dumps(result,ensure_ascii=False,indent=2))
(Path(__file__).parent/'final_statistics_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
