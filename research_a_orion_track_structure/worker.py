"""Private execution adapter. Shared solver and official files are never edited."""
from __future__ import annotations
import argparse
from copy import deepcopy
import gzip
import json
import math
from pathlib import Path
import time
import traceback
from research_a_orion_anytime.core import Graph, bounds, constructors, one_core, plan_view
from research_a_orion_anytime.engine import OfficialSession
from research_a_orion_anytime.worker import atomic_json
from .plugin import pad_plan, propose


def read(path):
    p = Path(path)
    if p.suffix == '.gz':
        with gzip.open(p, 'rt', encoding='utf8') as f:
            return json.load(f)
    return json.loads(p.read_text(encoding='utf-8-sig'))


def compressed(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + '.tmp')
    with gzip.open(tmp, 'wt', encoding='utf8', compresslevel=3) as f:
        json.dump(value, f, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    tmp.replace(p)


def solve_structure(req):
    out = Path(req['job'])
    out.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    deadline = start + req['seconds']
    q, n = req['q'], req['n']
    state = dict(status='initializing', q=q, n=n, case=req['case'], attempts=[],
                 incumbent=None, construction_errors=[], candidate_generation_seconds=0.0,
                 evaluations=0, identity=req['identity'])
    def save():
        state['elapsed_seconds'] = time.monotonic() - start
        atomic_json(out / 'progress.json', state)
    save()
    session = OfficialSession(req['official'], req['graph'], req['config'])
    g, cfg = session.graph, session.cfg
    context, seen = {}, set()
    best_score = (math.inf, math.inf)
    state['construction_seconds'] = time.monotonic() - start
    def proposals():
        if req.get('fixed_plan'):
            yield dict(name='same_plan_replay', family='fixed', plan=read(req['fixed_plan']))
            return
        if q == 0:
            yield dict(name='original_singlecore', family='singlecore', plan=one_core(g, 1))
            return
        if req.get('seed_plan'):
            yield dict(name='seed_revalidated_at_target', family='structure/effective_cores',
                       plan=pad_plan(read(req['seed_plan']), n))
        # Structural work precedes an expensive monolithic fallback evaluation.
        yield from propose(g, n, cfg, q, context, state['attempts'], deadline)
        if time.monotonic() < deadline:
            for c in constructors(g, n, cfg, q, diagnostics=state['construction_errors'])[:3]:
                yield {**c, 'name': 'fallback_' + c['name'], 'family': 'legacy_fallback'}
    stream = iter(proposals())
    save()
    while state['evaluations'] < req['max_evaluations'] and time.monotonic() < deadline:
        generated = time.monotonic()
        try:
            c = next(stream)
        except StopIteration:
            state['stopped'] = 'finite_candidate_pool_exhausted'
            break
        except Exception as e:
            state['construction_errors'].append(dict(error=str(e), traceback=traceback.format_exc()))
            state['stopped'] = 'generation_error'
            break
        generation = time.monotonic() - generated
        state['candidate_generation_seconds'] += generation
        if time.monotonic() >= deadline:
            state['stopped'] = 'deadline_after_generation'
            break
        plan = c['plan']
        plan_view(g, plan)
        key = (tuple(sorted((int(u), s) for u, s in plan['node_to_subgraph'].items())),
               tuple(tuple(x) for x in plan['core_schedules']))
        if key in seen:
            state['attempts'].append(dict(name=c['name'], status='duplicate', generation_seconds=generation))
            save()
            continue
        seen.add(key)
        cert = c.get('bounds') or bounds(g, cfg, n, max(1, q), plan)
        if cert['candidate_lower'] > best_score[0]:
            state['attempts'].append(dict(name=c['name'], status='certified_pruned',
                                         lower=cert['candidate_lower'], generation_seconds=generation))
            save()
            continue
        state['evaluations'] += 1
        i = state['evaluations']
        pn, rn = f'attempts/e{i:04d}_plan.json', f'attempts/e{i:04d}_result.json.gz'
        row = dict(index=i, name=c['name'], family=c['family'], status='running',
                   generation_seconds=generation, started_seconds=time.monotonic()-start,
                   plan_file=pn, result_file=rn, proxy=c.get('proxy', {}).get('score'))
        state['attempts'].append(row)
        atomic_json(out / pn, plan)
        save()
        evaluated = time.monotonic()
        try:
            result = session.evaluate(plan, q)
            compressed(out / rn, result)
            row.update(status=result['status'], eval_seconds=result['eval_seconds'])
            if result['status'] == 'ok':
                raw = result['official_result']
                score = (raw['makespan'], raw['data_movement_bytes']['added_copy_bytes'])
                row.update(makespan=score[0], added_copy_bytes=score[1], improved=score < best_score)
                if score < best_score:
                    best_score = score
                    state['incumbent'] = dict(name=c['name'], makespan=score[0], added_copy_bytes=score[1],
                        plan_file=pn, result_file=rn, elapsed_seconds=time.monotonic()-start,
                        evaluation=i, certificate=result['audit']['certificate'])
                    context.update(plan=plan, official_result=raw)
            else:
                row['audit_errors'] = result['audit']['errors']
        except Exception as e:
            row.update(status='error', error=str(e), traceback=traceback.format_exc())
            atomic_json(out / f'attempts/e{i:04d}_error.json', row)
        row['completed_seconds'] = time.monotonic() - start
        row['wall_seconds'] = time.monotonic() - evaluated
        row['best_makespan'] = best_score[0] if math.isfinite(best_score[0]) else None
        save()
        if q == 0 or req.get('fixed_plan'):
            state['stopped'] = 'single_official_evaluation'
            break
    state['status'] = 'ok' if state['incumbent'] else 'no_valid_solution'
    state.setdefault('stopped', 'evaluation_cap' if state['evaluations'] >= req['max_evaluations'] else 'time_budget')
    save()
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('request')
    req = read(parser.parse_args().request)
    try:
        from research_a_orion_anytime.solver import solve
        if req['method'] == 'old':
            state = solve(req)
        else:
            started = time.monotonic()
            legacy = False
            routing = {}
            if req['q'] > 0 and not req.get('seed_plan') and not req.get('fixed_plan'):
                graph = Graph(read(req['graph']))
                largest = max((graph.weight(c) for c in graph.components), default=0)
                balanced = graph.weight(graph.ops) / req['n']
                legacy = len(graph.components) > 1 and largest <= balanced
                routing = dict(largest_component_work=largest, balanced_work=balanced,
                               policy='component_granularity_gate', route='legacy' if legacy else 'structure')
                del graph
            routing['seconds'] = time.monotonic() - started
            atomic_json(Path(req['job']) / 'routing.json', routing)
            inner = deepcopy(req)
            inner['seconds'] = max(.001, req['seconds'] - routing['seconds'])
            state = solve(inner) if legacy else solve_structure(inner)
        return 0 if state.get('incumbent') else 1
    except Exception as e:
        atomic_json(Path(req['job']) / 'worker_error.json', dict(error=str(e), traceback=traceback.format_exc()))
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
