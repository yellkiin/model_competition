"""Run the official bootstrap with an untruncated, tolerance-pruned session pool.

Float dominance uses 1e-9 s / 1e-12 kWh tolerances; it does not assert strict
preservation of continuous or differently quantized integer objective optima.
No shared runtime source is changed. Re-evaluate any plan at finer precision.
"""
from pathlib import Path
import sys,runpy,time,json
from collections import defaultdict

OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT/'runtime'))
import research_fd.d_radio as radio
original=radio.session_pool

def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def dominant(a,b):
    return (a.departure>=b.departure-1e-9 and a.aircraft_end<=b.aircraft_end+1e-9
            and a.pack_end<=b.pack_end+1e-9 and a.returned<=b.returned+1e-9
            and a.energy<=b.energy+1e-12)

def pool(p,demands,sites,step=60.,max_sessions=18000):
    t=time.monotonic()
    print(json.dumps({'event':'start_untruncated_session_pool','demands':len(demands),'sites':len(sites)},ensure_ascii=False),flush=True)
    sessions,info=original(p,demands,sites,step,max_sessions=1000000)
    if info.get('pool_truncated'):
        raise MemoryError('One-million-column guard reached; untruncated guarantee unavailable')
    raw=len(sessions)
    print(json.dumps({'event':'raw_pool_ready','sessions':raw,'elapsed_s':time.monotonic()-t}),flush=True)
    grouped=defaultdict(list)
    for s in sessions:grouped[tuple(s.covers)].append(s)
    selected=[]
    for cover,group in grouped.items():
        frontier=[]
        for s in sorted(group,key=lambda x:(-x.departure,x.aircraft_end,x.pack_end,x.returned,x.energy)):
            if any(dominant(a,s) for a in frontier):continue
            frontier=[a for a in frontier if not dominant(s,a)]
            frontier.append(s)
        selected.extend(frontier)
    before={d for s in sessions for d in s.covers}
    after={d for s in selected for d in s.covers}
    assert before==after
    detail={'raw_sessions':raw,'retained_sessions':len(selected),'exact_cover_groups':len(grouped),
            'removed_dominated':raw-len(selected),'covered_requirements_before':len(before),
            'covered_requirements_after':len(after),'elapsed_s':time.monotonic()-t,
            'scope':'identical sampled covers; interval/return tolerance 1e-9 s and energy tolerance 1e-12 kWh; not a strict exact-objective preservation claim',
            'requested_max_sessions_ignored_to_avoid_truncation':max_sessions}
    folder=Path(sys.argv[sys.argv.index('--out')+1])
    save(folder/'session_pool_repair.json',detail)
    print(json.dumps({'event':'dominance_repair_done',**detail}),flush=True)
    info.update(sessions=len(selected),pool_truncated=False,dominance_repair=detail)
    return selected,info

radio.session_pool=pool
sys.argv=[str(OUT/'run_official.py'),*sys.argv[1:]]
runpy.run_path(str(OUT/'run_official.py'),run_name='__main__')
