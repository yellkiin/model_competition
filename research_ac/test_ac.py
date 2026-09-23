"""Unit and integration tests on synthetic data and a clearly labelled mock CLI."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
import pytest
from scipy.io import savemat
from a_search import (graph_view, validate_plan, boundary_bytes, candidates,
                      run_cli, search, load_json, save_json)
from c_pipeline import (pulse_onsets, event_table, load_record, extract_epochs,
                        spatial_projection, nested_record_cv)
from c_models import (fir_design, fit_fir, first_passage, diffusion_nll,
                      ei_basis, fit_ei, fit_diffusion)
from c_deconvolve import run as run_deconvolve
from experiments import random_graph, overlap_experiment, rank_experiment, fifo_hits


def test_reject_duplicate_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"a": 1, "a": 2}')
    with pytest.raises(ValueError):
        load_json(path)


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_candidates_cover_and_order(seed):
    view = graph_view(random_graph(seed))
    for i, plan in enumerate(candidates(view, 4, 2, 60., seed)):
        if i == 20:
            break
        validate_plan(view, plan)
        assert len(plan["core_schedules"]) == 4


def test_quotient_cycle_rejected():
    graph = random_graph(1, 3)
    graph["tensors"] = []
    graph["edges"] = [dict(source=0, target=1), dict(source=1, target=2)]
    view = graph_view(graph)
    with pytest.raises(ValueError, match="cycle"):
        validate_plan(view, {"node_to_subgraph": {"0": 0, "1": 1, "2": 0}, "core_schedules": [[0], [1]]})


def test_copy_contraction():
    graph = random_graph(1, 3)
    graph["tensors"] = []
    graph["ops"][1]["op"] = "COPY_IN"
    graph["edges"] = [dict(source=0, target=1), dict(source=1, target=2)]
    view = graph_view(graph)
    assert view["pred"][2] == {0}
    assert 1 not in view["pred"]


def test_duplicate_id_rejected():
    graph = random_graph(1)
    graph["ops"][1]["id"] = 0
    with pytest.raises(ValueError):
        graph_view(graph)


def test_fifo_not_lru():
    assert fifo_hits("ABACA", 2) == 1
    assert fifo_hits("ABACA", 2, True) == 2


def test_fanout_deduplicated():
    graph = random_graph(1, 4)
    graph["tensors"] = [dict(id=100, size=1024, pos="UB")]
    graph["edges"] = [dict(source=0, target=100)] + [dict(source=100, target=i) for i in (1, 2, 3)]
    view = graph_view(graph)
    assert boundary_bytes(view, {0: 0, 1: 1, 2: 1, 3: 1}) == 2048
    assert boundary_bytes(view, {0: 0, 1: 1, 2: 2, 3: 3}) == 4096


def mock_code(tmp_path):
    code = tmp_path / "mock_code"
    code.mkdir()
    text = '''import argparse,json
p=argparse.ArgumentParser();p.add_argument('graph');p.add_argument('plan',nargs='?')
p.add_argument('--config');p.add_argument('-o');p.add_argument('--trace-output');p.add_argument('--log-output')
a=p.parse_args()
json.dump({'makespan': 1000 if a.plan is None else 600, 'data_movement_bytes': {'physical_ddr_bytes': 20}},open(a.o,'w'))
'''
    for name in ("singlecore_evaluate.py", "multicore_cut_evaluate_problem_1.py"):
        (code / name).write_text(text)
    graph, config = tmp_path / "graph.json", tmp_path / "config.txt"
    save_json(graph, random_graph(2))
    config.write_text('[bandwidth]\nbandwidth=60\n')
    return code, graph, config


def test_mock_official_adapter(tmp_path):
    code, graph, config = mock_code(tmp_path)
    result = search(graph, code, config, tmp_path / "out", budget=3, timeout=3)
    assert result["status"] == "ok"
    assert result["speedup"] == 1000 / 600  # MOCK ONLY, never a competition score
    assert len(result["trials"]) == 3
    assert (tmp_path / "out" / "best_plan.json").is_file()
    with pytest.raises(FileExistsError):
        search(graph, code, config, tmp_path / "out")


def test_cli_failure_and_timeout(tmp_path):
    code, graph, config = mock_code(tmp_path)
    script = code / "failure.py"
    script.write_text("raise SystemExit(2)\n")
    assert run_cli(script, graph, config, tmp_path / "failed", 3)["status"] == "error"
    script.write_text("import time;time.sleep(5)\n")
    assert run_cli(script, graph, config, tmp_path / "timeout", .05)["status"] == "timeout"


def test_run_events_not_samples():
    cue = np.array([0, 1, 1, 1, 0, -1, -1, 0, 1, 0])
    action = np.array([0, 0, 2, 2, -2, 0, 0, 0, 0, 0])
    rows = event_table(cue, action, 10)
    assert len(rows) == 3
    assert rows[0]["n_clicks"] == 2
    assert rows[0]["rt_seconds"] == .1
    assert rows[1]["censored"] is True
    assert rows[0]["correctness"] == "unknown_task_mapping"


def test_illegal_events():
    with pytest.raises(ValueError):
        pulse_onsets(np.array([0, .5, 1]), {-1, 1})


def synthetic_mat(path: Path, seed=0, seconds=96):
    rng, fs = np.random.default_rng(seed), 256
    n = seconds * fs
    data = rng.normal(0, .3, (10, n))
    data[7:9] = 0
    data[9] = np.arange(n) / fs
    onsets = np.arange(12 * fs, n - 2 * fs, 2 * fs, dtype=int)
    for i, o in enumerate(onsets):
        cue = -1 if i % 2 else 1
        data[7, o:o + 3] = cue
        rt = int(fs * (.4 if cue == -1 else .65)) + int(rng.integers(-15, 16))
        data[8, o + rt:o + rt + 2] = cue * 2
        t = np.arange(180) / fs
        waveform = np.exp(-.5 * ((t - .25) / .08) ** 2)
        data[:3, o:o + len(t)] += cue * waveform[None] * np.array([[.4], [.8], [-.4]])
    labels = np.array(["Fz", "F3", "F4", "Decon1", "Decon2", "Decon3", "ECG", "VisCue", "TgtAct", "TimeStamp"], dtype=object).reshape(-1, 1)
    savemat(path, {"data": data, "SampleRate": fs, "DataLabel": labels})
    return data


def test_mat_audit_and_no_machine_channels(tmp_path):
    path = tmp_path / "record.mat"
    original = synthetic_mat(path)
    data, fs, audit = load_record(path)
    assert audit["channel_labels_verified"]
    rows = event_table(data[7], data[8], fs)
    x, kept, settings = extract_epochs(data, fs, rows)
    changed = data.copy()
    changed[3:7] = 1e12
    xx, _, _ = extract_epochs(changed, fs, rows)
    np.testing.assert_array_equal(x, xx)
    assert settings["causal"] and len(kept) > 20


def test_causal_filter_future_invariance(tmp_path):
    path = tmp_path / "record.mat"
    data = synthetic_mat(path)
    rows = event_table(data[7], data[8], 256)
    x, kept, _ = extract_epochs(data, 256, rows)
    cutoff = kept[0]["onset"] + round(.6 * 256)
    data[:3, cutoff + 1:] += 10000
    changed, _, _ = extract_epochs(data, 256, rows)
    np.testing.assert_array_equal(x[0], changed[0])


def test_mat_cli_nested_end_to_end(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    for i in range(4):
        synthetic_mat(data / f"VisualCog{i}_Task-1.mat", i)
    out = tmp_path / "run"
    proc = subprocess.run([sys.executable, str(Path(__file__).with_name("c_pipeline.py")),
                           str(data), "--out", str(out)], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    result = json.loads((out / "cv.json").read_text())
    assert len(result["folds"]) == 4
    assert "not diagnosis" in result["scope"]
    assert (out / "events.csv").exists()


def test_deconvolution_mat_end_to_end(tmp_path):
    path = tmp_path / "record.mat"
    synthetic_mat(path)
    report = run_deconvolve(path, tmp_path / "deconv")
    assert len(report["heldout_r2"]) == 3
    assert report["scope"].startswith("retrospective")


def test_projection_identity_and_train_only():
    rng = np.random.default_rng(1)
    x = rng.normal(size=(20, 3, 50))
    y = np.tile([-1, 1], 10)
    np.testing.assert_allclose(spatial_projection(x, y, "dss3"), np.eye(3), atol=1e-10)
    np.testing.assert_allclose(spatial_projection(x, y, "pca3"), np.eye(3), atol=1e-10)
    # Test labels are not even an input to the fitted spatial transform.
    p = spatial_projection(x, y, "dss1")
    assert p.shape == (3, 3)


def test_fir_exact_recovery():
    onsets = np.array([10, 60, 110, 160])
    x, _ = fir_design(200, {"cue": (onsets, np.ones(4))}, {"cue": (0, 10)}, trend=False)
    beta = np.linspace(-1, 1, 11)
    fitted, _ = fit_fir(x, x @ beta, alpha=0)
    np.testing.assert_allclose(fitted[:, 0], beta, atol=1e-7)


def test_fixed_latency_is_rank_deficient():
    onsets = np.array([20, 100, 180])
    x, _ = fir_design(250, {"cue": (onsets, np.ones(3)), "response": (onsets + 10, np.ones(3))},
                       {"cue": (0, 30), "response": (0, 30)}, trend=False)
    assert np.linalg.matrix_rank(x.toarray()) < x.shape[1]


def test_overlap_counterexample():
    result = overlap_experiment(0, 80)
    assert result["deconvolved_false_difference_rms"] < result["naive_false_difference_rms"] / 3


def test_denoising_can_destroy_direction():
    result = rank_experiment(0)
    assert result["pca1"]["reconstruction_mse"] < result["none"]["reconstruction_mse"]
    assert result["pca1"]["balanced_accuracy"] < .65
    assert result["none"]["balanced_accuracy"] > .9


def test_diffusion_mass_symmetry_and_bias():
    null = first_passage(0.)
    np.testing.assert_allclose(null["upper"], null["lower"], atol=1e-12)
    total = np.cumsum(null["upper"] + null["lower"]) + null["survival"][1:]
    np.testing.assert_allclose(total, 1., atol=1e-10)
    biased = first_passage(1.)
    assert biased["upper"].sum() > biased["lower"].sum()
    assert np.all(np.diff(null["survival"]) <= 0)


def test_censored_likelihood_not_dropped():
    plain = diffusion_nll([.8], [1], [1], 1., 1.)
    extra = diffusion_nll([.8, 1.2], [1, 0], [1, 1], 1., 1.)
    assert extra > plain
    assert np.isinf(diffusion_nll([.1], [1], [1], 1., 1., nondecision=.2))


def test_invalid_ddm_and_ei_inputs():
    with pytest.raises(ValueError):
        first_passage(0., n=10)
    with pytest.raises(ValueError):
        ei_basis(np.array([0., .1]), -.1, .1, 1.)
    with pytest.raises(ValueError):
        fit_diffusion([.1], [1], [1], nondecision=.2)


def test_ei_structural_equivalence_not_just_scale():
    times = np.linspace(0, .8, 120)
    h = np.array([[1., .8, .6], [-.3, -.1, .2]])
    h2 = np.vstack([h[0] * (.05 / .06), (h[0] + h[1]) * 1.25 - h[0] * (.05 / .06)])
    original = ei_basis(times, .06, .10, 1.2) @ h
    equivalent = ei_basis(times, .05, .15, 1.75) @ h2
    np.testing.assert_allclose(original, equivalent, atol=1e-7)


def test_ei_fixed_parameter_fit():
    times = np.linspace(0, .8, 80)
    response = ei_basis(times, .06, .10, 1.2) @ np.array([[1., .8, .6], [-.3, -.1, .2]])
    result = fit_ei(times, response, starts=1, fixed_tau_i=.10)
    assert result[0]["fixed_tau_i"] == .10
    assert result[0]["mse"] < 1e-6


def test_baseline_cache_wrong_graph_rejected(tmp_path):
    code, graph, config = mock_code(tmp_path)
    with pytest.raises(ValueError, match="provenance"):
        search(graph, code, config, tmp_path / "bad_cache", baseline_cache={"graph_sha256": "wrong"})


def test_batch_mock_and_matched_cache_comparison(tmp_path):
    code, graph, config = mock_code(tmp_path)
    mock = (code / "multicore_cut_evaluate_problem_1.py").read_text()
    for problem in (2, 3):
        (code / f"multicore_cut_evaluate_problem_{problem}.py").write_text(mock)
    raw = tmp_path / "raw"
    raw.mkdir()
    graph.rename(raw / "graph.json")
    output = tmp_path / "batch"
    proc = subprocess.run([sys.executable, str(Path(__file__).with_name("a_batch.py")), str(raw),
                           "--code", str(code), "--config", str(config), "--out", str(output),
                           "--expected-count", "1", "--cores", "2", "--budget", "2"],
                          capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    summary = json.loads((output / "summary.json").read_text())
    assert len(summary) == 3 and all(row["complete"] for row in summary)
    assert summary[-1]["mean_same_plan_cache_speedup"] == 1.
    assert all(row["arithmetic_mean_speedup"] == 1000 / 600 for row in summary)


def test_lfs_pointers_not_mistaken_for_data(tmp_path):
    path = tmp_path / "pointer"
    path.write_text("version https://git-lfs.github.com/spec/v1\noid sha256:123\nsize 100\n")
    with pytest.raises(ValueError, match="LFS"):
        load_json(path)
    with pytest.raises(ValueError, match="LFS"):
        load_record(path)


def test_local_mutations_remain_structurally_legal():
    import random
    from a_search import mutate_plan
    view = graph_view(random_graph(5))
    plan = next(candidates(view, 4, 2, 60., 0))
    rng = random.Random(0)
    for _ in range(200):
        plan = mutate_plan(view, plan, rng)
        validate_plan(view, plan)
