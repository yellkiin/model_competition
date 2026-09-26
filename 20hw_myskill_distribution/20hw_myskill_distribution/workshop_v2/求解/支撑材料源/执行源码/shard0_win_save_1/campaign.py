"""Three balanced shards: real validation -> complete solutions -> targeted diagnosis."""
from __future__ import annotations
import argparse, itertools, math, time, shutil
from pathlib import Path
from . import VERSION
from .io import ROOT,read,write,csv_read,csv_write,official_root,required_keys,key_name,plan_path,install_plan_archive
from .pool import run_jobs
from .seeds import catalogue
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


def historical_targets(material_root=None):
    """Reported values are diagnostic targets only; never fabricate their plans."""
    result={}
    base=Path(material_root) if material_root else ROOT
    sources=[(base/'research_a_orion_track_memory/results/coherent_v4_20260925/per_case.csv','new_makespan'),
             (base/'research_a_orion_track_memory/results/fivecore_final_20260924/per_case.csv','new_makespan'),
             (base/'research_a_orion_track_structure/results/safe_refine_20260925/review/per_case.csv','selected_makespan')]
    for path,column in sources:
        if not path.is_file():continue
        for r in csv_read(path):
            if not r.get(column):continue
            name=r.get('case','');case=name if name.startswith('case_') else f'case_{int(name):03d}'
            key=key_name(case,int(r['q']),int(r['n']));value=int(float(r[column]))
            if key not in result or value<result[key]['makespan']:
                result[key]={'makespan':value,'source':str(path.relative_to(base)),
                             'plan_path_declared_only':bool(r.get('plan_file'))}
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
              'historical_targets':historical_targets(args.study_materials),
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
    known, missing_seeds=catalogue(extras)
    write(out/'seed_catalogue.json',{'entries':[{'key':key,'plans':v} for key,v in sorted(known.items())],
                                     'missing_declared_plans':missing_seeds})
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
            baseline_alts=[x for x in known.get((case,q,n),[]) if x.get('recorded_makespan') is None or x['recorded_makespan']<int(r['makespan'])][:settings.get('max_seed_replays',4)] if q>0 else []
            if q>0 and 's' in settings['components']:
                for (cc,qq,nn),entries in known.items():
                    if cc==case and qq>0 and nn<=n and (qq,nn)!=(q,n):
                        for ent in entries[:1]:
                            alt.append({'path':ent['path'],'name':f'published_q{qq}_n{nn}'})
            specs.append({'out':str(out/'jobs'/key_name(case,q,n)),'case':case,'q':q,'n':n,
                'official':str(official),'config':str(config),'graph':str(graph),'version':VERSION,
                'mode':'warm','components':settings['components'],'fifo_module':settings.get('fifo_module'),
                'seconds':seconds,'job_seconds':seconds,'seed_timeout':settings['seed_timeout'],
                'campaign_jobs_root':str(out/'jobs'),'source_policy':settings.get('source_policy','staged'),
                'stop_gap':settings.get('stop_gap',.0025),'max_evaluations':settings['max_evaluations'],
                'pair_inline':q==3,'pair_reserve_seconds':settings.get('pair_reserve_seconds',60),
                'keep_all_responses':True,
                'seed_plan':str(plan_path(roots[0],case,q,n)),'reference_makespan':int(r['makespan']),
                'source_seed_seconds':costs.get((case,q,n)) if not baseline_alts and not alt else None,
                'known_day01_main_path_seconds':costs.get((case,q,n)),
                'alternatives':alt,'baseline_alternatives':baseline_alts})
    return specs


def pilot_keys(specs,features,shard):
    done_path=Path(__file__).parent/'evidence/local_checked.json'
    done={tuple(x) for x in read(done_path)['keys']} if done_path.is_file() else set()
    choices=[s for s in specs if s['n']==2 and s['q'] in (1+shard%2,3) and (s['case'],s['q'],s['n']) not in done]
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
        if read(p).get('pair_status')=='ok':continue
        # Optional repair of an interrupted pair is a separate, labelled job.
        plan=Path(req['out'])/'plan.json'
        target=out/'pairs'/key_name(req['case'],3,req['n'])
        pairs.append({**req,'q':2,'out':str(target),'components':'',
                      'fixed_plan':str(plan),'reference_makespan':None,'seed_plan':None,
                      'alternatives':[],'baseline_alternatives':[],'seconds':settings['seed_timeout'],'job_seconds':settings['seed_timeout'],
                      'seed_timeout':settings['seed_timeout'],'pair_inline':False,'pair_recovery':True})
    return pairs


