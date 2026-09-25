"""Tables for the required appendices and paper figures, from actual records."""
from __future__ import annotations
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from .io import read,write,csv_write


def build(destination, rows, records, prefixes):
    out=Path(destination)/'paper_data';out.mkdir(parents=True,exist_ok=True)
    main=[r for r in rows if r.get('status')=='ok'];by_case={r['case']:r for r in main if r['q']==0}
    curves=[]
    for q in (1,2,3):
        for n in range(1,6):
            points=[{'case':c,'speedup':1.0} for c in by_case] if q in (1,2) and n==1 else [r for r in main if r['q']==q and r['n']==n and r.get('speedup') is not None]
            vals=sorted(r['speedup'] for r in points)
            def quantile(f):
                if not vals:return None
                at=(len(vals)-1)*f;i=int(at);j=min(i+1,len(vals)-1)
                return vals[i]+(vals[j]-vals[i])*(at-i)
            cur={'q':q,'n':n,'count':len(vals),'mean_speedup':mean(vals) if vals else None,
                 'median_speedup':median(vals) if vals else None,'p10':quantile(.1),'p90':quantile(.9),
                 'min_speedup':vals[0] if vals else None,'max_speedup':vals[-1] if vals else None,
                 'single_core_point':'original_baseline' if q<3 and n==1 else 'evaluated_solution'}
            pairs=[r for r in points if r.get('pair_status')=='ok']
            if pairs:
                cur['same_plan_no_l2_mean_speedup']=mean(r['reference']/r['no_l2_makespan'] for r in pairs)
                cur['same_plan_cache_ratio_mean']=mean(r['same_plan_cache_speedup'] for r in pairs)
                cur['cache_pair_count']=len(pairs)
            curves.append(cur)
    csv_write(out/'mean_speedup_1_to_5_cores.csv',curves)
    csv_write(out/'per_case_all_metrics.csv',rows)
    for q in (1,2,3):
        appendix=[dict(r,point_kind='evaluated') for r in rows if r['q']==q]
        if q in (1,2):
            appendix += [dict(r,q=q,point_kind='original_singlecore_baseline',speedup=1.0) for r in rows if r['q']==0]
        csv_write(out/f'appendix_q{q}.csv',sorted(appendix,key=lambda r:(r['case'],r['n'])))
    cache_rows=[r for r in main if r['q']==3]
    csv_write(out/'q3_same_plan_cache_pairs.csv',cache_rows)
    events=[]; attempts=[];phase_rows=[];core_rows=[];features=[];seengraph=set()
    for (case,q,n),(summary,folder,root) in sorted(records.items()):
        p=folder/'progress.json'
        if not p.is_file():continue
        state=read(p);info={'case':case,'q':q,'n':n,'components':summary.get('components')}
        for event in state.get('improvement_events',[]):events.append({**info,**event})
        for r in state.get('attempts',[]):
            attempts.append({**info,**{k:r.get(k) for k in ('index','name','family','source','status','accepted',
                'gain_fraction','makespan','added_copy_bytes','generation_seconds','started_seconds',
                'completed_seconds','eval_seconds','eval_and_audit_seconds')}})
        phase=state.get('phase_events',[]);durations=defaultdict(float)
        end=summary.get('execution',{}).get('wall_seconds',state.get('elapsed_seconds',0))
        for i,a in enumerate(phase):
            b=phase[i+1]['elapsed_seconds'] if i+1<len(phase) else end
            durations[a.get('optimization_stage'),a['phase'],a.get('source')] += max(0,b-a['elapsed_seconds'])
        for (stage,phase_name,source),sec in durations.items():
            phase_rows.append({**info,'optimization_stage':stage,'phase':phase_name,'source':source,'seconds':sec})
        if case not in seengraph and state.get('graph_features'):
            features.append({'case':case,**state['graph_features'],'bound_core_count':n,'bound_question':q});seengraph.add(case)
        if summary.get('status')!='ok':continue
        result=read(folder/'result.json.gz')['official_result'];t=result['makespan']
        for core in result['per_core_timeline']:
            k=core['core_id'];work=defaultdict(float);count=defaultdict(int)
            for op in core['ops']:
                work[op['pipe']] += op['end']-op['start'];count[op['pipe']]+=1
            for pipe,w in work.items():
                core_rows.append({**info,'core_id':k,'pipe':pipe,'busy_cycles':w,'makespan_cycles':t,
                    'utilization':w/t if t else 0,'operation_count':count[pipe],
                    'interpretation':'observed occupied intervals, not additive causes of makespan'})
    csv_write(out/'anytime_30_seconds.csv',prefixes)
    csv_write(out/'incumbent_improvements.csv',events)
    csv_write(out/'candidate_attempts.csv',attempts)
    csv_write(out/'optimization_phase_seconds.csv',phase_rows)
    csv_write(out/'per_core_pipe_utilization.csv',core_rows)
    csv_write(out/'graph_features.csv',features)
    families=[];grouped=defaultdict(list)
    for r in attempts:grouped[r['q'],r.get('family')].append(r)
    for (q,family),rs in sorted(grouped.items(),key=lambda x:str(x[0])):
        families.append({'q':q,'family':family,'evaluated':len(rs),'valid':sum(r['status']=='ok' for r in rs),
            'makespan_improvements':sum((r.get('gain_fraction') or 0)>0 for r in rs),
            'accepted_including_bytes_ties':sum(bool(r.get('accepted')) for r in rs),
            'generation_seconds':sum(r.get('generation_seconds') or 0 for r in rs),
            'official_eval_seconds':sum(r.get('eval_seconds') or 0 for r in rs)})
    csv_write(out/'source_yield_and_cost.csv',families)
    write(out/'DATA_DICTIONARY.json',{'makespan':'official cycles; smaller is better','speedup':'original singlecore cycles / selected cycles',
        'bytes':'official extra COPY byte count, split into boundary and Spill','seconds':'host wall seconds, not device cycles',
        'time_cap':'per (graph,question,core_count) process start to persisted plan, <=600 seconds',
        'time_curves':'30 second cutoffs of observed incumbent events; stopped_hold is held output, not extra search',
        'warm_start':'historical seed acquisition is separate; unknown history is not set to zero',
        'source_yield':'search attribution for this trajectory, not a causal ablation effect',
        'bound':'lower is a global necessary-condition bound; 1-L/U upper-bounds possible remaining relative decrease',
        'missing':'blank/failed is not zero','formal_status':'see ../report.json; small subsets are not 100-case estimates',
        'cache_grid':'produced separately by mechanisms.py; never mixed with official-default rows'})
