"""A: conservative candidate search; ONLY the unmodified contest CLI scores plans.

The graph/tensor proxies below are not replicas of the official simulator.
All output is kept outside the source data. No graph attributes are modified.
"""
from __future__ import annotations
import argparse
import hashlib
import heapq
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import time

COPY = {"COPY_IN", "COPY_OUT"}
PIPES = {"PIPE_MTE2", "PIPE_MTE3", "PIPE_M", "PIPE_V"}


def load_json(path: Path) -> dict:
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError(f"Duplicate JSON key: {key}")
            out[key] = value
        return out
    text = path.read_text(encoding="utf-8")
    if text.startswith("version https://git-lfs.github.com/spec/v1"):
        raise ValueError(f"Git LFS pointer, not graph data: {path}; run git lfs pull")
    return json.loads(text, object_pairs_hook=unique)


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                               allow_nan=False) + "\n", encoding="utf-8")


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def topo(pred: dict, succ: dict, priority=None) -> list[int]:
    degree = {v: len(pred[v]) for v in pred}
    priority = priority or {v: v for v in pred}
    ready = [(priority[v], v) for v, d in degree.items() if not d]
    heapq.heapify(ready)
    order = []
    while ready:
        _, v = heapq.heappop(ready)
        order.append(v)
        for w in sorted(succ[v]):
            degree[w] -= 1
            if not degree[w]:
                heapq.heappush(ready, (priority[w], w))
    if len(order) != len(pred):
        raise ValueError("Dependency cycle")
    return order


def graph_view(graph: dict) -> dict:
    """Validate elementary format and contract COPY paths, not memory/FIFO edges."""
    for key in ("ops", "tensors", "edges"):
        if not isinstance(graph.get(key), list):
            raise ValueError(f"Missing graph list: {key}")
    objects = graph["ops"] + graph["tensors"]
    ids = [x.get("id") for x in objects]
    if any(type(i) is not int or i < 0 for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("IDs must be unique nonnegative integers in a shared namespace")
    ops = {x["id"]: x for x in graph["ops"]}
    tensors = {x["id"]: x for x in graph["tensors"]}
    for obj, field in [(o, "cycles") for o in ops.values()] + [(t, "size") for t in tensors.values()]:
        value = obj.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"Invalid {field}")
    if any(o.get("pipe") not in PIPES for o in ops.values()):
        raise ValueError("Unknown or absent pipe")
    allpred, allsucc = {i: set() for i in ids}, {i: set() for i in ids}
    producers, consumers = {t: set() for t in tensors}, {t: set() for t in tensors}
    for edge in graph["edges"]:
        u, v = edge["source"], edge["target"]
        if u not in allpred or v not in allpred or v in allsucc[u]:
            raise ValueError("Invalid endpoint or duplicate edge")
        if u in tensors and v in tensors:
            raise ValueError("tensor-to-tensor edge")
        allsucc[u].add(v)
        allpred[v].add(u)
        if u in ops and v in tensors:
            producers[v].add(u)
        if u in tensors and v in ops:
            consumers[u].add(v)
    topo(allpred, allsucc)
    eligible = {i for i in ops if ops[i].get("op") not in COPY}
    pred, succ = {i: set() for i in eligible}, {i: set() for i in eligible}
    for u in sorted(eligible):
        todo, seen = list(allsucc[u]), set()
        while todo:
            v = todo.pop()
            if v in seen:
                continue
            seen.add(v)
            if v in eligible:
                succ[u].add(v)
                pred[v].add(u)
            else:
                todo.extend(allsucc[v])
    order = topo(pred, succ)
    rank = {}
    for u in reversed(order):
        rank[u] = float(ops[u]["cycles"]) + max((rank[v] for v in succ[u]), default=0.)
    return dict(ops=ops, tensors=tensors, pred=pred, succ=succ,
                producers=producers, consumers=consumers, rank=rank)


