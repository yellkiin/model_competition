"""Rebuilt v6 execution adapter; does not overwrite PR34's v4 or official code.

The former local v4/v5 files are missing. This is new code, not their recovery.
PR34's plugin/structural.py remain the source of all FIFO/structural candidates.
"""
from __future__ import annotations
import argparse, time, traceback
from pathlib import Path
from .storage import read, write, incumbent_from_job

PEER_COMMIT = "27f7aa073bd7f91a1b1b9842eb2c9eb48117bf37"
POLICY = "reconcile-v6"


def representative_first(g, n, cfg, q, deadline):
    """Keep the first upstream stage candidate, then rank a bounded remainder."""
    from research_a_orion_anytime.strategies import stage_candidates
    source = iter(stage_candidates(g, n, cfg, q))
    if time.monotonic() >= deadline:
        return
    first = next(source, None)
    if first is None:
        return
    yield first
    # Generation is still charged by the parent adapter, never a free oracle.
    batch = []
    for _ in range(7):
        if time.monotonic() + .05 >= deadline:
            break
        item = next(source, None)
        if item is None:
            break
        batch.append(item)
    yield from sorted(batch, key=lambda c: (c["proxy"]["score"], c["name"]))
    yield from source


def early_seed_stop(request):
    """Only use a seed freshly re-evaluated by this run; use the SAME peer gates."""
    if not request.get("seed_validated_this_run") or not request.get("seed_job"):
        return None
    started = time.monotonic()
    best, prior = incumbent_from_job(request["seed_job"])
    if best is None or (prior.get("case"), prior.get("q"), prior.get("n")) != (
            request["case"], request["q"], request["n"]):
        raise ValueError("Seed context differs from the target job")
    # Certificate is only a cheap preliminary gate; recompute before accepting.
    raw = best["official_result"]
    upper = raw["makespan"]
    lb = best["response"]["audit"]["certificate"]["global_lower"]
    tol = request.get("gap_tolerance", .02)
    widened = request.get("near_bound_budget_gap", .0205)
    if lb <= 0 or (upper/lb > 1+tol and 1-lb/upper > widened):
        return None
    from research_a_orion_anytime.engine import OfficialSession
    from research_a_orion_anytime.core import bounds
    session = OfficialSession(request["official"], request["graph"], request["config"])
    lower = bounds(session.graph, session.cfg, request["n"], request["q"])["global_lower"]
    exact = lower > 0 and upper/lower <= 1+tol
    peer_large = (len(session.graph.ops) >= 2000 and lower > 0 and
                  max(0., 1-lower/upper) <= widened)
    if not (exact or peer_large):
        return None
    out = Path(request["job"])
    write(out/"incumbents/seed_plan.json", best["plan"])
    write(out/"incumbents/seed_response.json.gz", best["response"])
    state = dict(case=request["case"], q=request["q"], n=request["n"], status="ok",
                 identity=request["identity"], policy=POLICY,
                 stopped="recomputed_bound_before_candidate_generation",
                 actual_route="reconcile_v6_verified_seed_exit", global_lower=lower,
                 inherited_first_valid=True, first_valid_seconds=0.,
                 evaluations=0, attempts=[], construction_errors=[],
                 elapsed_seconds=time.monotonic()-started,
                 costs=dict(initialization_seconds=time.monotonic()-started,
                            candidate_generation_seconds=0., official_eval_seconds=0.),
                 guard=dict(upper_over_lower_minus_one=upper/lower-1,
                            one_minus_lower_over_upper=1-lower/upper,
                            peer_large_guard_used=not exact and peer_large,
                            gap_tolerance=tol, near_bound_budget_gap=widened),
                 incumbent=dict(makespan=upper,
                     added_copy_bytes=raw["data_movement_bytes"]["added_copy_bytes"],
                     plan_file="incumbents/seed_plan.json",
                     result_file="incumbents/seed_response.json.gz",
                     name="freshly_verified_seed", elapsed_seconds=0., from_seed=True))
    write(out/"progress.json", state)
    return state


def solve_rebuilt(request):
    from . import adapter as peer
    state = early_seed_stop(request)
    if state is not None:
        return state
    original = peer._prioritized_stages
    peer._prioritized_stages = representative_first
    try:
        return peer.solve(dict(request, method="combined", revision="v4"))
    finally:
        peer._prioritized_stages = original


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("request")
    request = read(parser.parse_args().request)
    out = Path(request["job"]); out.mkdir(parents=True, exist_ok=True)
    from research_a_orion_anytime.engine import OfficialSession
    # Pure logging around the unmodified call: same instrumentation for every arm.
    evaluate_original = OfficialSession.evaluate
    count = 0
    def recording(self, plan, q, *args, **kwargs):
        nonlocal count
        count += 1
        prefix = out/"official_calls"/f"{count:04d}"
        write(str(prefix)+"_plan.json", plan)
        before = time.monotonic()
        try:
            response = evaluate_original(self, plan, q, *args, **kwargs)
        except Exception as exc:
            write(str(prefix)+"_error.json", dict(error=str(exc), traceback=traceback.format_exc()))
            raise
        write(str(prefix)+"_response.json.gz", response)
        write(str(prefix)+"_meta.json", dict(q=q, evaluate_wall_seconds=time.monotonic()-before,
                                            evaluator_unchanged=True))
        return response
    OfficialSession.evaluate = recording
    try:
        write(out/"routing.json", dict(requested_method=request["method"],
               peer_commit=PEER_COMMIT, candidates_source="unchanged PR34 plugin/structural",
               source_policy=POLICY if request["method"]=="repair_v6" else request["method"]))
        if request["method"] == "fixed":
            session=OfficialSession(request["official"],request["graph"],request["config"])
            plan=read(request["fixed_plan"])
            if len(plan["core_schedules"])!=request["n"]:
                raise ValueError("Target core count differs from plan")
            response=session.evaluate(plan,request["q"])
            write(out/"fixed_plan.json",plan);write(out/"fixed_response.json.gz",response)
            raw=response.get("official_result",{})
            write(out/"progress.json",dict(case=request["case"],q=request["q"],n=request["n"],
              status=response["status"],attempts=[],evaluations=1,
              incumbent=dict(plan_file="fixed_plan.json",result_file="fixed_response.json.gz",
                makespan=raw["makespan"],added_copy_bytes=raw["data_movement_bytes"]["added_copy_bytes"],
                name="fixed",elapsed_seconds=0.,certificate=response["audit"]["certificate"])
                if response["status"]=="ok" else None))
        elif request["method"]=="old":
            from research_a_orion_anytime.solver import solve
            solve(request)
        elif request["method"]=="peer_v4":
            from .adapter import solve
            solve(dict(request,method="combined",revision="v4"))
        elif request["method"]=="repair_v6":
            solve_rebuilt(request)
        else:
            raise ValueError("Unknown execution arm")
    except Exception as exc:
        write(out/"worker_error.json",dict(error=str(exc),traceback=traceback.format_exc()))
        raise
    finally:
        OfficialSession.evaluate=evaluate_original

if __name__=="__main__":
    main()
