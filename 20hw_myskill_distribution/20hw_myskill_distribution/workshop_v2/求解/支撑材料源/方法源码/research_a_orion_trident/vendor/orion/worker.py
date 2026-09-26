"""Isolated official evaluator process. Windows-safe; no monkey patches."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import json
import math
import platform
import sys
import time
import traceback
from pathlib import Path
from .core import Graph, Config, bounds, plan_view


def atomic_json(path: str | Path, value: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False), encoding='utf8')
    tmp.replace(path)


def audit(g: Graph, plan: dict, result: dict, q: int, cfg: Config) -> dict:
    """Independent checks possible from the full public result timeline.

    Memory peaks are read from the official output, NOT independently replayed.
    The official full execution-DAG validator runs within the evaluator itself.
    """
    m, groups, core, order = plan_view(g, plan)
    problems = []
    originals = {}
    pipe_ops = defaultdict(list)
    all_ops = []
    task_times = {}
    for c in result['per_core_timeline']:
        k = c['core_id']
        for task in c['tasks']:
            task_times[task['task_id']] = task
        for o in c['ops']:
            all_ops.append(o)
            if o['start'] < 0 or o['end'] < o['start']:
                problems.append('negative or reversed operation interval')
            pipe_ops[k, o['pipe']].append(o)
            if o['op_id'] in g.ops:
                u = o['op_id']
                if u in originals:
                    problems.append(f'duplicated original operation {u}')
                originals[u] = (k, o)
                if k != core[m[u]]:
                    problems.append(f'wrong core for {u}')
                if o['duration'] != g.duration[u]:
                    problems.append(f'wrong compute duration for {u}')
    if set(originals) != set(g.ops):
        problems.append('incomplete original-operation coverage')
    for key, seq in pipe_ops.items():
        seq.sort(key=lambda o: (o['start'], o['end'], o['op_id']))
        for a, b in zip(seq, seq[1:]):
            if a['end'] > b['start']:
                problems.append(f'overlapping FIFO pipe {key}')
    for v, ps in g.retained_pred.items():
        for u in ps:
            if u in originals and v in originals:
                ku, ou = originals[u]
                kv, ov = originals[v]
                delay = cfg.cross_b if q in (2, 3) and ku != kv else 0
                if ov['start'] < ou['end'] + delay:
                    problems.append(f'data/synchronization dependency {u}->{v}')
    if q in (0, 1):
        for seq in plan['core_schedules']:
            for a, b in zip(seq, seq[1:]):
                if task_times[b]['start'] < task_times[a]['end'] + cfg.same_a:
                    problems.append('same-core Task delay violated')
        for v, ps in g.pred.items():
            for u in ps:
                a, b = m[u], m[v]
                if a != b and core[a] != core[b]:
                    if task_times[b]['start'] < task_times[a]['end'] + cfg.cross_a:
                        problems.append('cross-core Task delay violated')
    for t in result.get('cross_core_transfers', []):
        if t['copy_in_release'] != t['copy_out_end'] + cfg.cross_b or t['copy_in_start'] < t['copy_in_release']:
            problems.append('cross-core COPY release violated')
    if result['makespan'] != max((o['end'] for o in all_ops), default=0):
        problems.append('makespan differs from timeline maximum')
    for peaks in result.get('memory_peak_by_core', {}).values():
        for name in ('L1', 'UB'):
            if peaks.get(name, 0) > cfg.capacity[name]:
                problems.append('official memory peak exceeds capacity')
    cert = bounds(g, cfg, len(plan['core_schedules']), max(1, q), plan)
    if cert['candidate_lower'] > result['makespan'] + 1e-7:
        problems.append('certified lower bound exceeds feasible time; disable result and investigate')
    lb = cert['global_lower']
    cert.update(feasible_upper=result['makespan'],
                approximation_ratio_upper=(result['makespan'] / lb if lb else None),
                absolute_optimality_gap_upper=result['makespan'] - lb)
    return {'ok': not problems, 'errors': problems,
            'independent_checks': ['plan coverage/order', 'operation coverage/core/duration',
                                   'pipe non-overlap', 'retained data and synchronization',
                                   'task waits', 'makespan maximum', 'bound consistency'],
            'memory_check': 'official Step3 peaks checked against capacities; not independent global replay',
            'certificate': cert}


def execute(request: dict) -> dict:
    code = Path(request['official_code']).resolve()
    if not (code / 'evaluation_validation.py').is_file():
        raise FileNotFoundError(f'official code missing at {code}')
    sys.path.insert(0, str(code))
    from contest_io import _read_json
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import evaluate_scene_a, read_scene_a_config
    from multicore_cut_evaluate_problem_2 import evaluate_scene_b, read_scene_b_config
    from multicore_cut_evaluate_problem_3 import evaluate_problem_3, read_cache_config
    graph = _read_json(request['graph'])
    plan = _read_json(request['plan'])
    config = request['config']
    settings = read_evaluation_config(config)
    a, b, c = read_scene_a_config(config), read_scene_b_config(config), read_cache_config(config)
    q = request['q']
    start = time.perf_counter()
    if q in (0, 1):
        result = evaluate_scene_a(graph, plan, **settings,
                                 cross_core_wait=a['task_cross_core_wait_cycles'],
                                 same_core_wait=a['task_same_core_wait_cycles'])
    elif q == 2:
        result = evaluate_scene_b(graph, plan, **settings,
                                 cross_core_copy_delay=b['cross_core_copy_delay_cycles'])
    elif q == 3:
        # Sensitivity is opt-in and separately labelled; never change the source config.
        overrides = request.get('cache_overrides', {})
        result = evaluate_problem_3(graph, plan, **settings,
                                   cross_core_copy_delay=b['cross_core_copy_delay_cycles'],
                                   cache_capacity_bytes=overrides.get('capacity', c['cache_capacity_bytes']),
                                   cache_bandwidth_bytes_per_cycle=overrides.get('bandwidth', c['cache_bandwidth_bytes_per_cycle']))
    else:
        raise ValueError(f'unsupported problem {q}')
    eval_seconds = time.perf_counter() - start
    cfg = Config.read(config)
    if request.get('cache_overrides'):
        from dataclasses import replace
        cfg = replace(cfg, cache_capacity=request['cache_overrides'].get('capacity', cfg.cache_capacity),
                      cache_bandwidth=request['cache_overrides'].get('bandwidth', cfg.cache_bandwidth))
    checked = audit(Graph(graph), plan, result, q, cfg)
    return {'status': 'ok' if checked['ok'] else 'audit_failed', 'q': q,
            'official_result': result, 'audit': checked, 'eval_seconds': eval_seconds,
            'non_official_sensitivity': bool(request.get('cache_overrides')),
            'python': sys.version, 'platform': platform.platform()}


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument('request'); p.add_argument('response')
    args = p.parse_args(argv)
    try:
        result = execute(json.loads(Path(args.request).read_text(encoding='utf8')))
    except Exception as exc:
        result = {'status': 'error', 'error_type': type(exc).__name__, 'error': str(exc),
                  'traceback': traceback.format_exc()}
    atomic_json(args.response, result)
    return 0 if result['status'] == 'ok' else 1

if __name__ == '__main__':
    raise SystemExit(main())
