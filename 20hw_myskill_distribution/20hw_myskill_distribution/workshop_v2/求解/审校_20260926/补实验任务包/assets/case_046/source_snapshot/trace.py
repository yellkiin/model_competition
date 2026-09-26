"""Read ORIGINAL cache events; do not replace the official event simulator.

Event list order matters at equal timestamps. Fixed-duration criticality is an
explanation of one observed execution, not a cache-benefit counterfactual.
"""
from __future__ import annotations
from collections import defaultdict
import heapq


def operations(result: dict) -> dict[tuple[int, int], dict]:
    return {(c['core_id'], o['op_id']): {**o, 'core_id': c['core_id']}
            for c in result.get('per_core_timeline', []) for o in c['ops']}


def read_requests(result: dict) -> tuple[list[dict], list[dict]]:
    if result.get('problem') != 3 or 'cache_events' not in result:
        raise ValueError('An original Q3 response with cache_events is required')
    ops = operations(result)
    resident, last_eviction, prior_fills = {}, {}, set()
    in_flight = defaultdict(list)
    requests, fills = [], []
    capacity = result['cache_capacity_bytes']
    for event_index, event in enumerate(result['cache_events']):
        tid, now = event['tensor_id'], event['time']
        item = (event['core_id'], event['op_id'])
        op = ops[item]
        if event['event'] == 'insert':
            for evicted in event.get('evicted_tensor_ids', []):
                resident.pop(evicted, None)
                last_eviction[evicted] = now
            resident[tid] = now
            prior_fills.add(tid)
            fills.append({**event, 'event_index': event_index,
                          'completion_of_hit': bool(op.get('cache_hit', False)),
                          'copy_completion': op['end']})
            continue
        if event['event'] not in ('hit', 'miss'):
            raise ValueError(f"Unrecognized original cache event: {event['event']}")
        active = [r for r in in_flight[tid] if r['completion'] > now]
        in_flight[tid] = active
        hit = event['event'] == 'hit'
        if hit != (tid in resident):
            raise ValueError('Original event sequence and recorded residency disagree')
        if hit:
            cause = 'hit'
        elif event['size_bytes'] > capacity:
            cause = 'oversize'
        elif active:
            cause = 'evicted_inflight' if tid in prior_fills else 'cold_inflight'
        else:
            cause = 'evicted' if tid in prior_fills else 'cold_first'
        row = dict(event_index=event_index, tensor_id=tid, core_id=item[0], op_id=item[1],
                   subgraph_id=op.get('subgraph_id'), issue=now, completion=op['end'],
                   bytes=event['size_bytes'], hit=hit, cause=cause,
                   resident_since=resident.get(tid), last_eviction=last_eviction.get(tid),
                   earliest_pending_completion=min((r['completion'] for r in active), default=None),
                   concurrent_prior_reads=len(active))
        requests.append(row)
        in_flight[tid].append(row)
    return requests, fills


def frozen_criticality(result: dict, tasks: dict, cross_links: list[dict], delay: int) -> dict:
    """All official dependency/Pipe arcs, but durations frozen to the observed run.

    DDR/CACHE_READ contention is already inside measured durations. Removing a
    read would change those durations, so zero slack is not a causal guarantee.
    """
    ops = operations(result)
    pred = {item: {} for item in ops}
    for core, task in tasks.items():
        core = int(core)
        for v, parents in task['op_preds'].items():
            for u in parents:
                pred[(core, v)][(core, u)] = 0
        for sequence in task['pipe_ops'].values():
            for u, v in zip(sequence, sequence[1:]):
                pred[(core, v)][(core, u)] = 0
    for link in cross_links:
        u = (link['source_core'], link['source_copy_out_id'])
        v = (link['target_core'], link['target_copy_in_id'])
        pred[v][u] = max(delay, pred[v].get(u, 0))
    succ = {item: {} for item in ops}
    degree = {v: len(parents) for v, parents in pred.items()}
    for v, parents in pred.items():
        for u, lag in parents.items():
            succ[u][v] = lag
            if ops[u]['end'] + lag > ops[v]['start']:
                raise ValueError('Rebuilt official constraints disagree with observed timeline')
    queue = [u for u in ops if not degree[u]]
    heapq.heapify(queue)
    order = []
    while queue:
        u = heapq.heappop(queue)
        order.append(u)
        for v in succ[u]:
            degree[v] -= 1
            if degree[v] == 0:
                heapq.heappush(queue, v)
    if len(order) != len(ops):
        raise ValueError('Cycle in rebuilt dependency and Pipe constraints')
    latest, rows = {}, []
    for u in reversed(order):
        duration = ops[u]['end'] - ops[u]['start']
        latest_finish = min((latest[v] - lag for v, lag in succ[u].items()), default=result['makespan'])
        latest[u] = latest_finish - duration
        slack = latest[u] - ops[u]['start']
        if slack < 0:
            raise ValueError('Negative frozen-duration slack')
        rows.append(dict(core_id=u[0], op_id=u[1], op=ops[u]['op'],
                         start=ops[u]['start'], end=ops[u]['end'], frozen_slack=slack,
                         zero_slack=slack == 0, is_global_last=ops[u]['end'] == result['makespan']))
    return dict(model='complete_official_constraints_frozen_observed_durations',
                causal_claim=False, operations=rows)