def validate_plan(view: dict, plan: dict) -> None:
    """Coverage + quotient DAG + subgraph/core-order union; not official validation."""
    if set(plan) != {"node_to_subgraph", "core_schedules"}:
        raise ValueError("Unexpected plan fields")
    mapping = {int(k): v for k, v in plan["node_to_subgraph"].items()}
    if len(mapping) != len(plan["node_to_subgraph"]) or set(mapping) != set(view["pred"]):
        raise ValueError("Coverage mismatch")
    if any(type(s) is not int or s < 0 for s in mapping.values()):
        raise ValueError("Invalid subgraph ID")
    schedules = plan["core_schedules"]
    if not isinstance(schedules, list) or not schedules or any(not isinstance(s, list) for s in schedules):
        raise ValueError("Invalid core schedules")
    listed = [s for seq in schedules for s in seq]
    groups = set(mapping.values())
    if len(listed) != len(set(listed)) or set(listed) != groups:
        raise ValueError("Subgraph assignment mismatch")
    pred, succ = {s: set() for s in groups}, {s: set() for s in groups}
    pairs = [(mapping[u], mapping[v]) for u in mapping for v in view["succ"][u]]
    pairs += [(a, b) for seq in schedules for a, b in zip(seq, seq[1:])]
    for a, b in pairs:
        if a != b:
            succ[a].add(b)
            pred[b].add(a)
    topo(pred, succ)


def boundary_bytes(view: dict, assignment: dict[int, int]) -> float:
    """Hyperedge proxy: one producer write + one read per remote consumer task.

    COPY-backed inputs have no eligible producer and count reads only. This
    ignores spills, aliases, timing and FIFO-cache hits; it is NOT actual DDR.
    """
    total = 0.
    for tid, tensor in view["tensors"].items():
        sources = {assignment[u] for u in view["producers"][tid] if u in assignment}
        targets = {assignment[u] for u in view["consumers"][tid] if u in assignment}
        remote = targets - sources
        total += float(tensor["size"]) * (len(remote) + int(bool(sources and remote)))
    return total


def make_plan(view: dict, order: list[int], groups: int, cores: int,
              mode: str, problem: int, bandwidth: float) -> dict:
    if groups < 1 or cores < 1 or bandwidth <= 0 or mode not in {"round_robin", "affinity", "single"}:
        raise ValueError("Invalid candidate settings")
    width = max(1, math.ceil(len(order) / groups))
    blocks = [order[i:i + width] for i in range(0, len(order), width)]
    mapping = {u: s for s, block in enumerate(blocks) for u in block}
    schedules, assigned = [[] for _ in range(cores)], {}
    pipe_load = [{p: 0. for p in PIPES} for _ in range(cores)]
    for s, block in enumerate(blocks):
        work = {p: sum(float(view["ops"][u]["cycles"]) for u in block
                       if view["ops"][u]["pipe"] == p) for p in PIPES}
        if mode == "single":
            core = 0
        elif mode == "round_robin":
            core = s % cores
        else:
            costs = []
            for k in range(cores):
                trial = {**assigned, **{u: k for u in block}}
                # In A all inter-subgraph edges cost even on the same core;
                # therefore do not give same-core traffic rebates in A.
                traffic = boundary_bytes(view, trial) if problem != 1 else 0.
                load = max(max(pipe_load[j][p] + (work[p] if j == k else 0.)
                               for p in PIPES) for j in range(cores))
                costs.append((load + traffic / bandwidth, k))
            core = min(costs)[1]
        schedules[core].append(s)
        assigned.update({u: core for u in block})
        for p in PIPES:
            pipe_load[core][p] += work[p]
    plan = {"node_to_subgraph": {str(u): mapping[u] for u in order},
            "core_schedules": schedules}
    validate_plan(view, plan)
    return plan


