"""Plot all completed epsilon-cap attempts, including failures; no frontier fit."""
from pathlib import Path
import os, json, hashlib

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
for dirname in ["mplconfig", "tmp"]:
    (HERE / dirname).mkdir(exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(HERE / "mplconfig")
os.environ["TEMP"] = os.environ["TMP"] = str(HERE / "tmp")
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

sources = {}
def read(path):
    sources[str(path.relative_to(OUT.parent.parent))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return json.loads(path.read_text(encoding="utf-8"))

data = read(OUT / "official_pareto_summary.json")
rows = data["records"]
assert len(rows) == 13
for r in rows:
    plan = read(OUT / r["plan"])
    check = read(OUT / r["validation"])
    assert r["transport_validated"] == check["transport_valid"]
    assert abs(plan["metrics"]["energy_kwh"] - r["energy_kwh"]) < 1e-7
    assert abs(plan["metrics"]["makespan_s"] - r["makespan_s"]) < 1e-7
    if r["solver_feasible"]:
        assert r["transport_validated"] and not r["radio_checked"]
valid = [r for r in rows if r["solver_feasible"] and r["transport_validated"]]
assert len(valid) == 5
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "pdf.fonttype": 42, "axes.spines.top": False, "axes.spines.right": False})
fig = plt.figure(figsize=(12.4, 9.3))
grid = fig.add_gridspec(2, 2, height_ratios=[1.6, 1], left=.105, right=.97, top=.865, bottom=.17, hspace=.40, wspace=.31)
ax1, ax2, ax3 = fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 1]), fig.add_subplot(grid[1, :])
fig.suptitle("Official-input energy / makespan attempts | Transport only / Q2", fontsize=16, y=.967)
fig.text(.105, .915, "13 actual attempts: 8 with no incumbent, 5 validated transport incumbents; only one distinct observed nondominated point.", fontsize=10)
normal = [r for r in valid if "warm" not in r["attempt"]]
warm = next(r for r in valid if "warm" in r["attempt"])
for r in normal:
    ax1.scatter(r["makespan_s"]/60, r["energy_kwh"], color="#087F8C" if r["observed_nondominated"] else "#BC743C", s=62, zorder=4)
ax1.scatter(warm["makespan_s"]/60, warm["energy_kwh"], facecolor="none", edgecolor="#6D50A2", marker="D", s=150, linewidth=1.6, zorder=5)
offsets = {1.0: (3.5, -.09), 1.1: (3.5, .14), 1.25: (3.5, .04), 1.5: (-9.3, -.08)}
for r in normal:
    dx, dy = offsets[r["ratio"]]
    text = f"cap {r['ratio']:g}"
    if r["ratio"] == 1.0:
        text += " + cap 1.5 warm\n(same objective point)"
    ax1.annotate(text, (r["makespan_s"]/60, r["energy_kwh"]), xytext=(r["makespan_s"]/60+dx, r["energy_kwh"]+dy), fontsize=9, arrowprops={"arrowstyle": "-", "color": "#777777", "lw": .7}, va="center")
ax1.set_xlim(135.5, 167.5)
ax1.set_ylim(71.06, 71.96)
ax1.set_title("(a) Actual incumbents; magnified energy axis", loc="left", pad=10)
ax1.set_xlabel("Actual return makespan [min]")
ax1.set_ylabel("Transport energy [kWh]")
ax1.grid(color="#e0e4e7", linewidth=.65)
ax1.text(.04, .96, "No interpolated Pareto curve", transform=ax1.transAxes, va="top", fontsize=9, color="#444444")

for r in normal:
    ax2.plot([r["ratio"], r["ratio"]], [r["energy_bound_kwh"], r["energy_kwh"]], color="#92ADB2", lw=1.4)
    ax2.scatter(r["ratio"], r["energy_kwh"], s=48, color="#087F8C", zorder=3)
    ax2.scatter(r["ratio"], r["energy_bound_kwh"], s=52, marker="_", color="#087F8C", zorder=3)
    ax2.text(r["ratio"], r["energy_bound_kwh"]-.40, f"{100*r['energy_gap_from_bound']:.2f}%", fontsize=8.5, ha="center", va="top", color="#4b6267")
