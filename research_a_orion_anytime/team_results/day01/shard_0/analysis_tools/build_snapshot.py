"""Read-only result publication; never launches a solver or edits the active run."""
import argparse
import csv
import json
import shutil
import statistics as st
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r'D:\桌面\model_competition_orion_anytime')
BASE = Path(r'D:\桌面\model_competition\research_a_orion_anytime')
SOURCE = REPO/'research_a_orion_anytime/runs/team_day01_shard0_w4/auto'
sys.path.insert(0, str(REPO))
from research_a_orion_anytime.transfer import rewrite
from research_a_orion_anytime.reporting import collect

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def put(p,d):
    Path(p).parent.mkdir(parents=True,exist_ok=True)
    Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8')

def utc():return datetime.now(timezone.utc).isoformat()
def key(s):return (s['case'],s['q'],s['n'])
def seconds(s):return s.get('total_job_seconds',s.get('process_seconds',0))
def table_csv(path,columns,rows):
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,columns,extrasaction='ignore');w.writeheader();w.writerows(rows)

def stage_rows(root,name):
    answer={}
    for p in sorted((root/name).glob('*/summary.json')):
        s=read(p); k=key(s)
        if k in answer:raise ValueError(f'Duplicate {name} key: {k}')
        answer[k]=s
    return answer

