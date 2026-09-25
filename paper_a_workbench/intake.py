"""Normalize existing official records for writing. No solver/evaluator is executed."""
from __future__ import annotations
import gzip, json, math, statistics, re
from pathlib import Path
from common import read,write,csv_write,within,fresh

DEFAULT_LAYOUT={
 'request':'request.json','jobs':'jobs/*/summary.json','plan':'plan.json','response':'result.json.gz','progress':'progress.json',
 'inline_pair_plan':'same_plan_no_l2_plan.json','inline_pair_response':'same_plan_no_l2_result.json.gz',
 'external_pair_dir':'pairs/{job}','external_pair_plan':'plan.json','external_pair_response':'result.json.gz'}


def load(path):
    p=Path(path);data=p.read_bytes()
    return json.loads((gzip.decompress(data) if p.suffix=='.gz' else data).decode('utf-8-sig')),data


def number(value, name, minimum=0):
    v=float(value)
    if not math.isfinite(v) or v<minimum:raise ValueError(f'{name}: invalid numeric value')
    return v


def verified(response):
    if response.get('status')!='ok' or response.get('audit',{}).get('ok') is not True:
        raise ValueError('Selected response lacks recorded successful official evaluation/audit')
    return response['official_result']


def moments(state, end, horizon):
    events=state.get('improvement_events',[]);phases=state.get('phase_events',[])
    prior_t=-1;prior_u=math.inf
    for e in events:
        t=number(e['elapsed_seconds'],'event time');u=number(e['makespan'],'event makespan',1)
        if t<prior_t or u>prior_u:raise ValueError('Nonmonotone incumbent event stream')
        prior_t,prior_u=t,u
    result=[]
    for cutoff in range(0,int(horizon)+1,30):
        usable=[e for e in events if float(e['elapsed_seconds'])<=cutoff]
        e=usable[-1] if usable else {}
        active=[p for p in phases if float(p['elapsed_seconds'])<=min(cutoff,end if end is not None else cutoff)]
        result.append({'seconds':cutoff,'makespan':e.get('makespan'),'has_solution':bool(e),
            'phase':active[-1].get('optimization_stage',active[-1].get('phase')) if active else None,
            'source':e.get('source',e.get('family')),'clock':'local_total',
            'kind':'stopped_hold' if end is not None and cutoff>end else 'observed' if e else 'not_observed'})
    return result


def config_values(path):
    sections={};section=None
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        line=line.split('#',1)[0].strip()
        if not line:continue
        if line.startswith('['):section=line[1:-1];sections[section]={}
        else:
            k,v=line.split();sections[section][k]=int(v)
    return sections


def check_config(raw,cfg,q):
    required={'bandwidth_bytes_per_cycle':cfg['bandwidth']['bandwidth'],
              'capacity_bytes':cfg['capacity']}
    if q in (0,1):required.update(cfg['multicore_scene_a'])
    else:required.update(cfg['multicore_scene_b'])
    if q==3:required.update(cfg['problem_3'])
    for k,v in required.items():
        if raw.get(k)!=v:raise ValueError('Official response differs from selected config: '+k)
    if q==0 and raw.get('execution_mode')!='singlecore':raise ValueError('Baseline must use the original whole-graph singlecore entry')
    if q==3 and raw.get('problem')!=3:raise ValueError('Expected Q3 official response')
    if q==2 and (raw.get('scene')!='B' or raw.get('problem')==3):raise ValueError('Expected Q2 no-L2 response')


