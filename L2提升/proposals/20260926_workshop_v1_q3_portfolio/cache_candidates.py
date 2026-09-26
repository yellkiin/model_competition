"""Deterministic Q3 candidates; no changes to earlier solvers or evaluators.

Plans control ownership and the sequence supplied to Step2.  Step3 rebuilds
its own topological order, so a requested block order is not a promise about
the final issue order.  Selection must use the unchanged official evaluator.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CODE = ROOT / "数据/原始/A题官方附件/code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))

from stub_multicore_cut_and_schedule import (
    _build_op_adjacency, _contract_excluded_copy_nodes,
    validate_multicore_plan,
)
from multicore_cut_evaluate_problem_1 import _original_tensor_views


def _settings(config):
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_3 import read_cache_config
    path = str(ROOT / "数据/原始/A题官方附件/data/config.txt")
    values = {**read_evaluation_config(path), **read_cache_config(path)}
    values.update(config or {})
    return values


def _features(graph):
    ops = {o['id']: o for o in graph['ops']
           if o['op'] not in {'COPY_IN', 'COPY_OUT'}}
    _, full_succ = _build_op_adjacency(graph)
    pred, succ = _contract_excluded_copy_nodes(sorted(ops), full_succ)
    parent = {u: u for u in ops}

    def find(u):
        while parent[u] != u:
            parent[u] = parent[parent[u]]
            u = parent[u]
        return u

    for u in ops:
        for v in succ[u]:
            parent[find(v)] = find(u)
    groups = defaultdict(list)
    for u in sorted(ops):
        groups[find(u)].append(u)
    groups = sorted(groups.values(), key=lambda x: x[0])
    index = {u: i for i, group in enumerate(groups) for u in group}
    records = []
    for group in groups:
        pipes = defaultdict(float)
        for u in group:
            pipes[ops[u].get('pipe', 'PIPE_V')] += ops[u].get('cycles', 0) + 1
        records.append({'members': group, 'pipes': dict(pipes), 'inputs': {},
                        'output_bytes': 0, 'tensor_bytes': 0})
    producers, consumers, _ = _original_tensor_views(graph)
    for t in graph['tensors']:
        tid, size = t['id'], t['size']
        ps = {p for p in producers.get(tid, ()) if p in ops}
        cs = {c for c in consumers.get(tid, ()) if c in ops}
        touched = {index[u] for u in ps | cs}
        for i in touched:
            records[i]['tensor_bytes'] += size
        if cs and not ps:
            for i in {index[u] for u in cs}:
                records[i]['inputs'][tid] = size
        if ps and (not cs or any(o not in ops for o in consumers.get(tid, ()))):
            for i in {index[u] for u in ps}:
                records[i]['output_bytes'] += size
    return records


def _pack(records, queues, mode, cache_capacity):
    """Keep components whole: their contraction cannot introduce dependencies."""
    mapping, schedules = {}, [[] for _ in queues]
    next_sg = 0
    for core, queue in enumerate(queues):
        groups = []
        current, footprint = [], set()
        footprint_bytes = 0
        for i in queue:
            rec = records[i]
            # Whole-tensor working-set bound, an approximation to FIFO reuse.
            extra = sum(size for tid, size in rec['inputs'].items()
                        if tid not in footprint)
            if current and (mode == 'single' or footprint_bytes + extra > cache_capacity):
                groups.append(current)
                current, footprint, footprint_bytes = [], set(), 0
                extra = sum(rec['inputs'].values())
            current.extend(rec['members'])
            footprint.update(rec['inputs'])
            footprint_bytes += extra
        if current:
            groups.append(current)
        for group in groups:
            sg = next_sg
            next_sg += 1
            schedules[core].append(sg)
            mapping.update((str(u), sg) for u in group)
    return {'node_to_subgraph': mapping, 'core_schedules': schedules}


def _ordered(records, queues, variant):
    result = []
    for core, queue in enumerate(queues):
        if variant == 'id':
            order = sorted(queue, key=lambda i: records[i]['members'][0])
        elif variant == 'reverse':
            order = sorted(queue, key=lambda i: -records[i]['members'][0])
        else:
            # A dominant shared input is an inexpensive deterministic locality
            # key.  Rotate cache groups across cores to diversify cold starts.
            def key(i):
                ins = records[i]['inputs']
                anchor = min(ins, key=lambda t: (-ins[t], t)) if ins else -1
                return anchor, records[i]['members'][0]
            order = sorted(queue, key=key)
            if variant == 'stagger' and order:
                offset = (core * len(order)) // max(1, len(queues))
                order = order[offset:] + order[:offset]
        result.append(order)
    return result


def _balanced(records, cores, settings):
    bw = settings['bandwidth']
    cbw = settings['cache_bandwidth_bytes_per_cycle']
    cap = settings['cache_capacity_bytes']
    # Estimate overlappable compute by its busiest pipe and transfer by the
    # actual DDR/cache bandwidths; omit already local external tensors.
    loads = [defaultdict(float) for _ in range(cores)]
    local_inputs = [set() for _ in range(cores)]
    globally_read = set()
    queues = [[] for _ in range(cores)]

    def weight(i):
        r = records[i]
        return max(r['pipes'].values(), default=0) + (
            sum(r['inputs'].values()) + r['output_bytes']) / bw

    for i in sorted(range(len(records)), key=lambda i: (-weight(i), records[i]['members'][0])):
        rec = records[i]
        trials = []
        for c in range(cores):
            trial = dict(loads[c])
            for pipe, value in rec['pipes'].items():
                trial[pipe] = trial.get(pipe, 0) + value
            read = sum(size / (cbw if tid in globally_read and size <= cap else bw)
                       for tid, size in rec['inputs'].items() if tid not in local_inputs[c])
            trial['read'] = trial.get('read', 0) + read
            trial['write'] = trial.get('write', 0) + rec['output_bytes'] / bw
            predicted = max(trial.values(), default=0) + 0.15 * sum(trial.values())
            trials.append((predicted, sum(trial.values()), c, trial))
        _, _, core, trial = min(trials, key=lambda x: x[:3])
        loads[core].update(trial)
        local_inputs[core].update(rec['inputs'])
        globally_read.update(rec['inputs'])
        queues[core].append(i)
    return queues


def generate_candidates(graph, num_cores, baseline_plan, cache_config=None):
    """Yield (name, plan, metadata), retaining the supplied incumbent first.

    Independent components cannot create new cross-core communication.  The
    cold/warm estimates guide candidate construction only, never score claims.
    All yielded plans pass the official structural validator; execution must
    still be checked by the official Q3 evaluator.
    """
    if num_cores != len(baseline_plan['core_schedules']):
        raise ValueError('num_cores does not match baseline plan')
    seen = set()

    def emit(name, plan, meta):
        positions = {sg: (c, k) for c, order in enumerate(plan['core_schedules'])
                     for k, sg in enumerate(order)}
        key = tuple(sorted((int(u), *positions[sg]) for u, sg in plan['node_to_subgraph'].items()))
        if key in seen:
            return None
        validate_multicore_plan(graph, plan)
        seen.add(key)
        meta.update(method='q3_cache_component_candidates', num_cores=num_cores,
                    subgraphs=sum(map(len, plan['core_schedules'])),
                    scoring='unchanged official Q3 evaluator required')
        return name, plan, meta

    item = emit('cache_baseline', baseline_plan, {'variant': 'incumbent'})
    if item:
        yield item
    records = _features(graph)
    if len(records) < 2:
        return
    settings = _settings(cache_config)
    cap = settings['cache_capacity_bytes']
    core_of_sg = {sg: c for c, order in enumerate(baseline_plan['core_schedules']) for sg in order}
    core_of_op = {int(u): core_of_sg[sg] for u, sg in baseline_plan['node_to_subgraph'].items()}
    queues = [[] for _ in range(num_cores)]
    preserve_possible = True
    for i, rec in enumerate(records):
        cores = {core_of_op[u] for u in rec['members']}
        if len(cores) != 1:
            preserve_possible = False
            break
        queues[next(iter(cores))].append(i)
    options = []
    if preserve_possible:
        for order in ('id', 'reverse', 'stagger'):
            options.append((f'cache_fixed_{order}', _ordered(records, queues, order), 'single',
                            {'assignment': 'unchanged', 'order': order}))
    balanced = _balanced(records, num_cores, settings)
    for order, mode in (('id', 'single'), ('stagger', 'single'), ('locality', 'capacity')):
        options.append((f'cache_balance_{order}', _ordered(records, balanced, order), mode,
                        {'assignment': 'pipe_ddr_l2_estimate', 'order': order}))
    for name, queue, mode, meta in options:
        plan = _pack(records, queue, mode, cap)
        meta.update(components=len(records), packing=mode, cache_capacity_bytes=cap)
        item = emit(name, plan, meta)
        if item:
            yield item
