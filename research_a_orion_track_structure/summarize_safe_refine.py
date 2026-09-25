"""Summarize actually selected warm plans; distinguish full-ledger arithmetic from reruns."""
from __future__ import annotations
import argparse,csv,json,gzip
from pathlib import Path
from collections import Counter,defaultdict
ROOT=Path(__file__).resolve().parents[1]

def read(p):
    with (gzip.open(p,'rt',encoding='utf-8-sig') if str(p).endswith('.gz') else open(p,encoding='utf-8-sig')) as f:return json.load(f)
def csvwrite(p,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with open(p,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,required=True);ap.add_argument('--day',type=Path,default=ROOT/'research_a_orion_anytime/team_results/day01/combined_final/per_case.csv');a=ap.parse_args();run=a.run.resolve()
    manifest=read(run/'manifest.json');jobs=read(run/'all_jobs.json');formal=list(csv.DictReader(a.day.open(encoding='utf-8-sig')))
    fm={(r['case'].removeprefix('case_'),int(r['q']),int(r['n'])):r for r in formal};jobmap={(r['case'],r['q'],r['n'],r['method']):r for r in jobs}
    rows=[];prefixes=[];diagnostics={};improvements=[]
    for sel in sorted(run.glob('selected/*/selection.json')):
        s=read(sel);key=s['case'],s['q'],s['n'];f=fm[key];result=read(sel.parent/'response.json.gz');raw=result['official_result'];plan=read(sel.parent/'plan.json')
        if result['status']!='ok' or not result['audit']['ok']:raise ValueError('invalid selected response '+str(sel))
        if raw['makespan']!=s['makespan'] or raw['num_cores']!=s['n'] or len(plan['core_schedules'])!=s['n']:raise ValueError('selected plan/result mismatch')
        if s['makespan']>s['seed_makespan']:raise ValueError('protected-seed regression')
        old=jobmap.get((*key,'old'),{});safe=jobmap.get((*key,'safe'),{})
        winning=old if old.get('plan_file')==s['origin_plan'] else safe if safe.get('plan_file')==s['origin_plan'] else None
        if winning is None:
            for r in (old,safe):
                if r.get('makespan')==s['makespan'] and r.get('result_file'):
                    if read(r['plan_file'])==plan:winning=r;break
        pair=(winning or {}).get('no_l2',{})
        pair_ok=False
        if s['q']==3 and pair.get('plan_file') and pair.get('result_file'):
            pr=read(pair['result_file']);pair_ok=read(pair['plan_file'])==plan and pr.get('status')=='ok' and pr['audit']['ok']
        b=int(f['baseline']);row=dict(case=s['case'],q=s['q'],n=s['n'],formal_makespan=int(f['makespan']),seed_makespan=s['seed_makespan'],old_warm_makespan=old.get('makespan'),safe_warm_makespan=safe.get('makespan'),selected_makespan=s['makespan'],baseline=b,formal_speedup=b/int(f['makespan']),seed_speedup=b/s['seed_makespan'],selected_speedup=b/s['makespan'],new_reduction_pct=100*(1-s['makespan']/s['seed_makespan']),total_reduction_vs_formal_pct=100*(1-s['makespan']/int(f['makespan'])),winning_arm=(winning or {}).get('method','seed'),winning_name=s['winning_name'],added_copy_bytes=raw['data_movement_bytes']['added_copy_bytes'],spill_added_copy_bytes=raw['data_movement_bytes'].get('spill_added_copy_bytes'),lower=result['audit']['certificate']['global_lower'],portfolio_seconds=s['portfolio_seconds'],seed_validation_seconds=s['seed_validation_seconds'],seed_solve_seconds=s.get('seed_solve_seconds'),total_solve_seconds=None if s.get('seed_solve_seconds') is None else s['seed_solve_seconds']+s['seed_validation_seconds']+s['portfolio_seconds'],no_l2_makespan=pair.get('makespan') if pair_ok else None,cache_speedup=pair['makespan']/s['makespan'] if pair_ok else None,pair_status='ok' if pair_ok else 'missing' if s['q']==3 else 'not_applicable',no_regression=True)
        rows.append(row)
        for t in (30,60,120,300,600):
            obs=[o for o in s['observations'] if o['elapsed_seconds']<=t];best=min(obs,key=lambda x:x['makespan']) if obs else None
            prefixes.append(dict(case=s['case'],q=s['q'],n=s['n'],mode='costed_warm_portfolio',budget_seconds=t,elapsed_seconds=min(t,s['portfolio_seconds']),phase='stopped_carry_forward' if t>s['portfolio_seconds'] else 'running_prefix',best_makespan=best['makespan'] if best else None,speedup=b/best['makespan'] if best else None,total_elapsed_seconds=None if s.get('seed_solve_seconds') is None else s['seed_solve_seconds']+s['seed_validation_seconds']+min(t,s['portfolio_seconds'])))
        diagnostics[str(key)]={'cores':[dict(core=c['core_id'],end=max((o['end'] for o in c['ops']),default=0),ops=len(c['ops']),groups=len(plan['core_schedules'][c['core_id']])) for c in raw['per_core_timeline']], 'audit':result['audit'],'data_movement':raw['data_movement_bytes']}
    for r in jobs:
        jp=Path(r['job'])/'progress.json'
        if not jp.exists():continue
        state=read(jp)
        for e in state.get('attempts',[]):
            if e.get('improved'):
                improvements.append(dict(case=r['case'],q=r['q'],n=r['n'],method=r['method'],index=e.get('index'),name=e.get('name'),family=e.get('family'),makespan=e.get('makespan'),added_copy_bytes=e.get('added_copy_bytes'),elapsed_seconds=e.get('completed_seconds')))
    means=[]
    for q in manifest['questions']:
        for n in manifest['cores']:
            selected=[r for r in rows if r['q']==q and r['n']==n];allf=[r for r in formal if int(r['q'])==q and int(r['n'])==n]
            if not selected:continue
            prior=sum(float(r['speedup']) for r in allf)/len(allf)
            initial=prior+sum(r['seed_speedup']-r['formal_speedup'] for r in selected)/len(allf)
            final=prior+sum(r['selected_speedup']-r['formal_speedup'] for r in selected)/len(allf)
            means.append(dict(q=q,n=n,selected_cases=len(selected),sample_formal_mean=sum(r['formal_speedup'] for r in selected)/len(selected),sample_seed_mean=sum(r['seed_speedup'] for r in selected)/len(selected),sample_final_mean=sum(r['selected_speedup'] for r in selected)/len(selected),reference_ledger_cases=len(allf),reference_formal_mean=prior,hybrid_seed_mean=initial,hybrid_final_mean=final,new_mean_gain=final-initial,hybrid_gain_vs_formal=final-prior,full_algorithm_rerun=False,other_cases_unchanged=True,other_tracks_not_integrated=True))
    csvwrite(run/'selected_comparison.csv',rows);csvwrite(run/'portfolio_trajectory.csv',prefixes);csvwrite(run/'means.csv',means);csvwrite(run/'safe_improvements.csv',improvements)
    expected={(c,q,n) for c in manifest['cases'] for q in manifest['questions'] for n in manifest['cores']};done={(r['case'],r['q'],r['n']) for r in rows}
    stats=dict(planned_configurations=len(expected),selected_configurations=len(done),not_completed=[list(x) for x in sorted(expected-done)],selected_improved=sum(r['selected_makespan']<r['seed_makespan'] for r in rows),selected_equal=sum(r['selected_makespan']==r['seed_makespan'] for r in rows),selected_regressed=sum(r['selected_makespan']>r['seed_makespan'] for r in rows),algorithm_arms=len(jobs),arm_status_counts=dict(Counter(r['status'] for r in jobs)),selected_q3_pairs_valid=sum(r['pair_status']=='ok' for r in rows),actual_wall_seconds=manifest.get('actual_wall_seconds'),portfolio_work_seconds=sum(r['portfolio_seconds']+r['seed_validation_seconds'] for r in rows),means=means)
    (run/'FINAL_STATS.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf8');(run/'selected_diagnostics.json').write_text(json.dumps(diagnostics,separators=(',',':')),encoding='utf8')
    print(json.dumps(stats,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