def candidates(view: dict, cores: int, problem: int, bandwidth: float, seed: int):
    order = topo(view["pred"], view["succ"])
    # Legal-shaped fallback first. Final execution validity still needs the CLI.
    yield make_plan(view, order, 1, cores, "single", problem, bandwidth)
    seen, rng = set(), random.Random(seed)
    for repetition in range(8):
        priority = {u: (-view["rank"][u] if repetition == 0 else rng.random()) for u in order}
        current = topo(view["pred"], view["succ"], priority)
        for groups in sorted({cores, 2 * cores, 4 * cores, 8 * cores, len(order)}):
            for mode in ("round_robin", "affinity"):
                if mode == "affinity" and groups == len(order) and len(order) > 2000:
                    continue  # avoid the quadratic singleton-affinity proxy on large graphs
                plan = make_plan(view, current, max(1, groups), cores, mode, problem, bandwidth)
                key = digest(plan)
                if key not in seen:
                    seen.add(key)
                    yield plan



def mutate_plan(view: dict, plan: dict, rng: random.Random) -> dict:
    """Merge/split/migrate contiguous topological blocks; official validity is separate."""
    mapping = {int(u): group for u, group in plan["node_to_subgraph"].items()}
    order = topo(view["pred"], view["succ"], {u: (mapping[u], u) for u in mapping})
    ids = sorted(set(mapping.values()))
    owners = {group: core for core, seq in enumerate(plan["core_schedules"]) for group in seq}
    blocks = [[u for u in order if mapping[u] == group] for group in ids]
    assigned = [owners[group] for group in ids]
    cores = len(plan["core_schedules"])
    if not blocks:
        return plan
    action = rng.choice(("merge", "split", "migrate"))
    if action == "merge" and len(blocks) > 1:
        i = rng.randrange(len(blocks) - 1)
        blocks[i:i + 2] = [blocks[i] + blocks[i + 1]]
        assigned[i:i + 2] = [rng.choice(assigned[i:i + 2])]
    elif action == "split" and any(len(b) > 1 for b in blocks):
        i = rng.choice([j for j, block in enumerate(blocks) if len(block) > 1])
        cut = rng.randrange(1, len(blocks[i]))
        blocks[i:i + 1] = [blocks[i][:cut], blocks[i][cut:]]
        assigned[i:i + 1] = [assigned[i], rng.randrange(cores)]
    else:
        assigned[rng.randrange(len(blocks))] = rng.randrange(cores)
    schedules = [[] for _ in range(cores)]
    for group, core in enumerate(assigned):
        schedules[core].append(group)
    result = dict(node_to_subgraph={str(u): group for group, block in enumerate(blocks) for u in block},
                  core_schedules=schedules)
    validate_plan(view, result)
    return result


def run_cli(script: Path, graph: Path, config: Path, directory: Path,
            timeout: float, plan: Path | None = None) -> dict:
    """Fresh directory per call prevents accidental reuse of a stale success."""
    directory.mkdir(parents=True, exist_ok=False)
    result_path = directory / "result.json"
    cmd = [sys.executable, str(script.resolve()), str(graph.resolve())]
    if plan is not None:
        cmd.append(str(plan.resolve()))
    cmd += ["--config", str(config.resolve()), "-o", str(result_path.resolve()),
            "--trace-output", str((directory / "trace.json").resolve()),
            "--log-output", str((directory / "official.log").resolve())]
    start = time.perf_counter()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        (directory / "stdout.txt").write_text(proc.stdout, encoding="utf-8")
        (directory / "stderr.txt").write_text(proc.stderr, encoding="utf-8")
        if proc.returncode:
            return dict(status="error", returncode=proc.returncode,
                        seconds=time.perf_counter() - start, error=proc.stderr[-3000:])
        value = load_json(result_path)
        score = value.get("makespan")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or score <= 0:
            raise ValueError("Invalid makespan in evaluator output")
        return dict(status="ok", seconds=time.perf_counter() - start, result=value)
    except subprocess.TimeoutExpired:
        return dict(status="timeout", seconds=time.perf_counter() - start)
    except (OSError, ValueError) as exc:
        return dict(status="error", seconds=time.perf_counter() - start, error=str(exc))


