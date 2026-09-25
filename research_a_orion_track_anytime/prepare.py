"""Locate formal plans in raw records; re-evaluate and inspect true cache events."""
import argparse,csv,time,traceback
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from .storage import read,write
ROOT=Path(__file__).resolve().parents[1]
OFF=ROOT/'题目/A题/通用神经网络处理器下的多核调度问题  附件'
def csv_write(path,rows):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def fixed(spec):
    from research_a_orion_anytime.engine import OfficialSession
    from .diagnose import diagnose
    started=time.monotonic();dst=Path(spec['seed_job']);dst.mkdir(parents=True,exist_ok=False)
    write(dst/'request.json',spec);plan=read(spec['original_plan'])
    session=OfficialSession(OFF,OFF/'data'/f"{spec['case']}.json",OFF/'data/config.txt')
    r=session.evaluate(plan,spec['q']);write(dst/'plan.json',plan);write(dst/'response.json.gz',r)
    t=r['official_result']['makespan']
    if r['status']!='ok' or t!=spec['recorded_makespan']:raise ValueError('formal replay mismatch '+str((spec['case'],spec['q'],spec['n'],t,spec['recorded_makespan'])))
    write(dst/'progress.json',dict(case=spec['case'],q=spec['q'],n=spec['n'],status='ok',evaluations=1,attempts=[],incumbent=dict(plan_file='plan.json',result_file='response.json.gz',makespan=t,added_copy_bytes=r['official_result']['data_movement_bytes']['added_copy_bytes'],name='verified_formal',elapsed_seconds=0.,certificate=r['audit']['certificate'])))
    spec={**spec,'replayed_makespan':t,'validation_seconds':time.monotonic()-started,'eval_seconds':r['eval_seconds'],'result_file':str(dst/'response.json.gz'),'plan_file':str(dst/'plan.json')}
    if spec['q']==3:
        at=time.monotonic();pair=session.evaluate(plan,2);write(dst/'no_l2_response.json.gz',pair);write(dst/'no_l2_plan.json',plan)
        if pair['status']!='ok' or pair['official_result']['makespan']!=spec['recorded_no_l2']:raise ValueError('pair replay mismatch')
        spec['pair_seconds']=time.monotonic()-at;spec['no_l2_makespan']=pair['official_result']['makespan']
        d=diagnose(OFF,OFF/'data/config.txt',OFF/'data'/f"{spec['case']}.json",plan,r,dst/'diagnostics',dst/'no_l2_response.json.gz')
        raw=r['official_result'];pr=pair['official_result'];percore=[]
        for c,without in zip(raw['per_core_timeline'],pr['per_core_timeline']):
            end=max((o['end'] for o in c['ops']),default=0);end2=max((o['end'] for o in without['ops']),default=0)
            percore.append(dict(core=c['core_id'],end=end,no_l2_end=end2,tail=end==t,compute_work=sum(o['duration'] for o in c['ops'] if o['op_id'] in session.graph.ops),hit_count=sum(o.get('cache_hit',False) for o in c['ops']),miss_count=sum(o.get('cache_hit')==False for o in c['ops'] if 'cache_hit' in o)))
        d['per_core']=percore;d['last_ops']=[dict(core=c['core_id'],**o) for c in raw['per_core_timeline'] for o in c['ops'] if o['end']==t];write(dst/'diagnostics/diagnostics.json',d)
        spec['diagnostic_seconds']=d['diagnostic_seconds'];spec['hit_rate']=raw['cache_stats']['hit_rate'];spec['zero_slack_hit_bytes']=d['categories'].get('hit',{}).get('zero_slack_bytes',0)
    write(dst/'summary.json',spec);print('REPLAY',spec['case'],spec['q'],spec['n'],t,flush=True);return spec

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--cases',default='001,024,044,059,083,084,086');p.add_argument('--workers',type=int,default=2);a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    cases={'case_'+f'{int(x):03d}' for x in a.cases.split(',')};day=ROOT/'research_a_orion_anytime/team_results/day01/combined_final'
    allrows=list(csv.DictReader((day/'per_case.csv').open(encoding='utf-8-sig')));todo=[]
    for row in allrows:
        case=row['case'];q=int(row['q']);n=int(row['n'])
        if case not in cases or q not in (1,2,3) or n not in (2,5):continue
        candidates=[]
        for path in (ROOT/'raw_day01').glob(f'**/{case}_q{q}_n{n}/progress.json'):
            s=read(path);meta=s.get('incumbent')
            if meta and int(meta['makespan'])==int(row['makespan']):
                pp=path.parent/meta['plan_file'];rp=path.parent/meta['result_file']
                if pp.exists() and rp.exists():candidates.append((path,pp,rp))
        if not candidates:raise FileNotFoundError('No raw matching final plan '+str((case,q,n)))
        candidates.sort(key=lambda x:('refinement' not in str(x[0]),str(x[0])))
        pg,pp,rp=candidates[0]
        todo.append(dict(case=case,q=q,n=n,recorded_makespan=int(row['makespan']),baseline=int(row['baseline']),seed_solve_seconds=float(row['solve_seconds']),seed_cost_source='day01 per_case solve_seconds; historical machine, not same-host speed comparison',original_plan=str(pp),original_response=str(rp),original_progress=str(pg),seed_job=str(out/'seeds'/f'{case}_q{q}_n{n}'),recorded_no_l2=int(row['no_l2_makespan']) if row['no_l2_makespan'] else None))
    write(out/'original_sources.json',todo);records=[];errors=[]
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futures={ex.submit(fixed,s):s for s in todo}
        for f in as_completed(futures):
            try:records.append(f.result())
            except Exception as exc:errors.append(dict(spec=futures[f],error=str(exc),traceback=traceback.format_exc()))
            write(out/'seed_manifest.json',records);write(out/'prepare_errors.json',errors)
    csv_write(out/'replay_compare.csv',records)
    if errors:raise SystemExit('Actual replay errors: '+str(len(errors)))
if __name__=='__main__':main()
