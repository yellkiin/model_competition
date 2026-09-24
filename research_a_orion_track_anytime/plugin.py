"""COMMON.md FIFO candidate interface, separate from the pure selector.

Only an existing subgraph's position on its existing core can change. No new
partitioning, core reassignment, graph modification, or delay instruction.
"""
from __future__ import annotations
import time
from .trace import read_requests


def propose(g, n, cfg, q, incumbent=None, feedback=None, deadline=None):
    from research_a_orion_anytime.core import plan_view, estimate, bounds
    if q != 3 or not incumbent or n < 1:
        return
    if deadline is not None and time.monotonic() >= deadline:
        return
    plan = incumbent['plan']
    result = incumbent['official_result']
    requests, _ = read_requests(result)
    plan_view(g, plan)
    if len(plan['core_schedules']) != n:
        raise ValueError('The incumbent core count differs from n')
    makespan = max(1, result['makespan'])
    # Timing relevance is only a prioritization hint. Exact frozen criticality is
    # computed separately by diagnose.py and is NOT treated as a benefit bound.
    choices = []
    for row in requests:
        if row['cause'] not in ('cold_inflight', 'evicted_inflight', 'evicted'):
            continue
        k, s = row['core_id'], row['subgraph_id']
        sequence = plan['core_schedules'][k]
        if s not in sequence or len(sequence) < 2:
            continue
        direction = 1 if 'inflight' in row['cause'] else -1
        serial_saving = row['bytes'] * max(0.0, 1/cfg.bandwidth - 1/cfg.cache_bandwidth)
        relevance = .25 + .75 * row['completion'] / makespan
        choices.append((serial_saving * relevance, row, direction))
    choices.sort(key=lambda x: (-x[0], x[1]['event_index']))
    seen = set()
    emitted = 0
    for priority, row, direction in choices[:12]:
        k, s = row['core_id'], row['subgraph_id']
        original = plan['core_schedules'][k]
        source = original.index(s)
        for distance in (1, 2, 4):
            if deadline is not None and time.monotonic() >= deadline:
                return
            target = max(0, min(len(original)-1, source + direction*distance))
            if source == target:
                continue
            sequences = [list(seq) for seq in plan['core_schedules']]
            sequences[k].pop(source)
            sequences[k].insert(target, s)
            key = tuple(tuple(seq) for seq in sequences)
            if key in seen:
                continue
            seen.add(key)
            proposal = dict(node_to_subgraph=dict(plan['node_to_subgraph']), core_schedules=sequences)
            try:
                plan_view(g, proposal)
            except ValueError:
                # This is an invalid ordering, not a memory problem to repair.
                continue
            proxy = estimate(g, proposal, cfg, q)
            proxy['fifo_priority_hint'] = priority
            proxy['fifo_hint_is_bound'] = False
            yield dict(name=f'fifo_{row["cause"]}_c{k}_s{s}_move{target-source}',
                       family='anytime/fifo_window', plan=proposal, proxy=proxy,
                       bounds=bounds(g, cfg, n, q, proposal),
                       evidence=dict(tensor_id=row['tensor_id'], source_op=row['op_id'],
                                     miss_cause=row['cause'], issue=row['issue'],
                                     pending_fill=row['earliest_pending_completion'],
                                     previous_eviction=row['last_eviction'],
                                     operation='existing_same_core_subgraph_reinsertion'))
            emitted += 1
            if emitted >= 12:
                return
