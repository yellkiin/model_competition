"""One bounded real-instance job; invoked by run.py in a killable process tree."""
from __future__ import annotations
import json
import math
from pathlib import Path
import sys
import time
import traceback
from research_a.evaluator import Official
from research_a.model import Graph, Plan, settings
from .solver import construct, neighbors, proxy, relaxation_bound


def save(path: Path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temp.replace(path)


def main(request: Path):
    args = json.loads(request.read_text(encoding='utf-8'))
    out = request.parent
    started = time.perf_counter()
    deadline = started + args['job_seconds'] - 2.
    g = Graph(json.loads(Path(args['graph']).read_text(encoding='utf-8-sig')))
    cfg = settings(Path(args['config']))
    official = Official(Path(args['code']), Path(args['config']), Path(args['graph']), out / 'official')
    result = dict(case=Path(args['graph']).stem, question=args['question'], cores=args['cores'],
                  status='running', evaluations=[], incumbent=None, cache_pair=None,
                  bound=relaxation_bound(g, args['cores']),
                  bound_status='conditional_compute_relaxation_see_THEORY',
                  hardware_machine=args['machine'])
    best_plan = None
    best_key = None
    # Ordinary canonical JSON equality for candidate deduplication, no hashes.
    seen = set()

    def checkpoint():
        result['solve_seconds'] = time.perf_counter() - started
        save(out / 'result.json', result)

    def evaluate(plan, label, question):
        nonlocal best_plan, best_key
        left = deadline - time.perf_counter()
        if left <= 1.:
            return None
        if plan is not None:
            key = plan.key()
            if question == args['question'] and key in seen:
                return None
            if question == args['question']:
                seen.add(key)
            # Conversion checks coverage/order representation, not full feasibility.
            Plan.load(plan.json(), g)
        index = len(result['evaluations'])
        if plan is not None:
            save(out / f'candidate_{index:02d}.json', plan.json())
        official.timeout = min(args['eval_seconds'], max(1., left))
        metrics, raw = official.evaluate(plan, question)
        item = dict(index=index, label=label, question=question, **metrics)
        result['evaluations'].append(item)
        if raw is not None:
            save(out / f'official_{index:02d}.json', raw)
        if metrics['status'] == 'ok':
            score = float(metrics['makespan'])
            if not math.isfinite(score) or score <= 0:
                item.update(status='error', error='Official makespan must be finite and positive')
            elif question == args['question']:
                extra = float(metrics.get('partition_added_copy_bytes') or 0.) + float(metrics.get('spill_added_copy_bytes') or 0.)
                objective = (score, extra)
                if best_key is None or objective < best_key:
                    best_key, best_plan = objective, plan
                    result['incumbent'] = dict(item)
                    if plan is not None:
                        save(out / 'best_plan.json', plan.json())
                    save(out / 'best_official.json', raw)
        checkpoint()
        return item

    checkpoint()
    if args['question'] == 0:
        # Original single-core baseline, without an artificially partitioned plan.
        official.timeout = min(args['eval_seconds'], max(1., deadline - time.perf_counter()))
        metrics, raw = official.evaluate(None, 1)
        result['evaluations'].append(dict(label='original_singlecore', **metrics))
        if metrics['status'] == 'ok':
            result['incumbent'] = metrics
            save(out / 'best_official.json', raw)
        result['status'] = 'complete' if result['incumbent'] else 'failed'
        checkpoint()
        return
    q, n = args['question'], args['cores']
    search_budget = args['budget'] - (1 if q == 3 else 0)
    seeds = [('fast', lambda: construct(g, n, q, cfg)),
             ('components', lambda: construct(g, n, q, cfg, component_baseline=True)),
             ('single_fallback', lambda: Plan([list(g.order)], [0], n))]
    for label, builder in seeds:
        if len(result['evaluations']) >= search_budget or time.perf_counter() >= deadline - 1.:
            break
        try:
            plan = builder()
            key = plan.key()
            if key in seen:
                # Alias is exact plan equality, not a new evaluation.
                previous = next((x for x in result['evaluations'] if x.get('plan_key') == key), None)
                if previous:
                    result.setdefault('aliases', {})[label] = previous['index']
                continue
            item = evaluate(plan, label, q)
            if item is not None:
                item['plan_key'] = key
                checkpoint()
        except (ValueError, KeyError, TypeError) as exc:
            result.setdefault('construction_errors', []).append(dict(label=label, error=str(exc)))
            checkpoint()
    while best_plan is not None and len(result['evaluations']) < search_budget and time.perf_counter() < deadline - 1.:
        pool = []
        for candidate in neighbors(g, best_plan, cfg):
            if candidate.key() in seen:
                continue
            try:
                Plan.load(candidate.json(), g)
                prediction = proxy(g, candidate, q, cfg)
                pool.append((prediction['score'], candidate.key(), candidate, prediction))
            except (ValueError, KeyError, TypeError) as exc:
                result.setdefault('neighbor_errors', []).append(str(exc))
        if not pool:
            break
        _, _, candidate, prediction = min(pool, key=lambda x: (x[0], x[1]))
        item = evaluate(candidate, 'directed', q)
        if item is None:
            break
        item['proxy'] = prediction
        checkpoint()
    if q == 3 and best_plan is not None and len(result['evaluations']) < args['budget']:
        # Exact same selected JSON, Q2 evaluator as no-cache counterfactual.
        same = evaluate(best_plan, 'same_plan_no_cache', 2)
        if same and same['status'] == 'ok':
            result['cache_pair'] = dict(no_cache_makespan=same['makespan'],
                with_cache_makespan=result['incumbent']['makespan'],
                ratio=same['makespan'] / result['incumbent']['makespan'],
                plan_file='best_plan.json')
    if result['incumbent']:
        result['upper_bound'] = result['incumbent']['makespan']
        lb = result['bound']
        result['conditional_ratio_bound'] = result['upper_bound'] / lb if lb > 0 else None
        result['bound_violation'] = bool(lb > result['upper_bound'] + 1e-6)
    result['status'] = 'complete' if result['incumbent'] and (q != 3 or result['cache_pair']) else ('partial' if result['incumbent'] else 'failed')
    checkpoint()


if __name__ == '__main__':
    request = Path(sys.argv[1])
    try:
        main(request)
    except Exception:
        error = traceback.format_exc()
        save(request.parent / 'worker_error.json', dict(error=error))
        print(error, file=sys.stderr)
        raise SystemExit(1)
