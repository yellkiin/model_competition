"""Subprocess isolation for the ORIGINAL evaluator API (no trace formatting loop).

Only calls original public evaluate functions with original configuration values.
Raw responses are retained for final selected plans; no modified scoring.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from research_a.model import read_json


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    temp.replace(path)


def call(code, config, graph_path, plan, question, directory, timeout):
    from research_a.evaluator import metrics
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    write(directory/'plan.json', plan.json()) if plan is not None else None
    args = [sys.executable, '-X', 'utf8', '-m', 'research_a_next.official',
            '--code', str(code), '--config', str(config), '--graph', str(graph_path),
            '--question', str(question), '--out', str(directory/'raw.json')]
    if plan is not None: args += ['--plan', str(directory/'plan.json')]
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    start = time.monotonic()
    try:
        with (directory/'stdout.log').open('w', encoding='utf-8') as stdout, (directory/'stderr.log').open('w', encoding='utf-8') as stderr:
            proc = subprocess.run(args, stdout=stdout, stderr=stderr, timeout=timeout, env=env)
        if proc.returncode:
            return dict(status='error', seconds=time.monotonic()-start,
                        error=(directory/'stderr.log').read_text(encoding='utf-8')[-4000:]), None
        raw = read_json(directory/'raw.json')
        m = metrics(raw)
        m['cache_byte_hit_rate'] = raw.get('cache_stats', {}).get('hit_rate', 0.)
        # Both values are reported; do not silently relabel scheduled-copy extra
        # bytes as physical DDR extra bytes in Q3.
        m['official_added_copy_bytes'] = raw['data_movement_bytes']['added_copy_bytes']
        m['extra_ddr_accounted_bytes'] = m['ddr_accounted_bytes'] - raw['data_movement_bytes']['original_graph_copy_bytes']
        return dict(status='ok', seconds=time.monotonic()-start, **m), raw
    except subprocess.TimeoutExpired:
        return dict(status='timeout', seconds=time.monotonic()-start, error=f'Exceeded {timeout:g} seconds'), None
    except (OSError, ValueError, KeyError) as e:
        return dict(status='error', seconds=time.monotonic()-start, error=str(e)), None


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('code','config','graph','out'): p.add_argument('--'+flag, type=Path, required=True)
    p.add_argument('--plan', type=Path)
    p.add_argument('--question', type=int, choices=(0,1,2,3), required=True)
    a=p.parse_args(); sys.path.insert(0,str(a.code.resolve()))
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import evaluate_scene_a, read_scene_a_config
    from multicore_cut_evaluate_problem_2 import evaluate_scene_b, read_scene_b_config
    from multicore_cut_evaluate_problem_3 import evaluate_problem_3, read_cache_config
    from singlecore_evaluate import evaluate_singlecore
    cfg=read_evaluation_config(str(a.config)); g=read_json(a.graph)
    if a.question==0:
        raw=evaluate_singlecore(g, **cfg)
    else:
        plan=read_json(a.plan)
        if a.question==1:
            waits=read_scene_a_config(str(a.config))
            raw=evaluate_scene_a(g,plan,**cfg,cross_core_wait=waits['task_cross_core_wait_cycles'],same_core_wait=waits['task_same_core_wait_cycles'])
        elif a.question==2:
            raw=evaluate_scene_b(g,plan,**cfg,cross_core_copy_delay=read_scene_b_config(str(a.config))['cross_core_copy_delay_cycles'])
        else:
            raw=evaluate_problem_3(g,plan,**cfg,cross_core_copy_delay=read_scene_b_config(str(a.config))['cross_core_copy_delay_cycles'],**read_cache_config(str(a.config)))
    write(a.out,raw)

if __name__=='__main__':
    main()
