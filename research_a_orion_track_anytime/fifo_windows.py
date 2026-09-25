"""Observed-window FIFO proposals; only reorder existing groups on fixed cores.

Experimental extension of plugin.py. A target window is a heuristic from the
last full official run, not a counterfactual timing prediction or a lower bound.
"""
from __future__ import annotations
from collections import defaultdict
import time
from .trace import read_requests
from .storage import plan_key
from .plugin import propose as adjacent_proposals


def propose(g, n, cfg, q, incumbent=None, feedback=None, deadline=None):
    if q != 3 or not incumbent:
        return
    from research_a_orion_anytime.core import plan_view, estimate, bounds
    plan = incumbent['plan']
    raw = incumbent['official_result']
    if len(plan['core_schedules']) != n:
        raise ValueError('Target core count differs from the incumbent')
    mapping, groups, owner, _ = plan_view(g, plan)
    reads, _ = read_requests(raw)
    sequences = plan['core_schedules']
    group_span = {}
    core_end = {}
    for core in raw['per_core_timeline']:
        k = core['core_id']
        core_end[k] = max((op['end'] for op in core['ops']), default=0)
        for op in core['ops']:
            s = op.get('subgraph_id')
            if s is None:
                continue
            a, b = group_span.get((k,s), (op['start'],op['end']))
            group_span[k,s] = min(a,op['start']), max(b,op['end'])
    # Use distinct (core,group,cause) requests: a larger byte count alone does not
    # justify repeatedly proposing the identical ordering for every tensor read.
    targets = {}
    for read in reads:
        k, s = read['core_id'], read['subgraph_id']
        cause = read['cause']
        if s not in sequences[k] or cause not in ('cold_inflight','evicted_inflight','evicted'):
            continue
        tail_gap = max(0, raw['makespan'] - core_end[k])
        bandwidth_hint = read['bytes'] * max(0, 1/cfg.bandwidth - 1/cfg.cache_bandwidth)
        priority = bandwidth_hint / (1 + tail_gap/max(1,raw['makespan']))
        key = (k,s,cause)
        if key not in targets or priority > targets[key][0]:
            targets[key] = priority, read
    ranked = sorted(targets.values(), key=lambda x:(-x[0],x[1]['event_index']))[:12]
    own_key = plan_key(plan)
    seen = {own_key}
    emitted = 0
    def targeted():
        for priority, read in ranked:
            k, s = read['core_id'], read['subgraph_id']
            seq = sequences[k]
            i = seq.index(s)
            forward = 'inflight' in read['cause']
            target_time = read['earliest_pending_completion'] if forward else read['last_eviction']
            if target_time is None:
                continue
            need = abs(target_time - read['issue'])
            accumulated = 0
            positions = []
            # Sum observed *compute work*, not overlapping whole group spans.
            # It estimates how much natural ready work to put before a reader.
            direction = 1 if forward else -1
            for step in range(1, min(32, len(seq))+1):
                j = i + direction*step
                if not 0 <= j < len(seq):
                    break
                accumulated += sum(g.duration[u] for u in groups[seq[j]])
                if accumulated >= need:
                    positions.extend((j, j+direction))
                    break
            if not positions:
                positions.append(max(0,min(len(seq)-1,i+direction*16)))
            for j in dict.fromkeys(positions):
                if not 0 <= j < len(seq) or i == j:
                    continue
                new = [list(x) for x in sequences]
                new[k].pop(i); new[k].insert(j,s)
                p = {'node_to_subgraph':dict(plan['node_to_subgraph']), 'core_schedules':new}
                yield (p, f'fifo_observed_window_c{k}_g{s}_{i}_to{j}',
                       dict(tensor_id=read['tensor_id'],cause=read['cause'],
                            observed_issue=read['issue'],observed_target_time=target_time,
                            cumulative_work_hint=accumulated,priority_hint=priority,
                            counterfactual_prediction=False,changes_partition=False,changes_cores=False))
    fresh = iter(targeted())
    prior = iter(adjacent_proposals(g,n,cfg,q,incumbent,feedback,deadline))
    alive = [True,True]
    turn = 0
    while any(alive) and emitted < 32:
        if deadline is not None and time.monotonic() >= deadline:
            return
        family = turn % 2; turn += 1
        if not alive[family]:
            continue
        try:
            if family == 0:
                p,name,evidence = next(fresh)
                key = plan_key(p)
                if key in seen:
                    continue
                seen.add(key)
                try:
                    plan_view(g,p)
                except ValueError as exc:
                    if feedback is not None:
                        feedback.append(dict(name=name,family='anytime/fifo_completion_window',
                                             status='order_invalid',error=str(exc)))
                    continue
                candidate = dict(name=name,family='anytime/fifo_completion_window',plan=p,
                                 proxy=estimate(g,p,cfg,q),bounds=bounds(g,cfg,n,q,p),evidence=evidence)
            else:
                candidate = next(prior)
                key = plan_key(candidate['plan'])
                if key in seen:
                    continue
                seen.add(key)
        except StopIteration:
            alive[family] = False
            continue
        emitted += 1
        yield candidate
