"""CPU experiment driver. Run: python -m research_a.run --help"""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import itertools
from pathlib import Path
import platform
import random
import sys
from .model import Graph, Plan, cut_order, read_json, write_json, settings
from .solver import PROFILES, assign, search
from .evaluator import Official

ROOT = Path(__file__).resolve().parents[1]


def attachment():
    found = sorted((ROOT / '题目' / 'A题').glob('*附件'))
    if len(found) != 1:
        raise FileNotFoundError('Use --code and --config to identify the official A attachment')
    return found[0]


def selected(manifest, split):
    return [c for c in manifest['cases'] if split == 'all' or c['split'] == split]


def prepare(args):
    data = Path(args.data) if args.data else attachment() / 'data'
    paths = sorted(data.glob('case_*.json'))
    if len(paths) != args.expected:
        raise ValueError(f'Expected {args.expected} case_*.json files, found {len(paths)}')
    cases = []
    for path in paths:
        try:
            features = Graph(read_json(path)).features()
        except ValueError as exc:
            raise ValueError(f'{path}: unable to read graph JSON; restore A LFS data with git lfs pull') from exc
        cases.append(dict(case=path.stem, path=str(path.resolve()), features=features, split='eval'))
    # Deterministic complexity-stratified development selection. No performance labels.
    ranked = sorted(cases, key=lambda c: (c['features']['ops'], c['features']['parallelism'], c['case']))
    dev_count = min(args.dev_count, max(0, len(cases) - 1))
    for j in range(dev_count):
        ranked[int((j + .5) * len(ranked) / dev_count)]['split'] = 'dev'
    value = dict(cases=cases, expected=len(paths), dev_count=dev_count,
                 note='All-case score is descriptive; eval subset was not used for profile selection')
    write_json(Path(args.out), value)
    print(f'{args.out}: {len(cases)} cases, {dev_count} development cases')


def one_case(job):
    """A worker owns all selected Q/core/profile/seed jobs for one graph."""
    case, options = job
    graph_path = Path(case['path'])
    graph = Graph(read_json(graph_path))
    cfg = settings(Path(options['config']))
    graph_features = graph.features()
    case_dir = Path(options['out']) / case['case']
    case_dir.mkdir(parents=True, exist_ok=True)
    base_file = case_dir / 'baseline.json'
    if options['resume'] and base_file.exists():
        baseline = read_json(base_file)
    else:
        baseline, raw = Official(options['code'], options['config'], graph_path, case_dir / 'baseline', options['timeout']).evaluate()
        write_json(base_file, baseline)
    for question, cores, variant, seed in itertools.product(options['questions'], options['cores'], options['variants'], options['seeds']):
        if variant == 'no_cache' and question != 3:
            continue
        if variant == 'rr' and seed != options['seeds'][0]:
            continue
        directory = case_dir / f'q{question}_n{cores}_{variant}_s{seed}'
        result_path = directory / 'search.json'
        if options['resume'] and result_path.exists() and read_json(result_path).get('complete'):
            continue
        # Keep partial attempts; a new attempt starts the deterministic optimization anew.
        if directory.exists() and any(directory.iterdir()):
            i = 1
            while (directory.parent / (directory.name + f'_attempt{i}')).exists():
                i += 1
            directory.rename(directory.parent / (directory.name + f'_attempt{i}'))
        evaluator = Official(options['code'], options['config'], graph_path, directory, options['timeout'])
        result = search(graph, cfg, lambda p: evaluator.evaluate(p, question), directory,
                        question, cores, variant, options['budget'], seed, options['pool'],
                        memory_weight=options['memory_weight'])
        result.update(case=case['case'], split=case['split'], graph_path=str(graph_path), features=graph_features,
                      baseline_status=baseline['status'], singlecore_makespan=baseline.get('makespan'),
                      speedup=(baseline['makespan'] / result['best_makespan'])
                      if baseline['status'] == 'ok' and result['status'] == 'ok' else None,
                      complete=True)
        if options['trace'] and result['status'] == 'ok':
            plan = Plan.load(read_json(directory / 'best_plan.json'), graph)
            replay, _ = evaluator.evaluate(plan, question, trace=True)
            result['trace_replay'] = replay
        write_json(result_path, result)
    return case['case']


