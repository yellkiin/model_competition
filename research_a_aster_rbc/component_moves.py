"""Bounded whole-component moves for the next real-instance experiment.

This module is used by the second-round solver. Load balancing is a
candidate-ordering heuristic, not an official score or a feasibility proof.
The caller must retain Plan.load and the unchanged official evaluation chain.
"""
from __future__ import annotations

from collections import defaultdict
from heapq import nsmallest

from research_a.model import Graph, Plan


def component_neighbors(g: Graph, p: Plan, limit=6):
    """Yield at most six deterministic moves of an independent full component.

    Only global weak components wholly inside one current block are eligible.
    A component moves to an existing block on a different core. Other blocks
    retain their relative order, and no move empties a previously active core.

    Rank lexicographically by changes in maximum core/Pipe workload, maximum
    total core workload, squared core/Pipe workloads, and squared total core
    workloads. Lower is preferred; graph-order position and block indices break
    ties. These quantities omit communication, Spill and cache timing.
    """
    count = min(6, max(0, int(limit)))
    if not count or p.cores < 2 or not p.blocks:
        return

    position = {u: i for i, u in enumerate(g.order)}
    block_of = {u: s for s, block in enumerate(p.blocks) for u in block}
    core_nodes = [0] * p.cores
    pipe_load = [defaultdict(float) for _ in range(p.cores)]
    total_load = [0.] * p.cores
    for s, block in enumerate(p.blocks):
        k = p.owners[s]
        core_nodes[k] += len(block)
        for u in block:
            work = g.cost[u]
            pipe_load[k][g.ops[u]['pipe']] += work
            total_load[k] += work

    pipes = sorted({g.ops[u]['pipe'] for u in g.ids})
    base_peak_pipe = max((work for row in pipe_load for work in row.values()), default=0.)
    base_peak_total = max(total_load, default=0.)

    # Discover global components, rather than fragments cut by a current block.
    # Thus moving a component cannot create a compute edge to another block.
    visited = set()
    components = []
    for first in g.order:
        if first in visited:
            continue
        visited.add(first)
        stack, nodes = [first], []
        while stack:
            u = stack.pop()
            nodes.append(u)
            for adjacent in (g.pred[u], g.succ[u]):
                for v in adjacent:
                    if v not in visited:
                        visited.add(v)
                        stack.append(v)
        source = block_of[nodes[0]]
        if any(block_of[u] != source for u in nodes):
            continue
        source_core = p.owners[source]
        if len(nodes) >= core_nodes[source_core]:
            continue
        work_by_pipe = defaultdict(float)
        for u in nodes:
            work_by_pipe[g.ops[u]['pipe']] += g.cost[u]
        components.append((min(position[u] for u in nodes), source, nodes,
                           work_by_pipe, sum(work_by_pipe.values())))

    def ranked_moves():
        for component_id, (first, source, _, work_by_pipe, work) in enumerate(components):
            source_core = p.owners[source]
            # Multiple blocks on the same target core have the same load score.
            # Retain them as distinct candidates; block index is the fixed tie-break.
            for target, target_core in enumerate(p.owners):
                if source_core == target_core or not p.blocks[target]:
                    continue
                new_peak_pipe = max((
                    pipe_load[k].get(pipe, 0.)
                    + (work_by_pipe.get(pipe, 0.) if k == target_core else 0.)
                    - (work_by_pipe.get(pipe, 0.) if k == source_core else 0.)
                    for k in range(p.cores) for pipe in pipes
                ), default=0.)
                new_peak_total = max(
                    total_load[k] + (work if k == target_core else 0.)
                    - (work if k == source_core else 0.)
                    for k in range(p.cores)
                )
                # Only the source and target loads change in these sums.
                squared_pipe_delta = sum(
                    2. * moved * (pipe_load[target_core].get(pipe, 0.)
                                  - pipe_load[source_core].get(pipe, 0.) + moved)
                    for pipe, moved in work_by_pipe.items()
                )
                squared_total_delta = 2. * work * (
                    total_load[target_core] - total_load[source_core] + work)
                yield (new_peak_pipe - base_peak_pipe,
                       new_peak_total - base_peak_total,
                       squared_pipe_delta, squared_total_delta,
                       first, source, target, component_id)

    for move in nsmallest(count, ranked_moves()):
        source, target, component_id = move[-3:]
        moving = set(components[component_id][2])
        blocks, owners = [], []
        for s, block in enumerate(p.blocks):
            if s == source:
                updated = [u for u in block if u not in moving]
                if not updated:
                    continue
            elif s == target:
                updated = sorted([*block, *moving], key=position.__getitem__)
            else:
                updated = list(block)
            blocks.append(updated)
            owners.append(p.owners[s])
        yield Plan(blocks, owners, p.cores)
