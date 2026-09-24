"""Tensor-set boundary repair and bounded peak-frontier order candidates.

Only the two official plan fields change. This module neither evaluates a plan
nor changes the graph, capacities, Step1/2/3, or the FIFO controller. All memory
predictions are labelled surrogates; official execution is the acceptance gate.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import math
import time
from research_a_orion_anytime.core import (
    bounds, constructors, estimate, make_plan, plan_view, planned_traffic,
)

VERSION = 'memory-1.3'


def tensor_ledger(g, plan, q):
    """Pre-Spill byte accounting by producer/consumer TASK or CORE sets.

    Q1: read once per consumer Task without a local producer, write once per
    producer Task with a terminal or external consumer. Q2/3: COPY pair for each
    DISTINCT source-core/target-core pair; not (connectivity - 1) edge weights.
    This records scheduled logical bytes, never physical DDR bytes for Q3.
    """
    mapping, groups, cores, order = plan_view(g, plan)
    owner = {u: mapping[u] if q == 1 else cores[mapping[u]] for u in g.ops}
    rows = []
    for tid, tensor in g.tensors.items():
        ps = {owner[u] for u in g.tp[tid]}
        cs = {owner[u] for u in g.tc[tid]}
        if not (ps or cs):
            continue
        if q == 1:
            nr = len(cs - ps)
            nw = sum(bool(g.terminal[tid] or cs - {p}) for p in ps)
        else:
            pairs = sum(p != c for p in ps for c in cs)
            nr = (len(cs) if not ps else 0) + pairs
            nw = (len(ps) if g.terminal[tid] else 0) + pairs
        rows.append(dict(tensor_id=tid, size=tensor['size'], pos=tensor['pos'],
                         producer_owners=sorted(ps), consumer_owners=sorted(cs),
                         read_copies=nr, write_copies=nw,
                         scheduled_bytes=tensor['size'] * (nr + nw)))
    return rows


def _key(plan):
    # Canonical value equality for local deduplication; no fingerprints/tests.
    return (tuple(sorted((int(u), s) for u, s in plan['node_to_subgraph'].items())),
            tuple(tuple(x) for x in plan['core_schedules']))


def _merge(plan, members):
    """Tentative contraction; caller MUST run plan_view to reject nonconvexity."""
    p = deepcopy(plan)
    keep = min(members)
    for u, s in p['node_to_subgraph'].items():
        if s in members:
            p['node_to_subgraph'][u] = keep
    placed = False
    for k, seq in enumerate(p['core_schedules']):
        new = []
        for s in seq:
            if s not in members:
                new.append(s)
            elif not placed:
                new.append(keep)
                placed = True
        p['core_schedules'][k] = new
    return p


def _peak_window(g, plan, cfg, start, width=8):
    """Subset DP on a convex window in a common topological ordering.

    Objective is MAX normalized L1/UB live FRONTIER, then summed excess; never
    average occupancy as a capacity test. The frontier excludes intra-block
    execution and inserted COPY lifetimes, hence is ONLY a ranking surrogate.
    Peak feasibility and Spill are solely the unmodified evaluator's decision.
    """
    m, groups, owner, order = plan_view(g, plan)
    window = order[start:start + width]
    if len(window) < 2:
        return None
    ix = {s: i for i, s in enumerate(window)}
    before = set(order[:start]); after = set(order[start + len(window):])
    pred = {s: set() for s in window}
    for v, ps in g.pred.items():
        sv = m[v]
        if sv in pred:
            pred[sv].update(m[u] for u in ps if m[u] in ix and m[u] != sv)
    masks = {s: sum(1 << ix[p] for p in pred[s]) for s in window}
    tensors = []
    for t, tensor in g.tensors.items():
        for k in range(len(plan['core_schedules'])):
            ps = {m[u] for u in g.tp[t] if owner[m[u]] == k}
            cs = {m[u] for u in g.tc[t] if owner[m[u]] == k}
            if not (ps | cs) & ix.keys():
                continue
            p = sum(1 << ix[s] for s in ps & ix.keys())
            c = sum(1 << ix[s] for s in cs & ix.keys())
            pre = bool((ps | (cs if not ps else set())) & before)
            post = bool(cs & after)
            pos = tensor['pos'] if tensor['pos'] != 'DDR' else 'UB'
            tensors.append((k, pos, tensor['size'], p, c, pre, post, not ps))
    full = (1 << len(window)) - 1
    frontier = []
    for mask in range(full + 1):
        live = defaultdict(int)
        for k, pos, size, p, c, pre, post, external in tensors:
            born = pre or bool(p & mask) or (external and bool(c & mask))
            needed = post or bool(c & (full ^ mask))
            if born and needed:
                live[k, pos] += size
        peak = max((v / cfg.capacity[pos] for (_, pos), v in live.items()), default=0)
        excess = sum(max(0, v - cfg.capacity[pos]) for (_, pos), v in live.items())
        frontier.append((peak, excess))
    dp = {0: (frontier[0][0], 0, ())}
    for mask in range(full):
        if mask not in dp:
            continue
        peak, area, seq = dp[mask]
        for s in window:
            bit = 1 << ix[s]
            if mask & bit or masks[s] & mask != masks[s]:
                continue
            dest = mask | bit
            val = (max(peak, frontier[dest][0]), area + frontier[dest][1], seq + (s,))
            if dest not in dp or val < dp[dest]:
                dp[dest] = val
    if full not in dp:
        return None
    ordered = order[:start] + list(dp[full][2]) + order[start + len(window):]
    return make_plan([groups[s] for s in ordered], [owner[s] for s in ordered],
                     len(plan['core_schedules']))


def propose(g, n, cfg, q, incumbent=None, feedback=None, deadline=None):
    """COMMON.md compatible finite generator. No case-name/ID strategy branches."""
    if q not in (1, 2, 3) or n < 1:
        raise ValueError('q must be 1/2/3 and n positive')
    if deadline is not None and time.monotonic() >= deadline:
        return
    if incumbent is None:
        # Borrow existing construction rather than duplicate the structure track.
        pool = constructors(g, n, cfg, q, diagnostics=[])
        if not pool:
            return
        plan = pool[0]['plan']; result = {}
    else:
        plan = incumbent['plan']
        result = incumbent.get('official_result') or {}
    m, groups, owner, order = plan_view(g, plan)
    if len(plan['core_schedules']) != n:
        raise ValueError('NPU core count differs from plan')
    old_bytes = sum(planned_traffic(g, plan, q))
    upper = result.get('makespan', math.inf)
    candidates = []
    seen = {_key(plan)}
    max_trials = 48
    tried = 0
    diagnostics = []

    def add(p, name, family, mechanism):
        nonlocal tried
        if tried >= max_trials or (deadline is not None and time.monotonic() >= deadline):
            return
        tried += 1
        try:
            plan_view(g, p)
        except ValueError as exc:
            diagnostics.append(dict(name=name, status='structural_rejected', error=str(exc)))
            return
        key = _key(p)
        if key in seen:
            return
        seen.add(key)
        bd = bounds(g, cfg, n, q, p)
        # Pruning uses ONLY unchanged upstream necessary-condition bounds.
        if bd['candidate_lower'] > upper:
            diagnostics.append(dict(name=name, status='certified_pruned',
                                    candidate_lower=bd['candidate_lower'], upper=upper))
            return
        proxy = estimate(g, p, cfg, q)
        proxy['pre_spill_saved_bytes'] = old_bytes - sum(planned_traffic(g, p, q))
        candidates.append(dict(name=name, family='memory/' + family, plan=p,
                               proxy=proxy, bounds=bd, mechanism=mechanism,
                               generator_version=VERSION))

    # Residency repair for a coarse, already assigned block. The 1.0 real-graph
    # probe found no merge neighbourhood when every core already had one Task.
    # Split only within those blocks and KEEP their core assignments. This is a
    # local lifetime/Task-boundary experiment, not global repartitioning.
    observed_spill = result.get('data_movement_bytes', {}).get('spill_added_copy_bytes', 0)
    if observed_spill > 0 or not result:
        for count in (2, 4, 8):
            # Align consumers of shared parameters by dependency depth WITHIN
            # each already assigned block. No global mapping/partition framework.
            gg, kk = [], []
            for sg in order:
                local = groups[sg]
                depth = {}
                for u in g.topo:
                    if u in local:
                        depth[u] = 1 + max((depth[p] for p in g.pred[u] if p in local), default=-1)
                levels = sorted(set(depth.values()))
                rank = {d: j for j, d in enumerate(levels)}
                bands = defaultdict(set)
                for u in local:
                    bands[min(count - 1, rank[depth[u]] * count // max(1, len(levels)))].add(u)
                for band in sorted(bands):
                    gg.append(bands[band]); kk.append(owner[sg])
            add(make_plan(gg, kk, n), f'reuse_bands_{count}', 'reuse_bands',
                dict(bands_per_block=count, cores_unchanged=True,
                     trigger_spill_bytes=observed_spill,
                     note='consume shared parameters across branches before moving to later layers'))
        for count in (2, 4, 8):
            gg, kk = [], []
            for sg in order:
                seq = sorted(groups[sg], key=g.position.__getitem__)
                cuts = sorted({0, len(seq)} | {len(seq)*i//count for i in range(1, count)})
                for a, b in zip(cuts, cuts[1:]):
                    if a < b:
                        gg.append(set(seq[a:b])); kk.append(owner[sg])
            add(make_plan(gg, kk, n), f'pressure_chunks_{count}', 'pressure_split',
                dict(pieces_per_block=count, cores_unchanged=True,
                     trigger_spill_bytes=observed_spill,
                     note='Q1 resets Task memory; Q2/Q3 only changes legal subgraph priority'))

    # All same-core adjacency candidates: unlike a common-order-only merge, this
    # catches communication-related Tasks separated globally by other cores' work.
    pairs = []
    touched = {s: set().union(*(g.inputs[u] | g.outputs[u] for u in nodes))
               for s, nodes in groups.items()}
    for k, seq in enumerate(plan['core_schedules']):
        for a, b in zip(seq, seq[1:]):
            shared = touched[a] & touched[b]
            benefit = sum(g.tensors[t]['size'] for t in shared)
            pairs.append((-benefit, k, a, b))
    for _, k, a, b in sorted(pairs)[:(8 if q == 1 or observed_spill else 2)]:
        add(_merge(plan, {a, b}), f'convex_same_core_{a}_{b}', 'convex_merge',
            dict(groups=[a, b], core=k, note='same core does not imply free Task boundary'))
    # Batch adjacent same-core joins expose whether single-edge improvements are
    # too small. This is local coarsening of existing groups, NOT a new partitioner.
    for parity in ((0, 1) if q == 1 or observed_spill else ()):
        p = deepcopy(plan); joined = []
        for seq in plan['core_schedules']:
            for i in range(parity, len(seq) - 1, 2):
                a, b = seq[i:i + 2]
                candidate = _merge(p, {a, b})
                try:
                    plan_view(g, candidate)
                except ValueError:
                    continue
                p = candidate; joined.append([a, b])
        if joined:
            add(p, f'convex_batch_{parity}', 'convex_batch', dict(groups=joined))

    # Multi-consumer tensor-set moves; prefer late cross-core reads, not largest
    # Spill bytes. Criticality here is evidence-based priority, NOT a proof.
    late = defaultdict(float)
    for link in result.get('cross_core_transfers', []):
        late[link['tensor_id']] = max(late[link['tensor_id']], link['copy_in_end'])
    ledger = [row for row in tensor_ledger(g, plan, q)
              if g.tp[row['tensor_id']] and g.tc[row['tensor_id']] and row['scheduled_bytes'] > 0]
    ledger.sort(key=lambda r: (-(r['scheduled_bytes'] *
                        (1 + late[r['tensor_id']] / max(1, result.get('makespan', 1)))), r['tensor_id']))
    for row in ledger[:5]:
        t = row['tensor_id']
        ps = sorted({m[u] for u in g.tp[t]})
        cs = sorted({m[u] for u in g.tc[t]})
        if not ps or not cs:
            continue
        destinations = sorted({owner[s] for s in ps + cs})
        for k in destinations[:2]:
            movable = {s for s in cs if owner[s] != k}
            # Bound the local decision to at most three complete consumer groups.
            movable = set(sorted(movable, key=lambda s: (g.weight(groups[s]), s))[:3])
            if movable:
                p = make_plan([groups[s] for s in order],
                              [k if s in movable else owner[s] for s in order], n)
                add(p, f'consumer_set_{t}_to_{k}', 'consumer_set',
                    dict(tensor_id=t, moved_groups=sorted(movable), target_core=k))

    if q in (2, 3):
        # v1.2 real traces showed released COPY_IN waiting behind unrelated
        # target-core work. Move an EXISTING consumer subgraph earlier, not COPY
        # commands or FIFO internals. Full plan and official validators still run.
        links = sorted(result.get('cross_core_transfers', []),
                       key=lambda x: (-(x['copy_in_start'] - x['copy_in_release']),
                                      -x['copy_in_end'], -x['size']))
        selected = set()
        for link in links:
            if len(selected) >= 4:
                break
            if link['copy_in_start'] <= link['copy_in_release']:
                continue
            t = link['tensor_id']; k = link['target_core']
            for b in sorted({m[u] for u in g.tc.get(t, ()) if owner[m[u]] == k}):
                if b in selected:
                    continue
                selected.add(b)
                seq = plan['core_schedules'][k]; pos = seq.index(b)
                for at in sorted({0, pos // 2, max(0, pos - 1)}):
                    if at >= pos:
                        continue
                    p = deepcopy(plan); new_seq = p['core_schedules'][k]
                    new_seq.remove(b); new_seq.insert(at, b)
                    add(p, f'copy_queue_pull_{t}_{b}_{at}', 'copy_queue',
                        dict(tensor_id=t, consumer_group=b, target_core=k,
                             observed_queue_cycles=link['copy_in_start'] - link['copy_in_release'],
                             cores_unchanged=True, note='legal subgraph order only; official COPY queues untouched'))
                if len(selected) >= 4:
                    break

    if q in (2, 3):
        # Shorten actual producer-consumer group gaps without changing assignments.
        spans = []
        positions = {s: i for seq in plan['core_schedules'] for i, s in enumerate(seq)}
        for t, tensor in g.tensors.items():
            for v in g.tc[t]:
                b = m[v]
                for u in g.tp[t]:
                    a = m[u]
                    if a != b and owner[a] == owner[b] and positions[b] > positions[a] + 1:
                        spans.append((-(positions[b] - positions[a]) * tensor['size'], t, a, b))
        for _, t, a, b in sorted(set(spans))[:6]:
            p = deepcopy(plan); seq = p['core_schedules'][owner[b]]
            seq.remove(b); seq.insert(seq.index(a) + 1, b)
            add(p, f'residency_pull_{t}_{b}', 'residency_pull', dict(tensor_id=t, producer=a, consumer=b))
        # Cover beginning/middle/end of existing topological order, not only first
        # few swaps as in the old neighbourhood. The DP uses peak before area.
        starts = sorted({0, max(0, len(order)//2 - 4), max(0, len(order) - 8)})
        for start in starts:
            if deadline is not None and time.monotonic() >= deadline:
                break
            p = _peak_window(g, plan, cfg, start)
            if p:
                add(p, f'peak_window_{start}', 'peak_window',
                    dict(start=start, width=8, peak_model='subgraph frontier surrogate; not official capacity'))

    # Fixed round-robin representatives are an experiment ordering, not a new
    # anytime/FIFO controller. Consumers may select candidates themselves.
    families = defaultdict(list)
    for c in candidates:
        families[c['family']].append(c)
    for values in families.values():
        values.sort(key=lambda c: (c['proxy']['score'], -c['proxy']['pre_spill_saved_bytes'], c['name']))
    family_order = ['memory/reuse_bands', 'memory/pressure_split', 'memory/convex_batch', 'memory/convex_merge', 'memory/consumer_set',
                    'memory/copy_queue', 'memory/residency_pull', 'memory/peak_window']
    while any(families.values()):
        for family in family_order:
            if families[family]:
                c = families[family].pop(0)
                c['generation_diagnostics'] = diagnostics if diagnostics else []
                diagnostics = []
                yield c

    return dict(attempted_structures=tried, diagnostics=diagnostics)
