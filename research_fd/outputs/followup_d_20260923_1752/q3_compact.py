"""Finite official-radio CP-SAT model with relative-route blocks and relay slots.

The relay service interval, return flight, body turnaround and conservative
piecewise charging all depend on the chosen station and service duration.
Only a plan passing the independent numerical checker is frozen.
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research_fd" / "outputs" / "runtime"))
from research_fd.d_model import Problem
from research_fd.d_schedule import Job, metrics
from research_fd.d_experiments import load_plan, save_plan
from research_fd.d_radio import Session, ground, margin, route_samples, relay_flight_components, evaluate_radio
from ortools.sat.python import cp_model


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def relative_blocks(p, jobs, sites, dt, merge=True):
    cfg = p.data["radio"]
    base = ground(p)
    access_cache = {}
    direct_cache = {}
    raw = []
    unreachable = []
    n_sample = 0
    for owner, job in enumerate(jobs):
        current = None
        for t, xyz in route_samples(job.route, 0., dt):
            n_sample += 1
            key = tuple(xyz)
            if key not in direct_cache:
                direct_cache[key] = margin(p, xyz, base, cfg["direct_budget_db"])
            if direct_cache[key] >= 0:
                current = None
                continue
            eligible = []
            for site, pos in enumerate(sites):
                skey = (site, key)
                if skey not in access_cache:
                    access_cache[skey] = margin(p, xyz, pos, cfg["access_budget_db"])
                if access_cache[skey] >= 0:
                    eligible.append(site)
            if not eligible:
                unreachable.append({"route_id":job.route.id,"relative_time_s":t,"xyz":list(xyz),
                                    "direct_margin_db":direct_cache[key]})
            site_set = tuple(eligible)
            if merge and current is not None and current["eligible_sites"] == site_set:
                current["last_relative_s"] = t
                current["samples"] += 1
            else:
                current = {"route_index":owner,"route_id":job.route.id,"first_relative_s":t,
                           "last_relative_s":t,"eligible_sites":site_set,"samples":1}
                raw.append(current)
    return raw, unreachable, {"relative_samples":n_sample,"direct_ray_cache":len(direct_cache),
                              "access_ray_cache":len(access_cache)}


def solve(p, jobs, blocks, sites, physical, window, slots_per_aircraft, seconds, seed, allow_soft=False,
          diagnostic_relax_resources=False):
    model = cp_model.CpModel()
    horizon = 16000
    cfg = p.data["relay"]
    count = len(jobs)
    starts = []
    for i, j in enumerate(jobs):
        r = j.route
        lo = max(math.ceil(r.release-1e-7), math.ceil(j.start-window-1e-7), 0)
        soft = min(p.boxes[b].due-r.delivery[b] for b in r.boxes)
        hi = min(math.floor(soft+1e-7) if not allow_soft else horizon,
                 math.floor(r.latest+1e-7) if math.isfinite(r.latest) else horizon,
                 math.floor(j.start+window+1e-7), horizon-math.ceil(r.duration))
        if lo > hi:
            return None, {"status":"NO_ZERO_LATE_START","route":i,"lo":lo,"hi":hi}
        starts.append(model.new_int_var(lo, hi, f"transport_start_{i}"))
    for label, hold in (("aircraft", "aircraft_hold"), ("battery", "battery_hold")):
        for kind, f in p.fleet.items():
            total = f.count if label == "aircraft" else f.batteries
            for ident in range(total):
                seq = sorted([i for i,j in enumerate(jobs) if j.route.kind == kind and getattr(j,label) == ident],
                             key=lambda i:jobs[i].start)
                for i,k in zip(seq,seq[1:]):
                    model.add(starts[k] >= starts[i]+math.ceil(getattr(jobs[i].route,hold)-1e-7))

    ns = len(sites)
    prep = int(math.ceil(cfg["prepare"]))
    setup = int(math.ceil(cfg["setup"]))
    turn = int(math.ceil(cfg["turnaround"]))
    outbound = [math.ceil(x["outbound_s"]-1e-8) for x in physical]
    inbound = [math.ceil(x["inbound_s"]-1e-8) for x in physical]
    flight = [math.ceil(x["flight_energy_kwh"]*1e6-1e-6) for x in physical]
    hover_rate = math.ceil(cfg["hover_kw"]*1e6/3600)
    cap = math.floor(cfg["energy_kwh"]*(1-cfg["reserve"])*1e6+1e-8)
    charge_table = []
    for bucket in range(cap//10000+2):
        e = min(cap, bucket*10000)
        soc = max(0., 1-e/(cfg["energy_kwh"]*1e6))
        tab = cfg["charge_table"]
        import numpy as np
        charge_table.append(math.ceil(tab[-1][1]-float(np.interp(soc,[x[0] for x in tab],[x[1] for x in tab]))-1e-8))

    slots = []
    pack_intervals = []
    for aircraft in range(cfg["count"]):
        prior = None
        for ordinal in range(slots_per_aircraft):
            key = f"relay_{aircraft}_{ordinal}"
            active = model.new_bool_var(key+"_active")
            site = model.new_int_var(0,ns-1,key+"_site")
            choices = [model.new_bool_var(key+f"_site_{i}") for i in range(ns)]
            model.add_exactly_one(choices)
            for i,choice in enumerate(choices):
                model.add(site == i).only_enforce_if(choice)
            depart = model.new_int_var(0,horizon,key+"_depart")
            otime = model.new_int_var(0,max(outbound),key+"_outbound")
            itime = model.new_int_var(0,max(inbound),key+"_inbound")
            eflight = model.new_int_var(0,max(flight),key+"_flight_energy")
            model.add_element(site,outbound,otime)
            model.add_element(site,inbound,itime)
            model.add_element(site,flight,eflight)
            arrival = model.new_int_var(0,horizon+3000,key+"_arrival")
            ready = model.new_int_var(0,horizon+3000,key+"_ready")
            stop = model.new_int_var(0,horizon+3000,key+"_stop")
            returned = model.new_int_var(0,horizon+5000,key+"_returned")
            a_end = model.new_int_var(0,horizon+5000,key+"_aircraft_end")
            pack_end = model.new_int_var(0,horizon+7000,key+"_pack_end")
            hover = model.new_int_var(0,horizon+3000,key+"_hover")
            energy = model.new_int_var(0,cap,key+"_energy")
            bucket = model.new_int_var(0,len(charge_table)-1,key+"_energy_bucket")
            charge = model.new_int_var(0,max(charge_table),key+"_charge")
            model.add(arrival == depart+prep+otime)
            model.add(ready == arrival+setup)
            model.add(stop >= ready).only_enforce_if(active)
            model.add(stop == ready).only_enforce_if(active.Not())
            model.add(hover == stop-arrival)
            model.add(energy == eflight+hover_rate*hover).only_enforce_if(active)
            model.add(energy == 0).only_enforce_if(active.Not())
            model.add_division_equality(bucket,energy+9999,10000)
            model.add_element(bucket,charge_table,charge)
            model.add(returned == stop+itime)
            model.add(a_end == returned+turn)
            model.add(pack_end == returned+charge)
            model.add(pack_end <= horizon+7000).only_enforce_if(active)
            length = model.new_int_var(0,horizon+7000,key+"_pack_length")
            model.add(length == pack_end-depart)
            pack_intervals.append(model.new_optional_interval_var(depart,length,pack_end,active,key+"_pack"))
            if prior is not None and not diagnostic_relax_resources:
                model.add(active <= prior["active"])
                model.add(depart >= prior["aircraft_end"]).only_enforce_if(active)
            item = {"aircraft":aircraft,"ordinal":ordinal,"active":active,"site":site,"choices":choices,
                    "depart":depart,"arrival":arrival,"ready":ready,"stop":stop,"returned":returned,
                    "aircraft_end":a_end,"pack_end":pack_end,"energy":energy}
            slots.append(item)
            prior = item
    if not diagnostic_relax_resources:
        model.add_cumulative(pack_intervals,[1]*len(pack_intervals),cfg["packs"])
    for bidx, block in enumerate(blocks):
        eligible = block["eligible_sites"]
        if not eligible:
            return None, {"status":"NO_SITE_FOR_BLOCK","block":bidx}
        covers = []
        begin = math.floor(block["first_relative_s"]+1e-8)
        end = math.ceil(block["last_relative_s"]-1e-8)
        for k,slot in enumerate(slots):
            z = model.new_bool_var(f"cover_{bidx}_{k}")
            covers.append(z)
            model.add_implication(z,slot["active"])
            model.add(sum(slot["choices"][s] for s in eligible) >= 1).only_enforce_if(z)
            model.add(slot["ready"] <= starts[block["route_index"]]+begin).only_enforce_if(z)
            model.add(slot["stop"] >= starts[block["route_index"]]+end).only_enforce_if(z)
        model.add_bool_or(covers)
    # A time bound sharpens feasibility search without treating any incumbent as optimal.
    joint = model.new_int_var(0,horizon+7000,"joint_makespan")
    for i,j in enumerate(jobs):
        model.add(joint >= starts[i]+math.ceil(j.route.duration))
    for slot in slots:
        model.add(joint >= slot["returned"]).only_enforce_if(slot["active"])
    model.minimize(joint*1000+sum(slot["active"] for slot in slots))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = 8
    solver.parameters.random_seed = seed
    t0 = time.perf_counter()
    status = solver.solve(model)
    detail = {"status":solver.status_name(status),"window_s":window,"slots_per_aircraft":slots_per_aircraft,
              "allow_soft_lateness":allow_soft,"diagnostic_relax_resources":diagnostic_relax_resources,
              "relay_task_slots":len(slots),"site_count":ns,"radio_blocks":len(blocks),"variables":len(model.proto.variables),
              "constraints":len(model.proto.constraints),"solve_s":time.perf_counter()-t0,
              "objective_bound_scaled":solver.best_objective_bound if status in (cp_model.FEASIBLE,cp_model.OPTIMAL) else None}
    if status not in (cp_model.FEASIBLE,cp_model.OPTIMAL):
        return None,detail
    revised = [Job(j.route,float(solver.value(starts[i])),j.aircraft,j.battery) for i,j in enumerate(jobs)]
    selected = []
    for slot in slots:
        if not solver.value(slot["active"]):
            continue
        site = solver.value(slot["site"])
        xyz = sites[site]
        phys = physical[site]
        departure = float(solver.value(slot["depart"]))
        arrival = departure+cfg["prepare"]+phys["outbound_s"]
        ready = arrival+cfg["setup"]
        stop = float(solver.value(slot["stop"]))
        returned = stop+phys["inbound_s"]
        hover_s = stop-arrival
        energy = phys["flight_energy_kwh"]+cfg["hover_kw"]*hover_s/3600
        soc = 1-energy/cfg["energy_kwh"]
        import numpy as np
        tab = cfg["charge_table"]
        charge = tab[-1][1]-float(np.interp(soc,[x[0] for x in tab],[x[1] for x in tab]))
        s = Session(site,list(xyz),departure,ready,stop,returned,returned+cfg["turnaround"],
                    returned+charge,energy,[],preparation_s=cfg["prepare"],
                    departure_semantics="resource_start_before_preparation",takeoff=departure+cfg["prepare"],
                    arrival=arrival,flight_energy_kwh=phys["flight_energy_kwh"],
                    cruise_energy_kwh=phys["cruise_energy_kwh"],climb_energy_kwh=phys["climb_energy_kwh"],
                    hover_energy_kwh=cfg["hover_only_kw"]*hover_s/3600,
                    communication_energy_kwh=cfg["communication_kw"]*hover_s/3600)
        s.aircraft = slot["aircraft"]
        selected.append(s)
    if diagnostic_relax_resources:
        detail["status"]="DIAGNOSTIC_RELAXED_FEASIBLE"
        detail["relay_trips"]=len(selected)
        return (revised,selected),detail
    ready = [0.] * cfg["packs"]
    for s in sorted(selected,key=lambda x:x.departure):
        pack = min(range(len(ready)),key=lambda x:ready[x])
        if ready[pack] > s.departure+1e-6:
            detail["status"] = "PACK_COLORING_FAILURE"
            return None,detail
        s.pack=pack
        ready[pack]=s.pack_end
    detail.update(joint_makespan_s=max([j.start+j.route.duration for j in revised]+[s.returned for s in selected]),
                  transport_energy_kwh=sum(j.route.energy for j in revised),
                  relay_energy_kwh=sum(s.energy for s in selected),relay_trips=len(selected),
                  zero_late=metrics(p,revised)["weighted_tardiness_s"]<=1e-6)
    return (revised,selected),detail


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--plan",default=str(HERE/"q2_candidate_fast.json"))
    parser.add_argument("--seconds",type=float,default=90)
    parser.add_argument("--seed",type=int,default=20260923)
    parser.add_argument("--allow-soft",action="store_true")
    parser.add_argument("--single-window",type=int)
    parser.add_argument("--slots-per-aircraft",type=int,default=8)
    parser.add_argument("--all-sites",action="store_true")
    parser.add_argument("--split-blocks",action="store_true")
    a=parser.parse_args()
    p=Problem.load(ROOT/"research_fd"/"outputs"/"d_official.json")
    jobs,_=load_plan(a.plan)
    site_data=json.loads((ROOT/"research_fd"/"outputs"/"review"/"radio_temporal_candidate_pairs.json").read_text(encoding="utf-8"))
    indices=list(range(len(site_data["sites"]))) if a.all_sites else [12,14,17,26,28,36,43,44,52,66,67,82,86]
    sites=[site_data["sites"][i] for i in indices]
    physical=[relay_flight_components(p,site) for site in sites]
    blocks,unreachable,cache=relative_blocks(p,jobs,sites,60.,merge=not a.split_blocks)
    write_csv(HERE/"radio_blocks.csv",[dict(route_id=b["route_id"],route_index=b["route_index"],
              first_relative_s=b["first_relative_s"],last_relative_s=b["last_relative_s"],
              eligible_site_indices=";".join(str(indices[i]) for i in b["eligible_sites"]),samples=b["samples"])
              for b in blocks],["route_id","route_index","first_relative_s","last_relative_s","eligible_site_indices","samples"])
    dump(HERE/"q3_relative_cache.json",{"site_indices":indices,"cache":cache,"blocks":len(blocks),
         "unreachable":unreachable,"source_plan":str(Path(a.plan).resolve().relative_to(ROOT)),
         "split_blocks":a.split_blocks})
    witness_file=HERE/"witness_iterations.json"
    history=json.loads(witness_file.read_text(encoding="utf-8")) if witness_file.exists() else []
    frozen=None
    if not unreachable:
        runs=((a.single_window,a.slots_per_aircraft),) if a.single_window is not None else ((300,4),(600,5),(1200,6))
        for window,slots in runs:
            result,detail=solve(p,jobs,blocks,sites,physical,window,slots,a.seconds,a.seed,a.allow_soft)
            detail["iteration"]=len(history)+1
            detail["radio_block_count"]=len(blocks)
            detail["split_blocks"]=a.split_blocks
            detail["source_plan"]=str(Path(a.plan).resolve().relative_to(ROOT))
            detail["transport_start_options"]="continuous-integer-second-interval"
            if result is not None:
                jj,ss=result
                check=evaluate_radio(p,jj,ss,60.)
                detail["radio_misses_60s"]=check["misses"]
                detail["minimum_margin_60s_db"]=check["minimum_margin_db"]
                if check["misses"]==0:
                    for dt in (15.,10.):
                        check=evaluate_radio(p,jj,ss,dt)
                        dump(HERE/f"radio_validation_{int(dt)}s.json",check)
                        detail[f"radio_misses_{int(dt)}s"]=check["misses"]
                        detail[f"minimum_margin_{int(dt)}s_db"]=check["minimum_margin_db"]
                    if check["misses"]==0:
                        dense_data=copy.deepcopy(p.data)
                        dense_data["radio"]["ray_step_m"]=7.5
                        dense_p=Problem(dense_data)
                        dense_check=evaluate_radio(dense_p,jj,ss,10.)
                        dump(HERE/"radio_validation_ray7_5m.json",dense_check)
                        detail["radio_misses_ray7_5m"]=dense_check["misses"]
                        detail["minimum_margin_ray7_5m_db"]=dense_check["minimum_margin_db"]
                        check=dense_check
                        if check["misses"]==0:
                            frozen=result
                            detail["frozen_after_numerical_10s_ray7_5m"] = True
                if check["misses"]:
                    new_points=0
                    by_route={j.route.id:i for i,j in enumerate(jj)}
                    for witness in check["details"][:32]:
                        owner=by_route[witness["route_id"]]
                        relative=float(witness["time"]-jj[owner].start)
                        eligible=tuple(i for i,xyz in enumerate(sites) if
                                       margin(p,xyz,witness["xyz"],p.data["radio"]["access_budget_db"])>=0)
                        blocks.append({"route_index":owner,"route_id":witness["route_id"],
                                       "first_relative_s":relative,"last_relative_s":relative,
                                       "eligible_sites":eligible,"samples":1})
                        new_points+=1
                    detail["witness_points_added_next_iteration"]=new_points
                dump(HERE/"radio_validation_60s.json",evaluate_radio(p,jj,ss,60.))
            history.append(detail)
            dump(HERE/"witness_iterations.json",history)
            print(json.dumps(detail,ensure_ascii=False),flush=True)
            if frozen is not None:
                save_plan(HERE/"q3_joint_plan.json",p,frozen[0],detail,frozen[1])
                break
    if frozen is None:
        dump(HERE/"q3_status.json",{"status":"NO_VALIDATED_JOINT_PLAN",
             "interpretation":"No formal Q3 result; statuses reflect the finite model and time limits only.",
             "iterations":history,"relative_unreachable":unreachable,"q4_formal":None})
        for groups in (2,3):
            for policy in ("strict","duplicate"):
                dump(HERE/f"partition_{groups}_{policy}.json",{"status":"NOT_RUN_NO_FROZEN_Q3",
                     "formal_result":None,"groups":groups,"policy":policy})
    else:
        dump(HERE/"q3_status.json",{"status":"FROZEN_NUMERICAL_10S_PENDING_INDEPENDENT_VALIDATION",
             "iterations":history})


if __name__=="__main__":
    main()
