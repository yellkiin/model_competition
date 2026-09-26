"""Small separate cache capacity/bandwidth study on each host's final plans.

Default configuration reuses the actual main result. Other cells run the original
Q3 evaluator. Optional adaptation is limited to two corner cells per graph.
"""
from __future__ import annotations
import argparse,time
from pathlib import Path
from .io import read,write,csv_write,official_root
from .pool import run_jobs


def run(root,out,deadline,workers=0,reserve=.25,adapt=True,cases=None):
    root,out=Path(root).resolve(),Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    options=[]
    for p in (root/'jobs').glob('*_q3_n5/summary.json'):
        s=read(p)
        if s['status']!='ok':continue
        if cases and s['case'] not in cases:continue
        pair=root/'pairs'/p.parent.name/'summary.json'
        ratio=(s.get('no_l2_makespan') or s['makespan'])/s['makespan'] if s.get('pair_status')=='ok' else (read(pair).get('makespan',s['makespan'])/s['makespan'] if pair.is_file() else 1.)
        options.append((s.get('graph_features',{}).get('ops',0),ratio,s['case'],p))
    eligible=[x for x in options if x[0]<=6000] or options
    eligible.sort(key=lambda x:(x[1],x[2]))
    chosen=list({x[2]:x for x in (eligible[:1]+eligible[-1:])}.values())
    requests=[];rows=[]
    for _,_,case,p in chosen:
        source=read(p.parent/'request.json');main=read(p);plan=p.parent/'plan.json'
        for capacity in (262144,1048576,4194304):
            for bandwidth in (60,250,500):
                key=f'{case}_cap{capacity}_bw{bandwidth}'
                row={'case':case,'q':3,'n':5,'capacity_bytes':capacity,'bandwidth_bytes_per_cycle':bandwidth,
                     'mode':'fixed_plan','official_default':capacity==1048576 and bandwidth==250}
                if row['official_default']:
                    rows.append({**row,'status':'ok','makespan':main['makespan'],'cache_hit_rate':main.get('cache_hit_rate'),
                                 'record':str(p),'reused_main_result':True})
                    continue
                req={**source,'out':str(out/'fixed'/key),'q':3,'n':5,'components':'',
                     'fixed_plan':str(plan),'seed_plan':None,'reference_makespan':None,
                     'alternatives':[],'baseline_alternatives':[], 'seconds':120,'job_seconds':120,
                     'cache_overrides':{'cache_capacity_bytes':capacity,'cache_bandwidth_bytes_per_cycle':bandwidth}}
                requests.append(req);rows.append({**row,'record':str(Path(req['out'])/'summary.json')})
    run_jobs(requests,out/'fixed_resources',deadline,workers,reserve)
    for row in rows:
        if row.get('reused_main_result'):continue
        p=Path(row['record'])
        if p.is_file():
            s=read(p);row.update(status=s['status'],makespan=s.get('makespan'),cache_hit_rate=s.get('cache_hit_rate'),
                               added_copy_bytes=s.get('added_copy_bytes'),wall_seconds=s.get('execution',{}).get('wall_seconds'))
        else:row['status']='not_started_deadline'
    adapted=[]
    if adapt:
        for _,_,case,p in chosen:
            source=read(p.parent/'request.json')
            for capacity,bandwidth in ((262144,60),(4194304,500)):
                key=f'{case}_cap{capacity}_bw{bandwidth}'
                adapted.append({**source,'out':str(out/'adapted'/key),'seed_plan':str(p.parent/'plan.json'),
                    'reference_makespan':None,'fixed_plan':None,'baseline_alternatives':[],'alternatives':[],
                    'source_seed_seconds':None,'seconds':60,'job_seconds':60,'max_evaluations':256,
                    'cache_overrides':{'cache_capacity_bytes':capacity,'cache_bandwidth_bytes_per_cycle':bandwidth}})
        run_jobs(adapted,out/'adapted_resources',deadline,workers,reserve)
        for req in adapted:
            p=Path(req['out'])/'summary.json';s=read(p) if p.is_file() else {}
            co=req['cache_overrides']
            rows.append({'case':req['case'],'q':3,'n':5,'capacity_bytes':co['cache_capacity_bytes'],
                         'bandwidth_bytes_per_cycle':co['cache_bandwidth_bytes_per_cycle'],'mode':'bounded_readaptation',
                         'official_default':False,'status':s.get('status','not_started_deadline'),
                         'makespan':s.get('makespan'),'cache_hit_rate':s.get('cache_hit_rate'),
                         'added_copy_bytes':s.get('added_copy_bytes'),'record':str(p)})
    csv_write(out/'cache_parameter_grid.csv',rows)
    result={'cases':[x[2] for x in chosen],'rows':len(rows),'valid':sum(r['status']=='ok' for r in rows),
            'default_cells_reused':sum(bool(r.get('reused_main_result')) for r in rows),
            'scope':'two purposively chosen final five-core graphs per shard; not a 100-graph hardware claim',
            'original_config_modified':False,'all_cells_complete':bool(rows) and all(r['status']=='ok' for r in rows)}
    write(out/'mechanism_status.json',result);return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--out',required=True)
    p.add_argument('--seconds',type=float,default=600);p.add_argument('--workers',type=int,default=0)
    p.add_argument('--fixed-only',action='store_true');p.add_argument('--cases',nargs='*')
    a=p.parse_args();cases=['case_'+x.zfill(3) if x.isdigit() else x for x in a.cases] if a.cases else None
    r=run(a.root,a.out,time.time()+a.seconds,a.workers,adapt=not a.fixed_only,cases=cases)
    print(r)
    return 0 if r['all_cells_complete'] else 1

if __name__=='__main__':raise SystemExit(main())
