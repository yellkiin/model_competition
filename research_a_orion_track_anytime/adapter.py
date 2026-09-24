"""Independent solver adapter; upstream source and official functions stay intact.

The parent process owns a hard deadline covering imports, construction, scoring
and I/O. The child uses only its own locally computed monotonic deadline.
"""
from __future__ import annotations
from collections import deque
from pathlib import Path
import argparse
import json
import time
import traceback
from .storage import read, write, plan_key, incumbent_from_job
from .selector import select_candidate, selection_details, family_statistics, stop_reason
from .plugin import propose


def _frontier(g, n, cfg, q):
    """The SAME upstream partition/mapping primitives, evaluated lazily."""
    from research_a_orion_anytime.core import map_groups, plan_view, make_plan, partition, one_core
    from research_a_orion_anytime.strategies import candidate
    roots = map_groups(g, g.components, n, cfg, q)
    yield candidate(g, cfg, q, roots, 'component_order', 'frontier')
    mapping, _, owner, _ = plan_view(g, roots)
    packed = [{u for u in g.ops if owner[mapping[u]] == k} for k in range(n)]
    yield candidate(g, cfg, q, make_plan(packed, list(range(n)), n), 'component_pack', 'frontier')
    for grain in (2, 4, 8):
        yield candidate(g, cfg, q, map_groups(g, partition(g, n, cfg, q, grain), n, cfg, q),
                        f'frontier_g{grain}', 'frontier')
    if q == 3:
        phase = dict(node_to_subgraph=dict(roots['node_to_subgraph']),
                     core_schedules=[list(s) for s in roots['core_schedules']])
        for k, seq in enumerate(phase['core_schedules']):
            if seq:
                offset = k % len(seq)
                phase['core_schedules'][k] = seq[offset:] + seq[:offset]
        yield candidate(g, cfg, q, phase, 'fifo_phase_order', 'frontier')
    yield candidate(g, cfg, q, one_core(g, n), 'single_core_fallback', 'frontier')


def _family(value):
    return value if value.startswith('anytime/') else 'anytime/' + value


