"""Assemble final executed evidence only after the radio stage has closed."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent

def read(path):
    return json.loads((OUT / path).read_text(encoding='utf-8-sig'))

joint = read('official_joint_final/status.json')
plan = read('official_pareto_cpsat/energy_cap_1.json')
validation = read('official_pareto_cpsat/export_cap1/validation.json')
assert validation['transport_valid'] and not validation['issues']
summary = {
    'scope': 'Actual runs in this outputs directory; synthetic and official inputs are separate.',
    'source_commit': read('execution_inventory.json')['source_commit'],
    'official_input_audit': read('official_input_audit.json'),
    'official_q2_best_known': {
        'plan': 'official_pareto_cpsat/energy_cap_1.json',
        'export': 'official_pareto_cpsat/export_cap1/',
        'metrics': plan['metrics'],
        'transport_valid': True,
        'global_optimality_proved': False,
        'radio_scope': 'No relay in this plan; direct-only precision check fails. Not a feasible Q3 plan.'
    },
    'first_official_transport_comparison': read('official_transport_s7/comparison.json')['methods'],
    'full_cpsat_actual': [r for r in read('official_transport_cpsat/comparison.json')['methods'] if r['method']=='integrated_cpsat'],
    'fixed_route_precision': read('official_retime_grids/comparison.json'),
    'official_transport_pareto': read('official_pareto_summary.json'),
    'official_radio_final_status': joint,
    'official_radio_attempts': read('official_radio_runs.json'),
    'official_direct_only_precision': read('official_radio_baseline_no_relay_precision/summary.json'),
    'synthetic_results_reference': 'synthetic_summary/summary.json',
    'stress_on_earlier_fixed_route_q2_plan': read('official_stress.json'),
    'stress_scope': 'Hypothetical perturbations of all time except fixed preparation and of route energy; weighted tardiness, no radio replay. Not a weather probability estimate.',
    'reporting_rules': [
        'Empty-plan numeric zeros in original raw records are not valid objective values.',
        'Time limits and UNKNOWN do not prove original-problem infeasibility.',
        'Finite-pool solver bounds apply only to the stated discretized model.',
        'Missing joint-plan outputs are not filled from synthetic experiments.',
        'Official source values and additional modeling conventions are documented separately.'
    ]
}
(OUT / 'execution_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'q2': plan['metrics'], 'joint_status': joint}, ensure_ascii=False))
