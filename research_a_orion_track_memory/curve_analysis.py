"""Derive tables from saved official responses; no evaluator calls or rescoring."""
from __future__ import annotations
import argparse,csv,json
from collections import Counter,defaultdict
from pathlib import Path
from statistics import mean
from .continuous_run import read,write,table,OFFICIAL
from research_a_orion_anytime.core import Graph,Config,plan_view,planned_traffic,bounds


def intervals(raw):
    """Wall-time unions, not summed per-pipe cycles or measured DDR transactions."""
    changes=defaultdict(lambda:[0,0]);busy=defaultdict(int)
    for c in raw['per_core_timeline']:
        for o in c['ops']:
            typ=int(o['op'] in ('COPY_IN','COPY_OUT'))
            changes[o['start']][typ]+=1;changes[o['end']][typ]-=1
            busy[c['core_id'],o['pipe']]+=o['end']-o['start']
    live=[0,0];last=0;compute=copy=both=copy_only=idle=0
    for t,ds in sorted(changes.items()):
        dt=t-last
        if live[0]:compute+=dt
        if live[1]:copy+=dt
        if all(live):both+=dt
        if live[1] and not live[0]:copy_only+=dt
        if not any(live):idle+=dt
        live=[live[i]+ds[i] for i in (0,1)];last=t
    return dict(compute_union_cycles=compute,copy_union_cycles=copy,copy_compute_overlap_cycles=both,
                copy_without_compute_cycles=copy_only,all_pipes_idle_cycles=idle)


def plan_features(g,plan,q):
    mapping,groups,core,_=plan_view(g,plan)
    owners={u:core[mapping[u]] for u in g.ops};n=len(plan['core_schedules'])
    load=max(g.weight(u for u in g.ops if owners[u]==k) for k in range(n))
    return dict(subgraphs=len(groups),effective_cores=len(set(core.values())),pre_spill_bytes=sum(planned_traffic(g,plan,q)),
                maximum_core_compute_load=load),owners


