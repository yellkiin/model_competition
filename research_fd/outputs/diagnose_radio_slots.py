"""Necessary instantaneous coverage lower bound for a fixed sampled plan."""
from pathlib import Path
import sys,json,math,time,argparse
from functools import lru_cache
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT/'runtime'))
from research_fd.d_model import Problem
from research_fd.d_experiments import load_plan,save
from research_fd.d_radio import candidates,demands_for_options,margin
pa=argparse.ArgumentParser();pa.add_argument('--input',required=True);pa.add_argument('--plan',required=True);pa.add_argument('--out',required=True)
a=pa.parse_args();p=Problem.load(a.input);jobs,_=load_plan(a.plan)
sites=candidates(p,3);ds=demands_for_options(p,[(j.route,j.start) for j in jobs],60.)
cache={};records=[]
for tick in sorted({math.floor(d['time']/60+1e-9) for d in ds}):
    group=[d for d in ds if math.floor(d['time']/60+1e-9)==tick]
    masks=[]
    for s,xyz in enumerate(sites):
        mask=0
        for i,d in enumerate(group):
            key=(s,tuple(d['xyz']))
            if key not in cache:cache[key]=margin(p,xyz,d['xyz'],p.data['radio']['access_budget_db'])>=0
            if cache[key]:mask |= 1<<i
        masks.append(mask)
    target=(1<<len(group))-1
    lower=1 if target in masks else (2 if any(x|y==target for x in masks for y in masks) else 3)
    records.append({'slot_start_s':tick*60,'requirements':len(group),'distinct_routes':len({d['route_id'] for d in group}),
                    'minimum_sites_capped_at_3':lower,'demands':group if lower>2 else []})
all_masks=[]
for s in range(len(sites)):
    mask=0
    for i,d in enumerate(ds):
        if cache[(s,tuple(d['xyz']))]:mask|=1<<i
    all_masks.append(mask)
best_pairs=sorted([((x|y).bit_count(),i,j) for i,x in enumerate(all_masks) for j,y in enumerate(all_masks) if i<j],reverse=True)[:12]
pair_details=[{'covered':n,'site_indices':[i,j],'xyz':[sites[i],sites[j]],'uncovered':[k for k in range(len(ds)) if not (all_masks[i]|all_masks[j])>>k&1]} for n,i,j in best_pairs]
save(a.out,{'scope':'necessary fixed-slot geometric bound; 3 means at least three, not solved minimum','sites':len(sites),
            'requirements':len(ds),'slots_needing_more_than_two':sum(r['minimum_sites_capped_at_3']>2 for r in records),'rows':records})
save(Path(a.out).with_name('best_static_pairs.json'),{'requirements':len(ds),'pairs':pair_details})
print(json.dumps({'slots_needing_more_than_two':sum(r['minimum_sites_capped_at_3']>2 for r in records),'slots':len(records)}))
