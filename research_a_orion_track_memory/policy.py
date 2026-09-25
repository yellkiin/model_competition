"""Frozen, case-agnostic acceptance and stopping rules for memory repair.

Only original-official scores accept a plan. Proxy values never do. A small
posterior gap permits a heuristic stop; it is not proof of global optimality.
"""
from __future__ import annotations
from research_a_orion_anytime.core import bounds

STOP_RATIO = 1.04
PHASE_ORDER = ('epochs', 'local')
RULE_VERSION = 'memory-frozen-3.0'
PHASE_EVALUATIONS = {'epochs': 16, 'local': 24}


def official_key(makespan, added_copy_bytes):
    return int(makespan), int(added_copy_bytes)


def better(makespan, added_copy_bytes, incumbent_makespan, incumbent_added_copy_bytes):
    return official_key(makespan, added_copy_bytes) < official_key(incumbent_makespan, incumbent_added_copy_bytes)


def search_state(g, cfg, n, q, incumbent):
    raw = incumbent.get('official_result') or {}
    upper = float(raw.get('makespan', float('inf')))
    movement = raw.get('data_movement_bytes') or {}
    added = int(movement.get('added_copy_bytes', 0) or 0)
    spill = int(movement.get('spill_added_copy_bytes', 0) or 0)
    lower = float(bounds(g, cfg, n, q)['global_lower'])
    ratio = upper / lower if lower > 0 else float('inf')
    family = ('near_bound_stop' if ratio <= STOP_RATIO else
              'spill_or_residency' if spill > 0 else
              'task_boundary_or_release' if q == 1 else 'tensor_locality_or_order')
    return dict(upper=upper, lower=lower, ratio=ratio, added_copy_bytes=added,
                spill_bytes=spill, family=family, should_search=ratio > STOP_RATIO)