def main(argv=None):
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--root',default='.');a.add_argument('--run',required=True);args=a.parse_args(argv)
    root=Path(args.root).resolve();run=Path(args.run).resolve();rows=list(csv.DictReader((run/'per_case.csv').open(encoding='utf8')))
    means=[]
    for q in (1,2,3):
        for n in range(1,6):
            rs=[r for r in rows if int(r['q'])==q and int(r['n'])==n]
            if not rs:continue
            complete=all(r['search_status'] in ('completed','hard_time_budget') for r in rs)
            old,new=mean(float(r['old_speedup']) for r in rs),mean(float(r['new_speedup']) for r in rs)
            means.append(dict(q=q,n=n,graphs=len(rs),complete_attempted_coverage=complete,old_mean_speedup=old,new_mean_speedup=new,
              relative_change_pct=100*(new/old-1),strict_makespan_wins=sum(float(r['new_makespan'])<float(r['old_makespan']) for r in rs),
              byte_only_ties=sum(float(r['new_makespan'])==float(r['old_makespan']) and float(r['new_added_copy_bytes'])<float(r['old_added_copy_bytes']) for r in rs),
              retained=sum(not r['result_file'] for r in rs),regressions=sum(float(r['new_makespan'])>float(r['old_makespan']) for r in rs),
              old_cache_ratio_mean=mean(float(r['old_cache_speedup']) for r in rs) if q==3 and all(r['old_cache_speedup'] for r in rs) else '',
              new_cache_ratio_mean=mean(float(r['new_cache_speedup']) for r in rs) if q==3 and all(r['new_cache_speedup'] for r in rs) else ''))
    table(run/'curve_means.csv',means)
    graphs={};features=[];counterexamples=[];phase=Counter();status=Counter();gen_status=Counter();eval_time=0.;calls=0
    cfg=Config.read(root/OFFICIAL/'data/config.txt')
    for row in rows:
        out=(run/row['plan_file']).parent
        # Selected plans can live under raw/, whereas the request lives at job root.
        job=run/'jobs'/f"{row['case']}_q{row['q']}_n{row['n']}"
        if not (job/'progress.json').exists():continue
        s=read(job/'progress.json')
        for d in s.get('diagnostics',[]):gen_status[d['status']]+=1
        for t in s['attempts']:
            status[t['status']]+=1
            if t['status']=='ok':
                calls+=1;eval_time+=t['eval_seconds'];phase[t['phase']]+=int(t.get('accepted',False))
                ms,copy=float(t['makespan']),float(t['added_copy_bytes']);oldms,oldcopy=float(row['old_makespan']),float(row['old_added_copy_bytes'])
                label='fewer_bytes_but_slower' if copy<oldcopy and ms>oldms else 'more_bytes_but_faster' if copy>oldcopy and ms<oldms else ''
                if label:
                    counterexamples.append(dict(case=row['case'],q=row['q'],n=row['n'],kind=label,name=t['name'],
                      old_makespan=oldms,candidate_makespan=ms,old_copy_bytes=oldcopy,candidate_copy_bytes=copy,
                      spill_bytes=t['spill_bytes'],accepted=t.get('accepted'),plan_file=str((job/t['plan_file']).relative_to(run)),result_file=str((job/t['result_file']).relative_to(run))))
        if not row['result_file']:continue
        case=row['case'];q=int(row['q']);n=int(row['n'])
        if case not in graphs:graphs[case]=Graph(read(root/OFFICIAL/'data'/f'{case}.json'))
        g=graphs[case];seed=read(job/'seed_plan.json');plan=read(run/row['plan_file']);raw=read(run/row['result_file'])['official_result']
        oldf,oldowners=plan_features(g,seed,q);newf,newowners=plan_features(g,plan,q);limits=bounds(g,cfg,n,q,plan)
        transfers=raw.get('cross_core_transfers',[]);cache=raw.get('cache_stats',{});peak=raw.get('memory_peak_by_core',{})
        features.append(dict(case=case,q=q,n=n,selected_name=row['selected_name'],old_makespan=row['old_makespan'],new_makespan=row['new_makespan'],
          **{f'old_{k}':v for k,v in oldf.items()},**{f'new_{k}':v for k,v in newf.items()},
          operations_changed_core=sum(oldowners[u]!=newowners[u] for u in g.ops),task_count=raw['task_count'],
          official_peak_l1=max((v.get('L1',0) for v in peak.values()),default=0),official_peak_ub=max((v.get('UB',0) for v in peak.values()),default=0),
          maximum_copy_queue_cycles=max((t['copy_in_start']-t['copy_in_release'] for t in transfers),default=0),
          cross_core_transfers=len(transfers),new_spill_bytes=row['new_spill_bytes'],new_added_copy_bytes=row['new_added_copy_bytes'],
          global_lower=limits['global_lower'],candidate_lower=limits['candidate_lower'],certificate_ratio=float(row['new_makespan'])/limits['global_lower'],
          hit_bytes=cache.get('hit_bytes',0),**intervals(raw)))
    table(run/'mechanisms.csv',features);table(run/'counterexamples.csv',counterexamples)
    summary=dict(rows=len(rows),strict_makespan_wins=sum(float(r['new_makespan'])<float(r['old_makespan']) for r in rows),
       byte_only_ties=sum(float(r['new_makespan'])==float(r['old_makespan']) and float(r['new_added_copy_bytes'])<float(r['old_added_copy_bytes']) for r in rows),
       retained=sum(not r['result_file'] for r in rows),regressions=sum(float(r['new_makespan'])>float(r['old_makespan']) for r in rows),
       completed_official_candidates=calls,attempt_status=dict(status),accepted_by_phase=dict(phase),generator_status=dict(gen_status),
       official_eval_seconds=eval_time,all_process_seconds=sum(float(r['added_solve_seconds']) for r in rows),
       pair_seconds=sum(float(r['pair_seconds']) for r in rows),counterexample_counts=dict(Counter(x['kind'] for x in counterexamples)),
       q3_pair_status=dict(Counter(r['pair_status'] for r in rows if r['q']=='3')),
       evidence_limit='Official reported memory peaks; no independent physical-residency reconstruction. COPY unions are not measured DDR transactions.')
    write(run/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