def search(graph: Path, code: Path, config: Path, out: Path, cores: int = 4,
           problem: int = 1, budget: int = 24, timeout: float = 120., seed: int = 0,
           baseline_cache: dict | None = None) -> dict:
    import configparser
    if budget < 1 or not 1 <= cores <= 5 or problem not in (1, 2, 3) or timeout <= 0:
        raise ValueError("Invalid search configuration")
    cfg = configparser.ConfigParser()
    if not cfg.read(config, encoding="utf-8"):
        raise FileNotFoundError(config)
    bandwidth = cfg.getfloat("bandwidth", "bandwidth")
    script = code / f"multicore_cut_evaluate_problem_{problem}.py"
    baseline_script = code / "singlecore_evaluate.py"
    if not script.is_file() or not baseline_script.is_file():
        raise FileNotFoundError("Official evaluator scripts missing")
    source = load_json(graph)
    view = graph_view(source)
    out.mkdir(parents=True, exist_ok=False)
    manifest = dict(graph_sha256=hashlib.sha256(graph.read_bytes()).hexdigest(),
                    config_sha256=hashlib.sha256(config.read_bytes()).hexdigest(),
                    evaluator_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in sorted(code.glob("*.py"))},
                    problem=problem, cores=cores, seed=seed, budget=budget,
                    timeout_seconds=timeout, status="running", trials=[])
    save_json(out / "manifest.json", manifest)
    if baseline_cache is None:
        baseline = run_cli(baseline_script, graph, config, out / "baseline", timeout)
    else:
        for key in ("graph_sha256", "config_sha256", "evaluator_sha256"):
            if baseline_cache.get(key) != manifest[key]:
                raise ValueError(f"Baseline cache provenance mismatch: {key}")
        baseline = baseline_cache["record"]
        manifest["baseline_source"] = "hash-verified batch cache"
    manifest["baseline"] = baseline
    seen, best, best_plan, start = set(), None, None, time.perf_counter()
    pool = iter(candidates(view, cores, problem, bandwidth, seed))
    rng = random.Random(seed)
    for _ in range(max(200, 20 * budget)):
        if len(manifest["trials"]) >= budget:
            break
        origin = "portfolio"
        if best_plan is not None and len(manifest["trials"]) >= max(4, budget // 2) and rng.random() < .7:
            plan, origin = mutate_plan(view, best_plan, rng), "local_merge_split_migrate"
        else:
            try:
                plan = next(pool)
            except StopIteration:
                if best_plan is None:
                    break
                plan, origin = mutate_plan(view, best_plan, rng), "local_merge_split_migrate"
        key = digest(plan)
        if key in seen:
            continue
        seen.add(key)
        index = len(manifest["trials"])
        if index >= budget:
            break
        plan_path = out / f"plan_{index:04d}.json"
        save_json(plan_path, plan)
        record = run_cli(script, graph, config, out / f"eval_{index:04d}", timeout, plan_path)
        row = dict(index=index, generator=origin, plan_sha256=key, **record)
        manifest["trials"].append(row)
        if record["status"] == "ok":
            result = record["result"]
            movement = result.get("data_movement_bytes", {})
            objective = (result["makespan"], movement.get("physical_ddr_bytes",
                         movement.get("scheduled_copy_bytes", float("inf"))))
            if best is None or objective < best:
                best, best_plan = objective, plan
                save_json(out / "best_plan.json", plan)
                manifest["best_index"] = index
                manifest["best_makespan"] = objective[0]
        save_json(out / "manifest.json", manifest)
    manifest["search_seconds"] = time.perf_counter() - start
    manifest["status"] = "ok" if best is not None else "no_valid_candidate"
    if best is not None and baseline["status"] == "ok":
        manifest["speedup"] = baseline["result"]["makespan"] / best[0]
    save_json(out / "manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--code", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="New directory; never overwritten")
    parser.add_argument("--cores", type=int, default=4)
    parser.add_argument("--problem", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--budget", type=int, default=24)
    parser.add_argument("--timeout", type=float, default=120.)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    result = search(**vars(args))
    print(json.dumps({k: result.get(k) for k in ("status", "best_makespan", "speedup", "best_index")}, indent=2))
    if result["status"] != "ok":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
