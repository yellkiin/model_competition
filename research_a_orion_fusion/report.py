"""Complete/subset metrics, real anytime prefixes and official timeline recheck."""
from __future__ import annotations
from pathlib import Path
import math, statistics
from .io import read,write,csv_write,required_keys,official_root
from research_a_orion_anytime.core import Graph,Config
from research_a_orion_anytime.worker import audit


def prefixes(folder):
    req=read(folder/'request.json');s=read(folder/'progress.json')
    events=s.get('improvement_events',[]);start=s.get('search_started_seconds')
    elapsed=s.get('elapsed_seconds',0);rows=[]
    seed_cost=req.get('source_seed_seconds')
    for cutoff in (5,10,20,30,60,120,300,600):
        for phase in ('local_total','refinement'):
            origin=0 if phase=='local_total' else start
            if origin is None:continue
            absolute=origin+cutoff
            valid=[e for e in events if e['elapsed_seconds']<=absolute]
            best=valid[-1] if valid else None
            rows.append({'case':req['case'],'q':req['q'],'n':req['n'],'components':req['components'],
                         'phase':phase,'cutoff_seconds':cutoff,'best_makespan':best['makespan'] if best else None,
                         'source_seed_seconds':seed_cost,'has_valid_incumbent':best is not None,
                         'ended_before_cutoff':elapsed<absolute,'observed_run_seconds':elapsed})
    return rows


def collect(roots,destination,official=None,verify=True,require_complete=False):
    dest=Path(destination);dest.mkdir(parents=True,exist_ok=True)
    by_key={};policies=set();manifests=[]
    for root in map(Path,roots):
        m=root/'run_settings.json'
        if m.is_file():
            x=read(m);policies.add((x['version'],x['components'],x.get('fifo_module'),x['seconds'],x['large_seconds'],x['max_evaluations']))
        man=root/'manifest.json'
        if man.is_file():manifests.append(read(man))
        for p in sorted((root/'jobs').glob('*/summary.json')):
            s=read(p);key=(s['case'],s['q'],s['n'])
            if key in by_key:raise ValueError(f'Duplicate job {key}; merge disjoint shards, do not select by score')
            by_key[key]=(s,p.parent,root)
    if len(policies)>1:raise ValueError('Different experiment policies; report separately')
    ref={c:s['makespan'] for (c,q,n),(s,_,_) in by_key.items() if q==0 and s['status']=='ok'}
    rows=[];trajectory=[];checks=[];pair_checks=[];last_case=None;g=None
    of,cfgfile=official_root(official);cfg=Config.read(cfgfile)
    for (case,q,n),(s,folder,root) in sorted(by_key.items()):
        row={k:s.get(k) for k in ('case','q','n','components','status','makespan','added_copy_bytes','partition_added_copy_bytes','spill_added_copy_bytes','cache_hit_rate','selected_family','selected_name','baseline_makespan','raw_candidate_makespan','regression_retained','seed_replay_seconds','candidate_generation_seconds','official_eval_seconds','source_seed_seconds','end_to_end_seconds')}
        row['local_seconds']=s.get('execution',{}).get('wall_seconds')
        row['reference']=ref.get(case);row['speedup']=ref[case]/s['makespan'] if case in ref and s.get('makespan') else None
        row['relative_to_seed']=s['baseline_makespan']/s['makespan'] if s.get('baseline_makespan') and s.get('makespan') else None
        cert=s.get('certificate',{});row['lower']=cert.get('global_lower')
        row['ratio_upper']=cert.get('approximation_ratio_upper')
        row['seed_was_kept']=s.get('selected_family','').startswith('seed')
        pair=root/'pairs'/folder.name/'summary.json'
        pair_ok=False
        if q==3 and pair.is_file():
            ps=read(pair)
            if ps['status']=='ok' and s['status']=='ok':
                # Direct object equality, no source-file fingerprint stage.
                if read(pair.parent/'plan.json')!=read(folder/'plan.json'):raise ValueError('Q3/no-L2 pairing plan differs')
                row['no_l2_makespan']=ps['makespan'];row['same_plan_cache_speedup']=ps['makespan']/s['makespan'];pair_ok=True
                row['pair_seconds']=ps.get('execution',{}).get('wall_seconds')
        row['pair_status']='ok' if pair_ok else ('missing' if q==3 else 'not_applicable')
        if (folder/'progress.json').is_file():trajectory.extend(prefixes(folder))
        if verify and s['status']=='ok':
            if last_case!=case:g=Graph(read(of/'data'/f'{case}.json'));last_case=case
            plan=read(folder/'plan.json');response=read(folder/'result.json.gz')
            checked=audit(g,plan,response['official_result'],q,cfg)
            if not checked['ok']:raise ValueError(f'Timeline recheck failed {case,q,n}: {checked}')
            checks.append({'case':case,'q':q,'n':n,'ok':True})
            if pair_ok:
                pc=audit(g,plan,read(pair.parent/'result.json.gz')['official_result'],2,cfg)
                if not pc['ok']:raise ValueError(f'Paired timeline recheck failed {case,n}')
                pair_checks.append({'case':case,'n':n,'ok':True})
        if s['status']=='ok':
            write(dest/'plans'/f'q{q}'/f'n{n}'/f'{case}_multicore_res.json',read(folder/'plan.json'))
        rows.append(row)
    wanted={k for i in range(1,101) for k in required_keys(f'case_{i:03d}')}
    successes={k for k,(s,_,_) in by_key.items() if s['status']=='ok'}
    missing=sorted(wanted-successes)
    pairs=sum(r['pair_status']=='ok' for r in rows)
    grouped={}
    for q in (1,2,3):
        for n in range(1,6):
            values=[1.]*len(ref) if n==1 and q in(1,2) else [r['speedup'] for r in rows if r['q']==q and r['n']==n and r.get('speedup') is not None]
            grouped[f'q{q}_n{n}']={'count':len(values),'mean_speedup':statistics.mean(values) if values else None,
                                  'min_speedup':min(values) if values else None}
    complete=not missing and pairs==500 and len(checks)==1400 and len(pair_checks)==500
    report={'formal_complete':complete,'successful_main':len(successes),'paired':pairs,'independent_checks':len(checks),
            'pair_checks':len(pair_checks),'missing':missing,'groups':grouped,
            'scope':'full_100' if complete else 'subset_or_incomplete',
            'active_policies':list(policies),'memory_scope':'official Step3 peak fields; not independent allocation replay'}
    csv_write(dest/'per_case.csv',rows);csv_write(dest/'budget_prefixes.csv',trajectory)
    write(dest/'report.json',report);write(dest/'verification.json',{'main':checks,'pairs':pair_checks})
    if require_complete and not complete:raise ValueError('1400 main plus 500 paired records not complete; see report.json')
    return report
