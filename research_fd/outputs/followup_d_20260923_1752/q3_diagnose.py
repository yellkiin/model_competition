"""Diagnose compact Q3 infeasibility without changing official limits."""
from __future__ import annotations
import itertools
import json
import math
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
from q3_compact import Problem,load_plan,relative_blocks,relay_flight_components,solve,dump

def main():
    p=Problem.load(ROOT/"research_fd"/"outputs"/"d_official.json")
    jobs,_=load_plan(HERE/"q2_candidate_fast.json")
    data=json.loads((ROOT/"research_fd"/"outputs"/"review"/"radio_temporal_candidate_pairs.json").read_text(encoding="utf-8"))
    indices=[12,14,17,26,28,36,43,44,52,66,67,82,86]
    sites=[data["sites"][i] for i in indices]
    physical=[relay_flight_components(p,site) for site in sites]
    blocks,unreachable,cache=relative_blocks(p,jobs,sites,60.)
    _,no_radio=solve(p,jobs,[],sites,physical,1200,1,15,20260923,True)
    _,relaxed_radio=solve(p,jobs,blocks,sites,physical,1200,8,30,20260923,True,True)
    if no_radio["status"] not in ("OPTIMAL","FEASIBLE"):
        # The diagnostic is only credible when this control model is satisfiable.
        dump(HERE/"q3_diagnostic.json",{"no_radio":no_radio,"relaxed_radio":relaxed_radio,"diagnostic":"base model failed"})
        return
    min_sites={}
    hardest=[]
    individually_impossible=[]
    cfg=p.data["relay"]
    for b in blocks:
        j=jobs[b["route_index"]]
        hi=min(j.start+1200,j.route.latest if math.isfinite(j.route.latest) else 16000,16000-j.route.duration)
        admissible=[]
        for site in b["eligible_sites"]:
            phys=physical[site]
            lead=cfg["prepare"]+phys["outbound_s"]+cfg["setup"]-b["first_relative_s"]
            min_hover=cfg["setup"]+b["last_relative_s"]-b["first_relative_s"]
            energy=phys["flight_energy_kwh"]+cfg["hover_kw"]*min_hover/3600
            if lead<=hi+1e-7 and energy<=cfg["energy_kwh"]*(1-cfg["reserve"])+1e-7:
                admissible.append(site)
        if not admissible:
            individually_impossible.append({"route_id":b["route_id"],"relative_window_s":[b["first_relative_s"],b["last_relative_s"]],
                                           "start_upper_s":hi,"eligible_sites":b["eligible_sites"]})
    for tick in range(0,12001,30):
        active=[b for b in blocks if jobs[b["route_index"]].start+b["first_relative_s"]-1e-7<=tick
                <=jobs[b["route_index"]].start+b["last_relative_s"]+1e-7]
        sets=[set(b["eligible_sites"]) for b in active]
        if not sets:
            continue
        required=None
        for cardinality in range(1,4):
            if any(all(set(combo)&s for s in sets) for combo in itertools.combinations(range(len(sites)),cardinality)):
                required=cardinality
                break
        if required is None:
            required=4
        min_sites[required]=min_sites.get(required,0)+1
        if required>2:
            hardest.append({"time_s":tick,"active_blocks":len(active),"minimum_simultaneous_sites":required})
    dump(HERE/"q3_diagnostic.json",{"no_radio":no_radio,"relaxed_radio":relaxed_radio,
         "fixed_baseline_spatial_lower_bound_time_bins":min_sites,
         "more_than_two_sites_at_fixed_baseline":hardest,"scope":"Fixed Q2 start times, 30-s bins, 13 sites; spatial lower bound ignores relay travel and duration. Retiming may avoid conflicts.",
         "relative_cache":cache,"unreachable":unreachable,
         "individually_impossible_blocks_under_1200s_hard_window":individually_impossible})

if __name__=="__main__": main()
