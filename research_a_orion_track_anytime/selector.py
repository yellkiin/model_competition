"""Pure candidate selection. Proxies are predictions, never certificates.

Historical quality ratios can be reused within a compatible problem context.
Historical seconds are used only when time_source == 'local'. Selection does
not evaluate a plan, mutate a candidate, or spend the remaining budget.
"""
from __future__ import annotations
from collections import defaultdict
from math import isfinite, log, sqrt
from statistics import median
from typing import Any


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, dict):
        value = value.get('score')
    try:
        result = float(value)
        return result if isfinite(result) else default
    except (TypeError, ValueError):
        return default


def family_statistics(history: list[dict]) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    local_costs = []
    for row in history:
        if row.get('status') in ('ok', 'error', 'timeout', 'audit_failed', 'interrupted_by_budget'):
            grouped[row.get('family', 'frontier')].append(row)
            if row.get('time_source') == 'local':
                cost = _number(row.get('eval_seconds', row.get('wall_seconds')))
                if cost > 0:
                    local_costs.append(cost)
    fallback = median(local_costs) if local_costs else 1.0
    out = {}
    for family, rows in grouped.items():
        ratios, costs = [], []
        for row in rows:
            proxy = _number(row.get('proxy'))
            truth = _number(row.get('makespan'))
            if row.get('status') == 'ok' and proxy > 0 and truth > 0:
                ratios.append(truth / proxy)
            if row.get('time_source') == 'local':
                cost = _number(row.get('eval_seconds', row.get('wall_seconds')))
                if cost > 0:
                    costs.append(cost)
        # Shrink tiny-sample calibrations; median alone overreacts to one result.
        weight = len(ratios) / (len(ratios) + 3.0)
        center = median(ratios) if ratios else 1.0
        calibration = max(.25, min(4.0, 1.0 + weight * (center - 1.0)))
        mad = median(abs(x - center) for x in ratios) if ratios else .25
        error = max(.03, mad, .25 / sqrt(1 + len(ratios)))
        costs.sort()
        p90 = costs[min(len(costs)-1, int(.9 * len(costs)))] if costs else fallback
        out[family] = dict(calls=sum(x.get('time_source')=='local' for x in rows), historical_calls=sum(x.get('time_source')!='local' for x in rows), valid=len(ratios), calibration=calibration,
                           uncertainty=error, predicted_seconds=max(.001, 1.25 * p90),
                           failures=sum(r.get('status') != 'ok' for r in rows))
    out['_default'] = dict(calls=0, valid=0, calibration=1.0, uncertainty=.25,
                           predicted_seconds=max(.001, 1.5*fallback), failures=0)
    return out


def selection_details(candidates: list[dict], history: list[dict], remaining_seconds: float) -> list[dict]:
    stats = family_statistics(history)
    valid = [_number(h.get('makespan'), float('inf')) for h in history if h.get('status') == 'ok']
    incumbent = min(valid, default=float('inf'))
    details = []
    for index, candidate in enumerate(candidates):
        family = candidate.get('family', 'frontier')
        stat = stats.get(family, stats['_default'])
        cost = max(stat['predicted_seconds'], _number(candidate.get('estimated_eval_seconds')))
        proxy = max(1.0, _number(candidate.get('proxy'), incumbent if isfinite(incumbent) else 1.0))
        predicted = proxy * stat['calibration']
        candidate_lower = _number(candidate.get('bounds', {}).get('candidate_lower'))
        optimistic = max(0.0, candidate_lower, predicted - proxy * stat['uncertainty'])
        gain = max(0.0, incumbent - optimistic) / max(1.0, incumbent) if isfinite(incumbent) else 1.0
        confidence_bonus = .02 * sqrt(log(2 + len(history)) / (1 + stat['calls']))
        failure_discount = (1 + stat['valid']) / (1 + stat['valid'] + stat['failures'])
        details.append(dict(index=index, family=family, predicted_makespan=predicted,
                            estimated_eval_seconds=cost, first_evaluation=stat['calls'] == 0,
                            admitted=cost + .05 <= remaining_seconds,
                            acquisition=failure_discount*(gain + confidence_bonus)/cost))
    # A first feasible solution is preferable to rejecting every uncalibrated call.
    # The outer process deadline, not this estimate, enforces the hard time limit.
    if not valid and remaining_seconds > .1 and details and not any(d['admitted'] for d in details):
        min(details, key=lambda d: (d['estimated_eval_seconds'], d['index']))['admitted'] = True
    return details


def select_candidate(candidates: list[dict], history: list[dict], remaining_seconds: float) -> int | None:
    """COMMON.md interface: return an existing index, or None to stop admission."""
    admitted = [d for d in selection_details(candidates, history, remaining_seconds) if d['admitted']]
    if not admitted:
        return None
    # Cover each available family once before repeatedly exploiting one biased proxy.
    first = [d for d in admitted if d['first_evaluation']]
    chosen = max(first or admitted, key=lambda d: (d['acquisition'], -d['estimated_eval_seconds'], -d['index']))
    return chosen['index']


def stop_reason(history: list[dict], makespan: float | None, global_lower: float,
                gap_tolerance: float = .005, stagnation_calls: int = 12,
                minimum_calls: int = 16) -> str | None:
    """Only a GLOBAL bound can justify a quality-gap stop; stagnation is heuristic."""
    if makespan is not None and 0 < global_lower <= makespan:
        if 1.0 - global_lower / makespan <= gap_tolerance:
            return 'global_bound_gap'
    local = [r for r in history if r.get('time_source') == 'local' and
             r.get('status') in ('ok', 'error', 'timeout', 'audit_failed', 'interrupted_by_budget')]
    if len(local) >= minimum_calls and not any(r.get('improved_makespan', r.get('improved')) for r in local[-stagnation_calls:]):
        return 'stagnation_heuristic_not_optimality'
    return None