def build(spec_path, destination):
    """One explicitly selected publication; disjoint shards, no per-row best picking."""
    spec=read(spec_path);base=Path(spec_path).resolve().parent
    for k in ('publication_id','algorithm_revision','official_revision','config','protocol','runs'):
        if k not in spec:raise ValueError(f'Missing publication field: {k}')
    if spec['protocol'].get('budget_scope') not in ('graph_question_core','graph_all_questions_cores'):
        raise ValueError('Declare the actual budget_scope')
    cfg_path=Path(spec['config_local']);cfg_path=cfg_path if cfg_path.is_absolute() else within(base,str(cfg_path))
    cfg=config_values(cfg_path)
    out=fresh(destination);(out/'config.txt').write_bytes(cfg_path.read_bytes());layout={**DEFAULT_LAYOUT,**spec.get('layout',{})}
    rows=[];pairs=[];prefixes=[];events=[];errors=[];seen=set();raw_index=[]
    versions=set();protocol_rows=[];expected=set(spec.get('expected_cases',[f'case_{i:03d}' for i in range(1,101)]))
    for r in spec['runs']:
        root=Path(r);root=root.resolve() if root.is_absolute() else within(base,r)
        for summary_path in sorted(root.glob(layout['jobs'])):
            summary=read(summary_path);folder=summary_path.parent
            key=(summary['case'],int(summary['q']),int(summary['n']))
            if key in seen:raise ValueError(f'Duplicate configuration across runs: {key}; choose disjoint shards')
            seen.add(key);case,q,n=key
            if case not in expected:raise ValueError(f'Case outside declared cohort: {case}')
            if q not in (0,1,2,3) or n not in range(1,6):raise ValueError(f'Unexpected configuration {key}')
            target=out/'evidence'/f'{case}_q{q}_n{n}';target.mkdir(parents=True)
            row={'case':case,'q':q,'n':n,'status':summary.get('status'),'publication_id':spec['publication_id'],
                 'makespan':None,'added_copy_bytes':None,'spill_added_copy_bytes':None,'cache_hit_rate':None}
            try:
                plan,pbytes=load(within(folder,layout['plan']))
                response,rbytes=load(within(folder,layout['response']));raw=verified(response)
                if len(plan['core_schedules'])!=n:raise ValueError('Plan core count differs from result key')
                if raw.get('num_cores',n)!=n:raise ValueError('Official response core count mismatch')
                check_config(raw,cfg,q)
                if response.get('non_official') or response.get('non_official_sensitivity'):
                    raise ValueError('Sensitivity result belongs to a separate publication')
                u=number(raw['makespan'],'makespan',1)
                if summary.get('makespan') is not None and float(summary['makespan'])!=u:
                    raise ValueError('summary and original response disagree')
                (target/'plan.json').write_bytes(pbytes);(target/'result.json.gz').write_bytes(
                    rbytes if layout['response'].endswith('.gz') else gzip.compress(rbytes,mtime=0))
                row.update(status='ok',makespan=int(u),added_copy_bytes=raw['data_movement_bytes']['added_copy_bytes'],
                    spill_added_copy_bytes=raw['data_movement_bytes'].get('spill_added_copy_bytes'),
                    cache_hit_rate=raw.get('cache_stats',{}).get('hit_rate'),
                    plan=str((target/'plan.json').relative_to(out)),response=str((target/'result.json.gz').relative_to(out)))
                request_path=within(folder,layout['request'])
                req=read(request_path) if request_path.is_file() else {}
                ver=summary.get('version',req.get('version'))
                if ver:versions.add(ver)
                protocol_rows.append({'case':case,'q':q,'n':n,'version':ver,
                    'budget_seconds':summary.get('job_seconds',req.get('job_seconds',req.get('seconds'))),
                    'mode':summary.get('seed_mode',req.get('mode')),
                    'components':summary.get('components',req.get('components')),
                    'execution':summary.get('execution',{}),'request':str(request_path) if req else None})
                if spec.get('recorded_version') and ver!=spec['recorded_version']:
                    raise ValueError('Record version differs from chosen publication version')
                if req.get('cache_overrides') or summary.get('cache_overrides'):
                    raise ValueError('Parameter sensitivity must be kept separate')
                cap=protocol_rows[-1]['budget_seconds']
                if cap is not None and float(cap)>float(spec['protocol']['seconds']):
                    raise ValueError('Actual configuration cap exceeds declared protocol')
                if q==3:
                    pp=within(folder,layout['inline_pair_plan']);rp=within(folder,layout['inline_pair_response'])
                    if not(pp.is_file() and rp.is_file()):
                        pf=within(root,layout['external_pair_dir'].format(job=folder.name))
                        pp=within(pf,layout['external_pair_plan']);rp=within(pf,layout['external_pair_response'])
                    paired_plan,ppbytes=load(pp);paired_response,prbytes=load(rp)
                    paired=verified(paired_response)
                    if paired_plan!=plan:raise ValueError('Q3/no-L2 pair uses different complete plans')
                    if paired_response.get('q',2)!=2:raise ValueError('No-L2 response is not Q2')
                    if paired.get('num_cores',n)!=n:raise ValueError('Paired core count differs')
                    check_config(paired,cfg,2)
                    t0=number(paired['makespan'],'no-L2 makespan',1)
                    (target/'no_l2_plan.json').write_bytes(ppbytes)
                    (target/'no_l2_result.json.gz').write_bytes(prbytes if rp.suffix=='.gz' else gzip.compress(prbytes,mtime=0))
                    row.update(no_l2_makespan=int(t0),cache_speedup=t0/u,no_l2_added_copy_bytes=paired['data_movement_bytes']['added_copy_bytes'])
                    pairs.append({'case':case,'n':n,'with_l2':int(u),'without_l2':int(t0),'cache_speedup':t0/u,
                                  'hit_rate':row['cache_hit_rate'],'same_plan':True,
                                  'with_l2_added_bytes':row['added_copy_bytes'],'without_l2_added_bytes':paired['data_movement_bytes']['added_copy_bytes'],
                                  'plan':row['plan'],'no_l2_plan':str((target/'no_l2_plan.json').relative_to(out)),
                                  'no_l2_response':str((target/'no_l2_result.json.gz').relative_to(out))})
                raw_index.append({'case':case,'q':q,'n':n,'source_summary':str(summary_path),'evidence':str(target.relative_to(out))})
            except (OSError,ValueError,KeyError,TypeError) as exc:
                errors.append({'key':key,'error':str(exc)});row['record_error']=str(exc)
            row['local_seconds']=summary.get('execution',{}).get('wall_seconds',summary.get('process_seconds'))
            row['seed_seconds']=summary.get('source_seed_seconds',summary.get('seed_solve_seconds'))
            row['end_to_end_seconds']=None if row['seed_seconds'] is None or row['local_seconds'] is None else float(row['seed_seconds'])+float(row['local_seconds'])
            row['selected_source']=summary.get('selected_family');rows.append(row)
            sp=within(folder,layout['progress'])
            if sp.is_file():
                try:
                    state=read(sp);(target/'progress.json').write_bytes(sp.read_bytes())
                    events.extend({'case':case,'q':q,'n':n,**e} for e in state.get('improvement_events',[]))
                    horizon=spec['protocol'].get('seconds',600)
                    for p in moments(state,row['local_seconds'],horizon):prefixes.append({'case':case,'q':q,'n':n,**p})
                except (ValueError,KeyError,TypeError) as exc:errors.append({'key':key,'error':'trajectory: '+str(exc)})
    if len(versions)>1:errors.append({'error':'Multiple method versions in one publication','versions':sorted(versions)})
    baseline={r['case']:r['makespan'] for r in rows if r['q']==0 and r['status']=='ok' and r['makespan']}
    for r in rows:
        r['baseline']=baseline.get(r['case']);r['speedup']=r['baseline']/r['makespan'] if r['baseline'] and r['makespan'] else None
    required={(c,q,n) for c in expected for q,n in [(0,1),(3,1)]+[(q,n) for q in (1,2,3) for n in (2,3,4,5)]}
    valid={(r['case'],r['q'],r['n']) for r in rows if r['status']=='ok' and r['makespan'] is not None}
    required_pairs={(c,n) for c in expected for n in range(1,6)}
    present_pairs={(r['case'],r['n']) for r in pairs}
    formal=(len(expected)==100 and required==valid and required_pairs==present_pairs and not errors and spec.get('publication_state')=='final' and all(re.fullmatch(r'[0-9a-f]{40,64}',str(spec[k])) for k in ('algorithm_revision','official_revision')))
    csv_write(out/'main.csv',rows);csv_write(out/'pairs.csv',pairs);csv_write(out/'anytime.csv',prefixes);csv_write(out/'improvement_events.csv',events)
    means=[]
    for q in (1,2,3):
        for n in range(1,6):
            vals=[1.0 for c in sorted(baseline)] if q<3 and n==1 else [r['speedup'] for r in rows if r['q']==q and r['n']==n and r.get('speedup') is not None]
            means.append({'q':q,'n':n,'count':len(vals),'expected_count':len(expected),'mean_speedup':statistics.mean(vals) if vals else None,
                          'median_speedup':statistics.median(vals) if vals else None,'point':'baseline_convention' if q<3 and n==1 else 'evaluated'})
    csv_write(out/'means.csv',means)
    for q in (1,2,3):
        appendix=[r for r in rows if r['q']==q]
        if q<3:appendix += [{**r,'q':q,'point':'baseline_convention'} for r in rows if r['q']==0]
        csv_write(out/f'appendix_q{q}.csv',sorted(appendix,key=lambda r:(r['case'],r['n'])))
    status={'schema':1,'publication_id':spec['publication_id'],'formal_ready':formal,'expected_cases':len(expected),
            'main_count':len(rows),'valid_main_count':len(valid),'pair_count':len(pairs),'errors':errors,
            'missing_main':sorted(required-valid),'missing_pairs':sorted(required_pairs-present_pairs),
            'interpretation':'arithmetic mean of per-case speedups; one explicitly selected publication',
            'method_review':'required before scientific acceptance; no solver was executed'}
    write(out/'INTAKE_STATUS.json',status);write(out/'PUBLICATION.json',spec);write(out/'RAW_INDEX.json',raw_index);write(out/'ACTUAL_PROTOCOLS.json',protocol_rows)
    return status
