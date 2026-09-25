"""Rebuild research tables from actual selected plans/responses and observed prefixes.

Does not execute or invent solver attempts. Previous CI and new local experiments
remain distinct versions, budgets and hosts. Requires their original ZIPs unpacked.
"""
from __future__ import annotations
import csv,json,gzip
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research_a_orion_track_anytime/results/wu_resume_20260925_0900'

def read(p):
    with (gzip.open(p,'rt',encoding='utf-8-sig') if str(p).endswith('.gz') else Path(p).open(encoding='utf-8-sig')) as f:return json.load(f)

def writecsv(p,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with Path(p).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,keys);w.writeheader();w.writerows(rows)

def rel(p):
    try:return str(Path(p).relative_to(ROOT))
    except ValueError:return str(p)

def locate(s,root):
    p=Path(s)
    if p.exists():return p
    parts=p.parts
    # Longest existing suffix under the actual archive root, never basename search.
    for i in range(len(parts)-1):
        candidate=root.joinpath(*parts[i:])
        if candidate.exists():return candidate
    raise FileNotFoundError(s)

def sources():
    for prefix,group in [('wu_primary_','ci_v1.1'),('wu_revision2_','ci_v2'),('wu_revision3_','ci_v3')]:
        for root in sorted((ROOT/'retrieved').glob(prefix+'*')):
            for path in root.glob('*/all_jobs.json'):
                yield group,root,path
    for path in sorted(OUT.glob('*/all_jobs.json')):
        yield 'resume_local',ROOT,path

