"""Local negative-evidence cooldown for FIFO families, with periodic re-probing.

A heuristic opportunity-cost guard, not pruning by an unproved lower bound.
No case identifiers, no model changes, and no foreign-machine timing transfer.
"""
from __future__ import annotations
from .selector import family_statistics, stop_reason
from .selector import selection_details as base_details


def selection_details(candidates, history, remaining_seconds):
    details = base_details(candidates, history, remaining_seconds)
    local = [r for r in history if r.get('time_source') == 'local' and
             r.get('status') in ('ok','error','timeout','audit_failed','interrupted_by_budget')]
    fifo_indices = [i for i,r in enumerate(local)
                    if str(r.get('family','')).startswith('anytime/fifo')]
    recent = [local[i] for i in fifo_indices[-3:]]
    failed_probes = len(recent) == 3 and not any(
        r.get('improved_makespan',r.get('improved',False)) for r in recent)
    calls_after_probe = len(local)-1-fifo_indices[-1] if fifo_indices else 0
    # A changed parent can change FIFO timing: never blacklist a family forever.
    # Re-probe after eight completed non-FIFO calls, or whenever FIFO itself wins.
    cool = failed_probes and calls_after_probe < 8
    for d in details:
        d['fifo_negative_evidence_cooldown'] = cool and d['family'].startswith('anytime/fifo')
        d['nonfifo_calls_after_probe'] = calls_after_probe
        d['cooldown_is_heuristic'] = True
    return details


def select_candidate(candidates, history, remaining_seconds):
    admitted = [d for d in selection_details(candidates,history,remaining_seconds) if d['admitted']]
    if not admitted:
        return None
    preferred = [d for d in admitted if not d['fifo_negative_evidence_cooldown']]
    # Only deprioritize when another actual admitted candidate is available.
    # Do not claim exhausted search, optimality, or force idle waiting otherwise.
    active = preferred or admitted
    first = [d for d in active if d['first_evaluation']]
    return max(first or active, key=lambda d:(d['acquisition'],-d['estimated_eval_seconds'],-d['index']))['index']
