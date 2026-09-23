"""Read-only local attachment entry points. See README for validation boundaries."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from .f_models import fit_law, ridge_predict
from .d_core import grid_supercover, terrain_max, validate_resources


def fingerprint(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open('rb') as f:
        if f.read(160).startswith(b'version https://git-lfs.github.com/spec/v1'):
            raise ValueError(f'{path}: Git LFS pointer, run git lfs pull first')
        f.seek(0)
        for block in iter(lambda: f.read(1024*1024), b''):
            digest.update(block)
    return {'path': str(path), 'sha256': digest.hexdigest(), 'bytes': path.stat().st_size}


def audit_scaling(frame):
    cols = ['N_params_B', 'D_tokens_B', 'val_loss']
    if not set(cols).issubset(frame):
        raise ValueError(f'missing required columns: {cols}')
    a = frame[cols].to_numpy(float)
    if not np.isfinite(a).all() or np.any(a <= 0):
        raise ValueError('invalid N/D/loss rows: repair provenance, do not silently drop')
    duplicates = frame.duplicated(['N_params_B', 'D_tokens_B']).sum()
    unique_run = None if 'run_id' not in frame else int(frame.run_id.nunique())
    return {'rows': len(frame), 'sizes': int(frame.N_params_B.nunique()),
            'unique_run_ids': unique_run, 'duplicate_size_token_pairs': int(duplicates),
            'run_id_is_row_unique': unique_run == len(frame),
            'units': 'N and D in billions',
            'warning': 'size holdout is not independent-family validation; run_id semantics require source verification'}


def scaling(args):
    path = Path(args.repo)/'题目/F题/real_attachments/B_scaling_laws/pythia_training_log_existing.csv'
    source = fingerprint(path)
    frame = pd.read_csv(path)
    audit = audit_scaling(frame)
    if audit['duplicate_size_token_pairs']:
        raise ValueError('duplicate size/token pairs require a verified trajectory identifier')
    n, d, y = [frame[c].to_numpy(float) for c in ['N_params_B', 'D_tokens_B', 'val_loss']]
    sizes = np.unique(n)
    if len(sizes) < 4:
        raise ValueError('at least 4 sizes needed for leave-size-out fitting')
    records, predictions = [], []
    def one_split(name, train, test):
        law, diagnostic = fit_law(n[train], d[train], y[train], seed=args.seed, starts=args.starts)
        pred = law.loss(n[test], d[test])
        records.append({'split': name, 'n_test': int(test.sum()),
                        'rmse': float(np.sqrt(np.mean((pred-y[test])**2))), 'fit': diagnostic})
        for idx, value in zip(np.where(test)[0], pred):
            predictions.append({'split': name, 'row_zero_based': int(idx), 'actual': float(y[idx]), 'predicted': float(value)})
    for size in sizes:
        one_split(f'leave_size_{size:g}', n != size, n == size)
    early = np.zeros(len(n), bool)
    for size in sizes:
        early |= (n == size) & (d <= np.quantile(d[n == size], .8))
    one_split('within_size_forward_80_20', early, ~early)
    rng = np.random.default_rng(args.seed)
    perm = rng.permutation(len(n))
    train = np.zeros(len(n), bool)
    train[perm[:int(.8*len(n))]] = True
    one_split('random_rows_diagnostic_NOT_main_validation', train, ~train)
    law, diagnostic = fit_law(n, d, y, seed=args.seed, starts=args.starts)
    boot, failures = [], 0
    for b in range(args.bootstrap):
        sampled = rng.choice(sizes, size=len(sizes), replace=True)
        ix = np.concatenate([np.flatnonzero(n == s) for s in sampled])
        try:
            estimate, _ = fit_law(n[ix], d[ix], y[ix], seed=args.seed+b, starts=args.starts)
            boot.append(list(asdict(estimate).values()))
        except (ValueError, RuntimeError):
            failures += 1
    result = {'source': source, 'audit': audit, 'splits': records, 'all_data_fit': diagnostic,
              'bootstrap_success': len(boot), 'bootstrap_failures': failures,
              'bootstrap_note': 'size-block descriptive intervals; few clusters and shared recipe limit inference',
              'bootstrap_quantiles_025_975': None if len(boot) < 10 else np.quantile(boot, [.025, .975], axis=0).tolist(),
              'scope': 'B1 only; no quality effect, causal claim or family-wide extrapolation validation'}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(predictions).to_csv(out.with_suffix('.predictions.csv'), index=False)
    return result


def read_mixture(root, scale, train=False):
    prefix = 'train' if train else 'test'
    paths = [root/f'{prefix}_mixture_{scale}.csv', root/f'{prefix}_pile_loss_{scale}.csv']
    sources = [fingerprint(p) for p in paths]
    p, y = [pd.read_csv(p) for p in paths]
    if p['index'].isna().any() or y['index'].isna().any() or set(p['index']) != set(y['index']):
        raise ValueError('missing/unmatched recipe indices')
    frame = p.merge(y, on='index', validate='one_to_one')
    pc = [c for c in p if c.startswith('train_')]
    yc = [c for c in y if c.startswith('metric/') and c.endswith('_val_loss')]
    if len(pc) != 17 or len(yc) != 13:
        raise ValueError('expected 17 recipe domains and 13 validation losses; inspect schema')
    pp, yy = frame[pc].to_numpy(float), frame[yc].to_numpy(float)
    sums = pp.sum(axis=1)
    if not np.isfinite(pp).all() or not np.isfinite(yy).all() or np.any(pp < 0) or np.any(yy <= 0) or np.max(abs(sums-1)) > .01:
        raise ValueError('invalid values or recipe sum error above rounding tolerance .01')
    rounding = float(np.max(abs(sums-1)))
    pp = pp/sums[:, None]  # Explicitly logged: input proportions are rounded to .001.
    return pp, yy, pc, yc, {'sources': sources, 'max_sum_correction': rounding}


def mixtures(args):
    root = Path(args.repo)/'题目/F题/real_attachments/A_data_value/regmix_tables'
    p, y, pc, yc, source = read_mixture(root, '1m', True)
    keys = [tuple(row.round(12)) for row in p]
    unique = sorted(set(keys))
    if len(unique) < 10:
        raise ValueError('too few distinct training recipes')
    rng = np.random.default_rng(args.seed)
    val_keys = {unique[i] for i in rng.permutation(len(unique))[:max(1, len(unique)//5)]}
    val = np.array([k in val_keys for k in keys])
    choices = []
    for mode, eps in [('linear', 1e-4), ('clr', 1e-6), ('clr', 1e-4), ('clr', .01)]:
        for lam in [.001, .1, 10., 100.]:
            pred = ridge_predict(p[~val], y[~val], p[val], mode, lam, eps)
            choices.append((float(np.mean((pred-y[val])**2)), mode, lam, eps))
    mse, mode, lam, eps = min(choices)
    results = []
    for scale in ['1m', '60m', '1B']:
        pp, yy, ppc, yyc, meta = read_mixture(root, scale)
        if (pc, yc) != (ppc, yyc):
            raise ValueError('column ordering changed across scales')
        pred = ridge_predict(p, y, pp, mode, lam, eps)
        overlap = np.array([tuple(row.round(12)) in set(keys) for row in pp])
        metrics = []
        for subset, mask in [('all', np.ones(len(pp), bool)), ('novel_recipe_only', ~overlap)]:
            if mask.sum() < 3:
                metrics.append({'subset': subset, 'rows': int(mask.sum()), 'status': 'insufficient'})
                continue
            rho = []
            for j in range(yy.shape[1]):
                if np.std(pred[mask, j]) == 0 or np.std(yy[mask, j]) == 0:
                    rho.append(None)
                else:
                    rho.append(float(spearmanr(pred[mask, j], yy[mask, j]).statistic))
            metrics.append({'subset': subset, 'rows': int(mask.sum()),
                            'rmse_per_domain': np.sqrt(np.mean((pred[mask]-yy[mask])**2, axis=0)).tolist(),
                            'spearman_per_domain': rho})
        results.append({'scale': scale, 'overlapping_recipes': int(overlap.sum()), 'metrics': metrics,
                        'interpretation': 'same-scale prediction' if scale == '1m' else 'UNCALIBRATED scale transfer; prioritize rankings, do not interpret raw RMSE as calibrated loss fit', **meta})
    return {'training': source, 'domains': pc, 'targets': yc, 'selected': {'mode': mode, 'lambda': lam, 'epsilon': eps, 'inner_mse': mse},
            'validation': results, 'scope': 'linear/CLR ridge baseline, NOT a RegMix LightGBM reproduction; no Q or estimated 10B/70B evidence'}


def dem_arcs(args):
    import rasterio
    source = fingerprint(args.dem)
    config = json.loads(Path(args.nodes).read_text(encoding='utf-8'))
    nodes = config['nodes']
    if len({n['id'] for n in nodes}) != len(nodes):
        raise ValueError('duplicate node ids')
    with rasterio.open(args.dem) as ds:
        if not ds.crs or not ds.crs.is_projected or abs(ds.crs.linear_units_factor[1]-1) > 1e-9:
            raise ValueError('this prototype requires a projected metre CRS; geographic/other units must not be silently treated as metres')
        dem = ds.read(1, masked=True).astype(float).filled(np.nan)
        inv = ~ds.transform
        pixel, ground, work = {}, {}, {}
        for n in nodes:
            if not np.isfinite(n['work_height_m']) or n['work_height_m'] < 0:
                raise ValueError('invalid work height')
            pixel[n['id']] = inv*(n['x'], n['y'])
            ground[n['id']] = terrain_max(dem, pixel[n['id']], pixel[n['id']])
            work[n['id']] = ground[n['id']]+n['work_height_m']
        arcs = []
        for a in nodes:
            for b in nodes:
                if a['id'] == b['id']:
                    continue
                peak = terrain_max(dem, pixel[a['id']], pixel[b['id']])
                cruise = peak+50
                if max(work[a['id']], work[b['id']]) > cruise:
                    raise ValueError('work altitude exceeds cruise convention; inspect normalized inputs')
                arcs.append({'from': a['id'], 'to': b['id'],
                             'distance_km': float(np.hypot(a['x']-b['x'], a['y']-b['y'])/1000),
                             'terrain_max_m': peak, 'cruise_asl_m': cruise,
                             'climb_m': cruise-work[a['id']], 'descent_m': cruise-work[b['id']]})
        return {'source': source, 'nodes_source': fingerprint(args.nodes), 'crs': str(ds.crs),
                'ground_from_raster': ground, 'arcs': arcs,
                'scope': 'all directed straight raster-cell arcs, not routes or a continuous-radio solution'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    f = sub.add_parser('f-scaling')
    f.add_argument('--repo', default='.')
    f.add_argument('--starts', type=int, default=6)
    f.add_argument('--bootstrap', type=int, default=0)
    f.add_argument('--seed', type=int, default=20260923)
    f.add_argument('--out', required=True)
    m = sub.add_parser('f-mixtures')
    m.add_argument('--repo', default='.')
    m.add_argument('--seed', type=int, default=20260923)
    m.add_argument('--out', required=True)
    d = sub.add_parser('d-arcs')
    d.add_argument('--dem', required=True)
    d.add_argument('--nodes', required=True)
    d.add_argument('--out', required=True)
    v = sub.add_parser('d-resources')
    v.add_argument('--input', required=True)
    v.add_argument('--out', required=True)
    args = p.parse_args()
    if args.command == 'f-scaling':
        if args.bootstrap < 0 or args.starts < 1:
            p.error('bootstrap >= 0 and starts >= 1 required')
        result = scaling(args)
    elif args.command == 'f-mixtures':
        result = mixtures(args)
    elif args.command == 'd-arcs':
        result = dem_arcs(args)
    else:
        raw = json.loads(Path(args.input).read_text(encoding='utf-8'))
        result = validate_resources(raw['tasks'], raw['capacities'])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(out)


if __name__ == '__main__':
    main()