def diagnose(specs,manifest,out,settings,deadline,max_workers,reserve):
    """Only unexplained raw regressions / reported-target gaps get subset runs."""
    selected=[];observations=[]
    for req in specs:
        if req['q']==0:continue
        p=Path(req['out'])/'summary.json'
        if not p.is_file():continue
        s=read(p);target=manifest['historical_targets'].get(key_name(req['case'],req['q'],req['n']))
        gap=bool(target and s.get('makespan') and s['makespan']>target['makespan']*(1+settings.get('diagnostic_gap',.005)))
        baseline=s.get('baseline_makespan');candidate=s.get('raw_candidate_makespan')
        flag=bool(s.get('regression_retained',False) and baseline and candidate and candidate>baseline*(1+settings.get('diagnostic_gap',.005)))
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
    stages=[];per_config_caps={};spent={};seeds_for_diagnosis={}
    for _,req,reason in chosen:
        key=(req['case'],req['q'],req['n']);folder=Path(req['out'])
        summary=read(folder/'summary.json');progress=read(folder/'progress.json')
        main_seconds=summary.get('execution',{}).get('wall_seconds',0.)
        spent[key]=main_seconds;per_config_caps[key]=req.get('job_seconds',600.)
        base=progress.get('baseline')
        fixed=dict(req,campaign_jobs_root=None)
        if base:
            fixed.update(seed_plan=str(folder/base['plan_file']),seed_response=str(folder/base['result_file']),
                         reuse_verified_response=True,reference_makespan=base['makespan'],
                         baseline_alternatives=[],alternatives=[])
        seeds_for_diagnosis[key]=fixed
        masks=pairs if req['q']==3 else [('s',),('m',)]
        remaining=max(0.,per_config_caps[key]-spent[key])
        matched_cap=min(settings['diagnostic_seconds'],remaining/max(1,len(masks))-.5)
        if matched_cap<2:continue
        for mask in masks:
            label=''.join(mask);folder=out/'diagnostics'/key_name(req['case'],req['q'],req['n'])/label
            stages.append({**fixed,'out':str(folder),'components':label,'diagnostic_reason':reason,'campaign_jobs_root':None,
                           'seconds':matched_cap,'job_seconds':matched_cap,
                           'source_seed_seconds':req.get('source_seed_seconds'),'pair_inline':req['q']==3})
    results=run_jobs(stages,out/'diagnostics',deadline,max_workers,reserve) if stages else []
    for r in results:
        key=(r['case'],r['q'],r['n']);spent[key]+=r.get('execution',{}).get('wall_seconds',0.)
    singles=[]
    if len(active)>=3:
        for _,req,reason in chosen:
            if req['q']!=3:continue
            group=[r for r in results if (r['case'],r['q'],r['n'])==(req['case'],req['q'],req['n'])]
            main=read(Path(req['out'])/'summary.json')
            published=manifest['historical_targets'].get(key_name(req['case'],req['q'],req['n']),{})
            goal=min(main.get('baseline_makespan',float('inf')),published.get('makespan',float('inf')))
            found=any(r['status']=='ok' and r.get('raw_candidate_makespan') is not None and r['raw_candidate_makespan']<=goal for r in group)
            if not found:
                key=(req['case'],req['q'],req['n'])
                matched_cap=min(settings['diagnostic_seconds'],max(0.,per_config_caps[key]-spent[key])/len(active)-.5)
                if matched_cap<2:continue
                fixed=seeds_for_diagnosis[key]
                for component in active:
                    singles.append({**fixed,'components':component,
                        'out':str(out/'diagnostics'/key_name(req['case'],req['q'],req['n'])/component),
                        'diagnostic_reason':reason,'campaign_jobs_root':None,
                           'seconds':matched_cap,'job_seconds':matched_cap,
                           'source_seed_seconds':req.get('source_seed_seconds'),'pair_inline':req['q']==3})
        if singles:
            for r in run_jobs(singles,out/'diagnostics',deadline,max_workers,reserve):
                key=(r['case'],r['q'],r['n']);spent[key]+=r.get('execution',{}).get('wall_seconds',0.)
    write(out/'diagnostic_queue.json',{'observations':observations,'selected_configurations':len(chosen),
        'deferred_configurations':len(selected)-len(chosen),'active_components':active,
        'first_stage': [''.join(x) for x in pairs],'second_stage_count':len(singles),'configuration_costs':[{'case':k[0],'q':k[1],'n':k[2],'main_plus_diagnostic_seconds':v,'total_cap':per_config_caps[k]} for k,v in spent.items()],
        'note':'These are diagnostic runs, not silently mixed into the fixed-policy main table. FIFO absent: do not invent 3-component ablations.'})


