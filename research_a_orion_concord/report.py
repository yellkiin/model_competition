"""Original appendix and plotting data; 30-second points come from saved events."""
from __future__ import annotations
from collections import defaultdict
import argparse
import csv
import gzip
import json
from pathlib import Path
from statistics import mean,median,pstdev
from .io import read,write,csv_write,key,score,utc

def events(folder):
    out=[]
    p=Path(folder)/'events.jsonl'
    if p.is_file():
        for line in p.read_text(encoding='utf-8').splitlines():
            try:out.append(json.loads(line))
            except json.JSONDecodeError:pass # a killed final append is not a completed event
    return out

def graph_rows(folder):
    folder=Path(folder);req=read(folder/'request.json');ev=events(folder)
    receipt=read(folder/'process.json') if (folder/'process.json').exists() else {}
    selected={};initial={};first_valid={}
    for r in ev:
        if r['event']=='incumbent':
            k=(r['q'],r['n']);selected[k]=r;first_valid.setdefault(k,r['elapsed_seconds'])
            if r.get('source')=='seed' or k not in initial:initial[k]=r
    summary=read(folder/'summary.json') if (folder/'summary.json').is_file() else {}
    metadata={(r['q'],r['n']):r for r in summary.get('rows',[])}
    targets={}
    for e in ev:
        if e['event']=='published_targets':targets.update({(r['q'],r['n']):r['makespan'] for r in e['targets']})
    # Older development records can still read their frozen catalogue targets.
    if not targets and req.get('catalog') and Path(req['catalog']).is_file():
        for r in read(req['catalog']).get('targets',[]):
            if r.get('case')==req['case']:targets[int(r['q']),int(r['n'])]=float(r['makespan'])
    rows=[];base=selected.get((0,1),{}).get('makespan')
    duration=receipt.get('process_seconds',summary.get('graph_seconds',0))
    for q,n in [(0,1)]+[tuple(x) for x in req['keys']]:
        k=(q,n);meta=selected.get(k,{});old=initial.get(k,{})
        m=dict(metadata.get(k,{}));response=None;pair=None;plan=None
        if meta:
            plan=read(folder/meta['plan_file']);response=read(folder/meta['result_file'])
            if response.get('status')!='ok' or response.get('audit',{}).get('ok') is not True:
                raise ValueError(f'Unvalidated selected response {folder} {k}')
            if score(response)[0]!=meta['makespan']:raise ValueError('Selected metadata disagrees with its original response')
            if meta.get('pair_file'):
                pair=read(folder/meta['pair_file'])
                if pair.get('status')!='ok' or pair.get('audit',{}).get('ok') is not True:
                    raise ValueError('Invalid same-plan pair')
                if meta.get('pair_plan_file') and key(plan)!=key(read(folder/meta['pair_plan_file'])):
                    raise ValueError('Paired plan differs from selected Q3 plan')
                if pair['official_result'].get('problem')==3 or pair['official_result']['num_cores']!=n:
                    raise ValueError('Paired response has the wrong semantics')
        raw=response['official_result'] if response else {};movement=raw.get('data_movement_bytes',{})
        original_calls=[r for r in ev if r['event']=='evaluation_end' and r['q']==q and r['n']==n and r['source'] not in ('PAIR','SEED_TRACE')]
        spent=sum(r['seconds'] for r in ev if r['event']=='step' and (r['q'],r['n'])==k)
        raw_best=min((r['makespan'] for r in original_calls if r['status']=='ok'),default=None)
        m.update(case=req['case'],q=q,n=n,method=req['mode'],status='ok' if meta else 'missing',
            mode='warm_start' if old.get('source')=='seed' else 'cold_start',baseline=base,published_target_makespan=targets.get(k),
            old_makespan=old.get('makespan') if old.get('source')=='seed' else None,new_makespan=meta.get('makespan'),
            old_added_copy_bytes=old.get('added_copy_bytes') if old.get('source')=='seed' else None,
            new_added_copy_bytes=movement.get('added_copy_bytes'),best_unprotected_makespan=raw_best,
            seed_solve_seconds=meta.get('seed_solve_seconds'),added_solve_seconds=duration,
            total_solve_seconds=meta['seed_solve_seconds']+duration if meta.get('seed_solve_seconds') is not None else None,
            graph_seconds=duration,config_active_seconds=spent,cost_scope='shared_graph_wall_not_additive',
            evaluations=len(original_calls),no_l2_makespan=score(pair)[0] if pair else None,
            no_l2_added_copy_bytes=pair['official_result']['data_movement_bytes']['added_copy_bytes'] if pair else None,
            pair_status='ok' if pair else 'missing' if q==3 else None,
            cache_hit_rate=raw.get('cache_stats',{}).get('hit_rate'),spill_added_copy_bytes=movement.get('spill_added_copy_bytes'),
            partition_added_copy_bytes=movement.get('partition_added_copy_bytes'),scheduled_copy_bytes=movement.get('scheduled_copy_bytes'),
            source=meta.get('source'),candidate=meta.get('name'),epoch=meta.get('epoch'),
            lower=response['audit']['certificate']['global_lower'] if response else None,
            plan_file=str(folder/meta['plan_file']) if meta else None,result_file=str(folder/meta['result_file']) if meta else None,
            pair_file=str(folder/meta['pair_file']) if meta.get('pair_file') else None,
            process_exit_code=receipt.get('exit_code'),hard_deadline=receipt.get('hard_deadline',False),
            stopped=m.get('stopped') or ('graph_deadline' if receipt.get('hard_deadline') else 'worker_exit'),
            first_valid_seconds=first_valid.get(k))
        m['speedup']=base/m['new_makespan'] if base and m.get('new_makespan') else None
        m['cache_speedup']=m['no_l2_makespan']/m['new_makespan'] if m.get('no_l2_makespan') and m.get('new_makespan') else None
        rows.append(m)
    return rows,ev,duration

