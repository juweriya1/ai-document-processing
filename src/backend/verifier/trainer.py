"""Offline training for the plausibility verifier.

Pipeline:
  1. Pull verified extractions (clean positives) from the corpus loader.
  2. For each clean extraction, generate K corrupted negatives via the
     `corruption` operators.
  3. Featurize all examples → numpy matrix.
  4. Train LightGBM with class-weighted binary cross-entropy.
  5. Fit isotonic regression on a held-out validation slice for calibration.
  6. Choose F1-optimal threshold on the same validation slice.
  7. Save versioned artifact + metadata.

Training is deterministic given a seed. The trainer never touches the
request path; pipeline inference is in `predictor.py`.
"""

from __future__ import annotations

import logging
import pickle
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from src.backend.agents.state import ExtractedInvoice
from src.backend.verifier import corruption
from src.backend.verifier.features import (
    FEATURE_NAMES,
    N_FEATURES,
    SCHEMA_HASH,
    extract_features,
)

logger = logging.getLogger(__name__)


@dataclass
class TrainConfig:
    negatives_per_positive: int = 4
    val_fraction: float = 0.2
    seed: int = 42
    n_estimators: int = 200
    learning_rate: float = 0.05
    num_leaves: int = 31
    min_data_in_leaf: int = 5


@dataclass
class TrainReport:
    n_positives: int
    n_negatives: int
    n_features: int
    val_auroc: float
    val_auprc: float
    val_f1: float
    threshold: float
    pre_calibration_ece: float
    post_calibration_ece: float
    per_operator_recall: dict[str, float] = field(default_factory=dict)
    artifact_path: str | None = None
    # Breakdown so callers can see how much of the training data came
    # from real human corrections vs synthetic corruption.
    n_real_positives: int = 0
    n_real_negatives: int = 0
    n_synthetic_positives: int = 0
    n_synthetic_negatives: int = 0


def _build_dataset(
    invoices: Sequence[ExtractedInvoice],
    cfg: TrainConfig,
) -> tuple[list[list[float]], list[int], list[str]]:
    """Build (X, y, tags) where tags label the corruption type for negatives
    (or 'clean' for positives) — used for per-operator recall reporting."""
    rng = random.Random(cfg.seed)
    X: list[list[float]] = []
    y: list[int] = []
    tags: list[str] = []

    for inv in invoices:
        # Positive: clean extraction
        feats = extract_features(inv).values
        X.append(list(feats))
        y.append(1)
        tags.append("clean")

        # K negatives per positive — sample independently
        for _ in range(cfg.negatives_per_positive):
            corrupted = corruption.apply_random(inv, rng)
            if corrupted is None:
                continue
            cfeats = extract_features(corrupted.invoice).values
            X.append(list(cfeats))
            y.append(0)
            tags.append(corrupted.operator)

    return X, y, tags


def _stratified_split(
    X: list[list[float]],
    y: list[int],
    tags: list[str],
    val_fraction: float,
    rng: random.Random,
) -> tuple[
    tuple[list[list[float]], list[int], list[str]],
    tuple[list[list[float]], list[int], list[str]],
]:
    """Stratified by class label so val has positives even when negatives
    dominate. Tags travel with each example for per-operator analysis.
    """
    pos_idx = [i for i, lbl in enumerate(y) if lbl == 1]
    neg_idx = [i for i, lbl in enumerate(y) if lbl == 0]
    rng.shuffle(pos_idx)
    rng.shuffle(neg_idx)
    n_val_pos = max(1, int(round(len(pos_idx) * val_fraction)))
    n_val_neg = max(1, int(round(len(neg_idx) * val_fraction)))

    val_idx = set(pos_idx[:n_val_pos] + neg_idx[:n_val_neg])
    train: tuple[list[list[float]], list[int], list[str]] = ([], [], [])
    val: tuple[list[list[float]], list[int], list[str]] = ([], [], [])
    for i in range(len(y)):
        bucket = val if i in val_idx else train
        bucket[0].append(X[i])
        bucket[1].append(y[i])
        bucket[2].append(tags[i])
    return train, val


def _expected_calibration_error(
    probs: Sequence[float],
    labels: Sequence[int],
    n_bins: int = 10,
) -> float:
    """Standard ECE over equal-width bins."""
    if not probs:
        return 0.0
    n = len(probs)
    bin_edges = [i / n_bins for i in range(n_bins + 1)]
    ece = 0.0
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        in_bin = [
            (p, l) for p, l in zip(probs, labels)
            if (lo <= p < hi) or (i == n_bins - 1 and p == 1.0)
        ]
        if not in_bin:
            continue
        avg_p = sum(p for p, _ in in_bin) / len(in_bin)
        avg_l = sum(l for _, l in in_bin) / len(in_bin)
        ece += (len(in_bin) / n) * abs(avg_p - avg_l)
    return ece