def run(args):
    manifest = read_json(Path(args.manifest))
    cases = selected(manifest, args.split)
    if not cases:
        raise ValueError('Selected split is empty')
    options = {k: v for k, v in vars(args).items() if k != 'func'}
    options['code'] = str(Path(args.code).resolve()) if args.code else str(attachment() / 'code')
    options['config'] = str(Path(args.config).resolve()) if args.config else str(attachment() / 'data' / 'config.txt')
    options['out'] = str(Path(args.out).resolve())
    spec = {k: v for k, v in options.items() if k not in ('func', 'resume', 'workers', 'trace')}
    spec.update(config_values=settings(Path(options['config'])), cases=[c['case'] for c in cases],
                case_splits={c['case']: c['split'] for c in cases}, case_paths={c['case']: c['path'] for c in cases},
                python=platform.python_version(), execution='CPU; official evaluator subprocesses')
    out = Path(options['out'])
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'run.json').exists():
        previous = read_json(out / 'run.json')
        if not args.resume or previous != spec:
            raise ValueError('Existing run differs or --resume was not supplied. Choose a new --out.')
    write_json(out / 'run.json', spec)
    jobs = [(case, options) for case in cases]
    if args.workers == 1:
        for i, job in enumerate(jobs, 1):
            print(f'[{i}/{len(jobs)}] {one_case(job)}', flush=True)
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(one_case, job) for job in jobs]
            for i, future in enumerate(as_completed(futures), 1):
                print(f'[{i}/{len(jobs)}] {future.result()}', flush=True)


def cross(args):
    """3x3 same-plan replay; not merely Q2-best versus Q3-best."""
    source, out = Path(args.source), Path(args.out)
    spec = read_json(source / 'run.json')
    cross_spec = dict(source=str(source.resolve()), cores=args.cores, seeds=args.seeds, variant=args.variant)
    previous = {}
    if out.exists():
        if not args.resume or read_json(out / 'cross_spec.json') != cross_spec:
            raise FileExistsError('Use a new --out or resume the same cross experiment')
        previous = {(r['case'], r['cores'], r['seed'], r['origin'], r['target']): r for r in (read_json(out / 'cross.json') if (out / 'cross.json').exists() else [])}
    write_json(out / 'cross_spec.json', cross_spec)
    rows = []
    for case in spec['cases']:
        for cores, seed, origin, target in itertools.product(args.cores, args.seeds, (1, 2, 3), (1, 2, 3)):
            key = (case, cores, seed, origin, target)
            if key in previous:
                rows.append(previous[key])
                continue
            directory = source / case / f'q{origin}_n{cores}_{args.variant}_s{seed}'
            record = dict(case=case, cores=cores, seed=seed, origin=origin, target=target,
                          variant=args.variant, status='missing_source', makespan=None)
            if (directory / 'best_plan.json').exists():
                saved = read_json(directory / 'search.json')
                graph_path = Path(saved['graph_path'])
                if origin == target:
                    record.update(read_json(directory / 'best_metrics.json'), replay=False)
                else:
                    graph = Graph(read_json(graph_path))
                    plan = Plan.load(read_json(directory / 'best_plan.json'), graph)
                    evaluator = Official(spec['code'], spec['config'], graph_path,
                        out / case / f'n{cores}_s{seed}_p{origin}_e{target}', args.timeout)
                    score, raw = evaluator.evaluate(plan, target, trace=args.trace)
                    record.update(score, replay=True)
            rows.append(record)
            write_json(out / 'cross.json', rows)
    print(out / 'cross.json')


def granularity(args):
    manifest = read_json(Path(args.manifest))
    code = Path(args.code) if args.code else attachment() / 'code'
    config = Path(args.config) if args.config else attachment() / 'data' / 'config.txt'
    out = Path(args.out)
    if out.exists():
        raise FileExistsError(out)
    rows = []
    for case in selected(manifest, args.split):
        graph = Graph(read_json(Path(case['path'])))
        seen = set()
        for cores, question, factor in itertools.product(args.cores, args.questions, args.factors):
            count = min(len(graph.ids), max(1, round(factor * cores)))
            if (cores, question, count) in seen:
                continue
            seen.add((cores, question, count))
            blocks = cut_order(graph, graph.order, count)
            plan = assign(graph, blocks, cores, cores, question, 'rr')
            directory = out / case['case'] / f'q{question}_n{cores}_g{count}'
            evaluator = Official(code, config, Path(case['path']), directory, args.timeout)
            score, raw = evaluator.evaluate(plan, question)
            write_json(directory / 'plan.json', plan.json())
            rows.append(dict(case=case['case'], cores=cores, question=question,
                             requested_groups=count, actual_groups=len(blocks), **score))
            write_json(out / 'granularity.json', rows)
    print(out / 'granularity.json')


