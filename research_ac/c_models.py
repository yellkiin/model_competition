"""C research kernels: sparse FIR overlap correction, constrained E-I response,
and a mass-conserving absorbing diffusion likelihood (including no responses).
These are small, inspectable prototypes, not replacements for Unfold/PyDDM.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from scipy import sparse
from scipy.integrate import solve_ivp
from scipy.linalg import solve_banded
from scipy.optimize import minimize
from scipy.sparse.linalg import lsmr


def fir_design(n_samples: int, events: dict, lags: dict, trend: bool = True):
    """events[name]=(integer onsets, amplitudes); lags[name]=(start, stop), inclusive.

    Event kernels may have different supports, including negative response lags.
    Negative response lags are for retrospective explanation, NOT online features.
    """
    if n_samples < 1 or set(events) != set(lags):
        raise ValueError("Invalid design dimensions or event names")
    rr, cc, vv, layout = [], [], [], {}
    column = 0
    for name, (onsets, amplitudes) in events.items():
        onsets, amplitudes = np.asarray(onsets), np.asarray(amplitudes, dtype=float)
        if onsets.ndim != 1 or amplitudes.shape != onsets.shape or not np.isfinite(amplitudes).all():
            raise ValueError("Invalid event onsets/amplitudes")
        if not np.issubdtype(onsets.dtype, np.integer) or np.any(onsets < 0) or np.any(onsets >= n_samples):
            raise ValueError("Event onset outside record or not an integer")
        lo, hi = lags[name]
        if type(lo) is not int or type(hi) is not int or hi < lo:
            raise ValueError("Invalid FIR lag range")
        lag = np.arange(lo, hi + 1)
        rows = onsets[:, None] + lag[None, :]
        cols = np.broadcast_to(column + np.arange(len(lag)), rows.shape)
        vals = np.broadcast_to(amplitudes[:, None], rows.shape)
        valid = (rows >= 0) & (rows < n_samples)
        rr.extend(rows[valid].tolist())
        cc.extend(cols[valid].tolist())
        vv.extend(vals[valid].tolist())
        layout[name] = (column, column + len(lag))
        column += len(lag)
    if trend:
        for values in (np.ones(n_samples), np.linspace(-1, 1, n_samples)):
            rr.extend(range(n_samples))
            cc.extend([column] * n_samples)
            vv.extend(values.tolist())
            column += 1
    design = sparse.coo_matrix((vv, (rr, cc)), shape=(n_samples, column)).tocsr()
    return design, layout


def fit_fir(design, eeg: np.ndarray, alpha: float = 1., train_mask=None):
    eeg = np.asarray(eeg, dtype=float)
    if eeg.ndim == 1:
        eeg = eeg[:, None]
    if len(eeg) != design.shape[0] or not np.isfinite(eeg).all() or alpha < 0:
        raise ValueError("Invalid EEG or ridge strength")
    mask = np.ones(len(eeg), dtype=bool) if train_mask is None else np.asarray(train_mask, dtype=bool)
    if mask.shape != (len(eeg),) or not mask.any():
        raise ValueError("Empty or invalid training mask")
    fitted = [lsmr(design[mask], eeg[mask, ch], damp=np.sqrt(alpha), atol=1e-8,
                   btol=1e-8, maxiter=3000) for ch in range(eeg.shape[1])]
    if any(r[1] not in (0, 1, 2, 4, 5) for r in fitted):
        raise RuntimeError(f"FIR solver did not converge: {[r[1] for r in fitted]}")
    return np.stack([r[0] for r in fitted], axis=1), dict(
        solver="lsmr_ridge", alpha=alpha, iterations=[int(r[2]) for r in fitted],
        condition_estimates=[float(r[6]) for r in fitted],
        note="Solver estimates are not a proof of biological parameter identifiability")


def ei_basis(times: np.ndarray, tau_e: float, tau_i: float, inhibition: float,
             delay: float = 0.) -> np.ndarray:
    """Stable linearized E-I deviations with a fixed unit-scale visual pulse.

    State scale is fixed to remove the trivial H/z scaling ambiguity. E/I here
    are functional latent deviations, not measured neuronal firing rates.
    """
    times = np.asarray(times, dtype=float)
    if times.ndim != 1 or len(times) < 2 or times[0] < 0 or np.any(np.diff(times) <= 0):
        raise ValueError("Times must increase from a nonnegative origin")
    if min(tau_e, tau_i) <= 0 or inhibition < 0 or delay < 0:
        raise ValueError("Invalid E-I parameters")
    def derivative(t, state):
        e, i = state
        pulse = np.exp(-.5 * ((t - delay - .06) / .02) ** 2)
        return [(-e - inhibition * i + pulse) / tau_e, (e - i) / tau_i]
    result = solve_ivp(derivative, (0., float(times[-1])), [0., 0.], t_eval=times,
                       rtol=1e-7, atol=1e-9, max_step=.005)
    if not result.success:
        raise RuntimeError(result.message)
    return result.y.T


def fit_ei(times, response, starts: int = 4, seed: int = 0, fixed_tau_i: float | None = None):
    """Variable projection: optimize three dynamics parameters, solve H linearly.

    Multistart solutions are retained; fit quality does not establish uniqueness.
    Fixed input delay and scale reduce, but do not eliminate, nonidentifiability.
    """
    response = np.asarray(response, dtype=float)
    if response.ndim != 2 or response.shape != (len(times), 3) or starts < 1 or not np.isfinite(response).all():
        raise ValueError("Expected a finite (time, 3) ERP and positive start count")
    if fixed_tau_i is not None and not .01 <= fixed_tau_i <= .3:
        raise ValueError("fixed_tau_i must be within [.01, .3] seconds")
    rng, solutions = np.random.default_rng(seed), []
    def evaluate(theta):
        basis = ei_basis(times, theta[0], theta[1], theta[2])
        h = np.linalg.solve(basis.T @ basis + np.eye(2) * 1e-8, basis.T @ response)
        return float(np.mean((basis @ h - response) ** 2)), h, basis @ h
    for _ in range(starts):
        initial = [rng.uniform(.03, .12), rng.uniform(.03, .15), rng.uniform(.2, 2.)]
        if fixed_tau_i is not None:
            initial[1] = fixed_tau_i
        bounds = [(.01, .3), (fixed_tau_i, fixed_tau_i) if fixed_tau_i is not None else (.01, .3), (0., 4.)]
        solution = minimize(lambda p: evaluate(p)[0], initial, method="L-BFGS-B",
                            bounds=bounds, options={"maxiter":150})
        error, h, prediction = evaluate(solution.x)
        solutions.append(dict(parameters=solution.x.tolist(), mse=error,
                              observation_matrix=h.tolist(), converged=bool(solution.success),
                              fixed_tau_i=fixed_tau_i))
    solutions.sort(key=lambda s: s["mse"])
    return solutions


def first_passage(drift, boundary: float = 1., sigma: float = 1.,
                  dt: float = .005, horizon: float = 3., n: int = 81):
    """Implicit birth-death/upwind finite-volume approximation with absorbing ends.

    Returned upper/lower arrays contain probability MASS per time bin, not density.
    survival[0]=1 and cumulative absorbed mass + survival = 1 to roundoff.
    Upwind adds numerical diffusion: use grid refinement before interpreting fits.
    """
    if min(boundary, sigma, dt, horizon) <= 0 or n < 3 or n % 2 != 1:
        raise ValueError("Positive physical scales and odd n>=3 are required")
    steps = int(np.ceil(horizon / dt))
    dx = 2 * boundary / (n + 1)
    base = sigma ** 2 / (2 * dx ** 2)
    p = np.zeros(n)
    p[n // 2] = 1.
    upper, lower, survival = np.zeros(steps), np.zeros(steps), np.ones(steps + 1)
    for k in range(steps):
        v = float(drift((k + .5) * dt) if callable(drift) else drift)
        if not np.isfinite(v):
            raise ValueError("Nonfinite drift")
        plus, minus = base + max(v, 0.) / dx, base + max(-v, 0.) / dx
        band = np.zeros((3, n))
        band[0, 1:] = -dt * minus
        band[1] = 1 + dt * (plus + minus)
        band[2, :-1] = -dt * plus
        p = solve_banded((1, 1), band, p, check_finite=False)
        lower[k], upper[k] = dt * minus * p[0], dt * plus * p[-1]
        survival[k + 1] = p.sum()
    if np.min(p) < -1e-10 or abs(upper.sum() + lower.sum() + survival[-1] - 1) > 1e-8:
        raise RuntimeError("Diffusion mass conservation failed")
    return dict(upper=upper, lower=lower, survival=survival, dt=dt,
                times=np.arange(steps + 1) * dt)


def diffusion_nll(times, choices, cues, drift: float, boundary: float,
                  memory_gain: float = 0., memory_tau: float = .3,
                  nondecision: float = 0., dt: float = .01, n: int = 61):
    """choice +/-1 = observed boundary, 0 = right-censored at the given time.

    A cue-to-click fit is only a descriptive surrogate unless target onset and
    nondecision time are independently identified. sigma=1 fixes diffusion scale.
    """
    times, choices, cues = np.asarray(times), np.asarray(choices), np.asarray(cues)
    if times.ndim != 1 or times.shape != choices.shape or times.shape != cues.shape or not len(times):
        raise ValueError("Invalid behavioral arrays")
    if not np.isfinite(times).all() or np.any(times <= 0) or not set(np.unique(choices)) <= {-1, 0, 1} or not set(np.unique(cues)) <= {-1, 1}:
        raise ValueError("Invalid times, choices or cues")
    if memory_tau <= 0 or nondecision < 0:
        raise ValueError("Invalid fixed memory/nondecision settings")
    corrected = times - nondecision
    if np.any((corrected <= 0) & (choices != 0)):
        return float("inf")
    loss = 0.
    for cue in np.unique(cues):
        selected = cues == cue
        solution = first_passage(lambda t: cue * (drift + memory_gain * np.exp(-t / memory_tau)),
                                 boundary, dt=dt, horizon=max(float(corrected.max()) + dt, dt), n=n)
        for t, choice in zip(corrected[selected], choices[selected]):
            if choice == 0:
                probability = 1. if t <= 0 else np.interp(t, solution["times"], solution["survival"])
            else:
                index = min(int(t / dt), len(solution["upper"]) - 1)
                probability = solution["upper" if choice == 1 else "lower"][index] / dt
            loss -= np.log(max(float(probability), 1e-300))
    return float(loss)


def fit_diffusion(times, choices, cues, memory: bool = False,
                  memory_tau: float = .3, nondecision: float = 0.):
    def objective(theta):
        return diffusion_nll(times, choices, cues, theta[0], theta[1],
                             theta[2] if memory else 0., memory_tau, nondecision)
    initial = [1., 1.] + ([0.] if memory else [])
    if not np.isfinite(objective(initial)):
        raise ValueError("Observed response occurs at/before the fixed nondecision time")
    bounds = [(-4., 4.), (.2, 2.5)] + ([(-5., 5.)] if memory else [])
    result = minimize(objective, initial, method="L-BFGS-B", bounds=bounds,
                      options={"maxiter":80})
    return dict(parameters=result.x.tolist(), nll=float(result.fun),
                aic=float(2 * len(initial) + 2 * result.fun), converged=bool(result.success),
                memory_tau_fixed=memory_tau, nondecision_fixed=nondecision,
                sigma_fixed=1., note="In-sample fit only; blocked held-out likelihood still required")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fit descriptive diffusion models to an explicit behavioral CSV")
    parser.add_argument("csv", type=Path, help="Columns time (seconds), choice (-1/0/+1), cue (-1/+1); 0 means censored")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--memory-tau", type=float, default=.3)
    parser.add_argument("--nondecision", type=float, default=0.)
    args = parser.parse_args()
    with args.csv.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    times = np.array([float(r["time"]) for r in rows])
    choices = np.array([int(r["choice"]) for r in rows])
    cues = np.array([int(r["cue"]) for r in rows])
    result = {name: fit_diffusion(times, choices, cues, memory, args.memory_tau, args.nondecision)
              for name, memory in (("no_memory", False), ("decaying_drive", True))}
    if args.out.exists():
        raise FileExistsError(args.out)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
