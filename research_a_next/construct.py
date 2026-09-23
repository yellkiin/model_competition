"""Deterministic stage-constrained construction and bounded integer refinement.

A49/A02-inspired clustering and data-ready list assignment; A16-inspired live
Tensor costs; A42-inspired restricted local optimization. Not their solvers.
"""
from __future__ import annotations
from collections import defaultdict
import math
import time
from .core import components, normalize, predict
from research_a.model import Plan, PIPES


def _work(g, nodes):
    return {p: sum(g.cost[u] for u in nodes if g.ops[u]['pipe'] == p) for p in PIPES}


def _group(g, atoms, owners, cores, batch=0):
    buckets = defaultdict(list)
    for (stage, block), k in zip(atoms, owners):
        buckets[stage, k].extend(block)
    position = {u: i for i, u in enumerate(g.order)}
    blocks, ks = [], []
    for (stage, k), nodes in sorted(buckets.items()):
        nodes.sort(key=position.get)
        blocks.append(nodes)
        ks.append(k)
    return normalize(g, Plan(blocks, ks, cores))


def _depth(g, weighted=False):
    level = {}
    for u in g.order:
        level[u] = max((level[v] + (g.cost[v] if weighted else 1) for v in g.pred[u]), default=0.)
    return level


def atoms(g, cores, mode='adaptive'):
    comps = components(g)
    total = sum(g.cost.values())
    if mode == 'components':
        return [(0, c) for c in comps]
    level = _depth(g, weighted=mode != 'bands8')
    if mode == 'bands8':
        width = max(1., (max(level.values(), default=0.) + 1) / 8)
        stage = {u: min(7, int(level[u] / width)) for u in g.ids}
    else:
        # Leave parallel independent components intact; split only an overweight
        # component with enough internal concurrency. Bound atoms by <=16 bands.
        stage = dict.fromkeys(g.ids, 0)
        threshold = total / max(1, cores)
        for c in comps:
            work = sum(g.cost[u] for u in c)
            start = min(level[u] for u in c)
            span = max(level[u] + g.cost[u] for u in c) - start
            if work <= 1.25 * threshold or work / max(1., span) < 1.5:
                continue
            bands = min(16, max(2, int(math.ceil(work / max(1., threshold)) * 2)))
            # Nonuniform separators: among nearby weighted-depth thresholds,
            # choose the smallest crossing Tensor byte count (not edge count).
            candidate_levels = sorted(set(level[u] - start for u in c))
            boundaries = []
            members = set(c)
            intervals = []
            for t in {t for u in c for t in g.outputs[u]}:
                ps, cs = g.ps[t] & members, g.cs[t] & members
                if ps and cs:
                    intervals.append((min(level[u] - start for u in ps),
                                      max(level[u] - start for u in cs), g.tensors[t]['size']))
            for j in range(1, bands):
                nominal = span * j / bands
                nearby = sorted(candidate_levels, key=lambda x: (abs(x - nominal), x))[:5]
                if nearby:
                    point = min(nearby, key=lambda x: (sum(s for a, b, s in intervals if a < x <= b), abs(x - nominal), x))
                    if point > 0:
                        boundaries.append(point)
            boundaries = sorted(set(boundaries))
            for u in c:
                stage[u] = sum(level[u] - start >= b for b in boundaries)
    by_stage = defaultdict(set)
    for u, s in stage.items():
        by_stage[s].add(u)
    answer = []
    for s, nodes in sorted(by_stage.items()):
        answer.extend((s, c) for c in components(g, nodes))
    return answer


def assign(g, atomic, cores, q, cfg, mode='eft', profile='balanced'):
    """Stage-feasible integral recovery, with core/Pipe/data-readiness decisions."""
    order_index = {u: i for i, u in enumerate(g.order)}
    # Atoms in a stage are disconnected in the induced dependency graph.
    atomic = sorted(atomic, key=lambda a: (a[0], -max(g.rank[u] for u in a[1]), min(a[1])))
    clocks = [{p: 0. for p in PIPES} for _ in range(cores)]
    done, assigned, owners, scalar = {}, {}, [], [0.] * cores
    bandwidth = cfg['bandwidth']
    for s, unordered in atomic:
        block = sorted(unordered, key=order_index.get)
        work = _work(g, block)
        if mode == 'lpt':
            k = min(range(cores), key=lambda j: (scalar[j], j))
            ends = {}
        else:
            costs = []
            for k in range(cores):
                trial_clock, ends = dict(clocks[k]), {}
                remote_tensors = set()
                for u in block:
                    ready = 0.
                    for v, size in g.retained[u].items():
                        f = ends.get(v, done.get(v, 0.))
                        src = assigned.get(v, k)
                        delay = 0.
                        if v not in ends:
                            if q == 1:
                                # Distinct stages make different Tasks; same-stage
                                # atoms have no inter-atom dependencies.
                                delay = (cfg['task_same_core_wait_cycles'] if src == k
                                         else cfg['task_cross_core_wait_cycles']) + 2 * max(1, math.ceil(size / bandwidth))
                            elif src != k:
                                delay = cfg['cross_core_copy_delay_cycles'] + 2 * max(1, math.ceil(size / bandwidth))
                        ready = max(ready, f + delay)
                    p = g.ops[u]['pipe']
                    ends[u] = max(ready, trial_clock[p]) + g.cost[u]
                    trial_clock[p] = ends[u]
                    for t in g.inputs[u]:
                        if any(assigned.get(v, k) != k for v in g.ps[t]):
                            remote_tensors.add(t)
                transfer = sum(g.tensors[t]['size'] for t in remote_tensors) / bandwidth
                pressure = sum(max(0., sum(g.tensors[t]['size'] for t in g.inputs[u] | g.outputs[u]
                                             if g.tensors[t]['pos'] == pos) - cfg['capacity'][pos])
                               for u in block for pos in cfg['capacity']) / bandwidth
                multiplier = 1. if profile == 'locality' else .08
                cost = max(trial_clock.values()) + multiplier * transfer + pressure
                costs.append((cost, k, ends, trial_clock))
            _, k, ends, trial_clock = min(costs, key=lambda x: (x[0], x[1]))
            clocks[k] = trial_clock
        owners.append(k)
        scalar[k] += sum(g.ops[u]['cycles'] + 1 for u in block)
        assigned.update({u: k for u in block})
        done.update(ends)
    return _group(g, atomic, owners, cores), atomic, owners