def run(args):
    manifest=read(args.manifest);out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    if not 0<=args.shard_index<len(manifest['shards']):raise ValueError('Invalid shard index')
    if args.components not in ('s','m','sm','sf','mf','smf','f'):raise ValueError('Use s/m/sm/sf/mf/smf/f')
    if args.fifo_module not in (None,'research_a_orion_trident.fifo'):
        raise ValueError('This frozen release uses its own reviewed FIFO source; other modules require a separate experiment version')
    if 'f' in args.components and not args.fifo_module:args.fifo_module='research_a_orion_trident.fifo'
    settings={'version':VERSION,'components':args.components,'fifo_module':args.fifo_module,
              'seconds':args.seconds,'large_seconds':args.large_seconds,'max_evaluations':args.calls,
              'seed_timeout':args.seed_timeout,'shard_index':args.shard_index,'ablation_limit':args.ablation_limit,
              'source_policy':args.source_policy,'stop_gap':args.stop_gap,
              'pair_reserve_seconds':args.pair_reserve_seconds,'max_seed_replays':args.max_seed_replays,
              'diagnostic_gap':args.diagnostic_gap,'diagnostic_seconds':args.diagnostic_seconds}
    path=out/'run_settings.json'
    if path.is_file() and read(path)!=settings:raise ValueError('Changed method/budget; use a new output directory')
    write(path,settings);write(out/'manifest.json',manifest)
    snap=out/'source_snapshot'
    if not snap.exists():
        snap.mkdir()
        package=Path(__file__).parent
        for source in list(package.glob('*.py'))+list((package/'vendor').rglob('*.py')):
            target=snap/source.relative_to(package);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        shutil.copyfile(package/'SOURCE_MANIFEST.json',snap/'SOURCE_MANIFEST.json')
    clock=out/'clock.json'
    previous=Path(args.resume_from).resolve() if args.resume_from else None
    if previous:
        if previous==out:raise ValueError('Continuation needs a new output directory')
        old_settings=read(previous/'run_settings.json')
        if any(old_settings.get(k)!=v for k,v in settings.items() if k!='version'):
            raise ValueError('Continuation may change persistence version, not method/budget/shard settings')
        if read(previous/'manifest.json')!=manifest:raise ValueError('Continuation manifest differs')
        old_clock=read(previous/'clock.json')
        if clock.exists() and read(clock)!=old_clock:raise ValueError('Continuation cannot reset batch clock')
        if not clock.exists():write(clock,old_clock)
    if not clock.is_file():
        now=time.time();end=args.deadline_epoch or now+args.hours*3600
        duration=max(0,end-now)
        write(clock,{'started_epoch':now,'deadline_epoch':end,'main_deadline':now+.86*duration,
                     'pair_deadline':now+.90*duration,'diagnostic_deadline':now+.96*duration})
    deadline=read(clock)['deadline_epoch'];now=time.time()
    official,config=official_root(args.official)
    specs=requests(manifest,settings,out,official,config,args.extra_plans)
    if previous:
        continuation=[]
        for req in specs:
            prior=previous/'jobs'/key_name(req['case'],req['q'],req['n'])
            if not (prior/'summary.json').is_file():continue
            old=read(prior/'summary.json');execution=old.get('execution',{})
            spent=float(execution.get('wall_seconds',0))
            if execution.get('wall_time_is_upper_bound'):raise ValueError('Continuation cost is not measured')
            complete=(old.get('status')=='ok' and execution.get('reason')=='completed'
                      and (req['q']!=3 or old.get('pair_status')=='ok'))
            target=Path(req['out'])
            if complete:
                if not target.exists():
                    shutil.copytree(prior,target)
                    shutil.copyfile(target/'request.json',target/'original_request.json')
                    write(target/'request.json',req)
                    write(target/'reused_from.json',{'source':str(prior),'original_version':old.get('version'),
                          'reason':'completed actual result reused; no new solve or clock reset'})
                elif read(target/'request.json')!=req:raise ValueError('Reused request changed')
                continuation.append({'case':req['case'],'q':req['q'],'n':req['n'],'action':'reused_complete',
                                     'original_version':old.get('version'),'prior_wall_seconds':spent})
                continue
            remaining=max(0.,req['job_seconds']-spent)
            if remaining<2:raise ValueError('Failed configuration has no remaining budget; do not grant a fresh cap')
            history=old.get('source_seed_seconds')
            req.update(seconds=remaining,job_seconds=remaining,
                       max_evaluations=max(1,req['max_evaluations']-old.get('attempt_count',0)),
                       retry_source=str(prior),retry_prior_wall_seconds=spent,
                       source_seed_seconds=None if history is None else history+spent)
            if old.get('status')=='ok' and (prior/'plan.json').is_file():
                req.update(seed_plan=str(prior/'plan.json'),seed_response=str(prior/'result.json.gz'),
                           reuse_verified_response=True,reference_makespan=old['makespan'])
            continuation.append({'case':req['case'],'q':req['q'],'n':req['n'],'action':'retry_remaining_budget',
                                 'prior_wall_seconds':spent,'remaining_seconds':remaining,
                                 'retained_makespan':old.get('makespan'),'source':str(prior)})
        write(out/'continuation.json',{'source':str(previous),'version':VERSION,'batch_clock_reused':True,
                                     'entries':continuation})
    remaining=max(0,deadline-now);stored_clock=read(clock)
    main_deadline=stored_clock['main_deadline'];pair_deadline=stored_clock['pair_deadline']
    def run_batch(batch,phase,limit):return run_jobs(batch,out/phase,limit,args.workers,args.reserve)
    pilot=pilot_keys(specs,manifest['features'],args.shard_index)
    results=run_batch(pilot,'pilot_resources',min(main_deadline,now+max(600,remaining*.12)))
    if len(results)!=len(pilot) or not results or any(r['status']!='ok' or r.get('makespan',math.inf)>(r.get('baseline_makespan') or math.inf) or (r['q']==3 and r.get('pair_status')!='ok') for r in results):
        write(out/'gate.json',{'passed':False,'reason':'real fused pilot failed','results':results});return 1
    write(out/'gate.json',{'passed':True,'actual_new_checks':len(results),'components':args.components,
                           'fifo_pending':'f' not in args.components,'basis':'real official cases plus shipped local integrated runs'})
    if args.pilot_only:return 0
    pilot_names={x['out'] for x in pilot}
    rest=sorted((x for x in specs if x['out'] not in pilot_names),key=lambda x:(x['n'],x['q'],-manifest['features'][x['case']]['ops'],x['case']))
    # All configurations in one graph stay on one host; completed lower-core
    # solutions become a common seed pool before admitting the next core layer.
    for n in range(1,6):
        layer=[r for r in rest if r['n']==n]
        run_batch(layer,'main_resources',main_deadline)
    if args.repair_pairs:
        pairs=pair_requests(specs,out,settings);run_batch(pairs,'pair_resources',pair_deadline)
    diagnose(specs,manifest,out,settings,stored_clock['diagnostic_deadline'],args.workers,args.reserve)
    if not args.skip_mechanisms and time.time()<deadline-90:
        from .mechanisms import run as mechanism_run
        mechanism_run(out,out/'mechanisms',deadline-90,args.workers,args.reserve,adapt=True)
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
    a.add_argument('--baseline-plans');a.add_argument('--study-materials');a.add_argument('--cases',nargs='+');a.add_argument('--shards',type=int,default=3)
    a=sub.add_parser('run');a.add_argument('--manifest',required=True);a.add_argument('--out',required=True)
    a.add_argument('--official');a.add_argument('--shard-index',type=int,required=True);a.add_argument('--workers',type=int,default=0)
    a.add_argument('--reserve',type=float,default=.25);a.add_argument('--seconds',type=float,default=600)
    a.add_argument('--large-seconds',type=float,default=600);a.add_argument('--calls',type=int,default=2048)
    a.add_argument('--seed-timeout',type=float,default=600);a.add_argument('--hours',type=float,default=12)
    a.add_argument('--deadline-epoch',type=float);a.add_argument('--components',default='smf');a.add_argument('--fifo-module')
    a.add_argument('--source-policy',choices=['work_adaptive'],default='work_adaptive');a.add_argument('--stop-gap',type=float,default=.0025)
    a.add_argument('--extra-plans',action='append',default=[]);a.add_argument('--ablation-limit',type=int,default=6)
    a.add_argument('--pilot-only',action='store_true');a.add_argument('--skip-mechanisms',action='store_true')
    a.add_argument('--repair-pairs',action='store_true',help='Separate labelled recovery, not hidden in <=600s main cost')
    a.add_argument('--resume-from',help='New output, same batch clock; reuse completed jobs and charge retry prior cost')
    a.add_argument('--pair-reserve-seconds',type=float,default=60.)
    a.add_argument('--max-seed-replays',type=int,default=4)
    a.add_argument('--diagnostic-gap',type=float,default=.005)
    a.add_argument('--diagnostic-seconds',type=float,default=120.)
    a=sub.add_parser('collect');a.add_argument('roots',nargs='+');a.add_argument('--out',required=True);a.add_argument('--official')
    a.add_argument('--require-complete',action='store_true')
    args=p.parse_args(argv)
    if args.command=='prepare':
        if args.shards<1:p.error('shards must be positive')
        prepare(args);return 0
    if args.command=='collect':
        r=collect(args.roots,args.out,args.official,require_complete=args.require_complete)
        print(r);return 0
    if not 0<args.seconds<=600 or not 0<args.large_seconds<=600 or not 0<args.seed_timeout<=600 or not 0<=args.stop_gap<1 or args.hours<=0 or args.calls<1 or not 0<args.reserve<1 or not 0<args.diagnostic_seconds<=600 or args.max_seed_replays<0:
        p.error('Positive time/call limits and 0<reserve<1 required')
    return run(args)

if __name__=='__main__':raise SystemExit(main())
