"""Independent component placement and legal locality waves."""
from __future__ import annotations
from collections import defaultdict
import math
from .model import Graph, make_plan, topo


def component_owners(g: Graph, n: int, traffic_weight=0.):
    """Vector-load LPT. Shared input sets, not sums over consumer edges."""
    loads = [[0.] * 4 for _ in range(n)]
    inputs = [set() for _ in range(n)]
    owner = {}
    pieces = [(c, g.loads(c)) for c in g.components]
    pieces.sort(key=lambda cw: (-max(cw[1]), -sum(cw[1]), min(cw[0])))
    for c, w in pieces:
        external = set().union(*(g.inputs[u] for u in c))
        external = {t for t in external if not g.ps[t]}
        options = []
        for k in range(n):
            row = [a+b for a,b in zip(loads[k], w)]
            peak = max([max(row)] + [max(loads[j]) for j in range(n) if j != k])
            incremental = sum(g.tensors[t]['size'] for t in external-inputs[k])
            score = peak + traffic_weight*incremental
            options.append((score, sum(x*x for x in row)-sum(x*x for x in loads[k]), k, row))
        _, _, k, loads[k] = min(options)
        inputs[k].update(external)
        owner.update({u:k for u in c})
    return owner


def locality_waves(g: Graph, n: int, width: int | None, *, skew=False, traffic_weight=0.):
    """Keep each independent component on one core; order small depth windows.

    Components have no compute dependencies between them. This permits legal
    per-core different window widths without adding artificial delay operations.
    """
    owners = component_owners(g, n, traffic_weight)
    blocks, where = [], []
    # Generate a common topological ordering (window, core). For skewed widths,
    # components remain wholly on one core, so core-wise concatenation is legal.
    groups = defaultdict(list)
    for u in g.order:
        k = owners[u]
        step = None if width is None else max(1, width * (1 + k % 3) if skew else width)
        wave = 0 if step is None else g.depth[u] // step
        groups[wave, k].append(u)
    for wave, k in sorted(groups):
        blocks.append(groups[wave,k]); where.append(k)
    return make_plan(blocks, where, n)
