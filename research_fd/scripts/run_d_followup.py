"""Local orchestration for the D four-question follow-up.

This script does not invent missing Q3 results. It prepares a new output directory,
prints/runs the existing official baselines, and records the exact follow-up phases.
The compact Q3 implementation should be added under research_fd before enabling
its command in the generated plan.

No hash inventory or smoke-test workflow is included.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]

def cmd(*parts: object) -> list[str]:
    return [str(x) for x in parts]

def run(command: list[str], execute: bool) -> dict:
    print("$", " ".join(command), flush=True)
    if not execute:
        return {"command": command, "executed": False}
    cp = subprocess.run(command, cwd=ROOT, check=False)
    return {"command": command, "executed": True, "returncode": cp.returncode}

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out")
    p.add_argument("--execute", action="store_true",
                   help="Run available baseline/legacy commands. New compact Q3 remains a research implementation task.")
    p.add_argument("--seconds", type=int, default=60)
    p.add_argument("--python", default=sys.executable)
    a = p.parse_args()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(a.out or ROOT / "research_fd" / "outputs" / f"followup_d_{stamp}").resolve()
    out.mkdir(parents=True, exist_ok=True)

    official = ROOT / "research_fd" / "outputs" / "d_official.json"
    q2 = ROOT / "research_fd" / "outputs" / "official_pareto_cpsat" / "energy_cap_1.json"

    required = [official, q2]
    missing = [str(x) for x in required if not x.exists()]
    if missing:
        raise SystemExit("Missing official inputs/results:\n" + "\n".join(missing))

    py = a.python
    plan: list[dict] = []
    # Q2 baseline export / consistency pass through the existing official runtime.
    plan.append(run(cmd(
        py, "research_fd/outputs/run_official.py", "d_experiments", "stress",
        "--input", official, "--plan", q2,
        "--out", out / "q2_baseline_stress.json",
        "--seed", "20260923", "--scenarios", "1000", "--sigma", "0.08"
    ), a.execute))

    # Existing Q3 model retained only as a benchmark against the compact follow-up.
    plan.append(run(cmd(
        py, "research_fd/outputs/run_radio_cpsat_retime.py",
        "--site-indices-file", "research_fd/outputs/review/radio_temporal_candidate_pairs.json",
        "--allow-soft-lateness", "--transport-step", "300",
        "--cover-blocks", "--feasibility-first", "--dense-sessions",
        "d_experiments", "radio",
        "--input", official, "--plan", q2,
        "--out", out / "q3_legacy_session_baseline",
        "--mode", "retime", "--grid", "3", "--sample-step", "60",
        "--shift-window", "2400", "--horizon", "15000",
        "--seconds", str(a.seconds), "--max-sessions", "1000000"
    ), a.execute))

    phases = {
        "q1": {
            "goal": "45 safety capacities + exact per-service grouping + reserve sensitivity",
            "implementation": "count-state DP; lexicographic trips/energy/work-time",
            "outputs": ["q1_capacity_45.csv", "q1_batches.csv", "q1_reserve_sensitivity.csv", "q1_summary.json"]
        },
        "q2": {
            "goal": "improve the verified 26-trip plan without re-expanding the full route-time grid",
            "implementation": "continuous resource-DAG compression + 2/3-route box exchange + fleet/resource insertion",
            "outputs": ["q2_comparison.csv", "q2_candidate_energy.json", "q2_candidate_fast.json"]
        },
        "q3": {
            "goal": "replace 135k pre-enumerated relay sessions",
            "implementation": "relative trajectory coverage cache + radio blocks + variable-duration relay-task slots + witness cuts",
            "outputs": ["q3_joint_plan.json", "relay_tasks.csv", "radio_blocks.csv", "witness_iterations.json"]
        },
        "q4": {
            "goal": "partition only a frozen communication-valid Q3 plan",
            "implementation": "hypergraph components; strict/duplicate 2- and 3-group resource vectors; optional partition-aware Q3 rerun",
            "outputs": ["partition_2_strict.json", "partition_2_duplicate.json", "partition_3_strict.json", "partition_3_duplicate.json"]
        }
    }
    manifest = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "platform": platform.platform(),
        "python": sys.version,
        "baseline_q2": str(q2.relative_to(ROOT)),
        "official_input": str(official.relative_to(ROOT)),
        "execute_existing_commands": bool(a.execute),
        "commands": plan,
        "followup_phases": phases,
        "notes": [
            "Do not treat the legacy Q3 session-enumeration command as the new solution; it is a benchmark.",
            "Do not compute official Q4 until Q3 passes dense communication validation.",
            "No hash inventory or smoke-test task is part of this follow-up plan."
        ]
    }
    (out / "FOLLOWUP_PLAN.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    print("Plan:", out / "FOLLOWUP_PLAN.json")

if __name__ == "__main__":
    main()