def paper_candidates(g, cores):
    """Reimplementation from the supplied draft pp10-11, NOT recovered author code."""
    comps = sorted(components(g), key=lambda b: (-sum(g.ops[u]['cycles'] + 1 for u in b), min(b)))
    load, owners = [0.] * cores, []
    for b in comps:
        k = min(range(cores), key=lambda j: (load[j], j))
        owners.append(k)
        load[k] += sum(g.ops[u]['cycles'] + 1 for u in b)
    yield 'draft_components', _group(g, [(0, b) for b in comps], owners, cores)
    atomic = atoms(g, cores, 'bands8')
    by_stage = defaultdict(list)
    for s, b in atomic:
        by_stage[s].append(b)
    assigned, stages, stage_owners = {}, [], []
    for s, blocks in sorted(by_stage.items()):
        load = [0.] * cores
        for b in sorted(blocks, key=lambda b: (-sum(g.ops[u]['cycles'] + 1 for u in b), min(b))):
            w = sum(g.ops[u]['cycles'] + 1 for u in b)
            # Draft does not specify the affinity coefficient. Fixed .1 is OUR
            # reconstruction choice; never claim byte-identical reproduction.
            affinity = [sum(assigned.get(v, -1) == k for u in b for v in g.pred[u]) for k in range(cores)]
            k = min(range(cores), key=lambda j: (load[j] - .1 * w * affinity[j] / max(1, sum(affinity)), j))
            assigned.update({u: k for u in b})
            load[k] += w
            stages.append((s, b)); stage_owners.append(k)
    yield 'draft_bands8', _group(g, stages, stage_owners, cores)
    if len(g.ids) / cores > 2500 and max(map(len, comps), default=0) <= 600:
        blocks, ks = [], []
        for k in range(cores):
            batch = []
            for b, owner in zip(comps, owners):
                if owner != k:
                    continue
                if batch and len(batch) + len(b) > 800:
                    blocks.append(batch); ks.append(k); batch = []
                batch.extend(b)
            if batch:
                blocks.append(batch); ks.append(k)
        yield 'draft_batches800', normalize(g, Plan(blocks, ks, cores))


def construct(g, cores, q, cfg, profile='balanced'):
    atomic = atoms(g, cores, 'components' if profile == 'components' else 'adaptive')
    plan, atomic, owners = assign(g, atomic, cores, q, cfg, profile=profile)
    if q == 3 and profile != 'no_cache':
        alternative = cache_order(g, plan)
        if predict(g, alternative, q, cfg)['score'] < predict(g, plan, q, cfg)['score']:
            plan = alternative
    return plan


def cache_order(g, plan):
    # Split only independent induced components inside each original block.
    # Distinct orders per core move some repeated reads after a natural earlier
    # fill; no artificial idle/delay instructions are inserted.
    blocks, owners = [], []
    for b, k in zip(plan.blocks, plan.owners):
        parts = components(g, b)
        parts.sort(key=lambda c: (min((t for u in c for t in g.inputs[u]), default=-1), min(c)))
        if parts:
            offset = k % len(parts)
            parts = parts[offset:] + parts[:offset]
        blocks.extend(parts); owners.extend([k] * len(parts))
    return normalize(g, Plan(blocks, owners, plan.cores))


