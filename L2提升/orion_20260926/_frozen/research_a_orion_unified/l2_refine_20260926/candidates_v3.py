"""Fixed Q3 composition: weak FIFO orders, observed windows, local repair.

This is a new uniform policy, evaluated afresh from the original six seeds.
No per-case version selection. Reuse proxy remains explicitly heuristic.
"""
from .candidates import propose as weak_and_windows
from .candidates_v2 import propose as local_windows
from research_a_orion_unified.io import plan_key
import time


def propose(g, n, cfg, plan, raw, deadline):
    if raw.get('problem') != 3:
        return
    windows = []
    seen = {plan_key(plan)}

    def tag(c):
        c['evidence'] = {**c.get('evidence', {}),
                         'fixed_policy': 'weak_fifo_then_observed_then_local_v3'}
        return c

    # Permit only weak-component unpack and two bounded ordering policies.
    # No topo4 slicing and no broad shared/stagger ordering is evaluated.
    for c in weak_and_windows(g, n, cfg, plan, raw, deadline,
                              granularities=('weak',),
                              policies=('fifo', 'low_footprint')):
        if time.monotonic() >= deadline:
            return
        key = plan_key(c['plan'])
        if key in seen:
            continue
        seen.add(key)
        if c['family'] == 'l2/observed_window':
            windows.append(c)
        else:
            yield tag(c)
    for c in windows:
        if time.monotonic() >= deadline:
            return
        yield tag(c)
    count = 0
    for c in local_windows(g, n, cfg, plan, raw, deadline):
        if time.monotonic() >= deadline or count >= 24:
            return
        key = plan_key(c['plan'])
        if key in seen:
            continue
        seen.add(key)
        count += 1
        yield tag(c)