def quantile(values,p):
    xs=sorted(values);x=(len(xs)-1)*p;i=int(x);return xs[i]+(xs[min(i+1,len(xs)-1)]-xs[i])*(x-i)

def collect(root,expected_cases=None,keys=None,detailed=False):
    root=Path(root);paper=root/'paper_data';rows=[];trajectories=[];improvements=[];source_rows=[];pipes=[];cache_rows=[];graph_costs=[]
    folders=sorted((root/'graphs').glob('case_*'))
    for folder in folders:
        if not (folder/'request.json').is_file():continue
        rr,ev,elapsed=graph_rows(folder);rows.extend(rr)
        req=read(folder/'request.json');case=req['case'];by={(r['q'],r['n']):r for r in rr}
        graph_costs.append(dict(case=case,graph_seconds=elapsed,cap_seconds=req['seconds'],
            official_evaluations=sum(e['event']=='evaluation_end' for e in ev),
            diagnostic_evaluations=sum(r.get('official_calls',0) for r in read(folder/'diagnostics.json').get('arms',[])) if (folder/'diagnostics.json').exists() else 0,
            sensitivity_evaluations=sum(e['event']=='sensitivity_evaluation' for e in ev),
            interrupted_evaluations=sum(e['event']=='evaluation_start' for e in ev)-sum(e['event']=='evaluation_end' for e in ev)))
        saved=[e for e in ev if e['event']=='incumbent']
        for q,n in by:
            track=[r for r in saved if (r['q'],r['n'])==(q,n)]
            for cutoff in range(30,int(req['seconds'])+1,30):
                seen=[r for r in track if r['elapsed_seconds']<=cutoff];best=seen[-1] if seen else {}
                # The active stage at this time, not the final winner's stage.
                earlier=[e for e in ev if e['elapsed_seconds']<=cutoff]
                phase=earlier[-1]['event'] if earlier else 'initialization'
                stage=next((e for e in reversed(earlier) if 'source' in e or e['event'].startswith('diagnostic')), {})
                cost=best.get('seed_solve_seconds')
                trajectories.append(dict(case=case,q=q,n=n,method=req['mode'],cutoff_seconds=cutoff,
                    graph_elapsed_seconds=cutoff,best_makespan=best.get('makespan'),winner_source=best.get('source'),
                    winner_candidate=best.get('name'),active_phase=phase,active_source=stage.get('source',stage.get('mode')),
                    active_q=stage.get('q'),active_n=stage.get('n'),
                    status='stopped_hold' if cutoff>=elapsed and best else 'observed' if best else 'no_incumbent_yet',
                    observed_at_seconds=best.get('elapsed_seconds'),seed_solve_seconds=cost,
                    end_to_end_seconds=cost+cutoff if cost is not None else None,
                    official_calls=sum(e['event']=='evaluation_end' for e in earlier)))
        improvements.extend(dict(case=case,**{k:v for k,v in e.items() if k!='case'}) for e in ev if e['event']=='improvement')
        sources=defaultdict(lambda:defaultdict(float))
        for e in ev:
            if 'q' not in e or 'source' not in e:continue
            s=sources[e['q'],e['n'],e['source']]
            if e['event']=='step':
                s['work_seconds']+=e['seconds'];s['generation_seconds']+=e['generation_seconds'];s['improvements']+=int(e['improved']);s['gain_fraction_sum']+=e['gain_fraction']
            if e['event']=='evaluation_end':
                s['evaluations']+=1;s['evaluation_seconds']+=e['eval_audit_seconds'];s['failed']+=e['status']!='ok'
            if e['event']=='duplicate':s['duplicates']+=1
            if e['event']=='generation_error':s['generation_errors']+=1
            if e['event']=='bound_pruned':s['bound_pruned']+=1
        source_rows.extend(dict(case=case,q=q,n=n,source=s,**metrics) for (q,n,s),metrics in sources.items())
        for r in rr:
            if not r.get('result_file'):continue
            raw=read(r['result_file'])['official_result'];mk=raw['makespan']
            for core in raw['per_core_timeline']:
                for pipe in ('PIPE_M','PIPE_V','PIPE_MTE2','PIPE_MTE3'):
                    ops=[o for o in core['ops'] if o['pipe']==pipe]
                    pipes.append(dict(case=case,q=r['q'],n=r['n'],core=core['core_id'],pipe=pipe,
                        busy_cycles=sum(o['end']-o['start'] for o in ops),
                        utilization=sum(o['end']-o['start'] for o in ops)/max(1,mk),
                        core_last_end=max((o['end'] for o in core['ops']),default=0),makespan=mk))
            if r['q']==3:
                from research_a_orion_track_anytime.trace import read_requests
                reads,fills=read_requests(raw);stats=defaultdict(lambda:dict(count=0,bytes=0))
                for e in reads:stats[e['cause']]['count']+=1;stats[e['cause']]['bytes']+=e['bytes']
                cache_rows.extend(dict(case=case,n=r['n'],cause=cause,**m) for cause,m in stats.items())
                if detailed:
                    path=paper/'cache_reads'/f'{case}_n{r["n"]}.csv.gz';path.parent.mkdir(parents=True,exist_ok=True)
                    with gzip.open(path,'wt',encoding='utf-8',newline='') as f:
                        fields=list(dict.fromkeys(k for row in reads for k in row));w=csv.DictWriter(f,fields);w.writeheader();w.writerows(reads)
    unique={(r['case'],r['q'],r['n']) for r in rows}
    if len(unique)!=len(rows):raise ValueError('Duplicate case/q/n in primary dataset')
    expected_cases=expected_cases or [p.name for p in folders]
    if keys is None and (root/'campaign.json').is_file():keys=read(root/'campaign.json')['policy']['keys']
    if keys is None:
        from .run import required
        keys=required()
    wanted={(c,q,n) for c in expected_cases for q,n in [(0,1)]+list(keys)}
    missing=sorted(wanted-unique)
    regressions=[r for r in rows if r.get('old_makespan') and r.get('new_makespan') and r['new_makespan']>r['old_makespan']]
    incomplete=[(r['case'],r['q'],r['n']) for r in rows if r['status']!='ok' or (r['q']==3 and r['pair_status']!='ok')]
    queue=[]
    for r in rows:
        if r.get('q')==0:continue
        if r['status']!='ok':reason='missing_incumbent'
        elif r.get('old_makespan') and r['new_makespan']>r['old_makespan']:reason='selected_regression'
        elif r.get('published_target_makespan') and r.get('new_makespan') and r['new_makespan']>r['published_target_makespan']*1.005:reason='published_target_gap'
        elif r.get('best_unprotected_makespan') and r.get('old_makespan') and r['best_unprotected_makespan']>r['old_makespan']*1.005 and r.get('evaluations',0)>=6:reason='all_new_candidates_below_reference'
        else:continue
        queue.append(dict(case=r['case'],q=r['q'],n=r['n'],reason=reason,
            reference=r.get('old_makespan') or r.get('published_target_makespan'),selected=r.get('new_makespan'),raw_best=r.get('best_unprotected_makespan'),
            first_stage='SM SF MF',second_stage='S M F only if unresolved'))
    # Portable published paths, after loading full responses for metrics.
    for r in rows:
        for field in ('plan_file','result_file','pair_file'):
            if r.get(field):r[field]=str(Path(r[field]).relative_to(root))
    csv_write(root/'per_case.csv',rows);csv_write(root/'trajectory.csv',trajectories)
    csv_write(paper/'budget_prefixes.csv',trajectories);csv_write(paper/'improvement_edges.csv',improvements)
    csv_write(paper/'source_costs.csv',source_rows);csv_write(paper/'pipe_utilization.csv',pipes)
    csv_write(paper/'graph_features.csv',[dict(case=folder.name,**{k:v for k,v in e.items() if k not in ('event','case')}) for folder in folders for e in events(folder) if e['event']=='graph_features'])
    csv_write(paper/'cache_miss_causes.csv',cache_rows);csv_write(paper/'graph_costs.csv',graph_costs)
    csv_write(root/'diagnostic_queue.csv',queue)
    for q in (1,2,3):
        appendix=[r for r in rows if r['q']==q]
        if q in (1,2):appendix += [dict(r,q=q,n=1,source='fixed_singlecore_baseline',speedup=1.) for r in rows if r['q']==0]
        csv_write(paper/f'appendix_q{q}.csv',appendix)
    curves=[]
    for q in (1,2,3):
        for n in range(1,6):
            selected=[r for r in rows if r['q']==q and r['n']==n and r.get('speedup')]
            if n==1 and q in (1,2):
                selected=[dict(r,speedup=1.,new_makespan=r['baseline']) for r in rows if r['q']==0 and r.get('baseline')]
            if not selected:continue
            vals=[r['speedup'] for r in selected]
            pairs=[r['cache_speedup'] for r in selected if r.get('cache_speedup')]
            curves.append(dict(q=q,n=n,count=len(vals),expected_graphs=len(expected_cases),
                arithmetic_mean=mean(vals),median=median(vals),p10=quantile(vals,.1),p90=quantile(vals,.9),
                std=pstdev(vals),mean_same_plan_cache_speedup=mean(pairs) if pairs else None,
                complete_population=len(vals)==len(expected_cases)))
    csv_write(paper/'curves_1_to_5.csv',curves)
    worker_errors=[str(p.relative_to(root)) for p in (root/'graphs').glob('case_*/error.json')]
    complete=not missing and not incomplete and not regressions and not worker_errors and len(unique)==len(wanted)
    status=dict(created_utc=utc(),complete=complete,expected_main=len(wanted),observed_main=len(rows),
        expected_pairs=sum(q==3 for _,q,_ in wanted),valid_pairs=sum(r['q']==3 and r['pair_status']=='ok' for r in rows),
        missing=missing,incomplete=incomplete,worker_errors=worker_errors,selected_regressions=len(regressions),
        improvements=sum(r.get('old_makespan') is not None and r.get('new_makespan') is not None and r['new_makespan']<r['old_makespan'] for r in rows),
        published_target_regressions=sum(bool(r.get('published_target_makespan') and r.get('new_makespan') and r['new_makespan']>r['published_target_makespan']) for r in rows),
        graphs=len(folders),clock='one shared graph clock; historical seed cost is separate',formal_100_graph=len(expected_cases)==100 and complete)
    write(root/'next_seeds.json',dict(schema=1,targets=[],entries=[dict(case=r['case'],q=r['q'],n=r['n'],makespan=r['new_makespan'],added_copy_bytes=r['new_added_copy_bytes'],plan_file=r['plan_file'],result_file=r['result_file'],pair_file=r.get('pair_file'),seed_solve_seconds=r.get('total_solve_seconds'),origin=str(root),cost_scope='shared_graph_clock_not_additive') for r in rows if r['status']=='ok']))
    write(root/'collection.json',status)
    return status

def main():
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--detailed',action='store_true');a=p.parse_args()
    print(json.dumps(collect(a.root,detailed=a.detailed),ensure_ascii=False))
if __name__=='__main__':main()