def refine(g, plan, q, cfg, profile='balanced', max_proposals=16, seconds=3.):
    """Deterministic bounded neighbourhood optimization; returns a proxy winner.

    Feasibility is maintained at quotient/core-order level, not asserted for
    Step3's final execution graph. Never claims an official improvement.
    """
    start = time.monotonic()
    weights = dict(memory_weight=1. if profile == 'spill' else .15, cache=profile != 'no_cache')
    if profile == 'no_memory':
        weights['memory_weight'] = 0.
    best, score = plan, predict(g, plan, q, cfg, **weights)
    mapping = {u: s for s, b in enumerate(plan.blocks) for u in b}
    owner = {u: plan.owners[mapping[u]] for u in g.ids}
    edges = sorted([(cfg['cross_core_copy_delay_cycles'] + 2 * size / cfg['bandwidth'], mapping[u], mapping[v])
                    for v in g.ids for u, size in g.retained[v].items() if owner[u] != owner[v]], reverse=True)
    proposals = [cache_order(g, plan)] if q == 3 or profile == 'spill' else []
    for _, a, b in edges[:8]:
        for moving, target in ((b, plan.owners[a]), (a, plan.owners[b])):
            ks = list(plan.owners); ks[moving] = target
            proposals.append(Plan([list(x) for x in plan.blocks], ks, plan.cores))
    load = [sum(g.cost[u] for i, b in enumerate(plan.blocks) if plan.owners[i] == k for u in b) for k in range(plan.cores)]
    heavy = max(range(plan.cores), key=lambda k: load[k])
    light = min(range(plan.cores), key=lambda k: (load[k], k))
    for i in sorted(range(len(plan.blocks)), key=lambda i: (-sum(g.cost[u] for u in plan.blocks[i]), i))[:4]:
        ks = list(plan.owners); ks[i] = light if plan.owners[i] == heavy else heavy
        proposals.append(Plan([list(x) for x in plan.blocks], ks, plan.cores))
    merges=0
    for i in range(len(plan.blocks) - 1):
        if merges>=4: break
        if plan.owners[i] == plan.owners[i + 1]:
            proposals.append(Plan(plan.blocks[:i] + [plan.blocks[i] + plan.blocks[i + 1]] + plan.blocks[i + 2:],
                                  plan.owners[:i] + plan.owners[i + 1:], plan.cores))
            merges+=1
    if q == 3 or profile in ('cache', 'spill'):
        # Reverse independently ordered groups as a deterministic order alternative;
        # normalize rejects order choices that conflict with dependencies.
        proposals.insert(0, Plan(list(reversed(plan.blocks)), list(reversed(plan.owners)), plan.cores))
    tested, seen = 0, {plan.key()}
    for candidate in proposals:
        if tested >= max_proposals or time.monotonic() - start >= seconds:
            break
        try:
            candidate = normalize(g, candidate)
        except ValueError:
            continue
        if candidate.key() in seen:
            continue
        seen.add(candidate.key()); tested += 1
        value = predict(g, candidate, q, cfg, **weights)
        if value['score'] < score['score']:
            best, score = candidate, value
    return best, dict(proposals=tested, seconds=time.monotonic() - start,
                      surrogate=score, official_improvement_claimed=False)


def window_optimize(g, parent, q, cfg, width=3, node_limit=200, seconds=2.):
    """Restricted integer B&B; relaxed remaining Pipe loads bound each subtree.

    Fixed block membership/order; only up to width core assignments may change.
    Optimality, when exhaustive=True, is ONLY within this surrogate subproblem.
    """
    start = time.monotonic()
    best, best_score = parent, predict(g, parent, q, cfg)['score']
    chosen = sorted(range(len(parent.blocks)), key=lambda i: (-sum(g.cost[u] for u in parent.blocks[i]), i))[:width]
    chosen_set = set(chosen)
    work = [_work(g, b) for b in parent.blocks]
    load = [{p: 0. for p in PIPES} for _ in range(parent.cores)]
    for i, k in enumerate(parent.owners):
        if i not in chosen_set:
            for p in PIPES:
                load[k][p] += work[i][p]
    states, leaves, exhausted = 0, 0, True
    owners = list(parent.owners)
    def visit(depth):
        nonlocal states, leaves, exhausted, best, best_score
        if states >= node_limit or time.monotonic() - start >= seconds:
            exhausted = False; return
        states += 1
        remaining = chosen[depth:]
        bound = max(max(x.values()) for x in load)
        for p in PIPES:
            bound = max(bound, (sum(x[p] for x in load) + sum(work[i][p] for i in remaining)) / parent.cores)
        if bound >= best_score:
            return
        if depth == len(chosen):
            leaves += 1
            try:
                candidate = normalize(g, Plan(parent.blocks, list(owners), parent.cores))
                score = predict(g, candidate, q, cfg)['score']
                if score < best_score:
                    best, best_score = candidate, score
            except ValueError:
                pass
            return
        i = chosen[depth]
        for k in sorted(range(parent.cores), key=lambda k: (max(load[k][p] + work[i][p] for p in PIPES), k)):
            owners[i] = k
            for p in PIPES: load[k][p] += work[i][p]
            visit(depth + 1)
            for p in PIPES: load[k][p] -= work[i][p]
            if not exhausted: break
    visit(0)
    return best, dict(states=states, leaves=leaves, exhaustive=exhausted,
                      scope='fixed blocks/order, selected assignments, surrogate objective only', seconds=time.monotonic()-start)
