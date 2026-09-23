"""Deterministic mechanism experiments; synthetic except the 34-row CSV audit."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import platform
import numpy as np
import pandas as pd
import scipy
from scipy.optimize import minimize_scalar
from .f_models import Law, fit_law, effective_tokens, analytic_optimum, optimize_budget, minimax_regret
from .d_core import grid_supercover, terrain_max, terrain_blocked, fspl, link_certificate, color_intervals, charge_seconds, frozen_components
from .run_data import audit_scaling, fingerprint


def rectangle_oracle(a, b, shape):
    """Independent exhaustive slab clipping; intentionally not production traversal."""
    a, b = np.array(a), np.array(b)
    cells = set()
    for row in range(shape[0]):
        for col in range(shape[1]):
            lo, hi = 0., 1.
            for k, left in enumerate((col, row)):
                delta = b[k]-a[k]
                if delta == 0:
                    if a[k] < left or a[k] > left+1:
                        lo, hi = 1., 0.
                        break
                else:
                    u, v = sorted(((left-a[k])/delta, (left+1-a[k])/delta))
                    lo, hi = max(lo, u), min(hi, v)
            if lo <= hi+1e-12:
                cells.add((row, col))
    return cells


def run(seed=20260923):
    rng = np.random.default_rng(seed)
    fixture = Path(__file__).parent/'fixtures/pythia_head34.csv'
    observed = audit_scaling(pd.read_csv(fixture))
    observed['source'] = fingerprint(fixture)
    observed['evidence'] = 'projection of original B1 lines 2-35, NOT the complete dataset'
    truth = Law()
    n, d = np.meshgrid(np.geomspace(.1, 30, 8), np.geomspace(.2, 300, 18))
    n, d = n.ravel(), d.ravel()
    fitted, diagnostic = fit_law(n, d, truth.loss(n, d)+rng.normal(0, 1e-4, len(n)), seed=seed)
    p = rng.dirichlet(np.ones(3), size=128)
    q = p@np.array([.3, .8, .6])
    design = np.column_stack([np.ones(len(p)), p[:, :2], q])
    w = np.array([.8, -.4, .2])
    original = .5+p@w+1.3*q
    equivalent = .5+p@(w+1.3*np.array([.3, .8, .6]))
    classic = []
    for budget in [1e19, 1e22, 1e24]:
        na, da = analytic_optimum(truth, budget)
        sol = minimize_scalar(lambda ln: float(truth.loss(np.exp(ln), budget/(6e18*np.exp(ln)))),
                              bounds=(-15, 15), method='bounded', options={'xatol': 1e-12})
        classic.append({'budget': budget, 'analytic_N_B': na, 'analytic_D_B': da,
                        'relative_N_error': abs(np.exp(sol.x)-na)/na})
    scenarios = []
    for kind in ['exponential', 'power', 'logarithmic']:
        for budget in [1e19, 1e22, 1e24]:
            scenarios.append({'cost_kind': kind, **optimize_budget(truth, budget, kind=kind, seed=seed)})
    supplies = []
    for label, unique, retention in [('unlimited', None, 0.), ('finite_supply_no_filter', 10., 0.), ('filtered_supply', 10., 6.)]:
        for s in [17, 42, seed]:
            supplies.append({'case': label, 'seed': s, **optimize_budget(truth, 1e22, unique0=unique, retention=retention, r_star=3., seed=s)})
    grid_tests = 0
    for _ in range(300):
        a, b = rng.uniform(0, 12, (2, 2))
        assert set(grid_supercover(a, b, (12, 12))) == rectangle_oracle(a, b, (12, 12))
        grid_tests += 1
    for a, b in [((0, 0), (12, 12)), ((0, 6), (12, 6)), ((6, 0), (6, 12)), ((3, 3), (3, 3))]:
        assert set(grid_supercover(a, b, (12, 12))) == rectangle_oracle(a, b, (12, 12))
        grid_tests += 1
    dem = np.zeros((25, 25))
    dem[12, 11] = 100.
    start, end = np.array([.5, 12.5]), np.array([24.5, 12.5])
    sampled = [dem[int(xy[1]), int(xy[0])] for xy in [start+t*(end-start) for t in np.linspace(0, 1, 5)]]
    a0, a1, base = np.array([100., 0, 50]), np.array([1500., 500, 50]), np.zeros(3)
    cert = link_certificate(a0, a1, base, base, 115.)
    dense = min(115-fspl(np.linalg.norm(a0+t*(a1-a0)))-10 for t in np.linspace(0, 1, 1001))
    decision, regret = minimax_regret([[1., 4.], [2., 2.], [4., 1.]])
    return {'seed': seed, 'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__, 'pandas': pd.__version__},
            'real_attachment_excerpt_audit': observed,
            'synthetic_scaling_recovery': {'truth': asdict(truth), 'fitted': asdict(fitted), 'diagnostic': diagnostic},
            'synthetic_quality_mixture_nonidentifiability': {'columns': 4, 'rank': int(np.linalg.matrix_rank(design)), 'max_equal_prediction_error': float(np.max(abs(original-equivalent)))},
            'exponential_mixing_gauge_error': float(np.max(abs(2*np.exp(p@w) - 2*np.exp(-3)*np.exp(p@(w+3))))),
            'analytic_numeric_budget_crosscheck': classic,
            'conditional_synthetic_cost_scenarios': scenarios, 'conditional_synthetic_supply_multiseed': supplies,
            'repeated_data_example': {'trained_tokens_B': 100., 'unique_B': 10., 'r_star': 3., 'effective_B': float(effective_tokens(100., 10., 3.))},
            'grid_independent_oracle_passed': grid_tests,
            'synthetic_ridge_counterexample': {'five_point_max_m': float(max(sampled)), 'supercover_max_m': terrain_max(dem, start, end), 'ray_at_50m_blocked': terrain_blocked(dem, start, end, 50, 50)},
            'synthetic_radio_certificate': {**cert, 'dense_1001_worst_margin_db': float(dense)},
            'synthetic_resource_counterexample': {'flight_peak': color_intervals([(0, 10), (15, 25)])[0], 'battery_peak': color_intervals([(0, 30), (15, 45)])[0], 'charge_from_soc_09_s': charge_seconds(.9, 1800, .8, 2), 'frozen_components': frozen_components(['S1', 'S2', 'S3'], [['S1', 'S2'], ['S2', 'S3']])},
            'finite_scenario_minimax_regret': {'selected_row_zero_based': decision, 'worst_regrets': regret.tolist()},
            'not_done': ['complete official F fitting or Q construction', 'official D DEM/XLSX evaluation or feasible joint route', 'real LLM training', 'competition solution or optimality certificate']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', default='research_fd/results/local_validation.json')
    p.add_argument('--seed', type=int, default=20260923)
    a = p.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(run(a.seed), ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(out)


if __name__ == '__main__':
    main()