ax2.plot([warm["ratio"], warm["ratio"]], [warm["energy_bound_kwh"], warm["energy_kwh"]], color="#6D50A2", lw=2.0, ls="--")
ax2.scatter(warm["ratio"], warm["energy_kwh"], facecolor="none", edgecolor="#6D50A2", marker="D", s=100, linewidth=1.5, zorder=5)
ax2.scatter(warm["ratio"], warm["energy_bound_kwh"], color="#6D50A2", marker="_", s=70, zorder=5)
ax2.annotate("180 s repair: 3.48% gap", (1.5, warm["energy_bound_kwh"]), xytext=(1.25, 67.9), fontsize=8.8, color="#6D50A2", arrowprops={"arrowstyle": "-", "color": "#6D50A2", "lw": .7})
ax2.set_xlim(.96, 1.56)
ax2.set_ylim(60.0, 73.8)
ax2.set_xticks([1, 1.1, 1.25, 1.5])
ax2.set_title("(b) Solver energy bounds and incumbents", loc="left", pad=10)
ax2.set_xlabel("Allowed makespan / anchor makespan")
ax2.set_ylabel("Energy [kWh]")
ax2.grid(color="#e0e4e7", linewidth=.65)
ax2.text(.04, .96, "Dot: incumbent; lower tick: solver bound\nSegments are optimization gaps, not uncertainty bars", transform=ax2.transAxes, va="top", fontsize=8.5, color="#444444")

attempts = ["HiGHS 60s", "HiGHS 精确预删120s", "CP-SAT 30s/30s", "CP-SAT warm180s/30s"]
labels = ["HiGHS | 60 s", "HiGHS exact pruning | 120 s", "CP-SAT | 30 s / 30 s", "CP-SAT warm | 180 s / 30 s"]
caps = [1., 1.1, 1.25, 1.5]
for yi, attempt in enumerate(attempts):
    for xi, cap in enumerate(caps):
        record = next((r for r in rows if r["attempt"] == attempt and r["ratio"] == cap), None)
        state = "Not run" if record is None else ("FEASIBLE / Q2 pass" if record["solver_feasible"] else "Limit / no incumbent")
        color = "#eeeeee" if record is None else ("#D2E9E6" if record["solver_feasible"] else "#F3DCD7")
        ax3.add_patch(Rectangle((xi-.49, yi-.44), .98, .88, facecolor=color, edgecolor="white"))
        ax3.text(xi, yi, state, ha="center", va="center", fontsize=9)
ax3.set_xlim(-.5, 3.5)
ax3.set_ylim(3.5, -.5)
ax3.set_xticks(range(4), [f"cap {c:g}" for c in caps])
ax3.set_yticks(range(4), labels)
ax3.tick_params(length=0)
for spine in ax3.spines.values():
    spine.set_visible(False)
ax3.set_title("(c) All attempts preserved; no-incumbent zeros are not objective points", loc="left", pad=10)
fig.text(.105, .065, "Anchor: 8,310.169077 s and 75.069164 kWh (outside the magnified panel a). Same 600-route pool, 60 s start grid, zero weighted tardiness.\nWider caps yielded worse time-limited incumbents; the warm repair recovered the cap-1 point without further improvement. All CP energy stages: FEASIBLE.\nBounds apply to each finite capped model. No joint radio certification and no continuous/global Pareto-frontier claim.", fontsize=8.5, color="#444444")
fig.savefig(HERE / "pareto_attempts.png", dpi=180, bbox_inches="tight")
fig.savefig(HERE / "pareto_attempts.pdf", bbox_inches="tight")
plt.close(fig)
(HERE / "pareto_figure_provenance.json").write_text(json.dumps({"source_sha256": sources, "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "attempts": len(rows), "solver_incumbents": len(valid), "failed_no_incumbent": len(rows)-len(valid), "unique_observed_nondominated_coordinates": data["unique_nondominated_objective_points"], "figure_scope": "Q2 transportation only; same-route-pool epsilon-cap attempts. Do not connect observed points into an inferred global frontier.", "units": {"makespan": "minutes in panel a", "energy": "kWh", "vertical_segments": "solver optimality bounds, not confidence intervals"}}, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print("Saved pareto_attempts PNG/PDF; 13 attempts, 5 incumbents, 8 failures, one distinct observed nondominated coordinate.")
