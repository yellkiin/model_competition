"""Record unavailable Q3/Q4 outputs only after all actual attempts have ended.

Never compute Q4 on a communication-failing transportation-only plan.
"""
from pathlib import Path
import json
OUT=Path(__file__).resolve().parent
ledger=json.loads((OUT/'official_radio_runs.json').read_text(encoding='utf-8'))
attempts=ledger['attempts']
if not attempts or any(r['status']=='started_result_not_yet_saved' for r in attempts):
    raise RuntimeError('An experiment is still running or lacks its completion record')
if any(r['result'] is not None and r['result'].get('status')=='feasible' for r in attempts):
    raise RuntimeError('A feasible candidate exists; evaluate and export it instead')
if any((OUT/Path(r['directory']).name/'joint_plan.json').exists() for r in attempts):
    raise RuntimeError('A joint plan exists and must be reviewed instead of a failure placeholder')
status='not_computed_no_feasible_joint_plan'
reason=('No attempted official finite candidate/window model returned a joint incumbent. '
        'Time limits, candidate restrictions and external termination do not prove the original continuous problem infeasible.')
joint={'status':status,'selected_joint_plan':None,'input':'research_fd/outputs/d_official.json',
       'actual_attempts':len(attempts),'ledger':'research_fd/outputs/official_radio_runs.json',
       'reason':reason,'relay_sessions':None,'joint_makespan_s':None,'joint_energy_kwh':None,
       'joint_radio_precision_results':None,'transport_baseline_precision':'research_fd/outputs/official_radio_baseline_no_relay_precision/summary.json',
       'scope':'The precision file is a no-relay transportation negative control, not a feasible joint plan.'}
folder=OUT/'official_joint_final';folder.mkdir(exist_ok=True)
(folder/'status.json').write_text(json.dumps(joint,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(folder/'README.md').write_text('# 正式联合计划当前未取得\n\n'
    f'已执行 {len(attempts)} 次有限候选模型/修复试验，均未返回可供验证的正式联合方案。全部命令、候选规模、阶段状态和外部终止见 `../official_radio_runs.json` 与 `../official_radio_runs.md`。\n\n'
    '这不证明原问题不可行。未生成虚构的中继任务、联合能耗/工期或联合通信通过记录。正式运输方案和不加中继的九精度负对照由对应目录保存，不能据此计算问题四。\n\n'
    '两组/三组、严格/复制四种分区输出均以 `not_computed_no_feasible_joint_plan` 明示未计算，资源数量为 null。\n',encoding='utf-8')
for k in (2,3):
    for policy in ('strict','duplicate'):
        result={'status':status,'groups':k,'policy':policy,'feasible':None,'joint_plan':None,
                'resources':None,'resource_gaps':None,'partition':None,'reason':reason,
                'required_dependency':'official_joint_final: a complete physical and radio-feasible Q3 plan',
                'not_used':'Synthetic group counts and communication-failing transportation-only plans were not substituted.'}
        (OUT/f'official_partition_{k}_{policy}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':status,'actual_attempts':len(attempts),'partition_status_files':4},ensure_ascii=False))
