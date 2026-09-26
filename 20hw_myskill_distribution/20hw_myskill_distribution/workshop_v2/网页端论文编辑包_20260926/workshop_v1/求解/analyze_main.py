import csv,json,statistics
from pathlib import Path
W=Path(__file__).resolve().parent.parent;D=W/'求解/规范化数据/combined'
def rows(name):return list(csv.DictReader((D/name).open(encoding='utf-8-sig')))
main=rows('main.csv');pairs=rows('pairs.csv');attempts=rows('attempts.csv')
idx={(r['case'],int(r['q']),int(r['n'])):r for r in main}
def f(r,k):return float(r[k]) if r.get(k) else None
out={}
for q in [1,2,3]:
    x=[r for r in main if int(r['q'])==q and int(r['n'])==5]
    speeds=[f(r,'speedup') for r in x]
    out['q'+str(q)]={'superlinear_cases':sum(v>5 for v in speeds),'best':max(x,key=lambda r:f(r,'speedup'))['case'],'worst':min(x,key=lambda r:f(r,'speedup'))['case'],'smallest_speedup':min(speeds),'largest_speedup':max(speeds),'below_two_cases':sum(v<2 for v in speeds),'mean_wall_seconds':statistics.mean(f(r,'local_seconds') for r in x if f(r,'local_seconds') is not None),'median_wall_seconds':statistics.median(f(r,'local_seconds') for r in x if f(r,'local_seconds') is not None),'global_bound_within_1pct':sum(f(r,'relative_gap_upper')<=.01 for r in x if f(r,'relative_gap_upper') is not None),'stops':{s:sum(r['stop_reason']==s for r in x) for s in sorted(set(r['stop_reason'] for r in x))}}
cross=[]
for i in range(1,101):
    c=f'case_{i:03d}';a,b,e=[idx[(c,q,5)] for q in [1,2,3]]
    cross.append({'case':c,'q1_makespan':int(a['makespan']),'q2_makespan':int(b['makespan']),'q3_makespan':int(e['makespan']),'q1_to_q2_ratio':f(a,'makespan')/f(b,'makespan'),'q2_to_q3_ratio':f(b,'makespan')/f(e,'makespan'),'q1_added_bytes':f(a,'added_copy_bytes'),'q2_added_bytes':f(b,'added_copy_bytes'),'q3_added_bytes':f(e,'added_copy_bytes'),'q1_spill_bytes':f(a,'spill_added_copy_bytes'),'q2_spill_bytes':f(b,'spill_added_copy_bytes'),'q3_spill_bytes':f(e,'spill_added_copy_bytes')})
out['cross_question']={'q2_better_q1':sum(x['q1_to_q2_ratio']>1 for x in cross),'q2_equal_q1':sum(x['q1_to_q2_ratio']==1 for x in cross),'q2_worse_q1':sum(x['q1_to_q2_ratio']<1 for x in cross),'mean_q1_over_q2':statistics.mean(x['q1_to_q2_ratio'] for x in cross),'q3_better_q2':sum(x['q2_to_q3_ratio']>1 for x in cross),'q3_equal_q2':sum(x['q2_to_q3_ratio']==1 for x in cross),'q3_worse_q2':sum(x['q2_to_q3_ratio']<1 for x in cross)}
with (D/'cross_question.csv').open('w',encoding='utf-8-sig',newline='') as fp:
    wr=csv.DictWriter(fp,fieldnames=list(cross[0]));wr.writeheader();wr.writerows(cross)
src=[]
for q in [1,2,3]:
    for s in ['seed','b','s','m','f']:
        g=[a for a in attempts if int(a['q'])==q and a['source']==s]
        if not g:continue
        src.append({'q':q,'source':s,'evaluations':len(g),'successful':sum(a['status']=='ok' for a in g),'accepted':sum(a['accepted']=='True' for a in g),'makespan_improvements':sum(a['improved_makespan']=='True' for a in g),'total_generation_seconds':sum(f(a,'generation_seconds') or 0 for a in g),'total_eval_seconds':sum(f(a,'eval_seconds') or 0 for a in g)})
with (D/'source_summary.csv').open('w',encoding='utf-8-sig',newline='') as fp:
    wr=csv.DictWriter(fp,fieldnames=list(src[0]));wr.writeheader();wr.writerows(src)
out['pair_regressions']=[p for p in pairs if f(p,'cache_speedup')<1]
out['largest_cache_gain']=max(pairs,key=lambda p:f(p,'cache_speedup'))
(D/'ANALYSIS.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
