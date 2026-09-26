"""Review actual selected responses and provenance, not a synthetic test suite."""
from __future__ import annotations
import argparse, json, shutil
from pathlib import Path
from .io import read,write,csv_write,official_root,csv_read
from .vendor.orion.core import Graph,Config
from .vendor.orion.worker import audit
from .report import prefixes


def run(root,out,official=None):
    root,out=Path(root),Path(out);out.mkdir(parents=True,exist_ok=True)
    of,cfgp=official_root(official);cfg=Config.read(cfgp);graphs={};rows=[];curves=[];events=[];verify=[];f_proofs=[];candidate_calls=[]
    refs=Path(__file__).parent.parent/'research_a_orion_anytime/team_results/day01/combined_final/per_case.csv'
    published={(r['case'],int(r['q']),int(r['n'])):r for r in csv_read(refs)} if refs.is_file() else {}
    folders=[]
    for runroot in root.iterdir():
        if not runroot.is_dir():continue
        folders.extend((runroot,x.parent) for x in (runroot/'jobs').glob('*/summary.json'))
        if runroot.name.startswith('diagnostic_'):
            folders.extend((runroot,x.parent) for x in runroot.glob('*/summary.json') if x.parent.name in ('s','m','f','sm','sf','mf','smf'))
    for rr,folder in sorted(folders):
        s=read(folder/'summary.json');req=read(folder/'request.json');state=read(folder/'progress.json')
        c,q,n=s['case'],s['q'],s['n'];g=graphs.setdefault(c,Graph(read(of/'data'/f'{c}.json'))) if c not in graphs else graphs[c]
        plan=read(folder/'plan.json');resp=read(folder/'result.json.gz');raw=resp['official_result']
        checked=audit(g,plan,raw,q,cfg)
        if not checked['ok']:raise ValueError((folder,checked))
        inline=folder/'same_plan_no_l2_result.json.gz';external=rr/'pairs'/folder.name/'result.json.gz'
        pairpath=inline if inline.exists() and s.get('pair_status')=='ok' else external if external.exists() else None
        pairval=None
        if q==3 and pairpath:
            pp=folder/'same_plan_no_l2_plan.json' if pairpath==inline else pairpath.parent/'plan.json'
            if read(pp)!=plan:raise ValueError('Actual paired plan differs')
            pair=read(pairpath);v=audit(g,plan,pair['official_result'],2,cfg)
            if pair['status']!='ok' or not v['ok']:raise ValueError(('pair',folder))
            pairval=pair['official_result']['makespan']
        p=published.get((c,q,n),{});baseline=s.get('baseline_makespan');m=raw['makespan']
        row=dict(experiment=rr.name,arm=folder.name,case=c,q=q,n=n,components=s.get('components'),version=s.get('version'),
                 mode=req.get('mode'),published_day01=int(p['makespan']) if p else None,
                 initial_baseline=baseline,new_makespan=m,relative_gain_from_initial=1-m/baseline if baseline else None,
                 published_speedup_ratio=int(p['makespan'])/m if p else None,reference_singlecore=int(p['baseline']) if p else None,
                 local_seconds=s.get('execution',{}).get('wall_seconds'),job_seconds=req.get('job_seconds'),
                 seed_primary_seconds=req.get('source_seed_seconds'),full_history_cost_known=not bool(req.get('alternatives') or req.get('baseline_alternatives')) and req.get('source_seed_seconds') is not None,
                 added_copy_bytes=raw['data_movement_bytes']['added_copy_bytes'],spill_bytes=raw['data_movement_bytes']['spill_added_copy_bytes'],
                 cache_hit_rate=raw.get('cache_stats',{}).get('hit_rate'),no_l2_makespan=pairval,pair_status='ok' if pairval is not None else 'not_applicable' if q!=3 else 'missing',
                 pair_seconds=s.get('pair_seconds'),calls=len(state['attempts']),generation_seconds=state.get('candidate_generation_seconds'),
                 construction_seconds=state.get('construction_seconds'),official_seconds=state.get('official_eval_seconds'),io_seconds=state.get('io_seconds'),
                 stop=s.get('stop_reason'),selected_family=s.get('selected_family'),selected_name=s.get('selected_name'),
                 plan_file=str(folder.relative_to(root)/'plan.json'),result_file=str(folder.relative_to(root)/'result.json.gz'))
        rows.append(row);verify.append(dict(experiment=rr.name,arm=folder.name,main_ok=True,pair_ok=pairval is not None if q==3 else None))
        for e in prefixes(folder):curves.append(dict(experiment=rr.name,arm=folder.name,**e))
        for e in state.get('improvement_events',[]):events.append(dict(experiment=rr.name,arm=folder.name,case=c,q=q,n=n,**e))
        previous=read(folder/'seed_plan.json') if (folder/'seed_plan.json').exists() else None
        for a in state.get('attempts',[]):
            candidate_calls.append(dict(experiment=rr.name,arm=folder.name,case=c,q=q,n=n,**{k:a.get(k) for k in ('index','name','family','source','status','makespan','added_copy_bytes','accepted','gain_fraction','started_seconds','completed_seconds','generation_seconds','eval_seconds','eval_and_audit_seconds','parent_epoch','parent_makespan')}))
            if a.get('accepted'):
                candidate=read(folder/a['plan_file'])
                if a.get('source')=='f' and previous:
                    f_proofs.append(dict(experiment=rr.name,arm=folder.name,index=a['index'],name=a['name'],
                        mapping_unchanged=candidate['node_to_subgraph']==previous['node_to_subgraph'],
                        owner_unchanged=all(set(x)==set(y) for x,y in zip(candidate['core_schedules'],previous['core_schedules'])),
                        makespan=a['makespan'],previous_makespan=a.get('parent_makespan')))
                previous=candidate
    csv_write(out/'all_measured_arms.csv',rows);csv_write(out/'anytime_30_seconds.csv',curves)
    csv_write(out/'all_improvement_events.csv',events);csv_write(out/'candidate_calls.csv',candidate_calls)
    csv_write(out/'fifo_accepted_mapping_checks.csv',f_proofs)
    write(out/'selected_response_checks.json',verify)
    write(out/'SUMMARY.json',{'selected_main_responses':len(rows),'selected_q3_pairs':sum(r['pair_status']=='ok' for r in rows),
        'official_main_calls_started':len(candidate_calls),'all_selected_main_audit_ok':True,
        'fifo_accepted_reorders_checked':len(f_proofs),'all_fifo_fixed_mapping_owner':all(r['mapping_unchanged'] and r['owner_unchanged'] for r in f_proofs),
        'formal_100_run':False,'statistic_scope':'distinct experiments/versions retained; no best-of-versions performance splicing'})
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True);p.add_argument('--out',required=True);p.add_argument('--official');a=p.parse_args();print(len(run(a.root,a.out,a.official)))
if __name__=='__main__':main()
