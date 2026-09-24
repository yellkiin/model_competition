"""Read-only audit of the 100 registered A-problem graph inputs."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict, deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "数据/原始/A题官方附件/data"
OUT = ROOT / "求解/数据审计.json"
CSV = ROOT / "求解/数据审计.csv"


def audit_graph(path: Path) -> dict:
    graph = json.loads(path.read_text(encoding="utf-8"))
    assert set(graph) == {"ops", "tensors", "edges"}
    ops = graph["ops"]
    tensors = graph["tensors"]
    edges = graph["edges"]
    op_by_id = {x["id"]: x for x in ops}
    tensor_by_id = {x["id"]: x for x in tensors}
    assert len(op_by_id) == len(ops)
    assert len(tensor_by_id) == len(tensors)
    assert not set(op_by_id).intersection(tensor_by_id)
    for op in ops:
        assert isinstance(op["id"], int) and op["id"] >= 0
        assert op["pipe"] in {"PIPE_MTE2", "PIPE_MTE3", "PIPE_M", "PIPE_V"}
        assert isinstance(op["cycles"], int) and op["cycles"] >= 0
    for tensor in tensors:
        assert isinstance(tensor["id"], int) and tensor["id"] >= 0
        assert tensor["pos"] in {"DDR", "L1", "UB"}
        assert isinstance(tensor["size"], int) and tensor["size"] >= 0
    prod = defaultdict(list)
    cons = defaultdict(list)
    edge_set = set()
    for edge in edges:
        pair = (edge["source"], edge["target"])
        assert pair not in edge_set
        edge_set.add(pair)
        u, v = pair
        assert (u in op_by_id and v in tensor_by_id) or (
            u in tensor_by_id and v in op_by_id
        )
        if u in op_by_id:
            prod[v].append(u)
        else:
            cons[u].append(v)
    pred = {op_id: set() for op_id in op_by_id}
    succ = {op_id: set() for op_id in op_by_id}
    for tensor_id in tensor_by_id:
        for u in prod[tensor_id]:
            for v in cons[tensor_id]:
                assert u != v
                pred[v].add(u)
                succ[u].add(v)
    degrees = {u: len(p) for u, p in pred.items()}
    queue = deque(sorted(u for u, d in degrees.items() if d == 0))
    visited = 0
    depth = {u: 0 for u in op_by_id}
    while queue:
        u = queue.popleft()
        visited += 1
        for v in succ[u]:
            depth[v] = max(depth[v], depth[u] + 1)
            degrees[v] -= 1
            if degrees[v] == 0:
                queue.append(v)
    assert visited == len(ops), f"cyclic graph: {path.name}"
    internal = [op for op in ops if op["op"] not in {"COPY_IN", "COPY_OUT"}]
    # Connected components after excluding COPY endpoints quantify natural
    # parallel branches without treating independent DDR reads as coupling.
    parent = {op["id"]: op["id"] for op in internal}

    def find(u):
        while parent[u] != u:
            parent[u] = parent[parent[u]]
            u = parent[u]
        return u

    for u in parent:
        for v in succ[u]:
            if v in parent:
                parent[find(v)] = find(u)
    component_sizes = Counter(find(u) for u in parent)
    level_widths = Counter(depth[u] for u in parent)
    pipe_cycles = Counter()
    for op in internal:
        pipe_cycles[op["pipe"]] += op["cycles"]
    positions = Counter(t["pos"] for t in tensors)
    kinds = Counter(op["op"] for op in ops)
    return {
        "case": path.stem,
        "bytes": path.stat().st_size,
        "ops": len(ops),
        "internal_ops": len(internal),
        "tensors": len(tensors),
        "edges": len(edges),
        "op_edges": sum(map(len, succ.values())),
        "sources": sum(not p for p in pred.values()),
        "sinks": sum(not s for s in succ.values()),
        "max_tensor_bytes": max((t["size"] for t in tensors), default=0),
        "positions": dict(positions),
        "op_kinds": dict(kinds),
        "pipe_cycles": dict(pipe_cycles),
        "max_fanout": max((len(cons[t]) for t in tensor_by_id), default=0),
        "components": len(component_sizes),
        "largest_component": max(component_sizes.values(), default=0),
        "dag_depth": max(depth.values(), default=0),
        "max_level_width": max(level_widths.values(), default=0),
        "valid_dag": True,
    }


def main() -> None:
    paths = sorted(DATA.glob("case_*.json"))
    assert len(paths) == 100, f"expected 100 cases, got {len(paths)}"
    results = [audit_graph(path) for path in paths]
    assert [x["case"] for x in results] == [f"case_{i:03d}" for i in range(1, 101)]
    summary = {
        "case_count": len(results),
        "total_bytes": sum(x["bytes"] for x in results),
        "op_range": [min(x["ops"] for x in results), max(x["ops"] for x in results)],
        "internal_op_range": [min(x["internal_ops"] for x in results), max(x["internal_ops"] for x in results)],
        "tensor_range": [min(x["tensors"] for x in results), max(x["tensors"] for x in results)],
        "max_tensor_bytes": max(x["max_tensor_bytes"] for x in results),
        "op_kinds": dict(sum((Counter(x["op_kinds"]) for x in results), Counter())),
    }
    OUT.write_text(json.dumps({"summary": summary, "cases": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ["case", "bytes", "ops", "internal_ops", "tensors", "edges", "op_edges", "sources", "sinks", "max_tensor_bytes", "max_fanout", "components", "largest_component", "dag_depth", "max_level_width"]
    with CSV.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
