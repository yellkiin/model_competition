"""Q3 local L2 windows, version 2, using actual request/computation observations.

No global tensor sort or broad partition rewrite. Original group IDs/membership
are retained for ordinary moves. A small optional fallback splits only one
packed group into weak components. Every proposal needs original evaluation.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import defaultdict
import time

from research_a_orion_unified.io import plan_key
from research_a_orion_unified.trace import operations, read_requests
from research_a_orion_unified.vendor.orion.core import plan_view


def propose(g, n, cfg, plan, raw, deadline):
    if raw.get('problem') != 3 or len(plan['core_schedules']) != n:
        return
    mapping, groups, owners, _ = plan_view(g, plan)
    fixed_owner = {u: owners[mapping[u]] for u in g.ops}
    seqs = plan['core_schedules']
    requests, fills = read_requests(raw)
    ops = operations(raw)
    seen, emitted = {plan_key(plan)}, 0
    compute, group_compute, pipe_previous = defaultdict(list), defaultdict(list), {}
    core_finish = {}
    for core in raw['per_core_timeline']:
        k = core['core_id']
        core_finish[k] = max((o['end'] for o in core['ops']), default=0)
        by_pipe = defaultdict(list)
        for o in core['ops']:
            if o['op'] not in ('COPY_IN', 'COPY_OUT'):
                compute[k].append(o)
                group_compute[(k, o.get('subgraph_id'))].append(o)
                by_pipe[o['pipe']].append(o)
        for os in by_pipe.values():
            previous = 0
            for o in sorted(os, key=lambda x: (x['start'], x['end'], x['op_id'])):
                pipe_previous[(k, o['op_id'])] = previous
                previous = o['end']
    for os in group_compute.values():
        os.sort(key=lambda x: (x['start'], x['op_id']))
    reads_by_tensor = defaultdict(list)
    for r in requests:
        reads_by_tensor[r['tensor_id']].append(r)
    evictions = {}
    for f in fills:
        for t in f.get('evicted_tensor_ids', []):
            evictions[(t, f['time'])] = f

    def rank_request(r):
        # This is association with observed Pipe idle, not causal critical slack.
        os = group_compute.get((r['core_id'], r['subgraph_id']), [])
        starts = [o['start'] for o in os]
        i = bisect_left(starts, r['completion'])
        nxt = os[i] if i < len(os) else None
        gap = max(0, nxt['start'] - pipe_previous.get((r['core_id'], nxt['op_id']), 0)) if nxt else 0
        distance = max(0, nxt['start'] - r['completion']) if nxt else raw['makespan']
        overlap = min(gap, max(0, r['completion'] - r['issue']))
        near = 1 / (1 + distance / max(1, r['completion'] - r['issue']))
        late_core = core_finish.get(r['core_id'], 0) / max(1, raw['makespan'])
        score = (1 + overlap * near) * r['bytes'] * (.2 + late_core)
        return score, dict(observed_compute_gap_cycles=gap,
                           observed_next_compute_start=nxt['start'] if nxt else None,
                           observed_read_compute_distance=distance,
                           causality_confirmed=False, priority_hint=score)

    target_map = {}
    for r in requests:
        if r['cause'] not in ('cold_inflight', 'evicted_inflight', 'evicted'):
            continue
        score, evidence = rank_request(r)
        key = (r['tensor_id'], r['core_id'], r['subgraph_id'])
        if key not in target_map or score > target_map[key][0]:
            target_map[key] = (score, r, evidence)
    targets = sorted(target_map.values(), key=lambda x: (-x[0], x[1]['event_index']))

    def checked(p, name, family, evidence):
        nonlocal emitted
        if emitted >= 48 or time.monotonic() >= deadline:
            return None
        key = plan_key(p)
        if key in seen:
            return None
        seen.add(key)
        try:
            m, _, c, _ = plan_view(g, p)
            if any(c[m[u]] != fixed_owner[u] for u in g.ops):
                return None
        except ValueError:
            return None
        emitted += 1
        return dict(plan=p, name=name, family=family,
                    evidence=dict(heuristic_only=True, official_evaluation_required=True,
                                  core_assignment_fixed=True, **evidence))

    def move(k, s, delta, base=None):
        base = plan if base is None else base
        ss = [list(seq) for seq in base['core_schedules']]
        if s not in ss[k]:
            return None
        i = ss[k].index(s)
        j = max(0, min(len(ss[k]) - 1, i + delta))
        if i == j:
            return None
        ss[k].pop(i)
        ss[k].insert(j, s)
        return dict(node_to_subgraph=dict(base['node_to_subgraph']), core_schedules=ss)

    descriptors, descriptor_keys = [], set()
    # Select up to six distinct actual mechanisms first, then vary local radius.
    # Diversification is per moved core/group, not twelve reads of one group.
    for _, r, ev in targets:
        if time.monotonic() >= deadline:
            return
        k, s = r['core_id'], r['subgraph_id']
        mechanisms = [('consumer', k, s, 1 if 'inflight' in r['cause'] else -1)]
        pending = r['earliest_pending_completion']
        if pending is not None:
            rs = [x for x in reads_by_tensor[r['tensor_id']]
                  if x['event_index'] < r['event_index'] and x['completion'] == pending]
            if rs:
                first = min(rs, key=lambda x: x['event_index'])
                mechanisms.insert(0, ('fill', first['core_id'], first['subgraph_id'], -1))
        f = evictions.get((r['tensor_id'], r['last_eviction']))
        if f:
            fk = f['core_id']
            mechanisms.append(('evictor', fk, ops[(fk, f['op_id'])].get('subgraph_id'), 1))
        for kind, k, s, direction in mechanisms:
            key = (kind, k, s, direction)
            if key in descriptor_keys or s not in seqs[k] or len(seqs[k]) < 2:
                continue
            descriptor_keys.add(key)
            descriptors.append((kind, k, s, direction, r, ev))
            if len(descriptors) >= 10:
                break
        if len(descriptors) >= 10:
            break

    for distance in (1, 2, 4):
        for index, (kind, k, s, direction, r, ev) in enumerate(descriptors):
            if emitted >= 30 or time.monotonic() >= deadline:
                break
            p = move(k, s, direction * distance)
            if p is None:
                continue
            c = checked(p, f'l2v2_{kind}_c{k}_g{s}_d{direction * distance}', 'l2v2/local_window',
                        dict(mechanism=kind, tensor_id=r['tensor_id'], observed_cause=r['cause'],
                             observed_issue=r['issue'], observed_completion=r['completion'],
                             pending_fill=r['earliest_pending_completion'], previous_eviction=r['last_eviction'],
                             local_radius=distance, membership_fixed=True, **ev))
            if c:
                yield c

    # Joint moves may pass a flat single-move plateau. At most one move per core,
    # radius one only, with all unaffected relative order preserved.
    for a in range(min(4, len(descriptors))):
        for b in range(a + 1, min(7, len(descriptors))):
            if emitted >= 38 or time.monotonic() >= deadline:
                break
            x, y = descriptors[a], descriptors[b]
            if x[1] == y[1]:
                continue
            p = move(x[1], x[2], x[3])
            if p is None:
                continue
            p = move(y[1], y[2], y[3], p)
            if p is None:
                continue
            c = checked(p, f'l2v2_joint_{a}_{b}', 'l2v2/joint_local',
                        dict(mechanism='two_real_local_moves', membership_fixed=True, local_radius=1,
                             first=dict(core=x[1],group=x[2],tensor=x[4]['tensor_id'],kind=x[0]),
                             second=dict(core=y[1],group=y[2],tensor=y[4]['tensor_id'],kind=y[0])))
            if c:
                yield c

    # Bounded rescue for a packed group that cannot expose its internal reuse.
    # Split only one original group, only at existing weak-component boundaries.
    # No connected-component slicing, no all-graph tensor ordering.
    identity_to_consumers = defaultdict(set)
    for tid, t in g.tensors.items():
        identity_to_consumers[t.get('logical_tid', tid)].update(g.tc[tid])
    handled = set()
    next_id = max(groups, default=-1) + 1
    observed_start = {o['op_id']: o['start'] for o in ops.values() if o['op_id'] in g.ops}
    for _, r, ev in targets:
        if emitted >= 48 or time.monotonic() >= deadline or len(handled) >= 3:
            return
        k, s = r['core_id'], r['subgraph_id']
        if s in handled or s not in groups:
            continue
        consumers = identity_to_consumers.get(r['tensor_id'], set()) & groups[s]
        if not consumers:
            continue
        handled.add(s)
        parts = g.weak_components(set(groups[s]))
        if not 2 <= len(parts) <= 64:
            continue
        parts.sort(key=lambda part: (min(observed_start.get(u, raw['makespan']) for u in part), min(part)))
        ids = [s] + list(range(next_id, next_id + len(parts) - 1))
        split_map = dict(plan['node_to_subgraph'])
        for sid, part in zip(ids, parts):
            for u in part:
                split_map[str(u)] = sid
        schedules = [list(seq) for seq in seqs]
        pos = schedules[k].index(s)
        schedules[k][pos:pos+1] = ids
        base = dict(node_to_subgraph=split_map, core_schedules=schedules)
        c = checked(base, f'l2v2_local_unpack_c{k}_g{s}', 'l2v2/local_unpack',
                    dict(mechanism='single_group_weak_unpack_observed_order', tensor_id=r['tensor_id'],
                         original_group=s, units=len(parts), unaffected_groups_preserved=True, **ev))
        if c:
            yield c
        target_ids = [sid for sid, part in zip(ids, parts) if part & consumers]
        direction = 1 if 'inflight' in r['cause'] else -1
        for sid in target_ids[:2]:
            for distance in (1, 2):
                i = base['core_schedules'][k].index(sid)
                j = i + direction * distance
                # Keep the moved unit inside the footprint of its original group.
                if j < pos or j >= pos + len(ids):
                    continue
                p = move(k, sid, direction * distance, base)
                if p is None:
                    continue
                c = checked(p, f'l2v2_unpack_window_c{k}_g{s}_u{sid}_d{direction * distance}',
                            'l2v2/local_unpack_window', dict(mechanism='single_packed_group_window',
                                original_group=s, tensor_id=r['tensor_id'], local_radius=distance,
                                units=len(parts), unaffected_groups_preserved=True, **ev))
                if c:
                    yield c
