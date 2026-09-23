"""Collect only actually started official radio attempts and their real statuses."""
from pathlib import Path
import json
OUT=Path(__file__).resolve().parent
PREFIX='research_fd/outputs/'
common=['d_experiments','radio','--input',PREFIX+'d_official.json']
old=PREFIX+'official_transport_s7/best_plan.json'
cap=PREFIX+'official_pareto_cpsat/energy_cap_1.json'
configs=[
('official_radio_fixed','run_official.py',old,[],['--mode','fixed','--grid','3','--sample-step','60','--seconds','30','--max-sessions','6000']),
('official_radio_repair_fixed_pool30000','run_official.py',old,[],['--mode','fixed','--grid','3','--sample-step','60','--seconds','30','--max-sessions','30000']),
('official_radio_repair_fixed_untruncated','run_radio_dominance.py',old,[],['--mode','fixed','--grid','3','--sample-step','60','--seconds','60','--max-sessions','1000000']),
('official_radio_repair_retime600','run_radio_dominance.py',old,[],['--mode','retime','--grid','3','--sample-step','60','--shift-window','600','--horizon','10800','--seconds','60','--max-sessions','1000000']),
('official_radio_repair_cpsat_fixed60','run_radio_cpsat_fixed.py',old,[],['--mode','fixed','--grid','3','--sample-step','60','--seconds','60','--max-sessions','1000000']),
('official_radio_repair_cpsat_reduced60','run_radio_cpsat_fixed.py',old,['--site-policy','greedy_double'],['--mode','fixed','--grid','3','--sample-step','60','--seconds','60','--max-sessions','1000000']),
('official_radio_repair_cpsat_retime1200','run_radio_cpsat_retime.py',old,['--site-policy','greedy_double'],['--mode','retime','--grid','3','--sample-step','60','--shift-window','1200','--horizon','10800','--seconds','60','--max-sessions','1000000']),
('official_radio_repair_cpsat_retime2400_soft','run_radio_cpsat_retime.py',cap,['--site-policy','greedy_double','--allow-soft-lateness'],['--mode','retime','--grid','3','--sample-step','60','--shift-window','2400','--horizon','15000','--seconds','90','--max-sessions','1000000']),
('official_radio_repair_witness_coarse','run_radio_cpsat_retime.py',cap,['--site-indices-file',PREFIX+'review/radio_temporal_candidate_pairs.json','--allow-soft-lateness','--transport-step','300','--cover-blocks','--feasibility-first'],['--mode','retime','--grid','3','--sample-step','60','--shift-window','2400','--horizon','15000','--seconds','90','--max-sessions','1000000']),
('official_radio_repair_witness_dense_sessions','run_radio_cpsat_retime.py',cap,['--site-indices-file',PREFIX+'review/radio_temporal_candidate_pairs.json','--allow-soft-lateness','--transport-step','300','--cover-blocks','--feasibility-first','--dense-sessions'],['--mode','retime','--grid','3','--sample-step','60','--shift-window','2400','--horizon','15000','--seconds','90','--max-sessions','1000000'])
]
rows=[]
for label,script,plan,extra,tail in configs:
    log=OUT/'logs'/f'{label}.log'
    if not log.exists():continue
    events=[]
    for line in log.read_text(encoding='utf-8-sig',errors='replace').splitlines():
        try:value=json.loads(line)
        except (ValueError,TypeError):continue
        if isinstance(value,dict):events.append(value)
    folder=OUT/label;result_file=folder/'radio_result.json';timeout_file=folder/'external_timeout.json'
    result=json.loads(result_file.read_text(encoding='utf-8-sig')) if result_file.exists() else None
    external=json.loads(timeout_file.read_text(encoding='utf-8-sig')) if timeout_file.exists() else None
    build=next((e for e in events if e.get('event') in ('retime_cp_model_ready','cpsat_model_ready','dominance_repair_done')),None)
    budget=float(tail[tail.index('--seconds')+1])
    command=['research_fd/.venv/Scripts/python.exe',PREFIX+script,*extra,*common,'--plan',plan,'--out',PREFIX+label,*tail]
    rows.append({'directory':PREFIX+label,'transport_plan':plan,'command':command,'command_text':' '.join(command),
                 'log':PREFIX+'logs/'+label+'.log','phase_budget_s':budget,'model_build_event':build,
                 'result':result,'external_termination':external,'status':external['status'] if external else (result['status'] if result else 'started_result_not_yet_saved'),
                 'interpretation':'Only finite candidates/windows and actually executed solver status; no general infeasibility claim. horizon arguments bound transport return only.',
                 'source_version_note':'Runtime physics is outputs/runtime; helper evolved across attempts. Earlier floating-tolerance dominance and later integer-coefficient dominance are distinguished by result fields and review/radio_solver_review.md.'})
    if script in ('run_radio_dominance.py','run_radio_cpsat_fixed.py'):
        rows[-1]['numerical_dominance_caveat']='Executed early pruning used 1e-9 s interval/return and 1e-12 kWh energy tolerances. It must not be called strict exact-objective preservation, particularly after ceil/round integer conversion.'
    if '--site-indices-file' in extra:
        rows[-1]['site_policy_clarification']='Explicit temporal witness indices override the default site_policy label shown in early result metadata; all 13 selected indices are recorded.'
value={'attempts':rows,'source':'actual log/result files only; no future runs are listed',
       'physical_parameters':'d_official.json unchanged; no radio power or inventory increase',
       'limits':'Solver time limits exclude model construction/presolve overhead; external timeout gives actual wall time. Fixed-zero-soft and optimized-soft runs are distinct restrictions.'}
(OUT/'official_radio_runs.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
md=['# 正式中继实验实际命令台账','',value['source'],'', '|实际目录|阶段预算秒|状态|阶段记录|','|---|---:|---|---|']
for r in rows:
    stages=[] if r['result'] is None else r['result'].get('stages',[])
    md.append(f"|{Path(r['directory']).name}|{r['phase_budget_s']:g}|{r['status']}|"+'; '.join(str(s.get('stage'))+':'+str(s.get('status')) for s in stages)+'|')
md += ['','所有时限、候选集和方法范围以JSON为准。无 incumbent / UNKNOWN 不等于原问题不可行；INFEASIBLE 仅指该有限候选与窗口模型。早期浮点容差删列不声称严格保持原连续目标最优；后续CP-SAT按实际整数系数比较。horizon只约束运输返回，不是联合返回硬上限。','']
for r in rows:
    md += [f"## {Path(r['directory']).name}",'',f"运输输入：`{r['transport_plan']}`",'', '```powershell',r['command_text'],'```','',f"日志：`{r['log']}`。",'']
    if r['external_termination']:md += ['外部终止记录：`'+json.dumps(r['external_termination'],ensure_ascii=False)+'`。','']
(OUT/'official_radio_runs.md').write_text('\n'.join(md),encoding='utf-8')
print(json.dumps({'recorded_actual_attempts':len(rows),'statuses':{Path(r['directory']).name:r['status'] for r in rows}},ensure_ascii=False))
