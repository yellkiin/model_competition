"""Preserve the officially validated pre-switch incumbent after reinitialization timeout."""
import copy
import shutil
import sys
from pathlib import Path
sys.path.insert(0,r'D:\桌面\model_competition_orion_anytime')
from research_a_orion_anytime.solver import read
from research_a_orion_anytime.worker import atomic_json

root=Path(r'D:\桌面\model_competition_orion_anytime\research_a_orion_anytime\runs\team_day01_shard0_w2\auto')
folder=root/'refinement/case_043_q3_n3'
old=root/'refinement_interrupted/case_043_q3_n3'
summary=read(folder/'summary.json'); before=read(old/'progress.json'); progress=read(folder/'progress.json')
if summary['status']!='deadline_without_incumbent' or progress.get('incumbent'):
    raise ValueError('Expected one completed initialization-timeout segment without an incumbent')
if summary['signature']!=before['identity']:
    raise ValueError('Pre-switch source/input identity mismatch')
meta=before['incumbent']; result=read(old/meta['result_file'])
if result['status']!='ok' or not result['audit']['ok']:
    raise ValueError('Pre-switch result was not officially valid')
atomic_json(folder/'resume_attempt_outcome.json',summary)
atomic_json(folder/'resume_attempt_progress.json',progress)
(folder/'incumbents').mkdir(exist_ok=True)
kept=copy.deepcopy(meta)
for field,name in [('plan_file','carried_switch_plan.json'),('result_file','carried_switch_result.json.gz')]:
    target=folder/'incumbents'/name
    shutil.copy2(old/meta[field],target)
    kept[field]='incumbents/'+name
progress.update(incumbent=kept,status='ok',stopped='resumed_budget_exhausted_retained_pre_switch_incumbent',
    graph_features=before['graph_features'],retained_pre_switch_incumbent=True)
raw=result['official_result']
summary.update(status='ok',makespan=kept['makespan'],plan_hash=kept['plan_hash'],
    plan=str(folder/kept['plan_file']),result=str(folder/kept['result_file']),
    certificate=result['audit']['certificate'],cache_hit_rate=raw.get('cache_stats',{}).get('hit_rate'),
    features=before['graph_features'],stopped=progress['stopped'],
    resume_segment_status='deadline_without_incumbent',retained_pre_switch_incumbent=True,
    **raw['data_movement_bytes'])
atomic_json(folder/'progress.json',progress)
atomic_json(folder/'summary.json',summary)
atomic_json(root/'interrupted_incumbent_retention.json',dict(case=summary['case'],q=3,n=3,
    outcome='Prior officially validated incumbent preserved; failed resumed segment retained separately',
    makespan=summary['makespan'],extra_solver_seconds=0,failed_attempt=str(folder/'resume_attempt_outcome.json')))
print('Retained pre-switch valid incumbent: makespan',summary['makespan'],'; no extra solver work')
