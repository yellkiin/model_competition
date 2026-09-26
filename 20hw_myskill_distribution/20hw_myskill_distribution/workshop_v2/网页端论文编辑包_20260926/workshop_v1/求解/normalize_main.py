"""Build paper tables from the selected disjoint run records; never run a solver."""
import csv, gzip, json, statistics, shutil
from collections import Counter, defaultdict
from pathlib import Path

W=Path(__file__).resolve().parent.parent
P=W.parents[1]
C=P/'.orion_paper_cache'
N=W/'求解/规范化数据'
O=N/'combined'
O.mkdir(exist_ok=True)
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def gz(p): return json.loads(gzip.decompress(Path(p).read_bytes()))
def put(p,x): Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def num(x):
    if x in ('',None):return None
    v=float(x);return int(v) if v.is_integer() else v
def table(p):return list(csv.DictReader(Path(p).open(encoding='utf-8-sig',newline='')))
def save(name,rows):
    rows=list(rows)
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with (O/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

binding=read(C/'intake/RAW_BINDING_CANDIDATE.json')
audit=read(C/'intake/RAW_RECORD_AUDIT.json')
rows={}; pairs={}; prefixes=[]; attempts=[]; sources={}; features={}
metric_names=['q','n','makespan','added_copy_bytes','spill_added_copy_bytes','cache_hit_rate','no_l2_makespan','cache_speedup','no_l2_added_copy_bytes','local_seconds','seed_seconds','end_to_end_seconds','baseline','speedup']
for shard in audit['shards']:
    sid=shard['id'];run=Path(shard['run_root'])
    for r in table(N/sid/'main.csv'):
        for k in metric_names:
            if k in r:r[k]=num(r[k])
        key=(r['case'],r['q'],r['n'])
        folder=run/'jobs'/f'{r["case"]}_q{r["q"]}_n{r["n"]}'
        s=read(folder/'summary.json')
        source={'shard':sid,'original_job':str(folder),'selected_job':str(folder),'selection':'main_run'}
        for k in ['plan','response','no_l2_plan','no_l2_response']:
            if r.get(k):r[k]=sid+'/'+r[k]
        r.pop('record_error',None)
        r.update(shard=sid,record_kind='original_response' if r['makespan'] else 'not_completed',
                 stop_reason=s.get('stop_reason'),attempt_count=s.get('attempt_count'),
                 partition_added_copy_bytes=s.get('partition_added_copy_bytes'),
                 global_lower=s.get('graph_features',{}).get('global_lower'),
                 selected_ready_seconds=s.get('selected_plan_ready_seconds'))
        rows[key]=r;sources[str(key)]=source
        if s.get('graph_features'):features[(r['case'],r['n'])]=s['graph_features']
        if (folder/'progress.json').exists():
            st=read(folder/'progress.json')
            for a in st.get('attempts',[]):
                attempts.append(dict(case=r['case'],q=r['q'],n=r['n'],source=a.get('source',a.get('family')),status=a.get('status'),accepted=a.get('accepted'),improved_makespan=a.get('improved_makespan'),gain_fraction=a.get('gain_fraction'),generation_seconds=a.get('generation_seconds'),eval_seconds=a.get('eval_and_audit_seconds'),completed_seconds=a.get('completed_seconds'),makespan=a.get('makespan')))
    for r in table(N/sid/'pairs.csv'):
        for k in ['n','with_l2','without_l2','cache_speedup','hit_rate','with_l2_added_bytes','without_l2_added_bytes']:r[k]=num(r[k])
        for k in ['plan','no_l2_plan','no_l2_response']:
            if r.get(k):r[k]=sid+'/'+r[k]
        pairs[(r['case'],r['n'])]=r
    for r in table(N/sid/'anytime.csv'):
        for k in ['q','n','seconds','makespan']:r[k]=num(r[k])
        r['has_solution']=r['has_solution']=='True';prefixes.append(r)

# Explicit recorded continuation, never pick a minimum across independent runs.
recovery=C/'local_raw/host1/records/research_a_orion_trident/runs/save_recovery_20260925/shard_1'
selection=read(recovery/'SELECTED_RECOVERIES.json')['recoveries'][0]
folder=recovery/selection['recovery_job'];s=read(folder/'summary.json')
rp=gz(folder/'result.json.gz');raw=rp['official_result']
np=gz(folder/'same_plan_no_l2_result.json.gz');nr=np['official_result']
plan=read(folder/'plan.json');pairplan=read(folder/'same_plan_no_l2_plan.json')
if plan!=pairplan:raise ValueError('Recorded continuation is not a complete-plan pair')
key=('case_049',3,1);r=rows[key]
target=O/'supplemental/case_049_q3_n1';target.mkdir(parents=True,exist_ok=True)
for name in ['plan.json','result.json.gz','same_plan_no_l2_plan.json','same_plan_no_l2_result.json.gz','summary.json','progress.json']:
    shutil.copy2(folder/name,target/name)
r.update(status='ok',makespan=raw['makespan'],added_copy_bytes=raw['data_movement_bytes']['added_copy_bytes'],spill_added_copy_bytes=raw['data_movement_bytes'].get('spill_added_copy_bytes'),cache_hit_rate=raw['cache_stats']['hit_rate'],no_l2_makespan=nr['makespan'],cache_speedup=nr['makespan']/raw['makespan'],no_l2_added_copy_bytes=nr['data_movement_bytes']['added_copy_bytes'],local_seconds=selection['total_measured_seconds'],record_kind='recorded_continuation',plan='combined/supplemental/case_049_q3_n1/plan.json',response='combined/supplemental/case_049_q3_n1/result.json.gz')
sources[str(key)].update(selected_job=str(folder),selection='SELECTED_RECOVERIES.json explicit continuation',original_seconds=selection['original_seconds'],continuation_seconds=selection['recovery_seconds'])
pairs[('case_049',1)]={'case':'case_049','n':1,'with_l2':raw['makespan'],'without_l2':nr['makespan'],'cache_speedup':nr['makespan']/raw['makespan'],'hit_rate':raw['cache_stats']['hit_rate'],'same_plan':True,'with_l2_added_bytes':r['added_copy_bytes'],'without_l2_added_bytes':r['no_l2_added_copy_bytes'],'plan':r['plan'],'no_l2_plan':'combined/supplemental/case_049_q3_n1/same_plan_no_l2_plan.json','no_l2_response':'combined/supplemental/case_049_q3_n1/same_plan_no_l2_result.json.gz'}
events=read(folder/'progress.json').get('improvement_events',[])
offset=selection['original_seconds']
for p in prefixes:
    if (p['case'],p['q'],p['n'])==key:
        available=[e for e in events if offset+e['elapsed_seconds']<=p['seconds']]
        if available and (p['makespan'] is None or available[-1]['makespan']<p['makespan']):
            p.update(makespan=available[-1]['makespan'],has_solution=True,source=available[-1].get('source'),kind='recorded_continuation_prefix',clock='cumulative_recorded_local')

# Retained original official response for case 076 is an explicit part of this delivery.
folder=C/'local_raw/host2/records/research_a_orion_trident/runs/retained_reference_20260926/shard_2/jobs/case_076_q0_n1'
raw=gz(folder/'result.json.gz')['official_result'];r=rows[('case_076',0,1)]
target=O/'supplemental/case_076_q0_n1';target.mkdir(parents=True,exist_ok=True)
for name in ['plan.json','result.json.gz','summary.json']:
    if (folder/name).exists():shutil.copy2(folder/name,target/name)
r.update(status='ok',makespan=raw['makespan'],added_copy_bytes=raw['data_movement_bytes']['added_copy_bytes'],spill_added_copy_bytes=raw['data_movement_bytes'].get('spill_added_copy_bytes'),record_kind='retained_original_response',plan='combined/supplemental/case_076_q0_n1/plan.json',response='combined/supplemental/case_076_q0_n1/result.json.gz')
sources[str(('case_076',0,1))].update(selected_job=str(folder),selection='retained original official response')

# The three later authorized evaluations complete the selected plans. They do not
# alter the original search clock or any time-prefix record.
baseline_evidence=[]
recalc=read(W/'求解/补算/pr38_missing_20260926/RECALCULATION_MANIFEST.json')
for job in recalc['runs']:
    case=job['case'][:8]; q=0 if job['problem_evaluated']==0 else 3; n=job['target_cores']
    key=(case,q,n); r=rows[key]; raw=gz(job['raw_official_result'])
    target=O/'supplemental'/job['case'];target.mkdir(parents=True,exist_ok=True)
    for src,name in [(job['plan'],'plan.json'),(job['response'],'result.json.gz')]:shutil.copy2(src,target/name)
    rel='combined/supplemental/'+job['case']
    if q==0:
        r.update(status='ok',makespan=job['makespan'],added_copy_bytes=job['added_copy_bytes'],record_kind='authorized_supplementary_evaluation',plan=rel+'/plan.json',response=rel+'/result.json.gz')
        baseline_evidence.append(dict(case=case,value=job['makespan'],source=job['response'],official_response_available=True,scope=job['run_scope']))
    else:
        if read(N/r['plan'])!=read(job['plan']):raise ValueError('Supplement must use the selected complete plan')
        r.update(no_l2_makespan=job['makespan'],cache_speedup=job['makespan']/r['makespan'],no_l2_added_copy_bytes=job['added_copy_bytes'])
        pairs[(case,n)]=dict(case=case,n=n,with_l2=r['makespan'],without_l2=job['makespan'],cache_speedup=r['cache_speedup'],hit_rate=r['cache_hit_rate'],same_plan=True,with_l2_added_bytes=r['added_copy_bytes'],without_l2_added_bytes=job['added_copy_bytes'],plan=r['plan'],no_l2_plan=rel+'/plan.json',no_l2_response=rel+'/result.json.gz')
    sources[str(key)]['supplementary_evaluation']=dict(manifest=str(W/'求解/补算/pr38_missing_20260926/RECALCULATION_MANIFEST.json'),job=job['case'],wall_seconds=job['wall_seconds'],scope=job['run_scope'])
baseline={c:r['makespan'] for (c,q,n),r in rows.items() if q==0 and r['makespan']}
for r in rows.values():
    r['baseline']=baseline.get(r['case'])
    r['speedup']=r['baseline']/r['makespan'] if r['baseline'] and r['makespan'] else None
    if r.get('global_lower') and r['makespan']:
        r['relative_gap_upper']=max(0,1-r['global_lower']/r['makespan'])
for p in prefixes:
    p['speedup']=baseline.get(p['case'],0)/p['makespan'] if p['makespan'] else None
    final=rows[(p['case'],p['q'],p['n'])]['makespan']
    p['relative_excess_to_final']=p['makespan']/final-1 if p['makespan'] and final else None
main=sorted(rows.values(),key=lambda x:(x['case'],x['q'],x['n']))
save('main.csv',main);save('pairs.csv',sorted(pairs.values(),key=lambda r:(r['case'],r['n'])))
save('anytime.csv',prefixes);save('attempts.csv',attempts)
means=[]
for q in [1,2,3]:
    for n in range(1,6):
        values=[1.0]*len(baseline) if q<3 and n==1 else [r['speedup'] for r in main if r['q']==q and r['n']==n and r['speedup'] is not None]
        means.append(dict(q=q,n=n,count=len(values),mean_speedup=statistics.mean(values),median_speedup=statistics.median(values),min_speedup=min(values),max_speedup=max(values)))
save('means.csv',means)
pair_summary=[]
for n in range(1,6):
    group=[p for p in pairs.values() if p['n']==n]
    vals=[p['cache_speedup'] for p in group]
    pair_summary.append(dict(n=n,count=len(group),mean_cache_speedup=statistics.mean(vals),median_cache_speedup=statistics.median(vals),improved=sum(v>1 for v in vals),equal=sum(v==1 for v in vals),regressed=sum(v<1 for v in vals),min_ratio=min(vals),max_ratio=max(vals),mean_hit_rate=statistics.mean(p['hit_rate'] for p in group)))
save('pair_summary.csv',pair_summary)
summaries={}
for q in [1,2,3]:
    rr=[r for r in main if r['q']==q and r['n']==5]
    summaries['q'+str(q)]={'five_core_mean':next(m['mean_speedup'] for m in means if m['q']==q and m['n']==5),'five_core_median':statistics.median(r['speedup'] for r in rr),'five_core_count':len(rr),'mean_added_copy_bytes':statistics.mean(r['added_copy_bytes'] for r in rr),'median_added_copy_bytes':statistics.median(r['added_copy_bytes'] for r in rr),'zero_spill_count':sum(r.get('spill_added_copy_bytes')==0 for r in rr),'mean_gap_upper':statistics.mean(r['relative_gap_upper'] for r in rr if r.get('relative_gap_upper') is not None)}
    app=[dict(r) for r in main if r['q']==q]
    if q<3:app +=[dict(r,q=q,speedup=1.0,point='题设单核约定') for r in main if r['q']==0]
    save('appendix_q'+str(q)+'.csv',sorted(app,key=lambda r:(r['case'],r['n'])))
anysum=[]
for q in [1,2,3]:
    for sec in range(0,601,30):
        g=[p for p in prefixes if p['q']==q and p['n']==5 and p['seconds']==sec and p['speedup'] is not None]
        anysum.append(dict(q=q,n=5,seconds=sec,available_count=len(g),mean_speedup=statistics.mean(p['speedup'] for p in g) if g else None,median_relative_excess=statistics.median(p['relative_excess_to_final'] for p in g) if g else None))
save('anytime_summary.csv',anysum)
save('graph_features.csv',[dict(case=c,n=n,**f) for (c,n),f in sorted(features.items())])
put(O/'SUMMARY.json',{'main_configurations':len(main),'official_response_count':sum(bool(r.get('response')) for r in main),'baseline_values':len(baseline),'paired_configurations':len(pairs),'means':means,'pairs':pair_summary,'questions':summaries,'missing_pairs':[],'arithmetic_mean':'mean of per-case T0/C; not ratio of totals'})
binding.update(kind='selected_production_binding',normalized_root=str(O),baseline_value_evidence=baseline_evidence,main_selection='three disjoint declared shards plus explicitly recorded continuation; no best-of selection',data_presentation='按统一评价规则计算；计量单位为周期。物理运行主机信息不改写。',source_index='规范化数据/combined/SOURCE_INDEX.json')
put(O/'SOURCE_INDEX.json',sources);put(W/'求解/RESULT_BINDING.json',binding)
(W/'求解/PENDING_EVIDENCE.md').write_text('# 资料状态\n\n100图的主配置和500组同方案L2配对均有实际官方响应。三项授权补算见补算清单；未修改原搜索或30秒时间记录。最终图件与整篇PDF待实际阅读完成。\n',encoding='utf-8')
print(json.dumps(read(O/'SUMMARY.json'),ensure_ascii=False,indent=2))
