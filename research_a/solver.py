"""Shared optimizer and executable corrective profiles for all three A questions."""
from __future__ import annotations
import random
import time
from .model import Graph, Plan, cut_order, estimate, topo, write_json

# Controlled ablations keep the same proposal operators; only score terms differ.
PROFILES = {
    'common': dict(memory_weight=0., cache_weight=0., traffic_weight=.2),
    'full': dict(memory_weight=.15, cache_weight=1., traffic_weight=.2),
    'portfolio': dict(memory_weight=.15, cache_weight=1., traffic_weight=.2),
    'unranked': dict(memory_weight=0., cache_weight=0., traffic_weight=0.),
    'no_memory': dict(memory_weight=0., cache_weight=1., traffic_weight=.2),
    'no_cache': dict(memory_weight=.15, cache_weight=0., traffic_weight=.2),
    'coarse': dict(memory_weight=.15, cache_weight=1., traffic_weight=.4),
    'fine': dict(memory_weight=.15, cache_weight=1., traffic_weight=.1),
    'locality': dict(memory_weight=.15, cache_weight=1., traffic_weight=1.2),
    'spill': dict(memory_weight=1., cache_weight=1., traffic_weight=.2),
    'cache': dict(memory_weight=.15, cache_weight=1., traffic_weight=.6),
    'critical': dict(memory_weight=.05, cache_weight=.5, traffic_weight=.02),
    'explore': dict(memory_weight=.15, cache_weight=1., traffic_weight=.2),
}


def assign(graph: Graph, blocks, cores, active, question, mode, traffic=.2, wait_difference=0.):
    load = [{p: 0. for p in graph.work} for _ in range(cores)]
    seen, owners = {}, []
    for i, block in enumerate(blocks):
        work = {p: sum(graph.cost[u] for u in block if graph.ops[u]['pipe'] == p) for p in graph.work}
        if mode == 'rr':
            k = i % active
        else:
            links = []
            for u in block:
                for t in graph.inputs[u]:
                    links.extend((seen[v], graph.tensors[t]['size'])
                                 for v in graph.ps[t] | graph.cs[t] if v in seen)
            def cost(k):
                imbalance = max(load[k][p] + work[p] for p in work)
                # Q1 same-core task placement saves wait, NOT Task-boundary COPY.
                if question == 1:
                    remote = {v for u in block for v in graph.pred[u] if v in seen and seen[v] != k}
                    return imbalance + wait_difference * len(remote), k
                return imbalance + traffic * sum(size for owner, size in links if owner != k), k
            k = min(range(active), key=cost)
        owners.append(k)
        seen.update({u: k for u in block})
        for p in work:
            load[k][p] += work[p]
    return Plan([list(b) for b in blocks], owners, cores)


def fresh(graph, cores, question, rng, profile='full', index=None, bandwidth=1., wait_difference=0.):
    if index == 0:
        return assign(graph, cut_order(graph, graph.order, cores), cores, cores, question, 'rr')
    if index == 1:
        return Plan([list(graph.order)], [0], cores)
    modes = ['critical', 'memory', 'cache', 'random']
    if profile == 'spill':
        modes = ['memory', 'memory', 'critical', 'random']
    if profile == 'cache':
        modes = ['cache', 'cache', 'critical', 'random']
    if profile == 'critical':
        modes = ['critical', 'critical', 'random']
    order = graph.ordered(rng.choice(modes), rng)
    scales = [1, 2, 4, 8, 16]
    if profile in ('coarse', 'locality'):
        scales = [1, 1, 2]
    elif profile == 'fine':
        scales = [4, 8, 16, 32]
    active = rng.randint(1, cores) if profile in ('coarse', 'locality', 'critical') else cores
    groups = max(1, active * rng.choice(scales))
    return assign(graph, cut_order(graph, order, groups), cores, active, question, 'affinity',
                  PROFILES[profile]['traffic_weight'] / bandwidth, wait_difference)


def mutate(graph, parent, rng, profile='full'):
    blocks, owners = [list(b) for b in parent.blocks], list(parent.owners)
    actions = ['merge', 'split', 'move', 'reorder', 'shift']
    if profile in ('coarse', 'locality'):
        actions += ['merge', 'merge']
    if profile in ('fine', 'spill'):
        actions += ['split', 'move']
    if profile == 'cache':
        actions += ['reorder', 'reorder']
    action = rng.choice(actions)
    if action == 'merge' and len(blocks) > 1:
        i = rng.randrange(len(blocks) - 1)
        blocks[i:i + 2] = [blocks[i] + blocks[i + 1]]
        owners[i:i + 2] = [rng.choice(owners[i:i + 2])]
    elif action == 'split' and any(len(b) > 1 for b in blocks):
        i = rng.choice([j for j, b in enumerate(blocks) if len(b) > 1])
        cut = rng.randrange(1, len(blocks[i]))
        blocks[i:i + 1] = [blocks[i][:cut], blocks[i][cut:]]
        owners[i:i + 1] = [owners[i], rng.randrange(parent.cores)]
    elif action == 'shift' and len(blocks) > 1:
        i = rng.randrange(len(blocks) - 1)
        if len(blocks[i]) > 1:
            blocks[i + 1].insert(0, blocks[i].pop())
    elif action == 'reorder':
        mapping = {u: s for s, b in enumerate(blocks) for u in b}
        pred, succ = {s: set() for s in range(len(blocks))}, {s: set() for s in range(len(blocks))}
        for u in graph.ids:
            for v in graph.succ[u]:
                a, b = mapping[u], mapping[v]
                if a != b:
                    succ[a].add(b)
                    pred[b].add(a)
        if profile == 'cache':
            # Cluster independently-ready blocks by shared tensor identity, without
            # inventing delay operations or editing the original graph.
            priority = {s: (min((t for u in b for t in graph.inputs[u]), default=-1), rng.random())
                        for s, b in enumerate(blocks)}
        else:
            priority = {s: rng.random() for s in pred}
        order = topo(pred, succ, priority)
        blocks, owners = [blocks[s] for s in order], [owners[s] for s in order]
    else:
        owners[rng.randrange(len(owners))] = rng.randrange(parent.cores)
    return Plan(blocks, owners, parent.cores)


