"""confidence_calibrator.py — Per-field confidence threshold learning.

Learns optimal per-field thresholds from the corrections history in the DB.
Fields that are corrected even when confidence is high get lower thresholds,
causing AgenticExtractor to escalate them to VLM more aggressively.

Usage:
    calibrator = ConfidenceCalibrator(default_threshold=0.80)
    calibrator.fit(db)
    calibrator.save("adapters/calibrator_thresholds.json")

    # Later (at inference time):
    calibrator = ConfidenceCalibrator()
    calibrator.load("adapters/calibrator_thresholds.json")
    t = calibrator.threshold("vendor_name")
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

MIN_SAMPLES_FOR_HEURISTIC = 5
MIN_SAMPLES_FOR_LR = 10
CALIBRATOR_VERSION = 1


class ConfidenceCalibrator:
    """Learns per-field confidence thresholds from the HITL correction history.

    Three tiers based on how many corrections exist per field:
      - < 5 corrections  : return default_threshold (insufficient data)
      - 5–9 corrections  : mean-based heuristic (mean_corrected_conf - 1*std)
      - >= 10 corrections : sklearn LogisticRegression (binary: was_corrected)
    """

    def __init__(self, default_threshold: float = 0.80) -> None:
        self._default_threshold = default_threshold
        self._thresholds: dict[str, float] = {}
        self._sample_counts: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Fitting
    # ------------------------------------------------------------------

    def fit(self, db: Session) -> None:
        """Query correction history and compute per-field thresholds.

        Joins ExtractedField → Correction on Correction.field_id = ExtractedField.id.
        A field is considered "corrected" if any Correction row references it.
        Groups by field_name to compute per-field thresholds.

        Does NOT persist to disk — call save() separately.

        Args:
            db: active SQLAlchemy session (read-only inside this method)
        """
        from src.backend.db.models import Correction, ExtractedField

        # Pull all extracted fields (id, field_name, confidence)
        fields = db.query(ExtractedField).filter(
            ExtractedField.confidence.isnot(None)
        ).all()

        if not fields:
            logger.info("ConfidenceCalibrator.fit: no extracted fields found, using defaults")
            return

        # Build a set of corrected field ids
        corrected_ids: set[str] = {
            c.field_id for c in db.query(Correction).all()
        }

        # Group by field_name
        from collections import defaultdict
        field_data: dict[str, list[tuple[float, int]]] = defaultdict(list)
        for f in fields:
            was_corrected = int(f.id in corrected_ids)
            field_data[f.field_name].append((float(f.confidence), was_corrected))

        self._thresholds = {}
        self._sample_counts = {}

        for field_name, samples in field_data.items():
            confidences = [s[0] for s in samples]
            labels = [s[1] for s in samples]
            n = len(samples)
            self._sample_counts[field_name] = n

            if n < MIN_SAMPLES_FOR_HEURISTIC:
                # Not enough data — keep default (don't store, threshold() falls back)
                logger.debug(
                    "ConfidenceCalibrator: %s has %d samples (<5), using default %.2f",
                    field_name, n, self._default_threshold,
                )
            elif n < MIN_SAMPLES_FOR_LR:
                t = self._compute_threshold_heuristic(confidences, labels)
                self._thresholds[field_name] = t
                logger.info(
                    "ConfidenceCalibrator: %s (n=%d) heuristic threshold=%.3f", field_name, n, t
                )
            else:
                t = self._compute_threshold_lr(confidences, labels)
                self._thresholds[field_name] = t
                logger.info(
                    "ConfidenceCalibrator: %s (n=%d) LR threshold=%.3f", field_name, n, t
                )

    def _compute_threshold_heuristic(
        self, confidences: list[float], labels: list[int]
    ) -> float:
        """Compute threshold via mean-based heuristic (5–9 samples).

        Takes the mean confidence of corrected fields minus 1 standard deviation.
        If no corrected samples exist, falls back to default_threshold.
        Result is clamped to [0.0, 1.0].
        """
        import statistics

        corrected_confs = [c for c, l in zip(confidences, labels) if l == 1]
        if not corrected_confs:
            return self._default_threshold

        mean_c = statistics.mean(corrected_confs)
        std_c = statistics.stdev(corrected_confs) if len(corrected_confs) > 1 else 0.0
        threshold = mean_c - std_c
        return float(max(0.0, min(1.0, threshold)))

    def _compute_threshold_lr(
        self, confidences: list[float], labels: list[int]
    ) -> float:
        """Compute threshold using logistic regression (>= 10 samples).

        Fits LogisticRegression on single feature (confidence), binary label
        (was_corrected). Returns the confidence value at which P(corrected)=0.5,
        i.e. t = -intercept / coef[0], clamped to [0.5, 0.99].

        Falls back to heuristic if the model cannot converge or coef is zero.
        """
        from sklearn.linear_model import LogisticRegression  # type: ignore[import]
        import numpy as np

        X = np.array(confidences).reshape(-1, 1)
        y = np.array(labels)

        # Guard: if only one class present, LR won't be meaningful
        if len(set(y)) < 2:
            return self._compute_threshold_heuristic(confidences, labels)

        try:
            clf = LogisticRegression(max_iter=500)
            clf.fit(X, y)
            coef = clf.coef_[0][0]
            intercept = clf.intercept_[0]
            if abs(coef) < 1e-6:
                return self._compute_threshold_heuristic(confidences, labels)
            t = -intercept / coef
            return float(max(0.5, min(0.99, t)))
        except Exception as e:
            logger.warning("ConfidenceCalibrator: LR failed (%s), using heuristic", e)
            return self._compute_threshold_heuristic(confidences, labels)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def threshold(self, field_name: str) -> float:
        """Return the learned threshold for a field, or the default if unknown.

        Args:
            field_name: canonical field name (e.g. "vendor_name")
        Returns:
            float in [0.0, 1.0]
        """
        return self._thresholds.get(field_name, self._default_threshold)

    def save(self, path: str) -> None:
        """Persist learned thresholds to a JSON file.

        Creates parent directories if they do not exist.

        Args:
            path: file path ending in .json
        """
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": CALIBRATOR_VERSION,
            "default_threshold": self._default_threshold,
            "fitted_at": datetime.now(timezone.utc).isoformat(),
            "thresholds": self._thresholds,
            "sample_counts": self._sample_counts,
        }
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)
        logger.info("ConfidenceCalibrator thresholds saved to %s", path)

    def load(self, path: str) -> None:
        """Load thresholds from a JSON file produced by save().

        Args:
            path: path to a JSON file previously written by save()

        Raises:
            FileNotFoundError: if the file does not exist
            ValueError: on version mismatch
        """
        if not Path(path).exists():
            raise FileNotFoundError(f"Calibrator file not found: {path}")

        with open(path) as f:
            payload = json.load(f)

        if payload.get("version") != CALIBRATOR_VERSION:
            raise ValueError(
                f"Calibrator version mismatch: expected {CALIBRATOR_VERSION}, "
                f"got {payload.get('version')}"
            )

        self._thresholds = payload.get("thresholds", {})
        self._sample_counts = payload.get("sample_counts", {})
        self._default_threshold = payload.get("default_threshold", self._default_threshold)
        logger.info(
            "ConfidenceCalibrator loaded from %s (%d field thresholds)",
            path, len(self._thresholds),
        )
