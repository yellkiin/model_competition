"""Retrospective stimulus/button overlap model for one original C MAT record.

Negative button lags use known future response times: never call this an online
BCI predictor. No response timestamp is invented for a missing target marker.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi
from c_pipeline import load_record, pulse_onsets, event_table
from c_models import fir_design, fit_fir


def run(path: Path, out: Path, trust_channel_order: bool = False,
        alpha: float = 1., highpass: float = .5) -> dict:
    data, fs, audit = load_record(path, trust_channel_order)
    if not 0 < highpass < 30 < fs / 2 or alpha < 0:
        raise ValueError("Invalid filter or regularization settings")
    n = data.shape[1]
    onset = pulse_onsets(data[7], {-1, 1})
    clicks = pulse_onsets(data[8], {-2, 2})
    event = {}
    for name, times, values, sign in (("cue_left", onset, data[7], -1),
                                     ("cue_right", onset, data[7], 1),
                                     ("button_left", clicks, data[8], -2),
                                     ("button_right", clicks, data[8], 2)):
        selected = times[values[times] == sign]
        if not len(selected):
            raise ValueError(f"No events for {name}; redesign the model explicitly")
        event[name] = (selected, np.ones(len(selected)))
    lags = {name: (0, int(.8 * fs)) if name.startswith("cue")
            else (-int(.3 * fs), int(.3 * fs)) for name in event}
    design, layout = fir_design(n, event, lags)
    sos = butter(2, [highpass, 30.], btype="bandpass", fs=fs, output="sos")
    eeg = data[:3]
    filtered, _ = sosfilt(sos, eeg, axis=-1, zi=sosfilt_zi(sos)[:, None, :] * eeg[None, :, :1])
    filtered = filtered.T
    split, guard, warmup = int(.7 * n), int(np.ceil(.8 * fs)), int(np.ceil(5 * fs / highpass))
    indices = np.arange(n)
    train = (indices >= warmup) & (indices < split - guard)
    test = (indices >= split + guard) & (indices < n - guard)
    if train.sum() < 2 * design.shape[1] or test.sum() < fs:
        raise ValueError("Record too short for guarded deconvolution validation")
    # Fixed alpha is not tuned on the held-out block. Each event must appear in training.
    counts = {name: int(np.sum(train[times])) for name, (times, _) in event.items()}
    if min(counts.values()) < 5:
        raise ValueError(f"Fewer than five training events in a condition: {counts}")
    beta, solver = fit_fir(design, filtered, alpha, train)
    predicted = design @ beta
    mse = np.mean((filtered[test] - predicted[test]) ** 2, axis=0)
    reference = np.mean((filtered[test] - filtered[train].mean(axis=0)) ** 2, axis=0)
    if np.any(reference <= 0):
        raise ValueError("Zero-variance channel in held-out block")
    rows = event_table(data[7], data[8], fs)
    rt = np.array([r["rt_seconds"] for r in rows if r["rt_seconds"] is not None])
    report = dict(audit=audit, source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  scope="retrospective conditional EEG prediction, not online decoding",
                  observed_event_model="VisCue and button events only; target onset unavailable",
                  layout=layout, lags_samples=lags, train_event_counts=counts,
                  train_samples=int(train.sum()), test_samples=int(test.sum()), guard_samples=guard,
                  causal_filter=dict(highpass=highpass, lowpass=30., order=2, warmup_samples=warmup),
                  heldout_mse=mse.tolist(), heldout_r2=(1 - mse / reference).tolist(),
                  rt_std_seconds=float(np.std(rt)) if len(rt) else None, solver=solver,
                  warning="A good fit does not prove that stimulus and motor kernels are uniquely identifiable")
    out.mkdir(parents=True, exist_ok=False)
    np.savez_compressed(out / "kernels.npz", beta=beta, fs=fs)
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                               allow_nan=False), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--trust-channel-order", action="store_true")
    parser.add_argument("--alpha", type=float, default=1.)
    parser.add_argument("--highpass", type=float, default=.5)
    report = run(**vars(parser.parse_args()))
    print(json.dumps({k: report[k] for k in ("scope", "heldout_mse", "heldout_r2")}, indent=2))


if __name__ == "__main__":
    main()