def _f1_optimal_threshold(
    probs: Sequence[float], labels: Sequence[int]
) -> tuple[float, float]:
    """Sweep candidate thresholds; return (best_threshold, best_f1).

    Uses the unique sorted scores as candidates so we hit every separation
    boundary without arbitrary granularity.
    """
    if not probs:
        return 0.5, 0.0
    candidates = sorted(set(probs))
    best_t = 0.5
    best_f1 = -1.0
    for t in candidates:
        tp = sum(1 for p, l in zip(probs, labels) if p >= t and l == 1)
        fp = sum(1 for p, l in zip(probs, labels) if p >= t and l == 0)
        fn = sum(1 for p, l in zip(probs, labels) if p < t and l == 1)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        if f1 > best_f1:
            best_f1 = f1
            best_t = t
    return best_t, best_f1


def _per_operator_recall(
    probs: Sequence[float],
    labels: Sequence[int],
    tags: Sequence[str],
    threshold: float,
) -> dict[str, float]:
    """For each corruption operator, what fraction of its examples are caught
    (i.e. predicted < threshold, labeled negative)?"""
    by_op: dict[str, list[int]] = {}
    for p, l, t in zip(probs, labels, tags):
        if l == 1 or t == "clean":
            continue
        caught = 1 if p < threshold else 0
        by_op.setdefault(t, []).append(caught)
    return {op: sum(v) / len(v) for op, v in by_op.items() if v}


REAL_LABEL_WEIGHT = 4.0
"""Real human corrections are authoritative; synthetic corruptions are
plausible-but-not-confirmed failures. Weight real samples this many times
more in the training loss so the model learns the human-confirmed signal
preferentially. 4.0 was picked to match `negatives_per_positive=4` so a
single real correction balances against the K synthetic negatives one
clean doc generates."""


