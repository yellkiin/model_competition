"""Q3-only deterministic proposals; all timing/cache models are heuristics.

Only the original two-field plan changes. No delay operation, graph alteration,
core reassignment, config mutation, or substitute evaluator is introduced.
"""
from __future__ import annotations

from collections import Counter, OrderedDict, defaultdict
import time

from research_a_orion_unified.trace import operations, read_requests
from research_a_orion_unified.io import plan_key
from research_a_orion_unified.vendor.orion.core import plan_view, topological


def propose(g, n, cfg, plan, raw, deadline, *,
            granularities=('weak', 'topo4'),
            policies=('shared', 'stagger1', 'stagger2', 'fifo', 'fifo_critical', 'low_footprint')):
    """Yield <= 20 legal plan proposals: <=8 observed windows + <=12 unit orders.

    ``deadline`` is time.monotonic() based. plan_view is only structural screening;
    every yielded plan still requires full original official evaluation.
    """
    if raw.get('problem') != 3 or len(plan['core_schedules']) != n:
        return
    mapping, groups, owner, original_order = plan_view(g, plan)
    reads, fills = read_requests(raw)
    seqs = plan['core_schedules']
    op_owner = {u: owner[mapping[u]] for u in g.ops}
    seen = set()
    emitted = 0

    def signature(p):
        # Preserve exact official labels: ID renaming can change tie-breaking.
        return plan_key(p)

    seen.add(signature(plan))

    def checked(p, name, family, evidence):
        nonlocal emitted
        if time.monotonic() >= deadline or emitted >= 20:
            return None
        key = signature(p)
        if key in seen:
            return None
        seen.add(key)
        try:
            pm, _, pc, _ = plan_view(g, p)
            if any(pc[pm[u]] != op_owner[u] for u in g.ops):
                raise ValueError('core ownership changed')
        except ValueError:
            return None
        emitted += 1
        return dict(plan=p, name=name, family=family,
                    evidence=dict(heuristic_only=True, official_evaluation_required=True,
                                  core_assignment_fixed=True, **evidence))

    intervals = {}
    ops = operations(raw)
    for (k, _), o in ops.items():
        s = o.get('subgraph_id')
        if s not in groups:
            continue
        key = (k, s)
        start, end = intervals.get(key, (float('inf'), 0))
        intervals[key] = (min(start, o['start']), max(end, o['end']))
    by_tensor = defaultdict(list)
    for r in reads:
        by_tensor[r['tensor_id']].append(r)
    targets = {}
    for r in reads:
        if r['cause'] not in ('cold_inflight', 'evicted_inflight', 'evicted'):
            continue
        k, s = r['core_id'], r['subgraph_id']
        if s not in seqs[k] or len(seqs[k]) < 2:
            continue
        priority = r['bytes'] * (0.25 + r['completion'] / max(1, raw['makespan']))
        key = (r['tensor_id'], k, s)
        if key not in targets or priority > targets[key][0]:
            targets[key] = (priority, r)
    targets = sorted(targets.values(), key=lambda x: (-x[0], x[1]['event_index']))

    def event_move(k, s, target_time, direction):
        old = seqs[k].index(s)
        others = [x for x in seqs[k] if x != s]
        if direction > 0:
            eligible = [i for i, x in enumerate(others)
                        if intervals.get((k, x), (0, 0))[1] <= target_time]
            new = max(old + 1, (max(eligible) + 1) if eligible else old + 1)
        else:
            eligible = [i for i, x in enumerate(others)
                        if intervals.get((k, x), (float('inf'), 0))[0] >= target_time]
            new = min(old - 1, min(eligible) if eligible else old - 1)
        new = max(0, min(len(others), new))
        if new == old:
            return None
        schedules = [list(x) for x in seqs]
        others.insert(new, s)
        schedules[k] = others
        return {'node_to_subgraph': dict(plan['node_to_subgraph']), 'core_schedules': schedules}

    # Round-robin mechanisms avoid spending all eight slots on one tensor.
    event_count = 0
    for mechanism in ('consumer', 'fill', 'evictor'):
        for priority, r in targets[:24]:
            if time.monotonic() >= deadline or event_count >= 8:
                break
            k, s = r['core_id'], r['subgraph_id']
            target = r['earliest_pending_completion'] if 'inflight' in r['cause'] else r['last_eviction']
            direction = 1 if 'inflight' in r['cause'] else -1
            if mechanism == 'fill':
                if r['earliest_pending_completion'] is None:
                    continue
                candidates = [x for x in by_tensor[r['tensor_id']]
                              if x['event_index'] < r['event_index'] and
                              x['completion'] == r['earliest_pending_completion']]
                if not candidates:
                    continue
                first = min(candidates, key=lambda x: x['event_index'])
                k, s, target, direction = first['core_id'], first['subgraph_id'], r['issue'], -1
            elif mechanism == 'evictor':
                fs = [f for f in fills if r['tensor_id'] in f.get('evicted_tensor_ids', [])
                      and f['time'] == r['last_eviction']]
                if not fs:
                    continue
                f = fs[-1]
                k = f['core_id']
                s = ops[(k, f['op_id'])].get('subgraph_id')
                target, direction = r['issue'], 1
            if s not in seqs[k] or len(seqs[k]) < 2 or target is None:
                continue
            p = event_move(k, s, target, direction)
            if p is None:
                continue
            c = checked(p, f'l2_{mechanism}_t{r["tensor_id"]}_c{k}_g{s}', 'l2/observed_window',
                        dict(mechanism=mechanism, tensor_id=r['tensor_id'],
                             observed_cause=r['cause'], observed_issue=r['issue'],
                             observed_target_time=target, observed_group_interval=intervals.get((k, s)),
                             priority_hint=priority, counterfactual_prediction=False))
            if c:
                event_count += 1
                yield c
            if mechanism == 'consumer' and event_count >= 4:
                break
            if mechanism == 'fill' and event_count >= 6:
                break

    original_pos = {s: i for i, s in enumerate(original_order)}
    # Weak components undo packing of independent islands; local topo chunks
    # expose connected large groups. Quotient cycles are rejected, never relaxed.
    for granularity in granularities:
        if time.monotonic() >= deadline:
            return
        units, unit_owner, unit_parent = {}, {}, {}
        for s in original_order:
            parts = g.weak_components(set(groups[s]))
            if granularity == 'topo4':
                finer = []
                for part in parts:
                    order = topological(part, g.pred)
                    width = max(1, (len(order) + 3) // 4)
                    for i in range(0, len(order), width):
                        finer.extend(g.weak_components(set(order[i:i + width])))
                parts = finer
            for part in parts:
                uid = len(units)
                units[uid] = part
                unit_owner[uid], unit_parent[uid] = owner[s], s
        umap = {u: v for v, members in units.items() for u in members}
        pred = {v: set() for v in units}
        for u, ps in g.pred.items():
            pred[umap[u]].update(umap[p] for p in ps if umap[p] != umap[u])
        try:
            topological(units, pred)
        except ValueError:
            continue
        # Known retained tensor identities only; direct op-op synthetic tensor
        # identities are deliberately excluded instead of guessed.
        ins, sizes = {}, {}
        for v, members in units.items():
            wanted = set().union(*(g.inputs[u] for u in members))
            keys = set()
            for t in wanted:
                if g.tp[t] and all(op_owner[p] == unit_owner[v] for p in g.tp[t]):
                    continue
                tid = g.tensors[t].get('logical_tid', t)
                keys.add(tid)
                sizes[tid] = max(sizes.get(tid, 0), int(g.tensors[t]['size']))
            ins[v] = keys
        frequency = Counter(t for keys in ins.values() for t in keys)
        hot = sorted((t for t in frequency if frequency[t] > 1 and sizes[t] <= cfg.cache_capacity),
                     key=lambda t: (-sizes[t] * (frequency[t] - 1), t))
        hot_rank = {t: i for i, t in enumerate(hot)}
        anchor = {v: min((hot_rank[t] for t in ins[v] if t in hot_rank), default=len(hot)) for v in units}
        base = {v: (original_pos[unit_parent[v]], min(units[v])) for v in units}
        ranks = {v: max(g.rank[u] for u in members) for v, members in units.items()}
        # Six deterministic policies per granularity, at most twelve candidates.
        for policy in policies:
            if time.monotonic() >= deadline:
                return
            succ = {v: [] for v in units}
            degree = {v: len(pred[v]) for v in units}
            for v, ps in pred.items():
                for p in ps:
                    succ[p].append(v)
            ready = {v for v in units if degree[v] == 0}
            order, resident, resident_bytes = [], OrderedDict(), 0
            while ready:
                if time.monotonic() >= deadline:
                    return
                def key(v):
                    shared_bytes = sum(sizes[t] for t in ins[v] if t in resident)
                    new_bytes = sum(sizes[t] for t in ins[v] if t not in resident)
                    if policy.startswith('stagger'):
                        offset = int(policy[-1]) * unit_owner[v]
                        return ((anchor[v] + offset) % max(1, len(hot)), base[v])
                    if policy == 'shared':
                        return (anchor[v], base[v])
                    if policy == 'low_footprint':
                        return (new_bytes > cfg.cache_capacity, new_bytes, -shared_bytes, base[v])
                    return (-shared_bytes, new_bytes, -ranks[v] if policy == 'fifo_critical' else 0, base[v])
                v = min(ready, key=key)
                ready.remove(v)
                order.append(v)
                # Byte-aware FIFO-like proxy, not an event simulation or score.
                # Actual insert/hit-completion semantics remain evaluator-owned.
                for t in sorted(ins[v]):
                    if t in resident or sizes[t] > cfg.cache_capacity:
                        continue
                    while resident and resident_bytes + sizes[t] > cfg.cache_capacity:
                        _, size = resident.popitem(last=False)
                        resident_bytes -= size
                    resident[t] = sizes[t]
                    resident_bytes += sizes[t]
                for w in succ[v]:
                    degree[w] -= 1
                    if degree[w] == 0:
                        ready.add(w)
            schedules = [[] for _ in range(n)]
            for v in order:
                schedules[unit_owner[v]].append(v)
            p = {'node_to_subgraph': {str(u): v for u, v in umap.items()}, 'core_schedules': schedules}
            c = checked(p, f'l2_unpack_{granularity}_{policy}', 'l2/unpack_reorder',
                        dict(mechanism='global_unit_dag_then_core_projection', granularity=granularity,
                             policy=policy, original_groups=len(groups), unpacked_units=len(units),
                             shared_tensor_identities=len(hot), fifo_capacity_bytes=cfg.cache_capacity,
                             shared_identity_source='original_retained_tensor.logical_tid_or_id',
                             proxy_is_official_time=False, subgroup_is_not_task_barrier=True))
            if c:
                yield c