def search(graph: Graph, cfg: dict, evaluate, directory, question: int, cores: int,
           variant='full', budget=32, seed=0, pool=4, initial=None, memory_weight=None):
    """evaluate(Plan)->(record, raw official result). Failures consume the budget.

    The first k proposals do not depend on the final budget. Every successful
    incumbent is saved immediately; a repair starts by re-evaluating its parent.
    """
    if not graph.ids:
        raise ValueError('No compute operations to partition')
    if budget < 1 or pool < 1:
        raise ValueError('budget and pool must be positive')
    directory.mkdir(parents=True, exist_ok=True)
    weights = dict(PROFILES.get(variant, PROFILES['full']))
    if memory_weight is not None:
        weights['memory_weight'] = memory_weight
    rng, seen, trials, best, best_value = random.Random(seed), set(), [], None, None
    start = time.perf_counter()
    generation_seconds = 0.
    max_trials = 1 if variant == 'rr' else budget
    for generation in range(max(50, max_trials * 40)):
        if len(trials) >= max_trials:
            break
        before = time.perf_counter()
        profile = variant if variant in PROFILES else 'full'
        if len(trials) == 0 and initial is not None:
            choices = [initial]
        elif len(trials) < 2:
            choices = [fresh(graph, cores, question, rng, profile, len(trials), cfg['bandwidth'], wait_difference=max(0, cfg['task_cross_core_wait_cycles'] - cfg['task_same_core_wait_cycles']))]
        else:
            choices = []
            for _ in range(pool):
                exploit = profile != 'portfolio' and best is not None and len(trials) >= 6 and rng.random() < (.35 if profile == 'explore' else .7)
                choices.append(mutate(graph, best, rng, profile) if exploit else fresh(graph, cores, question, rng, profile, bandwidth=cfg['bandwidth'], wait_difference=max(0, cfg['task_cross_core_wait_cycles'] - cfg['task_same_core_wait_cycles'])))
        choices = [p for p in choices if p.key() not in seen]
        if not choices:
            # An initial plan can equal RR or one-core; do not get stuck on it.
            choices = [fresh(graph, cores, question, rng, profile, bandwidth=cfg['bandwidth'], wait_difference=max(0, cfg['task_cross_core_wait_cycles'] - cfg['task_same_core_wait_cycles']))]
            choices = [p for p in choices if p.key() not in seen]
        if not choices:
            generation_seconds += time.perf_counter() - before
            continue
        candidates = [(estimate(graph, p, question, cfg, **weights), p) for p in choices]
        chosen = rng.choice(candidates) if profile == 'unranked' or rng.random() < .15 else min(candidates, key=lambda x: x[0]['score'])
        proxy, plan = chosen
        generation_seconds += time.perf_counter() - before
        seen.add(plan.key())
        record, raw = evaluate(plan)
        index = len(trials) + 1
        row = dict(evaluation=index, generation=generation, proxy_score=proxy['score'], **record)
        if record['status'] == 'ok':
            value = (record['makespan'], record.get('ddr_accounted_bytes', float('inf')))
            if best_value is None or value < best_value:
                best, best_value = plan, value
                write_json(directory / 'best_plan.json', plan.json())
                write_json(directory / 'best_result.json', raw)
                write_json(directory / 'best_proxy.json', proxy)
                write_json(directory / 'best_metrics.json', record)
        row['incumbent_makespan'] = best_value[0] if best_value else None
        row['elapsed_seconds'] = time.perf_counter() - start
        trials.append(row)
        write_json(directory / 'trajectory.json', trials)
    result = dict(status='ok' if best else 'no_valid_candidate', question=question, cores=cores,
                  variant=variant, seed=seed, budget_requested=budget, evaluations=len(trials),
                  proposal_pool=pool, generation_seconds=generation_seconds,
                  search_seconds=time.perf_counter() - start,
                  evaluation_seconds=sum(r.get('seconds', 0.) for r in trials),
                  best_makespan=best_value[0] if best_value else None,
                  compute_lower_bound=graph.lower_bound(cores), weights=weights,
                  failed_evaluations=sum(r['status'] != 'ok' for r in trials),
                  initial_plan_provided=initial is not None,
                  active_cores=len(set(best.owners)) if best else None)
    write_json(directory / 'search.json', result)
    return result
