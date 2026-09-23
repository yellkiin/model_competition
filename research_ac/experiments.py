"""Reproducible synthetic counterexamples, NOT official contest scores or real EEG.
Run from the repository root: python research_ac/experiments.py --out <new.json>
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import platform
from collections import OrderedDict
import numpy as np
import scipy
import sklearn
from sklearn.metrics import balanced_accuracy_score
from a_search import graph_view, candidates, validate_plan, boundary_bytes
from c_pipeline import spatial_projection, fit_predict
from c_models import fir_design, fit_fir, first_passage, ei_basis, fit_ei


def random_graph(seed: int, n: int = 16) -> dict:
    rng = np.random.default_rng(seed)
    graph = dict(ops=[dict(id=i, op="COMPUTE", pipe="PIPE_M" if i % 2 else "PIPE_V",
                          cycles=int(rng.integers(10, 100))) for i in range(n)], tensors=[], edges=[])
    for u in range(n - 1):
        children = [v for v in range(u + 1, n) if rng.random() < .12]
        if children:
            tid = 10000 + u
            graph["tensors"].append(dict(id=tid, pos="UB", size=int(rng.integers(1, 100)) * 1024))
            graph["edges"].append(dict(source=u, target=tid))
            graph["edges"].extend(dict(source=tid, target=v) for v in children)
    return graph


def fifo_hits(trace, capacity: int, lru: bool = False) -> int:
    resident, hits = OrderedDict(), 0
    for item in trace:
        if item in resident:
            hits += 1
            if lru:
                resident.move_to_end(item)
        else:
            if len(resident) == capacity:
                resident.popitem(last=False)
            resident[item] = None
    return hits


def scheduling_checks() -> dict:
    checked = 0
    for seed in range(20):
        view = graph_view(random_graph(seed))
        for cores in (1, 2, 3, 4, 5):
            for problem in (1, 2, 3):
                for index, plan in enumerate(candidates(view, cores, problem, 60., seed)):
                    if index >= 12:
                        break
                    validate_plan(view, plan)
                    checked += 1
    graph = dict(ops=[dict(id=i, op="COMPUTE", pipe="PIPE_V", cycles=1) for i in range(4)],
                 tensors=[dict(id=100, size=1024, pos="UB")],
                 edges=[dict(source=0, target=100)] + [dict(source=100, target=i) for i in (1, 2, 3)])
    view = graph_view(graph)
    same_remote_task = boundary_bytes(view, {0: 0, 1: 1, 2: 1, 3: 1})
    separate_remote_tasks = boundary_bytes(view, {0: 0, 1: 1, 2: 2, 3: 3})
    return dict(data_kind="synthetic_structural_tests_not_official_simulation", checked_plans=checked,
                fanout_same_remote_task_proxy_bytes=same_remote_task,
                fanout_three_remote_tasks_proxy_bytes=separate_remote_tasks,
                naive_per_edge_read_write_bytes=3 * 2 * 1024,
                fifo_trace=["A", "B", "A", "C", "A"], fifo_hits=fifo_hits("ABACA", 2),
                lru_hits=fifo_hits("ABACA", 2, True),
                warning="Coverage/quotient/core-order tests do NOT establish Step3/Pipe/COPY execution validity")


def overlap_experiment(seed: int, trials: int = 160) -> dict:
    rng, fs = np.random.default_rng(seed), 100
    cue = np.tile([-1, 1], trials // 2)
    rng.shuffle(cue)
    onsets = np.cumsum(rng.integers(120, 170, trials)).astype(int)
    rt = np.clip(np.where(cue == -1, .35, .65) + rng.normal(0, .07, trials), .2, .85)
    responses = onsets + np.rint(rt * fs).astype(int)
    n = int(responses[-1] + 120)
    events = {"left": (onsets[cue == -1], np.ones(sum(cue == -1))),
              "right": (onsets[cue == 1], np.ones(sum(cue == 1))),
              "response": (responses, np.ones(trials))}
    lags = {"left": (0, 80), "right": (0, 80), "response": (-30, 30)}
    x, layout = fir_design(n, events, lags)
    t, r = np.arange(81) / fs, np.arange(-30, 31) / fs
    stimulus = (-np.exp(-.5 * ((t - .15) / .03) ** 2) + .7 * np.exp(-.5 * ((t - .32) / .07) ** 2))[:, None] * np.array([[1., .8, .6]])
    motor = 1.5 * np.exp(-.5 * ((r + .03) / .07) ** 2)[:, None] * np.array([[.8, 1., .7]])
    beta = np.vstack([stimulus, stimulus, motor, [[.1, .2, .1]], [[.05, -.05, .03]]])
    eeg = x @ beta + rng.normal(0, .2, (n, 3))
    split, guard = int(.7 * n), 100
    train, test = np.arange(n) < split - guard, np.arange(n) > split + guard
    fitted, _ = fit_fir(x, eeg, alpha=.1, train_mask=train)
    # Naive averages use ONLY training trials, just as deconvolution does.
    means = []
    for direction in (-1, 1):
        use = onsets[(cue == direction) & (onsets + 80 < split - guard)]
        means.append(np.stack([eeg[o:o + 81] for o in use]).mean(axis=0))
    a, b = layout["left"], layout["right"]
    left, right = fitted[slice(*a)], fitted[slice(*b)]
    return dict(seed=seed, true_stimulus_difference_rms=0.,
                naive_false_difference_rms=float(np.sqrt(np.mean((means[0] - means[1]) ** 2))),
                deconvolved_false_difference_rms=float(np.sqrt(np.mean((left - right) ** 2))),
                naive_stimulus_rmse=float(np.sqrt(np.mean((np.stack(means) - stimulus) ** 2))),
                deconvolved_stimulus_rmse=float(np.sqrt(np.mean((np.stack([left, right]) - stimulus) ** 2))),
                heldout_continuous_mse=float(np.mean((x[test] @ fitted - eeg[test]) ** 2)))


def rank_experiment(seed: int) -> dict:
    rng = np.random.default_rng(seed)
    ntrain, ntest, nt = 400, 200, 80
    times = np.linspace(-.2, .6, nt, endpoint=False)
    y = np.tile([-1, 1], (ntrain + ntest) // 2)
    rng.shuffle(y)
    common = np.exp(-.5 * ((times - .2) / .06) ** 2)
    discriminative = np.exp(-.5 * ((times - .38) / .06) ** 2)
    clean = np.zeros((len(y), 3, nt))
    clean[:, 0] = rng.normal(0, 5., len(y))[:, None] * common
    clean[:, 1] = .4 * y[:, None] * discriminative
    observed = clean + rng.normal(0, .6, clean.shape)
    out = {"seed": seed}
    for method in ("none", "pca1", "dss1", "dss2"):
        pred, _ = fit_predict(observed[:ntrain], y[:ntrain], observed[ntrain:], method, 20)
        p = spatial_projection(observed[:ntrain], y[:ntrain], method)
        estimate = np.einsum("cd,ndt->nct", p, observed[ntrain:])
        out[method] = dict(balanced_accuracy=float(balanced_accuracy_score(y[ntrain:], pred)),
                           reconstruction_mse=float(np.mean((estimate - clean[ntrain:]) ** 2)))
    return out


def diffusion_checks() -> dict:
    null = first_passage(0., horizon=4.)
    biased = first_passage(1., horizon=4.)
    fine = first_passage(1., horizon=4., dt=.0025, n=161)
    analytic_eventual_upper = 1 / (1 + np.exp(-2.))
    return dict(null_upper_mass=float(null["upper"].sum()), null_lower_mass=float(null["lower"].sum()),
                null_survival=float(null["survival"][-1]),
                mass_error=float(abs(null["upper"].sum() + null["lower"].sum() + null["survival"][-1] - 1)),
                biased_upper_mass=float(biased["upper"].sum()), fine_upper_mass=float(fine["upper"].sum()),
                analytic_eventual_upper=float(analytic_eventual_upper),
                finite_horizon_caveat="Mass at t<=4 is not exactly eventual hitting probability; see survival",
                biased_survival=float(biased["survival"][-1]), fine_survival=float(fine["survival"][-1]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    result = dict(data_kind="synthetic_only", seed_set=list(range(10)),
                  environment=dict(python=platform.python_version(), numpy=np.__version__,
                                   scipy=scipy.__version__, sklearn=sklearn.__version__),
                  source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sorted(Path(__file__).parent.glob("*.py"))},
                  A=scheduling_checks(), overlap=[overlap_experiment(s) for s in range(10)],
                  rank=[rank_experiment(s) for s in range(10)], diffusion=diffusion_checks())
    times = np.linspace(0, .8, 100)
    basis = ei_basis(times, .06, .10, 1.2)
    h = np.array([[1., .8, .6], [-.3, -.1, .2]])
    response = basis @ h
    equivalent = ei_basis(times, .05, .15, 1.75)
    equivalent_h = np.vstack([h[0] * (.05 / .06), (h[0] + h[1]) * (.05 * .15 / (.06 * .10)) - h[0] * (.05 / .06)])
    result["EI"] = dict(distinct_parameters_same_response_max_error=float(np.max(np.abs(equivalent @ equivalent_h - response))),
                        exact_equivalent_parameters=[[.06, .10, 1.2], [.05, .15, 1.75]],
                        scale_invariance_error=float(np.max(np.abs((basis * 2) @ (h / 2) - response))),
                        synthetic_multistart_solutions=fit_ei(times, response, starts=3, seed=0),
                        warning="Near-perfect fit need not recover a unique E-I parameter vector")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
