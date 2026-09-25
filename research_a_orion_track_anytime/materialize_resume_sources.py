"""Materialize additive sources used in real resumed runs; do not execute experiments.

The original private adapter/runner and all public/official code stay unchanged.
This publication helper is removed after the generated files have been committed.
"""
from pathlib import Path
P=Path(__file__).resolve().parent

def copy_lines(source,target,changes,expected_lines):
    lines=(P/source).read_text().splitlines(keepends=True)
    if len(lines)!=expected_lines:raise ValueError('Unexpected source version: '+source)
    for lo,hi,text in sorted(changes,reverse=True):lines[lo:hi]=[text]
    dst=P/target
    if dst.exists():raise FileExistsError(dst)
    dst.write_text(''.join(lines),encoding='utf8')

copy_lines('adapter.py','adapter_windows.py',[
 (14,15,"from .fifo_windows import propose\n"),
 (119,120,"    revised = request.get('revision') in ('v2','v3','v4-window')\n"),
 (125,126,"            streams.extend([('stage', iter(_prioritized_stages(g,n,cfg,q,deadline) if request.get('revision') in ('v3','v4-window') else stage_candidates(g,n,cfg,q))),\n")],338)
copy_lines('adapter.py','adapter_guarded.py',[
 (13,14,"from .selector_guarded import select_candidate, selection_details, family_statistics, stop_reason\n"),
 (119,120,"    revised = request.get('revision') in ('v2','v3','v4-select')\n"),
 (125,126,"            streams.extend([('stage', iter(_prioritized_stages(g,n,cfg,q,deadline) if request.get('revision')in ('v3','v4-select') else stage_candidates(g,n,cfg,q))),\n")],338)
copy_lines('runner.py','runner_resume.py',[
 (64,65,"        proc=subprocess.Popen([sys.executable,'-u','-m',({'v4-window':'research_a_orion_track_anytime.adapter_windows','v4-select':'research_a_orion_track_anytime.adapter_guarded'}.get(req.get('revision'),'research_a_orion_track_anytime.adapter')),str(folder/'request.json')],**kw)\n"),
 (88,88,"    row['known_primary_path_seconds']=row.get('total_solve_seconds')\n    row['seed_cost_complete']=not bool(req.get('seed_job'))\n    if req.get('seed_job'):row['total_solve_seconds']=None\n"),
 (101,102,"            prefixes.append(dict(case=r['case'],q=r['q'],n=r['n'],method=r['method'],mode=r['mode'],run_id=out.name,phase=phase,budget_seconds=t,elapsed_seconds=min(t,r.get('solve_seconds',0)),total_elapsed_seconds=None if r.get('seed_job') else min(t,r.get('solve_seconds',0)),known_primary_path_elapsed_seconds=None if r.get('seed_solve_seconds') is None else r['seed_solve_seconds']+min(t,r.get('solve_seconds',0)),best_makespan=best['makespan'] if best else None,baseline=r.get('baseline'),speedup=r['baseline']/best['makespan'] if best else None,has_valid_incumbent=best is not None,evaluations=sum(e['elapsed_seconds']<=t for e in r.get('evaluation_events',[]))))\n"),
 (103,104,"    write(out/'run_summary.json',dict(expected_jobs=len(manifest['cases'])*len(manifest['questions'])*len(manifest['cores'])*len(manifest['methods'])*len(manifest['modes']),jobs=len(records),statuses=dict(Counter(r['status'] for r in records)),q3_pairs_requested=sum(r['q']==3 and r.get('makespan') is not None for r in records),q3_pairs_completed=sum(r.get('pair_status')=='ok' for r in records),full_100_rerun=False,policy=manifest['policy']))\n"),
 (106,107,"    p=argparse.ArgumentParser();p.add_argument('--cases',required=True);p.add_argument('--questions',default='1,2,3');p.add_argument('--cores',default='2,5');p.add_argument('--methods',default='old,combined');p.add_argument('--modes',default='warm,cold');p.add_argument('--seconds',type=float,default=30);p.add_argument('--max-evaluations',type=int,default=16);p.add_argument('--total-seconds',type=float,default=1800);p.add_argument('--pair-seconds',type=float,default=60);p.add_argument('--workers',default='auto');p.add_argument('--max-workers',type=int,default=2);p.add_argument('--shards',type=int,default=1);p.add_argument('--shard-index',type=int,default=0);p.add_argument('--seed-manifest',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--official',type=Path,default=ROOT/'题目/A题/通用神经网络处理器下的多核调度问题  附件');p.add_argument('--revision',choices=['v1.1','v2','v3','v4-window','v4-select'],default='v3');p.add_argument('--gap-tolerance',type=float,default=.02);a=p.parse_args()\n"),
 (110,111,"    seed_rows=read(a.seed_manifest)\n    for row in seed_rows:\n        original=Path(row['seed_job'])\n        if original.exists():continue\n        candidates=[ROOT/original,a.seed_manifest.resolve().parent/original]\n        marker='research_a_orion_track_anytime'\n        if marker in original.parts:\n            candidates.append(ROOT.joinpath(*original.parts[original.parts.index(marker):]))\n        actual=next((path for path in candidates if (path/'progress.json').is_file()),None)\n        if actual is None:raise FileNotFoundError('Cannot relocate actual seed job: '+str(original))\n        row['original_recorded_seed_job']=str(original);row['seed_job']=str(actual.resolve())\n    seeds={(r['case'],r['q'],r['n']):r for r in seed_rows}\n    missing=[(c,q,n) for c in cases for q in qs for n in ns if (c,q,n) not in seeds]\n    if missing:raise ValueError('Incomplete seed manifest: '+repr(missing))\n    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)\n"),
 (114,115,"    write(out/'manifest.json',manifest);write(out/'seed_manifest_snapshot.json',seed_rows);(out/'source').mkdir()\n"),
 (125,126,"        cost=(None if seed.get('seed_solve_seconds') is None else seed['seed_solve_seconds']+seed.get('validation_seconds',0.)) if mode=='warm' else 0.\n"),
 (136,136,"            result['new_work_including_pair_seconds']=result['solve_seconds']+pair['solve_seconds']\n            if not result.get('seed_job'):result['total_solve_seconds']=result['new_work_including_pair_seconds']\n"),
 (146,146,"                    for method in methods:\n                        records.append(dict(case=s[0],q=s[1],n=s[2],mode=s[3]+'_start',method=method,seconds=a.seconds,status='controller_error',solve_seconds=0.,error=str(exc)))\n")],150)
print('Materialized additive adapters and runner; no experiment executed.')
