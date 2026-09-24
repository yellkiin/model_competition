"""Frozen, case-agnostic acceptance and stopping rules for the memory track.

This module contains no case identifiers. It centralizes the rules that were
validated on the tuned five-core set and then on a disjoint unseen set. Proxy
scores never decide acceptance; only an unchanged official evaluation can do so.
"""
from __future__ import annotations
from research_a_orion_anytime.core import bounds

STOP_RATIO = 1.04
PHASE_ORDER = ('epochs', 'local')


def official_key(makespan: int | float, added_copy_bytes: int | float) -> tuple[float, float]:
    """Primary objective first; bytes are only a tie-break at equal makespan."""
    return float(makespan), float(added_copy_bytes)


def better(makespan: int | float, added_copy_bytes: int | float,
           incumbent_makespan: int | float, incumbent_added_copy_bytes: int | float) -> bool:
    return official_key(makespan, added_copy_bytes) < official_key(
        incumbent_makespan, incumbent_added_copy_bytes)


def search_state(g, cfg, n: int, q: int, incumbent: dict) -> dict:
    raw = incumbent.get('official_result') or {}
    upper = float(raw.get('makespan', float('inf')))
    movement = raw.get('data_movement_bytes') or {}
    added = int(movement.get('added_copy_bytes', 0) or 0)
    spill = int(movement.get('spill_added_copy_bytes', 0) or 0)
    lower = float(bounds(g, cfg, n, q)['global_lower'])
    ratio = upper / lower if lower > 0 else float('inf')
    if ratio <= STOP_RATIO:
        family = 'near_bound_stop'
    elif spill > 0:
        family = 'spill_or_residency'
    elif q == 1:
        family = 'task_boundary_or_release'
    else:
        family = 'tensor_locality_or_order'
    return dict(upper=upper, lower=lower, ratio=ratio, added_copy_bytes=added,
                spill_bytes=spill, family=family, should_search=ratio > STOP_RATIO)
