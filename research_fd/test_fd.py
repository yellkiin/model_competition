"""Property tests, counterexamples and synthetic-schema integration tests."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from .f_models import Law, fit_law, effective_tokens, analytic_optimum, optimize_budget, minimax_regret, mixture_features, ridge_predict
from .d_core import Aircraft, grid_supercover, terrain_max, terrain_blocked, fspl, link_certificate, charge_seconds, color_intervals, frozen_components, validate_resources
from .experiments import rectangle_oracle
from .run_data import audit_scaling, fingerprint, read_mixture, mixtures, scaling, dem_arcs


def test_law_recovery():
    n, d = np.meshgrid(np.geomspace(.1, 30, 6), np.geomspace(.2, 200, 12))
    law = Law()
    got, diag = fit_law(n.ravel(), d.ravel(), law.loss(n, d).ravel(), starts=2)
    np.testing.assert_allclose(list(asdict(got).values()), list(asdict(law).values()), rtol=1e-4)
    assert diag['successful_starts'] > 0


def test_single_size_refused_and_real_excerpt():
    frame = pd.read_csv(Path(__file__).parent/'fixtures/pythia_head34.csv')
    audit = audit_scaling(frame)
    assert audit['rows'] == 34 and audit['sizes'] == 1 and audit['unique_run_ids'] == 34
    with pytest.raises(ValueError, match='identifiable'):
        fit_law(frame.N_params_B, frame.D_tokens_B, frame.val_loss)


@pytest.mark.parametrize('d,u', [(1, 2), (2, 2), (100, 1), (1e6, 2)])
def test_effective_tokens_limits(d, u):
    de = effective_tokens(d, u, 3)
    assert 0 < de <= d+1e-9 and de <= u*4+1e-9
    if d <= u:
        assert de == d


@pytest.mark.parametrize('d,u,r', [(0, 1, 3), (1, 0, 3), (1, 1, -1), (float('nan'), 1, 3)])
def test_effective_tokens_invalid(d, u, r):
    with pytest.raises(ValueError):
        effective_tokens(d, u, r)


def test_analytic_budget_and_stationarity():
    law = Law()
    for budget in [1e19, 1e22, 1e24]:
        n, d = analytic_optimum(law, budget, context=4096)
        assert abs((6+2e-4*4096)*n*d*1e18/budget-1) < 1e-12
        assert abs(law.alpha*law.A*n**-law.alpha-law.beta*law.B*d**-law.beta) < 1e-12


def test_quality_optimization_feasible():
    out = optimize_budget(Law(), 1e22, unique0=10, retention=6, seed=17)
    assert .05 <= out['N_B'] <= 300 and .3 <= out['Q'] <= 1
    assert abs(out['spent']/out['budget']-1) < 1e-12
    assert 0 <= out['quality_cost_share'] <= 1


def test_quality_mixture_nonidentifiable():
    p = np.random.default_rng(1).dirichlet(np.ones(3), 40)
    q = p@np.array([.3, .8, .6])
    assert np.linalg.matrix_rank(np.column_stack([np.ones(40), p[:, :2], q])) == 3


def test_mixture_zero_and_closure():
    p = np.array([[1., 0, 0], [0, 1, 0]])
    assert np.isfinite(mixture_features(p, 'clr')).all()
    np.testing.assert_allclose(mixture_features(p, 'clr').sum(axis=1), 0, atol=1e-12)
    with pytest.raises(ValueError):
        mixture_features([[.1, .2]])


def test_ridge_prediction_and_minimax():
    rng = np.random.default_rng(1)
    p = rng.dirichlet(np.ones(3), 100)
    y = p@rng.normal(size=(3, 2))+3
    pred = ridge_predict(p, y, p, lam=1e-6)
    np.testing.assert_allclose(pred, y, atol=1e-6)
    row, regret = minimax_regret([[1, 4], [2, 2], [4, 1]])
    assert row == 1 and regret.tolist() == [3, 1, 3]


@pytest.mark.parametrize('a,b', [((0, 0), (8, 8)), ((0, 4), (8, 4)), ((4, 0), (4, 8)), ((3, 3), (3, 3)), ((8, 0), (0, 8)), ((0, 0), (0, 0))])
def test_supercover_edges(a, b):
    assert set(grid_supercover(a, b, (8, 8))) == rectangle_oracle(a, b, (8, 8))


def test_supercover_random_oracle():
    rng = np.random.default_rng(20260923)
    for _ in range(100):
        a, b = rng.uniform(0, 8, (2, 2))
        assert set(grid_supercover(a, b, (8, 8))) == rectangle_oracle(a, b, (8, 8))


def test_nodata_and_outside_fail_closed():
    dem = np.zeros((5, 5)); dem[2, 2] = np.nan
    with pytest.raises(ValueError, match='NoData'):
        terrain_max(dem, (.5, 2.5), (4.5, 2.5))
    with pytest.raises(ValueError, match='outside'):
        grid_supercover((-1, 0), (1, 1), (5, 5))


def test_ridge_and_ray_height_interval():
    dem = np.zeros((5, 5)); dem[2, 2] = 100
    assert terrain_max(dem, (.5, 2.5), (4.5, 2.5)) == 100
    assert terrain_blocked(dem, (.5, 2.5), (4.5, 2.5), 50, 50)
    assert not terrain_blocked(dem, (.5, 2.5), (4.5, 2.5), 101, 101)


def test_radio_certificate_dense_check():
    a0, a1, b0, b1 = np.array([100, 0, 50]), np.array([1500, 500, 50]), np.zeros(3), np.array([20, 0, 0])
    out = link_certificate(a0, a1, b0, b1, 115)
    for t in np.linspace(0, 1, 101):
        d = np.linalg.norm((1-t)*(a0-b0)+t*(a1-b1))
        assert 115-fspl(max(d, 1))-10 >= out['worst_margin_db']-1e-10
    assert not link_certificate(a0, a1, b0, b1, 90)['certified']


@pytest.mark.parametrize('soc', [0, .2, .8, .9, 1.])
def test_charge(soc):
    seconds = charge_seconds(soc, 1800, .8, 2)
    assert 0 <= seconds <= 1800
    if soc == 0: assert seconds == 1800
    if soc == 1: assert seconds == 0


def test_charge_slow_phase_and_halfopen_resource():
    assert charge_seconds(.9, 1800, .8, 2) == pytest.approx(300)
    assert color_intervals([(0, 10), (10, 20)])[0] == 1
    assert color_intervals([(0, 10), (15, 25)])[0] == 1
    assert color_intervals([(0, 30), (15, 45)])[0] == 2
    assert color_intervals([]) == (0, [])


def test_aircraft_energy_and_limit():
    a = Aircraft(25, 30, 2, 50, 20, .7, .2)
    assert a.leg_energy(1, 20, 25) > a.leg_energy(1, 20, 0)
    assert a.roundtrip_limit(100, 0, 0) is None
    q = a.roundtrip_limit(14, 100, 100)
    assert q is not None
    assert a.leg_energy(14, 100, q)+a.leg_energy(14, 100, 0) <= 1.6+1e-10
    with pytest.raises(ValueError): a.leg_energy(1, 1, 26)


def test_frozen_components_and_resources():
    assert len(frozen_components(['a', 'b', 'c'], [['a', 'b'], ['b', 'c']])) == 1
    tasks = [dict(id=str(i), type='A', aircraft='a', battery='b', start=s, aircraft_end=e, battery_ready=e+20) for i, (s, e) in enumerate([(0, 10), (15, 25)])]
    out = validate_resources(tasks, {'A': {'aircraft': 1, 'battery': 2}})
    assert not out['valid_occupancy'] and out['required']['A']['battery'] == 2
    tasks[1]['battery'] = 'b2'
    assert validate_resources(tasks, {'A': {'aircraft': 1, 'battery': 2}})['valid_occupancy']


def test_lfs_guard(tmp_path):
    p = tmp_path/'dem.tif'; p.write_text('version https://git-lfs.github.com/spec/v1\noid sha256:x\nsize 99')
    with pytest.raises(ValueError, match='LFS pointer'): fingerprint(p)


def test_scaling_entry_synthetic_schema(tmp_path):
    root = tmp_path/'题目/F题/real_attachments/B_scaling_laws'; root.mkdir(parents=True)
    n, d = np.meshgrid(np.geomspace(.1, 10, 5), np.geomspace(.2, 200, 14))
    pd.DataFrame({'run_id': np.arange(n.size), 'N_params_B': n.ravel(), 'D_tokens_B': d.ravel(), 'val_loss': Law().loss(n, d).ravel()}).to_csv(root/'pythia_training_log_existing.csv', index=False)
    a = argparse.Namespace(repo=tmp_path, out=tmp_path/'out.json', seed=17, starts=1, bootstrap=0)
    out = scaling(a)
    assert len(out['splits']) == 7 and out['audit']['rows'] == 70
    assert all(s['rmse'] < 1e-5 for s in out['splits'])


def test_mixture_entry_synthetic_schema(tmp_path):
    root = tmp_path/'题目/F题/real_attachments/A_data_value/regmix_tables'; root.mkdir(parents=True)
    rng = np.random.default_rng(1); weights = rng.uniform(0, 1, (17, 13))
    pc = [f'train_d{i}' for i in range(17)]; yc = [f'metric/d{i}_val_loss' for i in range(13)]
    for prefix, scale, rows in [('train', '1m', 80), ('test', '1m', 25), ('test', '60m', 25), ('test', '1B', 25)]:
        p = rng.dirichlet(np.ones(17), rows); y = 3+p@weights
        pp, yy = pd.DataFrame(p, columns=pc), pd.DataFrame(y, columns=yc)
        pp.insert(0, 'index', np.arange(rows)); yy.insert(0, 'index', np.arange(rows))
        pp.to_csv(root/f'{prefix}_mixture_{scale}.csv', index=False)
        yy.iloc[::-1].to_csv(root/f'{prefix}_pile_loss_{scale}.csv', index=False)
    out = mixtures(argparse.Namespace(repo=tmp_path, seed=17))
    assert len(out['validation']) == 3
    assert max(out['validation'][0]['metrics'][0]['rmse_per_domain']) < .001
    bad = pd.read_csv(root/'test_mixture_1m.csv'); bad.loc[0, 'index'] = 999
    bad.to_csv(root/'test_mixture_1m.csv', index=False)
    with pytest.raises(ValueError, match='unmatched'): read_mixture(root, '1m')


def test_dem_entry_synthetic_geotiff(tmp_path):
    import rasterio
    from rasterio.transform import from_origin
    dem = tmp_path/'demo.tif'
    with rasterio.open(dem, 'w', driver='GTiff', height=4, width=4, count=1, dtype='float32', crs='EPSG:32648', transform=from_origin(500000, 3500000, 30, 30)) as ds:
        ds.write(np.arange(16, dtype='float32').reshape(4, 4), 1)
    nodes = tmp_path/'nodes.json'
    nodes.write_text(json.dumps({'nodes': [{'id': 'O01', 'x': 500015, 'y': 3499985, 'work_height_m': 0}, {'id': 'S001', 'x': 500105, 'y': 3499895, 'work_height_m': 30}]}))
    out = dem_arcs(argparse.Namespace(dem=dem, nodes=nodes))
    assert len(out['arcs']) == 2 and out['arcs'][0]['cruise_asl_m'] == 65


def test_capacity_invalid():
    with pytest.raises(ValueError):
        validate_resources([], {'A': {'aircraft': float('nan'), 'battery': 2}})


def test_mixing_exponential_gauge():
    p = np.random.default_rng(7).dirichlet(np.ones(3), 50)
    w = np.array([.2, -.3, .7])
    np.testing.assert_allclose(2*np.exp(p@w), 2*np.exp(-3)*np.exp(p@(w+3)), atol=1e-12)