def solve(request):
    from research_a_orion_anytime.engine import OfficialSession
    from research_a_orion_anytime.core import bounds, plan_view, fingerprint, neighbours
    from research_a_orion_anytime.strategies import stage_candidates, fine_candidates, mutations, joint_window, memory_window_order
    out = Path(request['job'])
    out.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    deadline = started + request['seconds']
    q, n = request['q'], request['n']
    state = dict(case=request['case'], q=q, n=n, identity=request['identity'],
                 status='initializing', attempts=[], incumbent=None, evaluations=0,
                 phase='initialization', construction_errors=[], stopped=None,
                 method=request['method'], source='unchanged original official evaluator')
    costs = dict(initialization_seconds=0.0, candidate_generation_seconds=0.0,
                 official_eval_seconds=0.0, io_seconds=0.0)
    constructive_seconds = 0.0
    calls = 0
    def checkpoint():
        state.update(elapsed_seconds=time.monotonic()-started, evaluations=calls, costs=dict(costs),
                     construction_seconds=constructive_seconds)
        st = time.monotonic()
        write(out/'progress.json', state)
        costs['io_seconds'] += time.monotonic()-st
    checkpoint()
    session = OfficialSession(request['official'], request['graph'], request['config'])
    g, cfg = session.graph, session.cfg
    lower = bounds(g, cfg, n, q)['global_lower']
    state['global_lower'] = lower
    best, history, seen = None, [], set()
    seed = request.get('seed_job')
    if seed:
        best, prior = incumbent_from_job(seed)
        if (prior['q'], prior['n'], prior['case']) != (q, n, request['case']):
            raise ValueError('Seed case/question/core mismatch')
        if best:
            # The controller admits only a same-context, already validated seed.
            write(out/'incumbents/seed_plan.json', best['plan'])
            write(out/'incumbents/seed_result.json.gz', best['response'])
            state['incumbent'] = dict(best['meta'], plan_file='incumbents/seed_plan.json',
                                      result_file='incumbents/seed_result.json.gz',
                                      elapsed_seconds=0.0, from_seed=True)
            seen.add(plan_key(best['plan']))
            state['first_valid_seconds'] = 0.0
            state['inherited_first_valid'] = True
            for row in prior.get('attempts', []):
                if row.get('status') not in ('ok', 'error', 'audit_failed', 'timeout', 'interrupted_by_budget'):
                    continue
                inherited = dict(row, family=_family(row.get('family', 'frontier')),
                                 time_source='historical')
                # Historical seconds never silently become this machine's timing model.
                history.append(inherited)
            history.append(dict(status='ok', family='anytime/seed', makespan=best['official_result']['makespan'],
                                proxy=None, time_source='historical'))
    costs['initialization_seconds'] = max(0.0, time.monotonic()-started-costs['io_seconds'])
    streams = deque([('frontier', iter(_frontier(g, n, cfg, q)))])
    pool, queued, generation_cost = [], set(), {}
    expanded, rounds, last_fifo_source = False, 0, None
    fifo_enabled = request['method'] == 'combined'

    def add_streams():
        nonlocal expanded, last_fifo_source
        if not expanded and best:
            streams.extend([('stage', iter(stage_candidates(g, n, cfg, q))),
                            ('finer', iter(fine_candidates(g, n, cfg, q)))])
            expanded = True
        if fifo_enabled and best:
            source = plan_key(best['plan'])
            if source != last_fifo_source:
                streams.appendleft(('fifo', iter(propose(g, n, cfg, q, best, history, deadline))))
                last_fifo_source = source

    def generate_one():
        nonlocal constructive_seconds
        def charge_generation(name, elapsed):
            nonlocal constructive_seconds
            costs['candidate_generation_seconds'] += elapsed
            if name in ('frontier', 'stage', 'finer'):
                constructive_seconds += elapsed
        while streams and time.monotonic() < deadline:
            name, stream = streams.popleft()
            remaining = deadline-time.monotonic()
            estimated_eval = family_statistics(history)['_default']['predicted_seconds']
            if best and generation_cost.get(name, 0) + estimated_eval + .05 > remaining:
                state.setdefault('generation_not_admitted', []).append(name)
                continue
            state['phase'] = 'candidate_generation:' + name
            checkpoint()
            before = time.monotonic()
            try:
                c = next(stream)
                streams.append((name, stream))
            except StopIteration:
                charge_generation(name, time.monotonic()-before)
                continue
            except Exception as exc:
                state['construction_errors'].append(dict(family=name, error=str(exc)))
                charge_generation(name, time.monotonic()-before)
                continue
            elapsed = time.monotonic()-before
            charge_generation(name, elapsed)
            generation_cost[name] = max(generation_cost.get(name, 0), elapsed)
            try:
                plan_view(g, c['plan'])
                key = plan_key(c['plan'])
                if key in seen or key in queued:
                    state['duplicate_candidates'] = state.get('duplicate_candidates', 0)+1
                    return False
                c['family'] = _family(c.get('family', 'frontier'))
                c['generation_seconds'] = elapsed
                if best and c['bounds']['candidate_lower'] > best['official_result']['makespan']:
                    state['attempts'].append(dict(status='certified_pruned', name=c['name'], family=c['family'],
                                                  plan_hash=fingerprint(c['plan']), lower=c['bounds']['candidate_lower']))
                    seen.add(key)
                    return False
                queued.add(key)
                pool.append(c)
                return True
            except Exception as exc:
                state['construction_errors'].append(dict(family=name, error=str(exc)))
                return False
        return False

    checkpoint()
    while time.monotonic() < deadline and calls < request.get('max_evaluations', 64):
        best_time = best['official_result']['makespan'] if best else None
        reason = stop_reason(history, best_time, lower, request.get('gap_tolerance', .005),
                             request.get('stagnation_calls', 12), request.get('minimum_calls', 16))
        if reason == 'stagnation_heuristic_not_optimality':
            statistics_now = family_statistics(history)
            untried_pool = any(statistics_now.get(c['family'], {}).get('calls', 0) == 0 for c in pool)
            constructive_pending = any(name in ('frontier', 'stage', 'finer') for name, _ in streams)
            if untried_pool or constructive_pending:
                reason = None
                state['stagnation_deferred_for_family_coverage'] = True
        if reason:
            state['stopped'] = reason
            break
        add_streams()
        # First feasible candidate is scored immediately; later lookahead is bounded.
        lookahead = 1 if best is None else 2
        for _ in range(lookahead):
            if len(pool) < 6:
                generate_one()
        if not pool:
            if streams:
                continue  # Every pass consumed a real candidate or an exhausted stream.
            if best is None or rounds >= 4:
                state['stopped'] = 'finite_candidate_space_exhausted'
                break
            rounds += 1
            def local_stream(parent=best, round_no=rounds):
                yield from neighbours(g, parent['plan'], cfg, q, parent['official_result'], limit=12)
                yield from mutations(g, parent['plan'], cfg, q, parent['official_result'], round_no)
                yield from joint_window(g, parent['plan'], cfg, q, parent['official_result'], round_no)
                c = memory_window_order(g, parent['plan'], cfg, q, round_no)
                if c is not None:
                    yield c
            streams.append(('upstream_local', iter(local_stream())))
            continue
        remaining = deadline-time.monotonic()
        index = select_candidate(pool, history, remaining)
        if index is None:
            state['stopped'] = 'no_candidate_fits_remaining_estimated_time'
            break
        detail = selection_details(pool, history, remaining)[index]
        c = pool.pop(index)
        key = plan_key(c['plan'])
        queued.discard(key)
        seen.add(key)
        if best and c['bounds']['candidate_lower'] > best['official_result']['makespan']:
            state['attempts'].append(dict(status='certified_pruned', name=c['name'], family=c['family'],
                                          plan_hash=fingerprint(c['plan']), lower=c['bounds']['candidate_lower']))
            continue
        calls += 1
        attempt_started = time.monotonic()
        relative = f'attempts/{calls:04d}'
        plan_path, result_path = relative+'_plan.json', relative+'_response.json.gz'
        row = dict(index=calls, name=c['name'], family=c['family'], status='running',
                   plan_hash=fingerprint(c['plan']), plan_file=plan_path, result_file=result_path,
                   proxy=c['proxy'].get('score'), generation_seconds=c['generation_seconds'],
                   started_seconds=time.monotonic()-started, time_source='local', selection=detail)
        state['attempts'].append(row)
        before = time.monotonic()
        write(out/plan_path, c['plan'])
        costs['io_seconds'] += time.monotonic()-before
        state['phase'] = 'official_evaluation'
        checkpoint()
        before = time.monotonic()
        try:
            response = session.evaluate(c['plan'], q)
        except Exception as exc:
            response = dict(status='error', error=str(exc), traceback=traceback.format_exc())
        spent = time.monotonic()-before
        costs['official_eval_seconds'] += spent
        row.update(status=response['status'], eval_seconds=spent,
                   original_eval_seconds=response.get('eval_seconds'),
                   completed_seconds=time.monotonic()-started)
        before = time.monotonic()
        write(out/result_path, response)
        costs['io_seconds'] += time.monotonic()-before
        if response['status'] == 'ok':
            raw = response['official_result']
            score = (raw['makespan'], raw['data_movement_bytes']['added_copy_bytes'])
            previous = ((best['official_result']['makespan'], best['official_result']['data_movement_bytes']['added_copy_bytes'])
                        if best else (float('inf'), float('inf')))
            row.update(makespan=score[0], added_copy_bytes=score[1], improved=score < previous, improved_makespan=score[0] < previous[0])
            if score < previous:
                meta = dict(makespan=score[0], added_copy_bytes=score[1], plan_hash=row['plan_hash'],
                            plan_file=plan_path, result_file=result_path, elapsed_seconds=row['completed_seconds'])
                best = dict(plan=c['plan'], official_result=raw, response=response, meta=meta)
                state['incumbent'] = meta
                state.setdefault('first_valid_seconds', row['completed_seconds'])
                # Persist before generating any next neighbourhood.
                checkpoint()
        row['wall_seconds'] = time.monotonic()-attempt_started
        history.append(dict(row))
        state['phase'] = 'selection'
        checkpoint()
    state['stopped'] = state['stopped'] or ('evaluation_cap' if calls >= request.get('max_evaluations', 64) else 'local_deadline')
    state['status'] = 'ok' if best else 'no_valid_solution'
    state['phase'] = 'stopped'
    state['family_statistics'] = family_statistics(history)
    costs['selection_other_seconds'] = max(0.0, time.monotonic()-started-sum(costs.values()))
    checkpoint()
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('request')
    args = parser.parse_args()
    request = read(args.request)
    try:
        if request['method'] == 'old':
            from research_a_orion_anytime.solver import solve as original_solve
            original_solve(request)
        else:
            solve(request)
    except BaseException as exc:
        write(Path(request['job'])/'worker_error.json', dict(error=str(exc), traceback=traceback.format_exc()))
        raise


if __name__ == '__main__':
    main()