def main():
    dest=OUT/'review';dest.mkdir(parents=True,exist_ok=True)
    rows=[];prefixes=[];pairs=[];failures=[];registry=[];attempts=[];coverage=[]
    for group,archive,path in sources():
        records=read(path);run=path.parent.name if group=='resume_local' else archive.name
        registry.append(dict(group=group,run=run,path=rel(path),rows=len(records)))
        for r in records:
            uid=group+'/'+run+'/'+r['case']+f"/q{r['q']}/n{r['n']}/"+r['mode']+'/'+r['method']
            row={k:v for k,v in r.items() if not isinstance(v,(list,dict))}
            row.update(evidence_group=group,run_id=run,record_uid=uid,source_records=rel(path),selected_raw_checked=False)
            # A seed's historical selected-path subtotal does not prove full pool acquisition cost.
            row['known_primary_path_seconds']=r.get('known_primary_path_seconds',r.get('total_solve_seconds'))
            if r.get('seed_job'):
                row['total_solve_seconds']=None;row['seed_cost_complete']=False
            if r.get('plan_file') and r.get('result_file'):
                try:
                    plan_path=locate(r['plan_file'],archive);response_path=locate(r['result_file'],archive)
                    plan=read(plan_path);response=read(response_path);raw=response['official_result']
                    ok=response['status']=='ok' and response['audit']['ok'] and raw['makespan']==r['makespan'] and len(plan['core_schedules'])==r['n']
                    if not ok:raise ValueError('Selected response mismatch or failed official audit')
                    row.update(selected_raw_checked=True,verified_plan_file=rel(plan_path),verified_result_file=rel(response_path),selected_hit_rate=raw.get('cache_stats',{}).get('hit_rate'))
                    if r['q']==3 and r.get('pair_result_file'):
                        pair_plan=locate(r['pair_plan_file'],archive);pair_response=locate(r['pair_result_file'],archive);pr=read(pair_response)
                        pair_ok=read(pair_plan)==plan and pr['status']=='ok' and pr['audit']['ok'] and pr['official_result']['makespan']==r['no_l2_makespan']
                        if not pair_ok:raise ValueError('Same-plan no-L2 pair mismatch')
                        pairs.append(dict(record_uid=uid,evidence_group=group,run_id=run,case=r['case'],n=r['n'],mode=r['mode'],method=r['method'],makespan=r['makespan'],no_l2_makespan=r['no_l2_makespan'],ratio=r['no_l2_makespan']/r['makespan'],exact_plan=True,official_valid=True,source_result=rel(response_path),source_pair=rel(pair_response),pair_seconds=r.get('pair_seconds')))
                except Exception as exc:failures.append(dict(record_uid=uid,stage='selected_raw',error=str(exc)))
            if r.get('job'):
                try:
                    progress=locate(str(Path(r['job'])/'progress.json'),archive);state=read(progress)
                    counts=Counter()
                    for a in state.get('attempts',[]):
                        counts[a.get('status')]+=1
                        attempts.append(dict(record_uid=uid,evidence_group=group,run_id=run,case=r['case'],q=r['q'],n=r['n'],mode=r['mode'],method=r['method'],index=a.get('index'),family=a.get('family'),name=a.get('name'),status=a.get('status'),makespan=a.get('makespan'),improved=a.get('improved'),improved_makespan=a.get('improved_makespan'),eval_seconds=a.get('eval_seconds'),generation_seconds=a.get('generation_seconds'),parent_provenance=rel(progress)))
                    row['fifo_evaluations']=sum(a.get('index') is not None and str(a.get('family','')).startswith('anytime/fifo') for a in state.get('attempts',[]))
                    row['fifo_makespan_wins']=sum(bool(a.get('improved_makespan',a.get('improved'))) and str(a.get('family','')).startswith('anytime/fifo') for a in state.get('attempts',[]))
                    row['no_improvement_evaluations']=sum(a.get('status')=='ok' and not a.get('improved_makespan',a.get('improved')) for a in state.get('attempts',[]))
                    row['invalid_or_failed_evaluations']=sum(counts[s] for s in ('error','audit_failed','timeout'))
                    row['generation_error_count']=len(state.get('construction_errors',[]));row['attempt_status_counts']=json.dumps(counts)
                except Exception as exc:failures.append(dict(record_uid=uid,stage='progress',error=str(exc)))
            row['new_work_including_pair_seconds']=r.get('solve_seconds',0)+r.get('pair_seconds',0)
            rows.append(row)
            for t in (30,60,120,300,600):
                obs=[o for o in r.get('observations',[]) if o['elapsed_seconds']<=min(t,r['seconds'])]
                b=min(obs,key=lambda o:(o['makespan'],o.get('added_copy_bytes',0))) if obs else None
                prefixes.append(dict(record_uid=uid,evidence_group=group,run_id=run,case=r['case'],q=r['q'],n=r['n'],mode=r['mode'],method=r['method'],budget_seconds=t,best_makespan=b['makespan'] if b else None,baseline=r.get('baseline'),speedup=r['baseline']/b['makespan'] if b else None,phase='not_started' if r['status']=='not_started' else 'stopped_carry_forward' if t>r['solve_seconds'] else 'observed_prefix',actual_search_seconds=min(t,r['solve_seconds']),seed_cost_complete=not bool(r.get('seed_job')),total_elapsed_seconds=None if r.get('seed_job') else min(t,r['solve_seconds']),source_records=rel(path)))
    ids=[r['record_uid'] for r in rows]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate evidence keys')
    writecsv(dest/'per_case.csv',rows);writecsv(dest/'trajectory.csv',prefixes);writecsv(dest/'cache_pairs.csv',pairs);writecsv(dest/'attempts.csv',attempts)
    writecsv(dest/'source_registry.csv',registry);writecsv(dest/'raw_check_failures.csv',failures)
    # Match only the same version/run/host/question/core/mode. Never pick best across versions.
    comparisons=[]
    for group in sorted(set(r['evidence_group'] for r in rows)):
        bucket=[r for r in rows if r['evidence_group']==group]
        old={(r['run_id'],r['case'],r['q'],r['n'],r['mode']):r for r in bucket if r['method']=='old'}
        for r in bucket:
            key=r['run_id'],r['case'],r['q'],r['n'],r['mode'];o=old.get(key)
            if r['method']=='old' or not o:continue
            comparisons.append(dict(evidence_group=group,run_id=r['run_id'],case=r['case'],q=r['q'],n=r['n'],mode=r['mode'],method=r['method'],old_makespan=o.get('makespan'),new_makespan=r.get('makespan'),reduction_pct=100*(1-r['makespan']/o['makespan']) if o.get('makespan') and r.get('makespan') else None,old_seconds=o['solve_seconds'],new_seconds=r['solve_seconds'],seconds_limit=r['seconds'],old_status=o['status'],new_status=r['status'],old_evaluations=o.get('evaluations_completed_within_budget'),new_evaluations=r.get('evaluations_completed_within_budget')))
    writecsv(dest/'matched_comparisons.csv',comparisons)
    totals={}
    for group in sorted(set(r['evidence_group'] for r in rows)):
        rr=[r for r in rows if r['evidence_group']==group];totals[group]=dict(arms=len(rr),status=dict(Counter(r['status'] for r in rr)),selected_raw_checked=sum(r['selected_raw_checked'] for r in rr),pairs=sum(p['evidence_group']==group for p in pairs))
    errors=[]
    for p in OUT.rglob('ERROR_*.json'):
        errors.append(dict(path=rel(p),**read(p)))
    stats=dict(groups=totals,total_arms=len(rows),raw_failures=len(failures),total_exact_valid_pairs=len(pairs),run_registry_count=len(registry),upfront_preparation_replays=len(read(OUT/'preparation/seed_manifest.json')),historical_full_pool_cost_known=False,full_100_rerun=False,orchestration_errors=errors)
    (dest/'SUMMARY.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2))
    print(json.dumps(stats,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