def train(
    invoices: Sequence[ExtractedInvoice],
    cfg: TrainConfig | None = None,
    output_dir: Path | str | None = None,
    *,
    extra_labeled: Sequence[tuple[ExtractedInvoice, int]] | None = None,
) -> TrainReport:
    """Train, calibrate, threshold, and serialize a verifier artifact.

    `invoices` are clean positives — each is corrupted K times to manufacture
    synthetic negatives.

    `extra_labeled` is an optional list of `(invoice, label)` pairs from
    real human corrections — labeled positives (label=1) are the
    extraction *as the human said it should be*, labeled negatives
    (label=0) are the extraction *as the model produced it before the
    human edit*. These are weighted REAL_LABEL_WEIGHT× higher in the loss
    because they're confirmed ground truth, not plausibility surrogates.

    Returns a TrainReport summarizing validation metrics and the path of
    the saved model (or None if `output_dir` was None — e.g. for testing).
    """
    cfg = cfg or TrainConfig()

    if not invoices and not extra_labeled:
        raise ValueError("training requires at least one verified invoice or one labeled pair")
    if len(invoices) < 5 and not extra_labeled:
        logger.warning(
            "training set is small (%d invoices); val metrics will be noisy",
            len(invoices),
        )

    # Lazy imports — these libraries are training-time only.
    try:
        import numpy as np
        from lightgbm import LGBMClassifier
        from sklearn.isotonic import IsotonicRegression
        from sklearn.metrics import average_precision_score, roc_auc_score
    except ImportError as e:
        raise RuntimeError(
            "Verifier training requires lightgbm, scikit-learn, and numpy. "
            "Install with: pip install -r requirements-train.txt"
        ) from e

    rng = random.Random(cfg.seed)

    X, y, tags = _build_dataset(invoices, cfg) if invoices else ([], [], [])
    n_synth_pos = sum(1 for lbl in y if lbl == 1)
    n_synth_neg = sum(1 for lbl in y if lbl == 0)

    n_real_pos = 0
    n_real_neg = 0
    if extra_labeled:
        for inv, label in extra_labeled:
            X.append(list(extract_features(inv).values))
            y.append(int(label))
            tags.append("real_correction_pos" if label == 1 else "real_correction_neg")
            if label == 1:
                n_real_pos += 1
            else:
                n_real_neg += 1
        logger.info(
            "added %d real labeled pairs (positives=%d, negatives=%d)",
            len(extra_labeled), n_real_pos, n_real_neg,
        )

    if not y:
        raise ValueError("no training data after corruption + labels")

    (X_train, y_train, tags_train), (X_val, y_val, tags_val) = _stratified_split(
        X, y, tags, cfg.val_fraction, rng
    )

    n_neg = sum(1 for lbl in y_train if lbl == 0)
    n_pos = sum(1 for lbl in y_train if lbl == 1)
    pos_weight = (n_neg / max(n_pos, 1))

    # Per-sample weights: real corrections weigh REAL_LABEL_WEIGHT× more
    # than synthetic ones. Stored as float; LightGBM handles them via
    # sample_weight at fit time.
    sample_weights = np.asarray([
        REAL_LABEL_WEIGHT if t.startswith("real_correction") else 1.0
        for t in tags_train
    ])

    model = LGBMClassifier(
        n_estimators=cfg.n_estimators,
        learning_rate=cfg.learning_rate,
        num_leaves=cfg.num_leaves,
        min_data_in_leaf=cfg.min_data_in_leaf,
        objective="binary",
        scale_pos_weight=pos_weight,
        random_state=cfg.seed,
        verbose=-1,
    )
    model.fit(
        np.asarray(X_train),
        np.asarray(y_train),
        sample_weight=sample_weights,
    )

    raw_val_probs = model.predict_proba(np.asarray(X_val))[:, 1]
    pre_ece = _expected_calibration_error(raw_val_probs.tolist(), y_val)

    calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    calibrator.fit(raw_val_probs, y_val)
    cal_val_probs = calibrator.transform(raw_val_probs)
    post_ece = _expected_calibration_error(cal_val_probs.tolist(), y_val)

    threshold, f1 = _f1_optimal_threshold(cal_val_probs.tolist(), y_val)
    auroc = float(roc_auc_score(y_val, cal_val_probs)) if len(set(y_val)) > 1 else 0.0
    auprc = (
        float(average_precision_score(y_val, cal_val_probs))
        if len(set(y_val)) > 1
        else 0.0
    )
    per_op = _per_operator_recall(cal_val_probs.tolist(), y_val, tags_val, threshold)

    feature_means = np.asarray(X_train).mean(axis=0).tolist()

    artifact_path: str | None = None
    if output_dir is not None:
        artifact_path = _save_artifact(
            model=model,
            calibrator=calibrator,
            threshold=threshold,
            cfg=cfg,
            train_report={
                "n_train": len(y_train),
                "n_val": len(y_val),
                "auroc": auroc,
                "auprc": auprc,
                "f1": f1,
                "pre_ece": pre_ece,
                "post_ece": post_ece,
            },
            feature_means=feature_means,
            output_dir=output_dir,
        )

    return TrainReport(
        n_positives=sum(1 for lbl in y if lbl == 1),
        n_negatives=sum(1 for lbl in y if lbl == 0),
        n_features=N_FEATURES,
        val_auroc=auroc,
        val_auprc=auprc,
        val_f1=f1,
        threshold=float(threshold),
        pre_calibration_ece=pre_ece,
        post_calibration_ece=post_ece,
        per_operator_recall=per_op,
        artifact_path=artifact_path,
        n_real_positives=n_real_pos,
        n_real_negatives=n_real_neg,
        n_synthetic_positives=n_synth_pos,
        n_synthetic_negatives=n_synth_neg,
    )


def _save_artifact(
    model: Any,
    calibrator: Any,
    threshold: float,
    cfg: TrainConfig,
    train_report: dict[str, Any],
    feature_means: list[float],
    output_dir: Path | str,
) -> str:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    existing = sorted(out.glob("verifier_v*.pkl"), key=lambda p: p.stat().st_mtime)
    next_n = 1
    for p in existing:
        try:
            n = int(p.stem.split("_v")[-1])
            next_n = max(next_n, n + 1)
        except ValueError:
            pass

    artifact = {
        "model": model,
        "calibrator": calibrator,
        "threshold": float(threshold),
        "feature_schema_hash": SCHEMA_HASH,
        "feature_names": list(FEATURE_NAMES),
        "metadata": {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "train_seconds": time.time(),
            "config": vars(cfg),
            "metrics": train_report,
            "feature_means": feature_means,
        },
    }
    path = out / f"verifier_v{next_n}.pkl"
    with path.open("wb") as f:
        pickle.dump(artifact, f)
    logger.info("verifier: saved artifact to %s", path)
    return str(path)
