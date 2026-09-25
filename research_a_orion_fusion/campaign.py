"""Three balanced shards: real validation -> complete solutions -> targeted diagnosis."""
from __future__ import annotations
import argparse, itertools, math, time
from pathlib import Path
from . import VERSION
from .io import ROOT,read,write,csv_read,csv_write,official_root,required_keys,key_name,plan_path,install_plan_archive
from .pool import run_jobs
from .report import collect

DEFAULT_RESULTS=ROOT/'research_a_orion_anytime/team_results/day01/combined_final'


def balanced_shards(cases,weights,count=3):
    """LPT with 34/33/33 cardinalities: balance estimated WORK, not odd/even IDs."""
    caps=[len(cases)//count+(i<len(cases)%count) for i in range(count)]
    bins=[[] for _ in range(count)];loads=[0.]*count
    for case in sorted(cases,key=lambda c:(-weights[c],c)):
        choices=[i for i in range(count) if len(bins[i])<caps[i]]
        k=min(choices,key=lambda i:(loads[i],len(bins[i]),i))
        bins[k].append(case);loads[k]+=weights[case]
    return [{'index':i,'cases':sorted(v),'estimated_weight':loads[i]} for i,v in enumerate(bins)]


def historical_targets():
    """Reported values are diagnostic targets only; never fabricate their plans."""
    result={}
    sources=[(ROOT/'research_a_orion_track_memory/results/coherent_v4_20260925/per_case.csv','new_makespan'),
             (ROOT/'research_a_orion_track_memory/results/fivecore_final_20260924/per_case.csv','new_makespan'),
             (ROOT/'research_a_orion_track_structure/results/safe_refine_20260925/review/per_case.csv','selected_makespan')]
    for path,column in sources:
        if not path.is_file():continue
        for r in csv_read(path):
            if not r.get(column):continue
            name=r.get('case','');case=name if name.startswith('case_') else f'case_{int(name):03d}'
            key=key_name(case,int(r['q']),int(r['n']));value=int(float(r[column]))
            if key not in result or value<result[key]['makespan']:
                result[key]={'makespan':value,'source':str(path.relative_to(ROOT)),
                             'plan_available_in_this_table':bool(r.get('plan_file'))}
    return result


def prepare(args):
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    source=Path(args.reference).resolve();table=csv_read(source/'per_case.csv')
    cases=sorted(set(f'case_{int(x):03d}' if x.isdigit() else x.removesuffix('.json') for x in args.cases)) if args.cases else sorted({r['case'] for r in table})
    seeds=Path(args.baseline_plans).resolve() if args.baseline_plans else out/'reference_plans'
    if not args.baseline_plans and not seeds.is_dir():install_plan_archive(source/'selected_plans.zip',seeds)
    by={(r['case'],int(r['q']),int(r['n'])):r for r in table}
    missing=[key for c in cases for key in required_keys(c) if key not in by or not plan_path(seeds,*key).is_file()]
    if missing:raise FileNotFoundError(f'Reference plan/row missing: {missing[:8]}; restore selected_plans.zip, not only score CSV')
    features={}
    for r in csv_read(source/'lower_tail.csv'):
        features.setdefault(r['case'],{'ops':int(float(r['ops'])),'components':int(float(r['components']))})
    weights={c:sum(float(by[k].get('solve_seconds') or 0) for k in required_keys(c)) + .02*features[c]['ops'] for c in cases}
    manifest={'version':VERSION,'cases':cases,'shards':balanced_shards(cases,weights,args.shards),
              'reference_dir':str(source),'reference_plans':str(seeds),'features':{c:features[c] for c in cases},
              'historical_targets':historical_targets(),
              'source_note':'Existing score tables guide scheduling/diagnosis; official replays decide acceptance.'}
    p=out/'manifest.json'
    if p.is_file() and read(p)!=manifest:raise ValueError('Changed input manifest; choose a new prepare directory')
    write(p,manifest)
    print([(x['index'],len(x['cases']),round(x['estimated_weight'],2)) for x in manifest['shards']])
    return manifest


def requests(manifest,settings,out,official,config,extra_roots):
    table=csv_read(Path(manifest['reference_dir'])/'per_case.csv')
    cost_file=Path(manifest['reference_dir'])/'improvements.csv'
    costs={(r['case'],int(r['q']),int(r['n'])):float(r['end_to_end_solve_seconds'])
           for r in csv_read(cost_file) if r.get('end_to_end_solve_seconds')} if cost_file.is_file() else {}
    by={(r['case'],int(r['q']),int(r['n'])):r for r in table}
    shard=manifest['shards'][settings['shard_index']]
    roots=[Path(manifest['reference_plans'])]
    extras=[Path(x).resolve() for x in extra_roots]
    specs=[]
    for case in shard['cases']:
        graph=official/'data'/f'{case}.json'
        if not graph.is_file():raise FileNotFoundError(f'Only restore this shard A input: {graph}')
        with graph.open('rb') as f:
            if f.read(80).startswith(b'version https://git-lfs.github.com'):raise ValueError(f'A input is still an LFS pointer: {graph}')
        for _,q,n in required_keys(case):
            r=by[case,q,n];large=manifest['features'][case]['ops']>=5000
            seconds=settings['large_seconds'] if large else settings['seconds']
            alt=[]
            if q>0 and 's' in settings['components']:
                smaller=[by[case,q,k] for k in range(1,n) if (case,q,k) in by]
                smaller.sort(key=lambda x:int(x['makespan']))
                for x in smaller[:1]:
                    if int(x['makespan'])<int(r['makespan']):
                        alt.append({'path':str(plan_path(roots[0],case,q,int(x['n']))),'name':f'effective_n{x["n"]}'})
            baseline_alts=[]
            for root in extras:
                p=plan_path(root,case,q,n)
                if p.is_file():baseline_alts.append({'path':str(p),'name':'available_external_seed'})
            specs.append({'out':str(out/'jobs'/key_name(case,q,n)),'case':case,'q':q,'n':n,
                'official':str(official),'config':str(config),'graph':str(graph),'version':VERSION,
                'mode':'warm','components':settings['components'],'fifo_module':settings.get('fifo_module'),
                'seconds':seconds,'seed_timeout':settings['seed_timeout'],'max_evaluations':settings['max_evaluations'],
                'seed_plan':str(plan_path(roots[0],case,q,n)),'reference_makespan':int(r['makespan']),
                'source_seed_seconds':costs.get((case,q,n)) if not baseline_alts and not alt else None,
                'known_day01_main_path_seconds':costs.get((case,q,n)),
                'alternatives':alt,'baseline_alternatives':baseline_alts})
    return specs


def pilot_keys(specs,features,shard):
    # New fused configurations, not unit/smoke/environment tests. Cases used in
    # shipped local evidence are excluded; they need not be repeated on Windows.
    done_path=Path(__file__).parent/'evidence/local_checked.json'
    done={tuple(x) for x in read(done_path)['keys']} if done_path.is_file() else set()
    choices=[s for s in specs if s['n']==5 and s['q'] in (1+shard%2,3) and (s['case'],s['q'],s['n']) not in done]
    choices.sort(key=lambda s:(features[s['case']]['ops']>=5000,features[s['case']]['components']>100,s['case'],s['q']))
    selected=[];qs=set()
    for s in choices:
        if s['q'] in qs:continue
        selected.append(s);qs.add(s['q'])
        if len(selected)==2:break
    return selected


def pair_requests(specs,out,settings):
    pairs=[]
    for req in specs:
        p=Path(req['out'])/'summary.json'
        if req['q']!=3 or not p.is_file() or read(p)['status']!='ok':continue
        plan=Path(req['out'])/'plan.json'
        target=out/'pairs'/key_name(req['case'],3,req['n'])
        pairs.append({**req,'q':2,'out':str(target),'components':'',
                      'fixed_plan':str(plan),'reference_makespan':None,'seed_plan':None,
                      'alternatives':[],'baseline_alternatives':[],'seconds':1,
                      'seed_timeout':settings['seed_timeout']})
    return pairs


def diagnose(specs,manifest,out,settings,deadline,max_workers,reserve):
    """Only unexplained raw regressions / reported-target gaps get subset runs."""
    selected=[];observations=[]
    for req in specs:
        if req['q']==0:continue
        p=Path(req['out'])/'summary.json'
        if not p.is_file():continue
        s=read(p);target=manifest['historical_targets'].get(key_name(req['case'],req['q'],req['n']))
        gap=bool(target and s.get('makespan') and s['makespan']>target['makespan'])
        flag=s.get('regression_retained',False)
        status='published_target_gap' if gap else ('raw_regression_retained' if flag else 'no_trigger')
        observations.append({'case':req['case'],'q':req['q'],'n':req['n'],'reason':status,
                             'current':s.get('makespan'),'target':target,'selected_nonregressing':not s.get('baseline_makespan') or s.get('makespan',math.inf)<=s['baseline_makespan']})
        if gap or flag:
            base=target['makespan'] if gap else s['baseline_makespan']
            numerator=s['makespan'] if gap else s.get('raw_candidate_makespan',base)
            selected.append((numerator/base,req,status))
    selected.sort(key=lambda x:(-x[0],x[1]['case'],x[1]['q'],x[1]['n']))
    chosen=selected[:settings['ablation_limit']]
    active=list(settings['components']);pairs=list(itertools.combinations(active,2)) if len(active)>=3 else ([(x,) for x in active] if len(active)>1 else [])
    # All variants start from the SAME original seed set, not the fused winner.
    stages=[]
    for _,req,reason in chosen:
        for mask in pairs:
            label=''.join(mask);folder=out/'diagnostics'/key_name(req['case'],req['q'],req['n'])/label
            stages.append({**req,'out':str(folder),'components':label,'diagnostic_reason':reason})
    results=run_jobs(stages,out/'diagnostics',deadline,max_workers,reserve) if stages else []
    singles=[]
    if len(active)>=3:
        for _,req,reason in chosen:
            group=[r for r in results if (r['case'],r['q'],r['n'])==(req['case'],req['q'],req['n'])]
            # If removing one component restores a useful response, stop at 3-choose-2.
            found=any(r['status']=='ok' and r.get('raw_candidate_makespan') is not None and r['raw_candidate_makespan']<=r.get('baseline_makespan',0) for r in group)
            if not found:
                for component in active:
                    singles.append({**req,'components':component,
                        'out':str(out/'diagnostics'/key_name(req['case'],req['q'],req['n'])/component),
                        'diagnostic_reason':reason})
        if singles:run_jobs(singles,out/'diagnostics',deadline,max_workers,reserve)
    write(out/'diagnostic_queue.json',{'observations':observations,'selected_configurations':len(chosen),
        'deferred_configurations':len(selected)-len(chosen),'active_components':active,
        'first_stage': [''.join(x) for x in pairs],'second_stage_count':len(singles),
        'note':'These are diagnostic runs, not silently mixed into the fixed-policy main table. FIFO absent: do not invent 3-component ablations.'})


def run(args):
    manifest=read(args.manifest);out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    if not 0<=args.shard_index<len(manifest['shards']):raise ValueError('Invalid shard index')
    if args.components not in ('s','m','sm','sf','mf','smf','f'):raise ValueError('Use s/m/sm/sf/mf/smf/f')
    if 'f' in args.components and not args.fifo_module:raise ValueError('F is reserved: supply completed --fifo-module adapter explicitly')
    settings={'version':VERSION,'components':args.components,'fifo_module':args.fifo_module,
              'seconds':args.seconds,'large_seconds':args.large_seconds,'max_evaluations':args.calls,
              'seed_timeout':args.seed_timeout,'shard_index':args.shard_index,'ablation_limit':args.ablation_limit}
    path=out/'run_settings.json'
    if path.is_file() and read(path)!=settings:raise ValueError('Changed method/budget; use a new output directory')
    write(path,settings);write(out/'manifest.json',manifest)
    clock=out/'clock.json'
    if not clock.is_file():write(clock,{'started_epoch':time.time(),'deadline_epoch':args.deadline_epoch or time.time()+args.hours*3600})
    deadline=read(clock)['deadline_epoch'];now=time.time()
    official,config=official_root(args.official)
    specs=requests(manifest,settings,out,official,config,args.extra_plans)
    # Leave a fixed portion of the REMAINING campaign for pairs, collection and diagnosis.
    remaining=max(0,deadline-now);main_deadline=now+remaining*.78;pair_deadline=now+remaining*.90
    def run_batch(batch,phase,limit):return run_jobs(batch,out/phase,limit,args.workers,args.reserve)
    pilot=pilot_keys(specs,manifest['features'],args.shard_index)
    results=run_batch(pilot,'pilot_resources',min(main_deadline,now+max(600,remaining*.12)))
    if any(r['status']!='ok' or r.get('makespan',math.inf)>r.get('baseline_makespan',math.inf) for r in results):
        write(out/'gate.json',{'passed':False,'reason':'real fused pilot failed','results':results});return 1
    write(out/'gate.json',{'passed':True,'actual_new_checks':len(results),'components':args.components,
                           'fifo_pending':'f' not in args.components,'basis':'real official cases plus shipped local integrated runs'})
    if args.pilot_only:return 0
    pilot_names={x['out'] for x in pilot}
    # Level ordering makes future lower-core inheritance straightforward; each graph is owned by one host.
    rest=sorted((x for x in specs if x['out'] not in pilot_names),key=lambda x:(x['n'],x['q'],-manifest['features'][x['case']]['ops'],x['case']))
    run_batch(rest,'main_resources',main_deadline)
    pairs=pair_requests(specs,out,settings);run_batch(pairs,'pair_resources',pair_deadline)
    diagnose(specs,manifest,out,settings,deadline-120,args.workers,args.reserve)
    report=collect([out],out/'report',official,verify=True)
    expected=len(manifest['shards'][args.shard_index]['cases'])*14
    expected_pairs=len(manifest['shards'][args.shard_index]['cases'])*5
    complete=report['successful_main']==expected and report['paired']==expected_pairs and report['independent_checks']==expected
    write(out/'shard_status.json',{'complete':complete,'expected_main':expected,'expected_pairs':expected_pairs,
                                  'report':'report/report.json','fifo_pending':'f' not in args.components})
    return 0 if complete else 1


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('prepare');a.add_argument('--out',required=True);a.add_argument('--reference',default=str(DEFAULT_RESULTS))
    a.add_argument('--baseline-plans');a.add_argument('--cases',nargs='+');a.add_argument('--shards',type=int,default=3)
    a=sub.add_parser('run');a.add_argument('--manifest',required=True);a.add_argument('--out',required=True)
    a.add_argument('--official');a.add_argument('--shard-index',type=int,required=True);a.add_argument('--workers',type=int,default=0)
    a.add_argument('--reserve',type=float,default=.25);a.add_argument('--seconds',type=float,default=120)
    a.add_argument('--large-seconds',type=float,default=300);a.add_argument('--calls',type=int,default=96)
    a.add_argument('--seed-timeout',type=float,default=300);a.add_argument('--hours',type=float,default=8)
    a.add_argument('--deadline-epoch',type=float);a.add_argument('--components',default='sm');a.add_argument('--fifo-module')
    a.add_argument('--extra-plans',action='append',default=[]);a.add_argument('--ablation-limit',type=int,default=6)
    a.add_argument('--pilot-only',action='store_true')
    a=sub.add_parser('collect');a.add_argument('roots',nargs='+');a.add_argument('--out',required=True);a.add_argument('--official')
    a.add_argument('--require-complete',action='store_true')
    args=p.parse_args(argv)
    if args.command=='prepare':
        if args.shards<1:p.error('shards must be positive')
        prepare(args);return 0
    if args.command=='collect':
        r=collect(args.roots,args.out,args.official,require_complete=args.require_complete)
        print(r);return 0
    if args.seconds<=0 or args.large_seconds<=0 or args.seed_timeout<=0 or args.hours<=0 or args.calls<1 or not 0<args.reserve<1:
        p.error('Positive time/call limits and 0<reserve<1 required')
    return run(args)

if __name__=='__main__':raise SystemExit(main())
