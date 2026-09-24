"""Bounded runs, isolated official evaluations, resumable records and sharding."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, replace
import csv
import hashlib
import json
import os
import platform
from pathlib import Path
import statistics
import subprocess
import sys
import time
import traceback
from .core import Config, Graph, constructors, neighbours, fingerprint, bounds, one_core, estimate
from .worker import atomic_json

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parent


def read_json(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def file_hash(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def source_hash(directory):
    return fingerprint({p.name: file_hash(p) for p in sorted(Path(directory).glob('*.py'))})


def locate_official(value=None):
    if value:
        root = Path(value).resolve()
    else:
        matches = list((ROOT / '题目' / 'A题').glob('*附件'))
        if len(matches) != 1:
            raise FileNotFoundError('Cannot locate A attachment. Supply --official <attachment directory>.')
        root = matches[0]
    config = next((p for p in [root / 'data/config.txt', root / 'config.txt'] if p.is_file()), None)
    if config is None or not (root / 'code/evaluation_validation.py').is_file():
        raise FileNotFoundError(f'Incomplete original A attachment: {root}')
    return root, config


def prepare_context(official, config, graph_path, options):
    return {'algorithm_sha256': source_hash(PACKAGE), 'official_sha256': source_hash(official / 'code'),
            'graph_sha256': file_hash(graph_path), 'config_sha256': file_hash(config),
            'policy': options, 'python_major_minor': list(sys.version_info[:2])}


def evaluate(official, config, graph_path, plan, q, out, identity, deadline, timeout,
             overrides=None):
    """A timeout kills the evaluator child. No shell, grandchildren or hidden workers."""
    key = fingerprint({'source': identity, 'q': q, 'plan': plan, 'overrides': overrides})
    folder = out / 'evaluations' / key
    response_path = folder / 'response.json'
    if response_path.is_file():
        prior = read_json(response_path)
        if prior.get('status') == 'ok':
            return {**prior, 'cache_reused': True, 'record': str(response_path), 'evaluation_key': key}
    remaining = deadline - time.monotonic()
    if remaining <= .1:
        return {'status': 'not_started_budget', 'evaluation_key': key}
    folder.mkdir(parents=True, exist_ok=True)
    if response_path.is_file():
        stamp = str(time.time_ns())
        for name in ('response.json', 'stdout.txt', 'stderr.txt', 'request.json'):
            old = folder / name
            if old.is_file():
                old.rename(folder / (stamp + '_' + name))
    atomic_json(folder / 'plan.json', plan)
    request = {'official_code': str(official / 'code'), 'config': str(config),
               'graph': str(graph_path), 'plan': str((folder / 'plan.json').resolve()), 'q': q}
    if overrides:
        request['cache_overrides'] = overrides
    atomic_json(folder / 'request.json', request)
    atomic_json(folder / 'identity.json', identity)
    started = time.monotonic()
    try:
        with (folder / 'stdout.txt').open('w', encoding='utf8') as stdout, (folder / 'stderr.txt').open('w', encoding='utf8') as stderr:
            p = subprocess.run([sys.executable, '-m', 'research_a_orion_anytime.worker',
                                str((folder / 'request.json').resolve()), str(response_path.resolve())],
                               cwd=ROOT, stdout=stdout, stderr=stderr,
                               timeout=min(timeout, remaining), check=False,
                               env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONHASHSEED': '0'})
        result = read_json(response_path) if response_path.is_file() else {'status': 'worker_crash', 'exitcode': p.returncode}
    except subprocess.TimeoutExpired:
        result = {'status': 'timeout', 'timeout_seconds': min(timeout, remaining)}
    except Exception as exc:
        result = {'status': 'launch_error', 'error': str(exc), 'traceback': traceback.format_exc()}
    result.update(wall_seconds=time.monotonic() - started, cache_reused=False, evaluation_key=key)
    atomic_json(response_path, result)
    return {**result, 'record': str(response_path)}


def solve(official, config, graph_path, out, q, n, mode='improve', evaluations=3,
          seconds=60, eval_timeout=20, overall_deadline=float('inf'), memory=True,
          cache=True, retry_failed=False):
    graph_path, out = Path(graph_path).resolve(), Path(out).resolve()
    job = out / 'jobs' / f'{graph_path.stem}_q{q}_n{n}_{mode}'
    policy = {'q': q, 'n': n, 'mode': mode, 'evaluations': evaluations,
              'seconds': seconds, 'eval_timeout': eval_timeout, 'memory': memory, 'cache': cache}
    identity = prepare_context(official, config, graph_path, policy)
    summary_path = job / 'summary.json'
    if summary_path.is_file():
        old = read_json(summary_path)
        if old.get('identity') != identity:
            raise ValueError(f'Resume identity changed; choose a NEW --out directory: {job}')
        if old['status'] == 'ok' or not retry_failed:
            return old
        # Preserve earlier failed attempt rather than overwrite its provenance.
        summary_path.rename(job / f'prior_summary_{time.time_ns()}.json')
    started = time.monotonic()
    deadline = min(started + seconds, overall_deadline)
    job.mkdir(parents=True, exist_ok=True)
    summary = {'case': graph_path.stem, 'q': q, 'n': n, 'mode': mode, 'identity': identity,
               'plan_file': str(job / 'plan.json'), 'status': 'not_started', 'attempts': [],
               'constructor_errors': [], 'is_pilot': True}
    if started >= deadline:
        summary['status'] = 'not_started_budget'
        atomic_json(summary_path, summary)
        return summary
    try:
        g, cfg = Graph(read_json(graph_path)), Config.read(config)
        if q == 0:
            candidates = [{'name': 'original_whole_graph_single_core', 'plan': one_core(g, 1),
                           'bounds': bounds(g, cfg, 1, 1, one_core(g, 1)), 'proxy': {}}]
        else:
            candidates = constructors(g, n, cfg, q, memory, cache, summary['constructor_errors'])
        summary['construction_seconds'] = time.monotonic() - started
        summary['constructor_candidates'] = [{'name': c['name'], 'plan_hash': fingerprint(c['plan']),
                                              'proxy': c['proxy'], 'bounds': c['bounds']} for c in candidates]
        atomic_json(job / 'construction.json', summary['constructor_candidates'])
        limit = 1 if mode == 'construct' or q == 0 else evaluations
        seen, best = set(), None
        pool = list(candidates)
        exact_calls = 0
        while pool and exact_calls < limit and time.monotonic() < deadline:
            c = pool.pop(0)
            h = fingerprint(c['plan'])
            if h in seen:
                continue
            seen.add(h)
            if best and c['bounds']['candidate_lower'] > best['official_result']['makespan']:
                summary['attempts'].append({'name': c['name'], 'plan_hash': h, 'status': 'certified_pruned',
                                            'lower': c['bounds']['candidate_lower']})
                continue
            outcome = evaluate(official, config, graph_path, c['plan'], q, out, identity, deadline, eval_timeout)
            exact_calls += 1
            row = {'name': c['name'], 'plan_hash': h, 'status': outcome['status'],
                   'record': outcome.get('record'), 'cache_reused': outcome.get('cache_reused', False),
                   'wall_seconds': outcome.get('wall_seconds'), 'eval_seconds': outcome.get('eval_seconds')}
            if outcome['status'] == 'ok':
                r = outcome['official_result']
                score = (r['makespan'], r['data_movement_bytes']['added_copy_bytes'])
                row.update(makespan=score[0], added_copy_bytes=score[1])
                previous = (best['official_result']['makespan'], best['official_result']['data_movement_bytes']['added_copy_bytes']) if best else (float('inf'), float('inf'))
                if score < previous:
                    best = {**outcome, 'candidate': c['name'], 'plan': c['plan']}
                    atomic_json(job / 'plan.json', c['plan'])
                    atomic_json(job / 'best.json', {k: v for k, v in best.items() if k != 'plan'})
                    if mode == 'improve' and q != 0:
                        local = neighbours(g, c['plan'], cfg, q, r, memory=memory, cache=cache)
                        # Finite local candidates compete with remaining constructive candidates.
                        pool.extend(local)
                        pool.sort(key=lambda x: (x['proxy'].get('score', 0), x['name']))
            summary['attempts'].append(row)
            times = [a['makespan'] for a in summary['attempts'] if 'makespan' in a]
            summary['best_trajectory'] = [min(times[:i+1]) for i in range(len(times))]
            # Checkpoint after every attempt; unsuccessful candidates are never erased.
            atomic_json(job / 'progress.json', summary)
        summary.update(status='ok' if best else 'no_valid_solution', evaluations=exact_calls,
                       solve_seconds=time.monotonic() - started,
                       official_eval_seconds=sum(a.get('eval_seconds') or 0 for a in summary['attempts']),
                       failed_evaluations=sum(a['status'] not in ('ok', 'certified_pruned') for a in summary['attempts']))
        if best:+            r = best['official_result']
            summary.update(candidate=best['candidate'], plan_hash=fingerprint(best['plan']),
                           makespan=r['makespan'], **r['data_movement_bytes'],
                           cache_hit_rate=r.get('cache_stats', {}).get('hit_rate'),
                           certificate=best['audit']['certificate'])
            # Required same-plan counterfactual is NOT used for selecting the cache plan.
            if q == 3 and time.monotonic() < deadline:
                paired = evaluate(official, config, graph_path, best['plan'], 2, out, identity, deadline, eval_timeout)
                atomic_json(job / 'same_plan_no_l2.json', paired)
                summary['paired_status'] = paired['status']
                summary['paired_eval_seconds'] = paired.get('eval_seconds')
                summary['paired_record'] = paired.get('record')
                if paired['status'] == 'ok':
                    summary.update(no_l2_makespan=paired['official_result']['makespan'],
                                   no_l2_added_copy_bytes=paired['official_result']['data_movement_bytes']['added_copy_bytes'],
                                   cache_speedup=(paired['official_result']['makespan'] / r['makespan'] if r['makespan'] else None),
                                   paired_plan_hash=fingerprint(best['plan']))
            elif q == 3:
                summary['paired_status'] = 'not_started_budget'
    except Exception as exc:
        summary.update(status='error', error=str(exc), traceback=traceback.format_exc())
    summary['total_seconds_including_pair'] = time.monotonic() - started
    atomic_json(summary_path, summary)
    return summary


def collect(roots, destination):
    """Merge immutable job records, reject inconsistent duplicate jobs."""
    by_key = {}
    for root in roots:
        for path in sorted(Path(root).glob('jobs/*/summary.json')):
            s = read_json(path)
            key = (s['case'], s['q'], s['n'], s['mode'])
            if key in by_key:
                old = by_key[key]
                if old['identity'] != s['identity'] or (old.get('plan_hash'), old.get('makespan'), old['status']) != (s.get('plan_hash'), s.get('makespan'), s['status']):
                    raise ValueError(f'Conflicting duplicate job {key}; do not silently select a winner')
            by_key[key] = s
    rows = list(by_key.values())
    signatures = {(s['identity']['algorithm_sha256'], s['identity']['official_sha256'], s['identity']['config_sha256']) for s in rows}
    if len(signatures) > 1:
        raise ValueError('Different algorithm/official/config versions cannot be aggregated')
    baseline = {s['case']: s['makespan'] for s in rows if s['q'] == 0 and s['status'] == 'ok'}
    fields = ['case','q','n','mode','status','candidate','makespan','baseline','speedup','added_copy_bytes',
              'partition_added_copy_bytes','spill_added_copy_bytes','cache_hit_rate','no_l2_makespan',
              'cache_speedup','paired_status','construction_seconds','solve_seconds','official_eval_seconds',
              'total_seconds_including_pair','failed_evaluations','global_lower','speedup_ceiling','ratio_upper','plan_hash']
    simple = []
    for s in rows:
        r = {k: s.get(k) for k in fields}
        if s['case'] in baseline:
            r['baseline'] = baseline[s['case']]
            if s['status'] == 'ok' and s['makespan'] > 0:
                r['speedup'] = r['baseline'] / s['makespan']
        cert = s.get('certificate', {})
        r.update(global_lower=cert.get('global_lower'), ratio_upper=cert.get('approximation_ratio_upper'))
        if r['global_lower'] and r['baseline']:
            r['speedup_ceiling'] = r['baseline'] / r['global_lower']
        simple.append(r)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / 'metrics.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fields); w.writeheader(); w.writerows(simple)
    groups = {}
    for r in simple:
        if r['q'] == 0:
            continue
        key = f"q{r['q']}_n{r['n']}_{r['mode']}"
        groups.setdefault(key, []).append(r)
    stats = {}
    for key, rs in groups.items():
        vals = [r['speedup'] for r in rs if r['speedup'] is not None]
        pairs = [r['cache_speedup'] for r in rs if r['cache_speedup'] is not None]
        stats[key] = {'requested_records':len(rs), 'successful_records':sum(r['status']=='ok' for r in rs),
                      'speedup_valid_count':len(vals), 'mean_of_per_case_speedups':statistics.mean(vals) if vals else None,
                      'min_speedup':min(vals) if vals else None,
                      'same_plan_cache_valid_count':len(pairs), 'mean_same_plan_cache_speedup':statistics.mean(pairs) if pairs else None}
    manifest_jobs = set()
    for root in roots:
        p = Path(root) / 'manifest.json'
        if p.is_file():
            for case in read_json(p)['all_cases']:
                for n in read_json(p)['cores']:
                    for q in read_json(p)['questions']:
                        manifest_jobs.add((case,q,n,read_json(p)['mode']))
    missing = sorted(manifest_jobs-set(by_key))
    report = {'scope':'pilot/subset unless explicit 100-case completeness is established',
              'baseline':'original whole graph, one core, no L2; arithmetic mean of individual ratios',
              'records':len(rows), 'missing_jobs':missing, 'groups':stats,
              'all_case_names':sorted({s['case'] for s in rows}),
              'failures':[{'case':s['case'],'q':s['q'],'n':s['n'],'status':s['status']} for s in rows if s['status']!='ok']}
    atomic_json(destination / 'report.json', report)
    return report


def hardware_probe():
    free = None
    if os.name == 'nt':
        import ctypes
        class Memory(ctypes.Structure):
            _fields_ = [('length',ctypes.c_ulong),('load',ctypes.c_ulong)] + [(n,ctypes.c_ulonglong) for n in
                ['total','avail','total_page','avail_page','total_virtual','avail_virtual','avail_extended']]
        x = Memory(); x.length = ctypes.sizeof(x)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(x)):
            free = x.avail
    else:
        try:
            text = Path('/proc/meminfo').read_text()
            free = int(next(x for x in text.splitlines() if x.startswith('MemAvailable:')).split()[1])*1024
        except (OSError,StopIteration):
            pass
    compatible = sys.version_info[:2] == (3,12) and sys.maxsize > 2**32
    return {'python':sys.version, 'executable':sys.executable, 'platform':platform.platform(),
            'logical_cpus':os.cpu_count(), 'available_memory_gib':free/2**30 if free else None,
            'reference_compatible':compatible, 'stdlib_only':True,
            'recommended_workers':2 if free and free>=8*2**30 else 1,
            'local_agent_setup_required':not compatible or (free is not None and free<4*2**30)}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command', required=True)
    sub.add_parser('probe')
    c=sub.add_parser('collect'); c.add_argument('roots',nargs='+');c.add_argument('--out',required=True)
    for name in ('solve','pilot','sensitivity'):
        a=sub.add_parser(name);a.add_argument('--official');a.add_argument('--out',required=True)
        a.add_argument('--seconds',type=float,default=60);a.add_argument('--eval-timeout',type=float,default=20)
        a.add_argument('--evaluations',type=int,default=3);a.add_argument('--mode',choices=['construct','improve'],default='improve')
        a.add_argument('--retry-failed',action='store_true');a.add_argument('--no-memory',action='store_true');a.add_argument('--no-cache-proxy',action='store_true')
        if name=='solve':
            a.add_argument('--graph',required=True);a.add_argument('--q',type=int,choices=[0,1,2,3],required=True);a.add_argument('--n',type=int,default=5)
        elif name=='pilot':
            a.add_argument('--cases',nargs='+',default=['001','002','044']);a.add_argument('--cores',nargs='+',type=int,default=[2,5])
            a.add_argument('--questions',nargs='+',type=int,choices=[1,2,3],default=[1,2,3]);a.add_argument('--workers',type=int,choices=[1,2],default=1)
            a.add_argument('--total-seconds',type=float,default=1200);a.add_argument('--shards',type=int,default=1);a.add_argument('--shard-index',type=int,default=0)
        else:
            a.add_argument('--graph',required=True);a.add_argument('--plan',required=True)
            a.add_argument('--capacities',type=int,nargs='+',default=[262144,1048576,4194304]);a.add_argument('--bandwidths',type=float,nargs='+',default=[60,250,500])
    args=p.parse_args(argv)
    if args.command=='probe':
        print(json.dumps(hardware_probe(),ensure_ascii=False,indent=2));return 0
    if args.command=='collect':
        print(json.dumps(collect(args.roots,args.out),ensure_ascii=False,indent=2));return 0
    if args.seconds<=0 or args.eval_timeout<=0 or args.evaluations<1:
        p.error('Time budgets and evaluation count must be positive')
    official,config=locate_official(args.official)
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    kw={'mode':args.mode,'evaluations':args.evaluations,'seconds':args.seconds,'eval_timeout':args.eval_timeout,
        'memory':not args.no_memory,'cache':not args.no_cache_proxy,'retry_failed':args.retry_failed}
    if args.command=='solve':
        if args.n<1:p.error('n must be positive')
        result=solve(official,config,args.graph,out,args.q,args.n,**kw)
        print(json.dumps({k:v for k,v in result.items() if k not in ('identity','constructor_candidates','attempts')},ensure_ascii=False,indent=2))
        return 0 if result['status']=='ok' else 1
    if args.command=='sensitivity':
        plan=read_json(args.plan);g=Graph(read_json(args.graph));cfg=Config.read(config)
        identity=prepare_context(official,config,args.graph,{'kind':'non_official_sensitivity'})
        rows=[];deadline=time.monotonic()+args.seconds
        for cap in args.capacities:
            for bw in args.bandwidths:
                if cap<0 or bw<=0:p.error('capacity >=0, bandwidth >0 required')
                r=evaluate(official,config,Path(args.graph).resolve(),plan,3,out,identity,deadline,args.eval_timeout,{'capacity':cap,'bandwidth':bw})
                row={'capacity':cap,'bandwidth':bw,'status':r['status'],'plan_hash':fingerprint(plan),'record':r.get('record')}
                if r['status']=='ok':row.update(makespan=r['official_result']['makespan'],hit_rate=r['official_result']['cache_stats']['hit_rate'])
                rows.append(row)
        atomic_json(out/'sensitivity.json',{'non_official':True,'policy':'same plan, no reoptimization','rows':rows})
        return 0 if all(r['status']=='ok' for r in rows) else 1
    if args.total_seconds<=0:p.error('total-seconds must be positive')
    if args.shards<1 or not 0<=args.shard_index<args.shards or any(n<1 for n in args.cores):p.error('Invalid shard/core arguments')
    cases=sorted(set(f'case_{int(c):03d}' if c.isdigit() else c.removesuffix('.json') for c in args.cases))
    selected=[c for i,c in enumerate(cases) if i%args.shards==args.shard_index]
    manifest={'all_cases':cases,'selected_cases':selected,'shards':args.shards,'shard_index':args.shard_index,
              'cores':args.cores,'questions':args.questions,'mode':args.mode,'policy':kw,'hardware':hardware_probe(),
              'total_seconds':args.total_seconds}
    if (out/'manifest.json').is_file():
        prev=read_json(out/'manifest.json')
        for key in ('all_cases','selected_cases','shards','shard_index','cores','questions','mode','policy'):
            if prev[key]!=manifest[key]:raise ValueError(f'Manifest changed at {key}; use new output root')
    atomic_json(out/'manifest.json',manifest)
    deadline=time.monotonic()+args.total_seconds
    def run_case(case):
        path=official/'data'/f'{case}.json'
        if not path.is_file() or path.read_bytes()[:80].startswith(b'version https://git-lfs.github.com'):
            # No automatic global LFS fetch, no fabricated replacement graphs.
            return {'case':case,'status':'input_missing_or_lfs_pointer','path':str(path)}
        common={**kw,'overall_deadline':deadline}
        solve(official,config,path,out,0,1,**common)
        results=[]
        for n in args.cores:
            for q in args.questions:
                r=solve(official,config,path,out,q,n,**common)
                print(f"{case} q{q} n{n}: {r['status']} T={r.get('makespan')} seconds={r.get('total_seconds_including_pair',0):.2f}",flush=True)
                results.append({'case':case,'q':q,'n':n,'status':r['status']})
        return {'case':case,'jobs':results}
    case_records=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(run_case,c) for c in selected]
        for f in as_completed(futures):
            try:case_records.append(f.result())
            except Exception as exc:case_records.append({'status':'case_error','error':str(exc),'traceback':traceback.format_exc()})
    atomic_json(out/'case_status.json',{'cases':case_records})
    report=collect([out],out/'report')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    expected={(c,q,n,args.mode) for c in selected for q in args.questions for n in args.cores}
    records=[read_json(path) for path in out.glob('jobs/*/summary.json')]
    success={(r['case'],r['q'],r['n'],r['mode']) for r in records if r['status']=='ok' and (r['q']!=3 or r.get('paired_status')=='ok')}
    required_baselines={(c,0,1,args.mode) for c in selected}
    return 0 if (expected | required_baselines)<=success else 1

if __name__=='__main__':
    raise SystemExit(main())
