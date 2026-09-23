"""Retain relative-radio blocks for every finite Q3 site/route granularity tried."""
from __future__ import annotations
import csv
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
from q3_compact import Problem,load_plan,relative_blocks,dump

def main():
    p=Problem.load(ROOT/"research_fd"/"outputs"/"d_official.json")
    saved=json.loads((ROOT/"research_fd"/"outputs"/"review"/"radio_temporal_candidate_pairs.json").read_text(encoding="utf-8"))
    short=[12,14,17,26,28,36,43,44,52,66,67,82,86]
    scenarios=[("fast_13_merged",HERE/"q2_candidate_fast.json",short,True),
               ("fast_13_split",HERE/"q2_candidate_fast.json",short,False),
               ("fast_88_merged",HERE/"q2_candidate_fast.json",list(range(len(saved["sites"]))),True),
               ("fast_88_split",HERE/"q2_candidate_fast.json",list(range(len(saved["sites"]))),False),
               ("energy_13_merged",HERE/"q2_candidate_energy.json",short,True),
               ("baseline_13_merged",ROOT/"research_fd"/"outputs"/"official_pareto_cpsat"/"energy_cap_1.json",short,True)]
    out=[]
    for name,path,indices,merged in scenarios:
        jobs,_=load_plan(path)
        sites=[saved["sites"][i] for i in indices]
        blocks,unreachable,cache=relative_blocks(p,jobs,sites,60.,merge=merged)
        rows=[]
        for b in blocks:
            rows.append({"route_id":b["route_id"],"route_index":b["route_index"],
                         "first_relative_s":b["first_relative_s"],"last_relative_s":b["last_relative_s"],
                         "eligible_site_indices":";".join(str(indices[i]) for i in b["eligible_sites"]),
                         "samples":b["samples"]})
        output=HERE/f"q3_blocks_{name}.csv"
        with output.open("w",encoding="utf-8",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=["route_id","route_index","first_relative_s","last_relative_s",
                                                "eligible_site_indices","samples"])
            writer.writeheader()
            writer.writerows(rows)
        out.append({"scenario":name,"source_plan":str(path.relative_to(ROOT)),"site_indices":indices,
                    "merged":merged,"blocks":len(blocks),"unreachable":unreachable,
                    "cache":cache,"file":output.name})
    dump(HERE/"q3_block_catalog.json",out)

if __name__=="__main__": main()
