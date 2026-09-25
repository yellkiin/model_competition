"""Revalidate committed comparison plans without missing local paths or raw_day01.
Creates the exact seed-manifest schema expected by reconcile_runner.
This is a real fixed-plan official evaluation, not a smoke/unit test.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from .storage import read, write
from .reconcile_runner import run_job

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLANS = ROOT / "research_a_orion_track_anytime/results/reconcile_20260925_1012/AVAILABLE_SEEDS.json"
OFF = ROOT / "题目/A题/通用神经网络处理器下的多核调度问题  附件"

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plans", type=Path, default=DEFAULT_PLANS)
    p.add_argument("--cases", required=True)
    p.add_argument("--questions", default="3")
    p.add_argument("--cores", default="5")
    p.add_argument("--official", type=Path, default=OFF)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--verify-seconds", type=float, default=90.)
    a = p.parse_args()
    if a.verify_seconds <= 0:
        p.error("verify-seconds must be positive")
    cases = {"case_" + f"{int(c.removeprefix('case_')):03d}" for c in a.cases.split(",")}
    qs, ns = set(map(int, a.questions.split(","))), set(map(int, a.cores.split(",")))
    wanted = {(c,q,n) for c in cases for q in qs for n in ns}
    entries = {}
    for r in read(a.plans):
        key = r["case"], int(r["q"]), int(r["n"])
        if key in entries:
            raise ValueError("Duplicate configuration in plan manifest")
        entries[key] = r
    if wanted - entries.keys():
        raise ValueError("No committed plan for requested configurations: " + repr(sorted(wanted - entries.keys())))
    off = a.official.resolve()
    cfg = off / "data/config.txt"
    if not cfg.is_file():
        raise FileNotFoundError(cfg)
    for c,q,n in wanted:
        if not (off/"data"/f"{c}.json").is_file():
            raise FileNotFoundError(c)
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    result, errors = [], []
    for c,q,n in sorted(wanted):
        src = entries[c,q,n]
        plan = Path(src["plan_file"])
        if not plan.is_absolute():
            plan = ROOT/plan
        req = dict(case=c,q=q,n=n,method="fixed",job=str(out/"seeds"/f"{c}_q{q}_n{n}"),
                   fixed_plan=str(plan),seconds=a.verify_seconds,official=str(off),
                   graph=str(off/"data"/f"{c}.json"),config=str(cfg),
                   identity={"purpose":"revalidate actually committed plan"})
        r = run_job(req,a.verify_seconds,src["baseline"],None)
        if r["status"] != "ok" or r.get("makespan") != src["recorded_makespan"]:
            errors.append(dict(case=c,q=q,n=n,status=r["status"],observed=r.get("makespan"),
                               recorded=src["recorded_makespan"],source_plan=str(plan)))
        else:
            result.append(dict(case=c,q=q,n=n,seed_job=req["job"],baseline=src["baseline"],
                recorded_makespan=r["makespan"],seed_solve_seconds=None,seed_cost_complete=False,
                validation_seconds=r["solve_seconds"],source_plan=str(plan),
                source_record=src,replay_plan=r["plan_file"],replay_response=r["result_file"]))
        write(out/"seed_manifest.json",result)
        write(out/"errors.json",errors)
    write(out/"validation_summary.json",dict(expected=len(wanted),verified=len(result),
          errors=len(errors),new_search_runs=0,official_fixed_replays=len(wanted)))
    if errors:
        raise SystemExit("Some official plan replays failed; inspect errors.json")
    print(out/"seed_manifest.json")

if __name__ == "__main__":
    main()