def freeze(stage):
    snap=SOURCE.parent/'snapshots'/stage/'auto'
    dest=BASE/'phase_publication_20260924/artifacts/shard_0'/stage
    if snap.exists() or dest.exists():raise ValueError('Immutable publication root already exists')
    policy=read(SOURCE/'refinement_policy.json')
    if len(stage_rows(SOURCE,'refinement'))!=policy['jobs']:raise ValueError('Refinement not terminal')
    if not (SOURCE/'refinement_complete.json').exists():raise ValueError('Refinement not merged')
    if not list((SOURCE/'pairs').glob('*/request.json')) and not (SOURCE/'final_index.json').exists():
        raise ValueError('No proof of phase transition')
    if stage=='final':
        if read(SOURCE/'continuation_status.json').get('status')!='complete':raise ValueError('Final not ready')
        if read(SOURCE.parent/'team_status.json').get('status')=='running':raise ValueError('Supervisor not finished')
    start=utc();snap.mkdir(parents=True);dest.mkdir(parents=True)
    if stage=='final':
        shutil.copytree(SOURCE,snap,dirs_exist_ok=True,ignore=shutil.ignore_patterns('*.tmp'))
    else:
        for name in ['coverage','coverage_retry','refinement','refinement_interrupted']:
            if (SOURCE/name).exists():shutil.copytree(SOURCE/name,snap/name,ignore=shutil.ignore_patterns('*.tmp'))
        for p in SOURCE.glob('*.json'):
            if p.name.startswith(('campaign','capacity_','continuation_','refinement_','interrupted_','phase_index')):
                shutil.copy2(p,snap/p.name)
    for f in snap.rglob('*.json'):
        if f.name.endswith('_plan.json') or f.name=='current_plan.json':continue
        val=read(f);changed=rewrite(val,str(SOURCE),snap.as_posix())
        if changed!=val:put(f,changed)
    idxname='final_index.json' if stage=='final' else 'phase_index.json'
    idx=read(snap/idxname)
    idx['policy'].update(iteration_id='day01',stage=stage,partial_pairs=stage!='final')
    if stage!='final':idx['pairs']=[]
    put(snap/idxname,idx)
    for name in ['team_status.json','research_day_clock.json','launcher_stdout.txt','launcher_stderr.txt']:
        shutil.copy2(SOURCE.parent/name,dest/name)
    trace=dest/'execution_provenance';trace.mkdir()
    shutil.copytree(BASE/'continuation_20260924',trace/'continuation_20260924',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for dirname in ['team_day01_shard0','team_day01_shard0_w2','team_day01_shard0_w4']:
        origin=SOURCE.parent.parent/dirname
        target=trace/dirname;target.mkdir()
        for name in ['worker_switch.json','team_status.json','research_day_clock.json','launcher_stdout.txt','launcher_stderr.txt','supervisor_stderr.txt']:
            if (origin/name).exists():shutil.copy2(origin/name,target/name)
        for p in (origin/'auto').glob('continuation_*.json'):
            shutil.copy2(p,target/p.name)
    shutil.copytree(trace,snap/'execution_provenance')
    put(dest/'snapshot_manifest.json',dict(stage=stage,snapshot_started_at_utc=start,snapshot_finished_at_utc=utc(),
        source_run_root=str(SOURCE),snapshot_root=str(snap),source_revision='93ae122',
        note='Output-only relocation; all underlying algorithm/config/plan identity values are preserved, not recomputed.'))
    print('FROZEN',snap,flush=True)
    return snap,dest

def analyze(stage):
    snap=SOURCE.parent/'snapshots'/stage/'auto'
    dest=BASE/'phase_publication_20260924/artifacts/shard_0'/stage
    manifest=read(dest/'snapshot_manifest.json')
    phases={x:stage_rows(snap,x) for x in ['coverage','coverage_retry','refinement','pairs']}
    cov=dict(phases['coverage'])
    cov.update({k:v for k,v in phases['coverage_retry'].items() if v['status']=='ok'})
    expected={(f'case_{i:03d}',q,n) for i in range(1,101,2) for q,n in [(0,1),(3,1)]+[(q,n) for q in [1,2,3] for n in [2,3,4,5]]}
    if set(cov)!=expected or any(v['status']!='ok' for v in cov.values()):raise ValueError('Coverage incomplete')
    selected=dict(cov)
    for k,v in phases['refinement'].items():
        if v['status']=='ok':
            if (v['makespan'],v['added_copy_bytes'])>(cov[k]['makespan'],cov[k]['added_copy_bytes']):raise ValueError(f'Regression {k}')
            selected[k]=v
    idx=read(snap/('final_index.json' if stage=='final' else 'phase_index.json'))
    if len(idx['chosen'])!=700 or len({tuple(x['key']) for x in idx['chosen']})!=700:raise ValueError('Index conflict')
    if {tuple(x) for x in idx['expected']}!=expected:raise ValueError('Expected mismatch')
    for x in idx['chosen']:
        s=read(x['summary']); k=tuple(x['key'])
        if key(s)!=k or s!=selected[k]:raise ValueError(f'Selection mismatch: {k}')
        for field in ['job','plan','result']:
            p=Path(s[field])
            if not p.is_relative_to(snap) or not p.exists():raise ValueError(f'Unrelocated or missing {field}: {k}')
    if stage=='final':
        # Use the original process's completed official verification, not another verification run.
        for f in (snap/'final_report').iterdir():
            if f.is_file():shutil.copy2(f,dest/f.name)
        report=read(dest/'report.json')
        checks=read(dest/'verification.json')
        if len(checks)!=700 or not all(x['ok'] for x in checks):raise ValueError('Final verification incomplete')
    else:
        report=collect(snap/'phase_index.json',snap/'phase_report',verify=False,require_complete=False)
        for f in (snap/'phase_report').iterdir():
            if f.is_file() and f.name!='verification.json':shutil.copy2(f,dest/f.name)
    with (dest/'per_case.csv').open(encoding='utf-8-sig',newline='') as f:csvrows=list(csv.DictReader(f))
    rows=[]
    for r in csvrows:
        row={k:(None if v=='' else v) for k,v in r.items()}
        for field in row:
            if field not in ['case','status','pair_status'] and row[field] is not None:row[field]=float(row[field])
        row['q']=int(row['q']);row['n']=int(row['n']);rows.append(row)
    improved=[]
    for k,s in sorted(selected.items()):
        c=cov[k];r=phases['refinement'].get(k)
        improved.append(dict(case=k[0],q=k[1],n=k[2],coverage_status=c['status'],coverage_makespan=c['makespan'],
          selected_status=s['status'],selected_makespan=s['makespan'],coverage_over_selected=c['makespan']/s['makespan'],
          relative_makespan_reduction=1-s['makespan']/c['makespan'],coverage_added_copy_bytes=c['added_copy_bytes'],selected_added_copy_bytes=s['added_copy_bytes'],
          refinement_ran=r is not None,refinement_status=r['status'] if r else 'not_planned',refinement_hard_timeout=r.get('hard_timeout') if r else None,
          coverage_solve_seconds=seconds(c),refinement_solve_seconds=seconds(r) if r else 0,
          end_to_end_solve_seconds=seconds(c)+(seconds(r) if r else 0)))
    table_csv(dest/'improvements.csv','case,q,n,coverage_status,coverage_makespan,selected_status,selected_makespan,coverage_over_selected,relative_makespan_reduction,coverage_added_copy_bytes,selected_added_copy_bytes,refinement_ran,refinement_status,refinement_hard_timeout,coverage_solve_seconds,refinement_solve_seconds,end_to_end_solve_seconds'.split(','),improved)
    tails=[];groups={}
    for q in [1,2,3]:
        rs=sorted([r for r in rows if r['q']==q and r['n']==5],key=lambda r:(r['speedup'],r['case']))
        values=[r['speedup'] for r in rs];med=st.median(values);pos=(len(values)-1)*.1;lo=int(pos);p10=values[lo]+(values[lo+1]-values[lo])*(pos-lo)
        for rank,r in enumerate(rs,1):
            s=selected[(r['case'],q,5)];cert=s.get('certificate') or {};features=s.get('features') or {}
            tail={**r,**features,**{k:cert.get(k) for k in ['compute_path','compute_load','compulsory_ddr','global_lower']},
                  'rank_ascending':rank,'median_speedup':med,'mean_gap_contribution_vs_median':(med-r['speedup'])/len(values)}
            tails.append(tail)
        groups[q]=dict(mean=st.mean(values),median=med,p10=p10,worst=values[0],worst_case=rs[0]['case'],below1=sum(v<1 for v in values),missing=50-len(values),
                       other45_mean=st.mean(values[5:]),bottom5=rs[:5],top5=rs[-5:],bottom5_gap_contribution=sum((med-v)/50 for v in values[:5]),
                       mean_without_bottom5_increase=st.mean(values[5:])-st.mean(values))
    table_csv(dest/'lower_tail.csv','q,n,case,rank_ascending,speedup,makespan,baseline,median_speedup,mean_gap_contribution_vs_median,added_copy_bytes,partition_added_copy_bytes,spill_added_copy_bytes,cache_hit_rate,ops,components,max_component,compute_path,compute_load,compulsory_ddr,global_lower,ratio_upper'.split(','),tails)
    prefix=[];prefix_groups={}
    for ph in ['coverage','coverage_retry','refinement']:
        for k,s in sorted(phases[ph].items()):
            p=read(Path(s['job'])/'progress.json')
            # The existing verified coverage incumbent is available at t=0 for the logical refinement stage.
            # Its earlier solve cost is reported separately and is never credited as free end-to-end work.
            seed=cov[k]['makespan'] if ph=='refinement' else None
            choices=[('evaluations',v) for v in [3,8,16,24]]+[('seconds',v) for v in [5,10,20,30]]
            if seed is not None:choices=[('seed_at_zero',0)]+choices
            for kind,cut in choices:
                best=seed
                if kind!='seed_at_zero':
                    vals=[a['makespan'] for a in p.get('attempts',[]) if a.get('status')=='ok' and a.get('index' if kind=='evaluations' else 'completed_seconds',float('inf'))<=cut]
                    if vals:best=min(vals+([seed] if seed is not None else []))
                prefix.append(dict(case=k[0],q=k[1],n=k[2],stage=ph,cutoff_kind=kind,cutoff_value=cut,best_makespan=best,has_valid_incumbent=best is not None))
    table_csv(dest/'budget_prefixes.csv','case,q,n,stage,cutoff_kind,cutoff_value,best_makespan,has_valid_incumbent'.split(','),prefix)
    for cut in [5,10,20,30]:
        rs=[r for r in prefix if r['stage']=='refinement' and r['cutoff_kind']=='seconds' and r['cutoff_value']==cut]
        prefix_groups[cut]=dict(count=len(rs),strictly_improved=sum(r['best_makespan']<cov[(r['case'],r['q'],r['n'])]['makespan'] for r in rs),
            mean_coverage_over_prefix=st.mean(cov[(r['case'],r['q'],r['n'])]['makespan']/r['best_makespan'] for r in rs))
    costs={}
    for ph,data in phases.items():
        costs[ph]=dict(completed=len(data),ok=sum(s['status']=='ok' for s in data.values()),failed=sum(s['status']!='ok' for s in data.values()),
            job_seconds=sum(seconds(s) for s in data.values()),process_seconds=sum(s.get('process_seconds',0) for s in data.values()),
            failed_job_seconds=sum(seconds(s) for s in data.values() if s['status']!='ok'),
            timeout_valid=sum(s.get('hard_timeout',False) and s['status']=='ok' for s in data.values()),
            timeout_without_valid=sum(s.get('hard_timeout',False) and s['status']!='ok' for s in data.values()))
    mainimp=[r for r in improved if r['q']>0]
    changed=[r for r in mainimp if r['coverage_makespan']>r['selected_makespan']]
    no_improve=[r for r in mainimp if r['refinement_ran'] and r['coverage_makespan']==r['selected_makespan']]
    metrics=dict(stage=stage,groups=groups,report_groups=report['groups'],costs=costs,refinement_prefixes=prefix_groups,
         improved_count=len(changed),ties_count=sum(r['coverage_makespan']==r['selected_makespan'] for r in mainimp),
         copy_only_improvements=sum(r['coverage_makespan']==r['selected_makespan'] and r['coverage_added_copy_bytes']>r['selected_added_copy_bytes'] for r in mainimp),
         no_makespan_gain_refinement_count=len(no_improve),no_makespan_gain_refinement_seconds=sum(r['refinement_solve_seconds'] for r in no_improve),
         best_improvements=sorted(changed,key=lambda r:r['coverage_over_selected'],reverse=True)[:12],
         coverage_means={f'q{q}_n{n}':st.mean(cov[(c,0,1)]['makespan']/s['makespan'] for (c,qq,nn),s in cov.items() if qq==q and nn==n) for q in [1,2,3] for n in [2,3,4,5]},
         selected_memory_bytes={f'q{q}_n5':dict(scheduled_ddr_sum=sum(s['scheduled_copy_bytes'] for (c,qq,n),s in selected.items() if qq==q and n==5),
             added_ddr_sum=sum(s['added_copy_bytes'] for (c,qq,n),s in selected.items() if qq==q and n==5),
             partition_added_sum=sum(s['partition_added_copy_bytes'] for (c,qq,n),s in selected.items() if qq==q and n==5),
             spill_added_sum=sum(s['spill_added_copy_bytes'] for (c,qq,n),s in selected.items() if qq==q and n==5)) for q in [1,2,3]},
         features_and_certificates={f'{c}_q{q}_n{n}':{k:s.get(k) for k in ['makespan','features','certificate','cache_hit_rate','scheduled_copy_bytes','added_copy_bytes','partition_added_copy_bytes','spill_added_copy_bytes','evaluations']} for (c,q,n),s in selected.items() if n==5})
    if stage=='final':
        prs=[r for r in rows if r['q']==3]
        metrics['cache']=dict(count=len(prs),mean_ratio=st.mean(r['cache_speedup'] for r in prs),median_ratio=st.median(r['cache_speedup'] for r in prs),
            less_than_1=[r for r in prs if r['cache_speedup']<1],least=sorted(prs,key=lambda r:r['cache_speedup'])[:10],
            top=sorted(prs,key=lambda r:r['cache_speedup'],reverse=True)[:10],mean_hit_rate=st.mean(r['cache_hit_rate'] for r in prs),
            n5_mean_hit_rate=st.mean(r['cache_hit_rate'] for r in prs if r['n']==5))
    put(dest/'analysis_metrics.json',metrics)
    status={**manifest,'schema_version':1,'iteration_id':'day01','shards':2,'shard_index':0,
       'algorithm_changed_since_pilot':False,'workers':4,'worker_sequence':[1,2,4],
       'team_deadline_utc':'2026-09-24T17:43:48.3137853+00:00','main_deadline_utc':'2026-09-24T16:43:48.3137853+00:00',
       'expected_main':700,'valid_main':report['valid'],'expected_pairs':250,'valid_pairs':costs['pairs']['ok'],
       'fully_covered_graphs':50,'refinement_planned':620,'refinement_completed':620,'refinement_failed':1,
       'historical_failure_count':5,'historical_failure_detail':{'coverage_recovered':3,'resume_subsegment_retained_prior_incumbent':1,'refinement_fallback_to_coverage':1},
       'unresolved_main_keys':[],'hard_timeout_with_valid_count':sum(c['timeout_valid'] for c in costs.values()),
       'hard_timeout_without_valid_count':sum(c['timeout_without_valid'] for c in costs.values()),
       'timeout_count_scope':'Logical stage summaries; the retained failed resume subsegment is recorded separately, not counted twice.',
       'phase_complete':True,'shard_complete':stage=='final' and not report['failures_or_missing'] and report['independent_checks']==700,
       'formal_complete':report['formal_complete'],'final_verification_complete':stage=='final' and report['independent_checks']==700,
       'cache_comparison_status':'complete' if stage=='final' else 'pending','original_stdout_name':'launcher_stdout.txt','original_stderr_name':'launcher_stderr.txt'}
    put(dest/'PHASE_STATUS.json',status)
    print(json.dumps({'status':status,'groups':groups,'improved_count':len(changed),'costs':costs,'prefixes':prefix_groups,'best_improvements':metrics['best_improvements'][:3]},ensure_ascii=True),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','analyze']);p.add_argument('stage',choices=['refinement_complete','final']);a=p.parse_args()
    if a.command=='freeze':freeze(a.stage)
    else:analyze(a.stage)
