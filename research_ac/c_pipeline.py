"""C: MAT-v5 audit, pulse/run event extraction and nested leave-record-out EEG baseline.

Only raw rows Fz/F3/F4 enter the model. Fixed causal filtering never uses future
samples. The score concerns cue direction, NOT disease diagnosis or source location.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from scipy.io import loadmat
from scipy.linalg import eigh
from scipy.signal import butter, sosfilt, sosfilt_zi
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import balanced_accuracy_score, f1_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def pulse_onsets(values: np.ndarray, allowed: set[int]) -> np.ndarray:
    values = np.asarray(values).reshape(-1)
    if not np.isfinite(values).all() or not set(np.unique(values)).issubset(allowed | {0}):
        raise ValueError("Unexpected or nonfinite event code")
    previous = np.r_[0, values[:-1]]
    return np.flatnonzero((values != 0) & (values != previous))


def event_table(cue: np.ndarray, action: np.ndarray, fs: float,
                timeout: float | None = None) -> list[dict]:
    if len(cue) != len(action) or fs <= 0 or (timeout is not None and timeout <= 0):
        raise ValueError("Invalid event arrays, sampling rate or timeout")
    starts, clicks = pulse_onsets(cue, {-1, 1}), pulse_onsets(action, {-2, 2})
    rows = []
    for index, onset in enumerate(starts):
        stop = int(starts[index + 1]) if index + 1 < len(starts) else len(cue)
        if timeout is not None:
            stop = min(stop, int(onset + timeout * fs))
        found = clicks[(clicks >= onset) & (clicks < stop)]
        first = int(found[0]) if len(found) else None
        rows.append(dict(trial=index, onset=int(onset), stop=stop,
                         cue=int(cue[onset]), response=first,
                         action=int(action[first]) if first is not None else None,
                         rt_seconds=(first - onset) / fs if first is not None else None,
                         observation_seconds=(stop - onset) / fs,
                         n_clicks=len(found), censored=first is None,
                         correctness="unknown_task_mapping"))
    return rows


def _label(value) -> str:
    while isinstance(value, np.ndarray) and value.size == 1:
        value = value.item()
    if isinstance(value, np.ndarray):
        return "".join(str(v) for v in value.ravel()).strip()
    return str(value).strip()


def load_record(path: Path, trust_channel_order: bool = False):
    """MAT-v5 only; explicit failure rather than silently misreading MAT-v7.3."""
    with path.open("rb") as stream:
        if stream.read(128).startswith(b"version https://git-lfs.github.com/spec/v1"):
            raise ValueError("Git LFS pointer, not MAT data; run git lfs pull")
    raw = loadmat(path)
    data = np.asarray(raw["data"], dtype=float)
    if data.ndim != 2:
        raise ValueError("data must be a 2D matrix")
    if data.shape[0] != 10 and data.shape[1] == 10:
        data = data.T
    if data.shape[0] != 10 or not np.isfinite(data[[0, 1, 2, 7, 8, 9]]).all():
        raise ValueError("Expected ten rows and finite raw EEG/events/timestamps")
    rate = np.asarray(raw["SampleRate"]).reshape(-1)
    if rate.size != 1 or not np.isfinite(rate[0]) or rate[0] <= 0:
        raise ValueError("Invalid SampleRate")
    fs = float(rate[0])
    labels = [_label(x) for x in np.asarray(raw.get("DataLabel", [])).ravel()]
    verified = [s.lower() for s in labels[:3]] == ["fz", "f3", "f4"]
    if not verified and not trust_channel_order:
        raise ValueError("Fz/F3/F4 row order not confirmed; inspect DataLabel then explicitly use --trust-channel-order")
    step = np.diff(data[9])
    if not len(step) or np.any(step <= 0):
        raise ValueError("Non-increasing timestamps: split/repair the record explicitly first")
    median_step = float(np.median(step))
    gaps = np.flatnonzero(step > 1.5 * median_step)
    if len(gaps):
        raise ValueError(f"Timestamp gaps at {gaps[:8].tolist()}; split the record before filtering")
    audit = dict(file=path.name, shape=list(data.shape), fs=fs, labels=labels,
                 raw_rows_used=[0, 1, 2], machine_decon_rows_used=False,
                 channel_labels_verified=verified, timestamp_median_step=median_step,
                 timestamp_unit="unverified", amplitude_unit="unverified",
                 subject_identity="unverified_record_group",
                 timestamp_step_relative_max_deviation=float(np.max(np.abs(step / median_step - 1))))
    return data, fs, audit


def extract_epochs(data: np.ndarray, fs: float, rows: list[dict],
                   window: float = .6, highpass: float = .5):
    if not 0 < highpass < 30 < fs / 2 or window <= 0:
        raise ValueError("Invalid sampling rate, bandpass or analysis window")
    sos = butter(2, [highpass, 30], btype="bandpass", fs=fs, output="sos")
    eeg = data[:3]
    zi = sosfilt_zi(sos)[:, None, :] * eeg[None, :, :1]
    filtered, _ = sosfilt(sos, eeg, axis=-1, zi=zi)
    # Explicit conservative startup guard, not a claim of perfect settling.
    warmup = int(np.ceil(5 * fs / highpass))
    before, after = int(round(.2 * fs)), int(round(window * fs))
    kept, epochs = [], []
    for row in rows:
        onset = row["onset"]
        if onset - before < warmup or onset + after >= data.shape[1]:
            continue
        # Do not include a subsequent cue in the same feature window.
        if onset + after >= row["stop"]:
            continue
        epoch = filtered[:, onset - before:onset + after].copy()
        epoch -= epoch[:, :before].mean(axis=1, keepdims=True)
        epochs.append(epoch)
        kept.append({**row, "response_inside_window": row["response"] is not None and row["response"] < onset + after})
    if not epochs:
        raise ValueError("No epochs remain after boundary/startup guards")
    return np.stack(epochs), kept, dict(causal=True, highpass=highpass, lowpass=30.,
                                       butter_order=2, warmup_samples=warmup,
                                       baseline_samples=before, window_seconds=window)


def spatial_projection(x: np.ndarray, labels: np.ndarray, method: str) -> np.ndarray:
    """Training-only PCA or ERP-biased generalized-eigen projection (DSS-inspired).

    This small spatial baseline is not a full implementation of DSS or xDAWN.
    Three raw channels limit the attainable spatial rank to three.
    """
    if x.ndim != 3 or x.shape[1] != 3 or not np.isfinite(x).all():
        raise ValueError("Expected finite (trials, 3, time) data")
    if method == "none":
        return np.eye(3)
    rank = int(method[-1])
    if rank not in (1, 2, 3):
        raise ValueError("Invalid spatial rank")
    total = np.einsum("nct,ndt->cd", x, x) / (x.shape[0] * x.shape[2])
    if method.startswith("pca"):
        _, vectors = eigh(total)
        w = vectors[:, -rank:]
        return w @ w.T
    if not method.startswith("dss") or len(labels) != len(x):
        raise ValueError("Invalid projection method or labels")
    means = np.stack([x[labels == c].mean(axis=0) for c in np.unique(labels)])
    signal = np.einsum("nct,ndt->cd", means, means) / (len(means) * x.shape[2])
    regular = total + np.eye(3) * max(np.trace(total) * 1e-6, 1e-12)
    _, vectors = eigh(signal, regular)
    w = vectors[:, -rank:]
    patterns = regular @ w @ np.linalg.inv(w.T @ regular @ w)
    return patterns @ w.T


def features(x: np.ndarray, baseline_samples: int) -> np.ndarray:
    # Ten fixed bins of post-cue means, no time-window search on test labels.
    if x.shape[-1] - baseline_samples < 10:
        raise ValueError("Analysis window too short for ten bins")
    bins = np.array_split(np.arange(baseline_samples, x.shape[-1]), 10)
    return np.stack([x[:, :, b].mean(axis=-1) for b in bins], axis=-1).reshape(len(x), -1)


def fit_predict(xtrain, ytrain, xtest, method, baseline_samples):
    if len(np.unique(ytrain)) != 2:
        raise ValueError("Training fold must contain both directions")
    projection = spatial_projection(xtrain, ytrain, method)
    train = features(np.einsum("cd,ndt->nct", projection, xtrain), baseline_samples)
    test = features(np.einsum("cd,ndt->nct", projection, xtest), baseline_samples)
    model = make_pipeline(StandardScaler(), LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto"))
    model.fit(train, ytrain)
    positive = list(model.classes_).index(1)
    return model.predict(test), model.predict_proba(test)[:, positive]


def nested_record_cv(x, y, groups, baseline_samples):
    unique = np.unique(groups)
    if len(unique) < 3:
        raise ValueError("Nested leave-record-out requires at least three records")
    methods = ("none", "pca1", "dss1", "dss2")
    folds, prediction_rows = [], []
    for held in unique:
        train, test = groups != held, groups == held
        scores = {}
        for method in methods:
            inner = []
            for val in unique[unique != held]:
                fit, valid = train & (groups != val), groups == val
                if len(np.unique(y[fit])) != 2 or len(np.unique(y[valid])) != 2:
                    raise ValueError("An inner fold is missing a direction; redesign splits explicitly")
                predicted, _ = fit_predict(x[fit], y[fit], x[valid], method, baseline_samples)
                inner.append(balanced_accuracy_score(y[valid], predicted))
            scores[method] = float(np.mean(inner))
        selected = max(methods, key=lambda m: scores[m])
        predicted, probability = fit_predict(x[train], y[train], x[test], selected, baseline_samples)
        baseline, _ = fit_predict(x[train], y[train], x[test], "none", baseline_samples)
        metrics = dict(record=str(held), n_train=int(train.sum()), n_test=int(test.sum()),
                       selected=selected, inner_scores=scores,
                       balanced_accuracy=float(balanced_accuracy_score(y[test], predicted)),
                       unprojected_balanced_accuracy=float(balanced_accuracy_score(y[test], baseline)),
                       macro_f1=float(f1_score(y[test], predicted, average="macro", zero_division=0)),
                       auc=float(roc_auc_score(y[test], probability)) if len(np.unique(y[test])) == 2 else None)
        folds.append(metrics)
        for i, pred, prob in zip(np.flatnonzero(test), predicted, probability):
            prediction_rows.append(dict(index=int(i), record=str(held), truth=int(y[i]),
                                        predicted=int(pred), probability=float(prob)))
    return dict(folds=folds, macro_record_balanced_accuracy=float(np.mean([f["balanced_accuracy"] for f in folds])),
                predictions=prediction_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path, help="Directory containing the four original MAT files")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--trust-channel-order", action="store_true")
    parser.add_argument("--window", type=float, default=.6)
    parser.add_argument("--highpass", type=float, default=.5)
    args = parser.parse_args()
    paths = sorted(args.data.rglob("VisualCog*.mat"))
    if len(paths) < 3:
        raise ValueError("Expected at least three VisualCog MAT records")
    args.out.mkdir(parents=True, exist_ok=False)
    xs, ys, gs, audits, allrows = [], [], [], [], []
    common_rate, before = None, None
    for index, path in enumerate(paths):
        data, fs, audit = load_record(path, args.trust_channel_order)
        if common_rate is not None and fs != common_rate:
            raise ValueError("Sampling rates differ; explicit anti-aliased resampling is required")
        common_rate = fs
        rows = event_table(data[7], data[8], fs)
        x, kept, processing = extract_epochs(data, fs, rows, args.window, args.highpass)
        before = processing["baseline_samples"]
        audit.update(n_trials=len(rows), n_epochs=len(kept),
                     n_no_response=sum(r["censored"] for r in rows),
                     n_multiple_clicks=sum(r["n_clicks"] > 1 for r in rows), processing=processing,
                     response_inside_feature_window_fraction=float(np.mean([r["response_inside_window"] for r in kept])))
        audits.append(audit)
        record = str(path.relative_to(args.data))
        allrows.extend({**r, "record": record} for r in rows)
        xs.append(x)
        ys.append(np.array([r["cue"] for r in kept]))
        gs.extend([record] * len(kept))
    (args.out / "audit.json").write_text(json.dumps(audits, ensure_ascii=False, indent=2), encoding="utf-8")
    with (args.out / "events.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(allrows[0]))
        writer.writeheader()
        writer.writerows(allrows)
    result = nested_record_cv(np.concatenate(xs), np.concatenate(ys), np.array(gs), before)
    result["scope"] = "record-held-out cue-direction prediction; not diagnosis, not source localization"
    result["data_kind"] = "user_supplied_MAT_not_prevalidated_by_authors"
    (args.out / "cv.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in {"predictions", "folds"}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
