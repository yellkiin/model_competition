"""Plot completed official-input runs. Reads validated exports; performs no solving.

Default: Q2 transport-only plan. Future Q3: --scope q3 --plan PATH --export PATH
requires that export/validation.json explicitly certifies joint_valid=true.
All output, Matplotlib cache and temporary files stay beside this script.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUTS = HERE.parent
REPO = OUTPUTS.parent.parent
for name in ["mplconfig", "tmp"]:
    (HERE / name).mkdir(parents=True, exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(HERE / "mplconfig")
os.environ["TEMP"] = os.environ["TMP"] = str(HERE / "tmp")
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9.5,
                     "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})

SOURCES = {}


def register(path):
    path = Path(path).resolve()
    SOURCES[path.relative_to(REPO).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return path


def read(path):
    return json.loads(register(path).read_text(encoding="utf-8"))


def table(path):
    with register(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def savefig(fig, stem):
    fig.savefig(HERE / f"{stem}.png", dpi=170)
    fig.savefig(HERE / f"{stem}.pdf")
    plt.close(fig)


def write_json(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def comparison_figure():
    a = read(OUTPUTS / "official_transport_s7/comparison.json")
    b = read(OUTPUTS / "official_transport_cpsat/comparison.json")
    c = read(OUTPUTS / "official_retime_grids/comparison.json")
    rows = []
    labels = {"greedy": "Greedy", "route_milp": "Static route MILP", "dual_route_milp": "Dual route MILP", "resource_dispatch": "Resource dispatch", "alns": "ALNS", "fixed_route_retime": "Fixed routes | HiGHS 60 s", "integrated_highs": "Full model | HiGHS", "integrated_cpsat": "Full model | CP-SAT", "highs_step_30": "Fixed routes | HiGHS 30 s", "highs_step_10": "Fixed routes | HiGHS 10 s", "cpsat_seconds": "Fixed routes | CP-SAT 1 s"}
    for item in a["methods"]:
        rows.append({**item, "solver": a["details"][item["method"]], "source": "official_transport_s7/comparison.json"})
    item = next(r for r in b["methods"] if r["method"] == "integrated_cpsat")
    rows.append({**item, "solver": b["details"][item["method"]], "source": "official_transport_cpsat/comparison.json"})
    for item in c["results"]:
        if item["method"] not in ["highs_step_30", "highs_step_10", "cpsat_seconds"]:
            continue
        feasible = bool(item["found"]) and not any(item[k] for k in ["hard_violations", "unserved", "duplicated", "resource_overlaps"])
        rows.append({**item, "feasible": feasible, "source": "official_retime_grids/comparison.json"})
    for r in rows:
        r["incumbent"] = bool(r["trips"]) and r["unserved"] == 0
        r["display"] = labels[r["method"]]
        if not r["incumbent"]:
            r["plot_makespan_min"] = None
            r["plot_energy_kwh"] = None
            r["plot_status"] = "NO INCUMBENT"
        else:
            r["plot_makespan_min"] = r["makespan_s"] / 60
            r["plot_energy_kwh"] = r["energy_kwh"]
            r["plot_status"] = "Q2 feasible" if r["feasible"] else f"{r['hard_violations']} hard violations"
    fig, axs = plt.subplots(1, 3, figsize=(13.5, 7.9), sharey=True, gridspec_kw={"width_ratios": [1.35, 2.8, 2.5]})
    fig.subplots_adjust(left=.22, right=.97, top=.83, bottom=.20, wspace=.15)
    fig.suptitle("Official-input method comparison | Transport only / Q2", fontsize=16, y=.965)
    fig.text(.22, .905, "Same 80-box input and physical runtime; finite route pools. Radio feasibility is not certified by these transport results.", fontsize=10)
    for i, r in enumerate(rows):
        color = "#D77742" if not r["feasible"] else "#087F8C"
        if r["method"] == "integrated_cpsat":
            color = "#8167A9"
        for ax in axs:
            if i % 2 == 0:
                ax.axhspan(i-.45, i+.45, color="#f4f5f6", zorder=0)
        axs[0].text(.02, i, r["plot_status"], va="center", fontsize=9, color=color if r["incumbent"] else "#7c3540", fontweight="bold")
        for ax, key in [(axs[1], "plot_makespan_min"), (axs[2], "plot_energy_kwh")]:
            value = r[key]
            if value is None:
                ax.text(.03, i, "N/A: time limit, no incumbent", transform=ax.get_yaxis_transform(), va="center", color="#7c3540", fontsize=9)
            else:
                ax.barh(i, value, color=color, height=.54, hatch="//" if not r["feasible"] else None, alpha=.9)
                ax.text(value + (3 if key == "plot_makespan_min" else 1.5), i, f"{value:.2f}", va="center", fontsize=9)
    axs[0].set_yticks(range(len(rows)), [r["display"] for r in rows])
    axs[0].invert_yaxis()
    axs[0].set_xlim(0, 1.1)
    axs[0].set_xticks([])
    axs[0].set_title("Feasibility status", loc="left")
    axs[0].spines["bottom"].set_visible(False)
    axs[0].spines["left"].set_visible(False)
    axs[0].tick_params(axis="y", length=0, pad=12)
    for ax, title, xmax in [(axs[1], "Return makespan [min]", 305), (axs[2], "Transport energy [kWh]", 180)]:
        ax.set_title(title, loc="left")
        ax.set_xlim(0, xmax)
        ax.grid(axis="x", color="#d9dde0", linewidth=.65)
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", left=False)
    fig.text(.22, .075, "Hatched orange: hard-deadline violations (not acceptable solutions). Purple: full CP-SAT kept its first-stage incumbent;\nits makespan stage returned UNKNOWN and it is worse than ALNS. HiGHS full model and 10 s retiming found no incumbent.\nNo-incumbent metrics are displayed as N/A, never as zero-valued winners. Stage limits: 30 s; candidate truncation retained.", fontsize=9, color="#444444")
    savefig(fig, "transport_method_comparison")
    write_json("transport_method_comparison.json", {"scope": "Official-input Q2 transport only; numerical controls and energy interpretations remain explicit in d_official.json", "records": rows, "comparison_sources": ["official_transport_s7/comparison.json", "official_transport_cpsat/comparison.json", "official_retime_grids/comparison.json"]})
    return rows


def plan_figures(instance, plan, export_dir, prefix, scope):
    validation = read(export_dir / "validation.json")
    assert validation["transport_valid"], "Transport export did not pass validation"
    assert Path(validation["plan"]).resolve() == plan.resolve(), "Export belongs to another plan"
    if scope == "q3":
        assert validation.get("joint_valid") is True, "Cannot label a radio-unverified plan Q3"
    plan_data = read(plan)
    air = table(export_dir / "aircraft_timeline.csv")
    bat = table(export_dir / "battery_timeline.csv")
    trips = table(export_dir / "transport_trips.csv")
    segments = table(export_dir / "transport_segments.csv")
    relays = table(export_dir / "relay_tasks.csv") if scope == "q3" else []
    model_path = Path(validation["runtime_model"])
    assert model_path.resolve() == (OUTPUTS / "runtime/research_fd/d_model.py").resolve(), "Expected official physical adaptation"
    register(model_path)
    ids = instance["metadata"]["transport_aircraft_ids"]
    id_order = [i for kind in ["A", "B", "C"] for i in ids[kind]]
    kind_of = {i: kind for kind, values in ids.items() for i in values}
    palette = ["#1B6585", "#148798", "#45AEB1", "#70BFB0", "#B36526", "#DE974A", "#775B9B", "#AA80B4"]
    colors = dict(zip(id_order, palette))
    for r in air:
        assert r["aircraft_id"] == ids[r["kind"]][int(r["resource_id"])]
    battery_order = [f"{g['id']}-B{i+1:02d}" for g in instance["fleet"] for i in range(g["batteries"])]
    trip_by_job = {r["job"]: r for r in trips}
    air_rows = id_order.copy()
    battery_rows = battery_order.copy()
    if relays:
        air_rows += sorted({r["aircraft_id"] for r in relays})
        battery_rows += sorted({r["pack_label"] for r in relays})
        colors.update({r["aircraft_id"]: "#A83859" for r in relays})
    fig, axs = plt.subplots(2, 1, figsize=(13.2, 10.5), sharex=True, gridspec_kw={"height_ratios": [len(air_rows), len(battery_rows)]})
    fig.subplots_adjust(left=.12, right=.97, top=.86, bottom=.14, hspace=.32)
    label = "Transport only / Q2" if scope == "q2" else "Transport and relay / Q3"
    metric = plan_data["metrics"]
    fig.suptitle(f"{label} | aircraft and battery schedule", fontsize=16, y=.97)
    fig.text(.12, .925, f"{len(trips)} transport trips; return makespan {metric['makespan_s']/60:.3f} min; transport energy {metric['energy_kwh']:.3f} kWh", fontsize=10)
    fig.text(.12, .895, "Q2 transport plan only: this figure does not certify joint radio feasibility." if scope == "q2" else "Joint export passed its documented finite-sample validation; this is not a continuous-time communication proof.", fontsize=9.5, color="#8b3941" if scope == "q2" else "#444444")
    for r in air:
        y = air_rows.index(r["aircraft_id"])
        start, motion, end, avail = [float(r[k])/60 for k in ["prepare_start_s", "motion_start_s", "returned_s", "available_s"]]
        axs[0].barh(y, motion-start, left=start, height=.68, color="#C3C9CF", edgecolor="white", linewidth=.4)
        axs[0].barh(y, end-motion, left=motion, height=.68, color=colors[r["aircraft_id"]], edgecolor="white", linewidth=.4)
        if avail > end:
            axs[0].barh(y, avail-end, left=end, height=.68, color="#E4E8EB", hatch="..")
        axs[0].text((motion+end)/2, y, f"J{int(r['job'])+1:02d}", color="white", ha="center", va="center", fontsize=7.4)
    for r in bat:
        y = battery_rows.index(r["battery_label"])
        start, end, chg, full = [float(r[k])/60 for k in ["occupied_start_s", "returned_s", "charging_start_s", "full_available_s"]]
        aircraft = trip_by_job[r["job"]]["aircraft_id"]
        axs[1].barh(y, end-start, left=start, height=.72, color=colors[aircraft], edgecolor="white", linewidth=.4)
        axs[1].barh(y, full-chg, left=chg, height=.72, color="#E0E5E9", hatch="///", edgecolor="#98A3AB", linewidth=.4)
        axs[1].text((start+end)/2, y, f"J{int(r['job'])+1:02d}", color="white", ha="center", va="center", fontsize=7.4)
    for r in relays:
        values = {k: float(r[k])/60 for k in ["preparation_start_s", "departure_s", "arrived_s", "ready_s", "service_stop_s", "returned_s", "aircraft_available_s", "pack_full_s"]}
        y = air_rows.index(r["aircraft_id"])
        axs[0].barh(y, values["departure_s"]-values["preparation_start_s"], left=values["preparation_start_s"], height=.68, color="#C3C9CF")
        axs[0].barh(y, values["returned_s"]-values["departure_s"], left=values["departure_s"], height=.68, color=colors[r["aircraft_id"]])
        axs[0].text((values["departure_s"]+values["returned_s"])/2, y, f"R{int(r['session'])+1:02d}", color="white", ha="center", va="center", fontsize=7.4)
        yb = battery_rows.index(r["pack_label"])
        axs[1].barh(yb, values["returned_s"]-values["preparation_start_s"], left=values["preparation_start_s"], height=.72, color=colors[r["aircraft_id"]])
        axs[1].barh(yb, values["pack_full_s"]-values["returned_s"], left=values["returned_s"], height=.72, color="#E0E5E9", hatch="///", edgecolor="#98A3AB")
    axs[0].set_yticks(range(len(air_rows)), [f"{i} ({kind_of[i]})" if i in kind_of else i for i in air_rows])
    axs[1].set_yticks(range(len(battery_rows)), battery_rows)
    for ax, title in [(axs[0], "(a) Aircraft bodies: official entity IDs"), (axs[1], "(b) Batteries: derived export labels")]:
        ax.set_title(title, loc="left", pad=10)
        ax.invert_yaxis()
        ax.grid(axis="x", color="#dde1e5", linewidth=.65)
        ax.set_axisbelow(True)
        ax.axvline(metric["makespan_s"]/60, ls="--", lw=1, color="#24282b")
    max_end = max(float(r["full_available_s"])/60 for r in bat)
    if relays:
        max_end = max(max_end, max(float(r["pack_full_s"])/60 for r in relays))
    axs[1].set_xlim(0, max_end*1.015)
    axs[1].set_xlabel("Time from operation start [min]")
    fig.legend(handles=[Patch(facecolor="#C3C9CF", label="Preparation/loading"), Patch(facecolor="#148798", label="Flight/service (color by aircraft)"), Patch(facecolor="#E0E5E9", edgecolor="#98A3AB", hatch="///", label="Battery charging")], loc="lower center", bbox_to_anchor=(.54, .077), ncol=3, frameon=False, fontsize=9)
    fig.text(.12, .025, "J01 = export job 0; job labels map directly to transport_trips.csv. Battery labels are derived, not official serial numbers.\nDashed line: all transport returned; final charging may finish later. Parallel charging assumption; no finite charger inventory supplied.", fontsize=8.4, color="#444444")
    savefig(fig, f"{prefix}_aircraft_battery_gantt")

    nodes = {n["id"]: n for n in instance["nodes"]}
    all_xy = np.array([[n["x"], n["y"]] for n in instance["nodes"]]) / 1000
    fig, axes = plt.subplots(2, 2, figsize=(12.1, 10.8), sharex=True, sharey=True)
    fig.subplots_adjust(left=.09, right=.94, top=.86, bottom=.15, hspace=.30, wspace=.23)
    fig.suptitle(f"{label} | horizontal route legs", fontsize=16, y=.96)
    fig.text(.09, .913, "Straight-leg projection in the supplied local metric coordinates; path height and terrain clearance are recorded in segment exports.", fontsize=9.5)
    for ax, group in zip(axes.flat, ["All", "A", "B", "C"]):
        chosen = {r["job"] for r in trips if group == "All" or r["kind"] == group}
        edge_counts = {}
        for seg in segments:
            if seg["job"] not in chosen or seg["phase"] != "cruise":
                continue
            start = tuple(json.loads(seg["from_xyz_m"])[:2])
            end = tuple(json.loads(seg["to_xyz_m"])[:2])
            if start == end:
                continue
            aircraft = trip_by_job[seg["job"]]["aircraft_id"]
            key = (start, end, aircraft)
            edge_counts[key] = edge_counts.get(key, 0) + 1
        for (start, end, aircraft), count in edge_counts.items():
            axy, bxy = np.array(start)/1000, np.array(end)/1000
            ax.plot([axy[0], bxy[0]], [axy[1], bxy[1]], color=colors[aircraft], alpha=.64, lw=.7 + .35*count, zorder=1)
            p, q = axy + .53*(bxy-axy), axy + .61*(bxy-axy)
            ax.annotate("", xy=q, xytext=p, arrowprops={"arrowstyle": "-|>", "color": colors[aircraft], "lw": .9, "mutation_scale": 8}, zorder=2)
        for n in instance["nodes"]:
            x, y = n["x"]/1000, n["y"]/1000
            ax.scatter(x, y, s=65 if n["id"] == "O01" else 23, marker="*" if n["id"] == "O01" else "o", color="#252c32", zorder=4)
            ax.annotate(n["id"], (x, y), xytext=(4, 5), textcoords="offset points", fontsize=7.7, zorder=5,
                        bbox={"facecolor": "white", "edgecolor": "none", "alpha": .7, "pad": .3})
        if group == "All" and relays:
            for relay in relays:
                x, y = float(relay["site_x_m"])/1000, float(relay["site_y_m"])/1000
                ax.plot([0, x], [0, y], ls="--", lw=1.5, color="#A83859")
                ax.scatter(x, y, marker="D", s=35, color="#A83859")
        number = sum(1 for t in trips if group == "All" or t["kind"] == group)
        ax.set_title(f"{'All aircraft' if group == 'All' else 'Type '+group} | {number} trips", loc="left", pad=8)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlim(all_xy[:, 0].min()-1.0, all_xy[:, 0].max()+1.8)
        ax.set_ylim(all_xy[:, 1].min()-1.0, all_xy[:, 1].max()+1.2)
        ax.grid(color="#e4e6e8", linewidth=.6)
    for ax in axes[1]:
        ax.set_xlabel("Local east [km]")
    for ax in axes[:, 0]:
        ax.set_ylabel("Local north [km]")
    fig.legend(handles=[Patch(facecolor=colors[i], label=f"{i} ({kind_of[i]})") for i in id_order], loc="lower center", bbox_to_anchor=(.53, .068), ncol=4, frameon=False, fontsize=9)
    fig.text(.09, .026, "Source: validated transport_segments.csv and actual aircraft-ID mapping in d_official.json. Overlapping legs are aggregated per aircraft.\nThis is a horizontal schematic, not a flight-clearance or continuous-radio certificate. " + ("Q2 only: relay support is not shown." if scope == "q2" else "Dashed burgundy lines show relay site trips."), fontsize=8.4, color="#444444")
    savefig(fig, f"{prefix}_routes")
    return {"scope": label, "plan": str(plan.relative_to(REPO)), "export": str(export_dir.relative_to(REPO)), "metrics": metric, "validation": validation, "aircraft_ids": ids, "battery_labels": battery_order,
            "job_label_mapping": {f"J{int(t['job'])+1:02d}": {"job": int(t["job"]), "route_id": int(t["route_id"]), "aircraft_id": t["aircraft_id"]} for t in trips}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=OUTPUTS / "d_official.json")
    parser.add_argument("--plan", type=Path, default=OUTPUTS / "official_retime_grids/cpsat_seconds.json")
    parser.add_argument("--export", type=Path, dest="export_dir", default=OUTPUTS / "official_best_transport_export")
    parser.add_argument("--scope", choices=["q2", "q3"], default="q2")
    parser.add_argument("--prefix", default=None)
    parser.add_argument("--skip-comparison", action="store_true")
    args = parser.parse_args()
    prefix = args.prefix or args.scope
    assert prefix.replace("_", "").replace("-", "").isalnum(), "Prefix must be a simple filename token"
    instance = read(args.input)
    comparisons = [] if args.skip_comparison else comparison_figure()
    meta = plan_figures(instance, args.plan.resolve(), args.export_dir.resolve(), prefix, args.scope)
    write_json(f"{prefix}_figure_provenance.json", {**meta, "source_sha256": SOURCES, "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "uncertainty": "Deterministic single-instance plans; no statistical confidence intervals asserted."})
    print(json.dumps({"figures_prefix": prefix, "comparison_records": len(comparisons), "metrics": meta["metrics"], "validation_status": meta["validation"]["status"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
