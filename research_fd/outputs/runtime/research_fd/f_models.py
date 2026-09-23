"""F research kernels. N and D are in billions; budgets are actual FLOPs.
References and limitations are in REPORT_F.md. No coefficients are universal.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import numpy as np
from scipy.optimize import least_squares, differential_evolution


@dataclass(frozen=True)
class Law:
    E: float = 1.5
    A: float = 0.7
    B: float = 1.2
    alpha: float = 0.35
    beta: float = 0.28

    def __post_init__(self):
        v = np.array(list(asdict(self).values()))
        if not np.isfinite(v).all() or self.E < 0 or np.any(v[1:] <= 0):
            raise ValueError("E >= 0; A, B, alpha, beta must be positive and finite")

    def loss(self, n, d):
        n, d = np.broadcast_arrays(np.asarray(n, float), np.asarray(d, float))
        if np.any(n <= 0) or np.any(d <= 0) or not np.isfinite(n + d).all():
            raise ValueError("positive finite N_B, D_B required")
        return self.E + self.A * n ** -self.alpha + self.B * d ** -self.beta


def fit_law(n, d, y, seed=0, starts=6):
    """Multi-start robust NLS; diagnostic condition number is coordinate dependent."""
    n, d, y = [np.asarray(a, float) for a in (n, d, y)]
    if any(a.ndim != 1 for a in (n, d, y)) or not (len(n) == len(d) == len(y)):
        raise ValueError("equal-length one-dimensional arrays required")
    if len(y) < 12 or not np.isfinite(n + d + y).all() or np.any(np.minimum(n, d) <= 0) or np.any(y <= 0):
        raise ValueError("at least 12 positive finite observations required")
    if len(np.unique(n)) < 3 or len(np.unique(d)) < 3:
        raise ValueError("N-D law is not identifiable from fewer than 3 distinct N or D values")
    if starts < 1:
        raise ValueError("starts must be positive")
    def decode(x):
        return Law(float(x[0]), *np.exp(x[1:]).tolist())
    lo = np.array([0, -15, -15, np.log(.01), np.log(.01)])
    hi = np.array([min(y) * .999, 15, 15, np.log(2), np.log(2)])
    rng = np.random.default_rng(seed)
    candidates = []
    for _ in range(starts):
        x = np.array([min(y)*rng.uniform(.2, .8), np.log(rng.uniform(.2, 3)),
                      np.log(rng.uniform(.2, 3)), np.log(rng.uniform(.15, .7)),
                      np.log(rng.uniform(.15, .7))])
        r = least_squares(lambda z: decode(z).loss(n, d) - y, x, bounds=(lo, hi),
                          loss="soft_l1", f_scale=.02, max_nfev=2500)
        if r.success and np.isfinite(r.cost):
            candidates.append(r)
    if not candidates:
        raise RuntimeError("all nonlinear fits failed to converge")
    best = min(candidates, key=lambda r: r.cost)
    sv = np.linalg.svd(best.jac, compute_uv=False)
    law = decode(best.x)
    return law, {"rmse": float(np.sqrt(np.mean((law.loss(n, d)-y)**2))),
                 "condition_number": float(sv[0]/max(sv[-1], 1e-300)),
                 "near_bound": bool(np.any(np.minimum(best.x-lo, hi-best.x) < 1e-4)),
                 "successful_starts": len(candidates), "n_rows": len(y),
                 "n_sizes": len(np.unique(n)), "params": asdict(law)}


def effective_tokens(d, unique, r_star=15.0):
    """Muennighoff et al. (2023), Eq. 5: smooth saturation, NOT an overfit model."""
    d, unique = np.broadcast_arrays(np.asarray(d, float), np.asarray(unique, float))
    if not np.isfinite(d + unique).all() or np.any(d <= 0) or np.any(unique <= 0) or not np.isfinite(r_star) or r_star <= 0:
        raise ValueError("positive finite token counts and r_star required")
    u = np.minimum(d, unique)
    repeats = d/u - 1
    return u * (1 + r_star * (-np.expm1(-repeats/r_star)))


def analytic_optimum(law, budget, context=0):
    """Fixed Q=1, no quality overhead, no supply/bound constraints."""
    if budget <= 0 or context < 0 or not np.isfinite(budget + context):
        raise ValueError("invalid budget/context")
    k = 6 + 2e-4 * context
    product = budget/(k*1e18)
    n = (law.alpha*law.A/(law.beta*law.B)*product**law.beta)**(1/(law.alpha+law.beta))
    d = product/n
    return float(n), float(d)


def quality_cost(q, q0, scale, kind):
    if not (0 < q0 <= q <= 1) or not np.isfinite(scale) or scale < 0:
        raise ValueError("require 0 < q0 <= Q <= 1 and nonnegative finite scale")
    x = q - q0
    if kind == "exponential":
        return scale*np.expm1(4*x)
    if kind == "power":
        return scale*(q**3 - q0**3)
    if kind == "logarithmic":
        return scale*np.log1p(4*x)
    raise ValueError("unknown quality cost")


def optimize_budget(law, budget, context=4096, q0=.3, kappa=1.,
                    cost_scale=1e10, kind="exponential", unique0=None,
                    retention=0., r_star=15., n_bounds=(.05, 300.), seed=0):
    """Conditional scenario optimization, not a calibrated competition solution.
    cost_scale: FLOPs/token. unique0: billion unique tokens available at q0.
    Supply assumption: U(Q)=unique0*exp[-retention*(Q-q0)].
    """
    if budget <= 0 or context < 0 or not 0 < q0 < 1 or kappa < 0 or retention < 0:
        raise ValueError("invalid scenario")
    if not np.isfinite([budget, context, kappa, retention, *n_bounds]).all() or not 0 < n_bounds[0] < n_bounds[1]:
        raise ValueError("invalid numeric bounds")
    quality_cost(q0, q0, cost_scale, kind)
    if unique0 is not None and (unique0 <= 0 or not np.isfinite(unique0)):
        raise ValueError("unique0 must be positive")
    def evaluate(x):
        n, q = np.exp(x[0]), float(x[1])
        overhead = quality_cost(q, q0, cost_scale, kind)
        d = budget/(1e9*((6+2e-4*context)*n*1e9+overhead))
        u = None if unique0 is None else unique0*np.exp(-retention*(q-q0))
        de = d if u is None else effective_tokens(d, u, r_star)
        return float(law.loss(n, de*q**kappa)), n, d, q, overhead
    bounds = [(np.log(n_bounds[0]), np.log(n_bounds[1])), (q0, 1.)]
    sol = differential_evolution(lambda x: evaluate(x)[0], bounds, seed=seed,
                                  popsize=10, maxiter=120, tol=1e-8, polish=True)
    # Explicit edges avoid missing boundary optima of the conditional model.
    candidates = [sol.x, *[np.array([np.log(n), q]) for n in n_bounds for q in (q0, 1.)]]
    x = min(candidates, key=lambda z: evaluate(z)[0])
    loss, n, d, q, overhead = evaluate(x)
    spent = d*1e9*((6+2e-4*context)*n*1e9+overhead)
    return {"loss": loss, "N_B": float(n), "D_B": float(d), "Q": q,
            "budget": float(budget), "spent": float(spent),
            "quality_cost_share": float(d*1e9*overhead/budget),
            "boundary": bool(q < q0+1e-3 or q > .999 or n < n_bounds[0]*1.01 or n > n_bounds[1]*.99),
            "solver_success": bool(sol.success), "scenario_only": True}


def minimax_regret(loss_matrix):
    """Rows=candidate decisions, columns=plausible worlds; finite candidate set."""
    a = np.asarray(loss_matrix, float)
    if a.ndim != 2 or min(a.shape) == 0 or not np.isfinite(a).all():
        raise ValueError("finite nonempty decision x scenario matrix required")
    regret = a - a.min(axis=0, keepdims=True)
    worst = regret.max(axis=1)
    return int(np.argmin(worst)), worst


def mixture_features(p, mode="linear", epsilon=1e-4):
    """No silent row renormalization. Caller must log rounded-CSV normalization."""
    p = np.asarray(p, float)
    if p.ndim != 2 or p.shape[1] < 2 or not np.isfinite(p).all() or np.any(p < 0):
        raise ValueError("nonnegative finite recipe matrix required")
    if not np.allclose(p.sum(axis=1), 1, atol=1e-8, rtol=0):
        raise ValueError("recipe rows must sum to one")
    if mode == "linear":
        return p[:, :-1]  # reference-domain contrasts, including zeros
    if mode == "clr":
        if epsilon <= 0 or not np.isfinite(epsilon):
            raise ValueError("positive epsilon required")
        z = np.log(p+epsilon)
        return z-z.mean(axis=1, keepdims=True)
    raise ValueError("mode must be linear or clr")


def ridge_predict(train_p, train_y, test_p, mode="linear", lam=1e-3, epsilon=1e-4):
    x, z = [mixture_features(p, mode, epsilon) for p in (train_p, test_p)]
    y = np.asarray(train_y, float)
    if y.ndim != 2 or len(y) != len(x) or not np.isfinite(y).all() or lam <= 0 or not np.isfinite(lam):
        raise ValueError("invalid targets or ridge penalty")
    mu, scale = x.mean(axis=0), np.maximum(x.std(axis=0), 1e-8)
    xx, zz = (x-mu)/scale, (z-mu)/scale
    coef = np.linalg.solve(xx.T@xx + lam*np.eye(xx.shape[1]), xx.T@(y-y.mean(axis=0)))
    return zz@coef+y.mean(axis=0)