def oracle(args):
    """Exact only within fixed-topology, contiguous-block, monotone-core-order family."""
    graph_path, out = Path(args.graph), Path(args.out)
    graph = Graph(read_json(graph_path))
    n = len(graph.ids)
    total = args.cores * (1 + args.cores) ** max(0, n - 1)
    if n < 1 or n > 8 or total > args.limit:
        raise ValueError(f'Restricted enumeration has {total} plans; use <=8 ops and increase --limit explicitly')
    if out.exists():
        raise FileExistsError(out)
    code = Path(args.code) if args.code else attachment() / 'code'
    config = Path(args.config) if args.config else attachment() / 'data' / 'config.txt'
    evaluator = Official(code, config, graph_path, out, args.timeout)
    count, failed, best = 0, 0, None
    for mask in range(1 << (n - 1)):
        blocks, current = [], []
        for i, u in enumerate(graph.order):
            current.append(u)
            if i == n - 1 or mask & (1 << i):
                blocks.append(current)
                current = []
        for owners in itertools.product(range(args.cores), repeat=len(blocks)):
            plan = Plan(blocks, list(owners), args.cores)
            score, raw = evaluator.evaluate(plan, args.question)
            with (out / 'oracle_trials.jsonl').open('a', encoding='utf-8') as stream:
                import json
                stream.write(json.dumps(dict(index=count, plan=plan.json(), **score), ensure_ascii=False) + '\n')
            count += 1
            failed += score['status'] != 'ok'
            if score['status'] == 'ok' and (best is None or score['makespan'] < best):
                best = score['makespan']
                write_json(out / 'best_plan.json', plan.json())
                write_json(out / 'best_result.json', raw)
    result = dict(family='fixed topological order, contiguous partitions, ascending block order per core',
                  candidates=total, evaluated=count, infeasible_or_failed=failed,
                  best_makespan=best, compute_lower_bound=graph.lower_bound(args.cores),
                  # Timeouts/errors are not proofs of mathematical infeasibility.
                  enumeration_complete=count == total, all_calls_succeeded=failed == 0,
                  optimum_claim='best observed in the enumerated family; inspect every failed call before certifying exactness')
    write_json(out / 'oracle.json', result)
    print(result)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--data'); prep.add_argument('--expected', type=int, default=100)
    prep.add_argument('--dev-count', type=int, default=20); prep.add_argument('--out', required=True)
    prep.set_defaults(func=prepare)
    main = sub.add_parser('run')
    main.add_argument('--manifest', required=True); main.add_argument('--out', required=True)
    main.add_argument('--split', choices=['all', 'dev', 'eval'], default='all')
    main.add_argument('--questions', nargs='+', type=int, choices=[1, 2, 3], default=[1, 2, 3])
    main.add_argument('--cores', nargs='+', type=int, choices=range(1, 6), default=[1, 2, 3, 4, 5])
    main.add_argument('--variants', nargs='+', choices=['rr'] + list(PROFILES), default=['rr', 'full'])
    main.add_argument('--seeds', nargs='+', type=int, default=[0])
    main.add_argument('--budget', type=int, default=32); main.add_argument('--pool', type=int, default=4)
    main.add_argument('--workers', type=int, default=2); main.add_argument('--memory-weight', type=float)
    main.add_argument('--resume', action='store_true'); main.add_argument('--trace', action='store_true')
    main.set_defaults(func=run)
    mat = sub.add_parser('cross')
    mat.add_argument('--source', required=True); mat.add_argument('--out', required=True)
    mat.add_argument('--cores', nargs='+', type=int, default=[1, 2, 3, 4, 5])
    mat.add_argument('--seeds', nargs='+', type=int, default=[0]); mat.add_argument('--variant', default='full')
    mat.add_argument('--trace', action='store_true'); mat.add_argument('--resume', action='store_true'); mat.set_defaults(func=cross)
    gran = sub.add_parser('granularity')
    gran.add_argument('--manifest', required=True); gran.add_argument('--out', required=True)
    gran.add_argument('--split', choices=['all', 'dev', 'eval'], default='dev')
    gran.add_argument('--cores', nargs='+', type=int, default=[2, 4, 5])
    gran.add_argument('--questions', nargs='+', type=int, default=[1, 2, 3])
    gran.add_argument('--factors', nargs='+', type=float, default=[.25, 1, 2, 4, 8])
    gran.set_defaults(func=granularity)
    exact = sub.add_parser('oracle')
    exact.add_argument('--graph', required=True); exact.add_argument('--out', required=True)
    exact.add_argument('--question', type=int, choices=[1, 2, 3], required=True)
    exact.add_argument('--cores', type=int, choices=[1, 2, 3], default=2)
    exact.add_argument('--limit', type=int, default=5000); exact.set_defaults(func=oracle)
    for cmd in [main, gran, exact]:
        cmd.add_argument('--code'); cmd.add_argument('--config')
    for cmd in [main, mat, gran, exact]:
        cmd.add_argument('--timeout', type=float, default=300.)
    return p


if __name__ == '__main__':
    args = parser().parse_args()
    if hasattr(args, 'workers') and args.workers < 1:
        raise SystemExit('--workers must be positive')
    args.func(args)
