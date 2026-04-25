"""Inference-time entry point for the plausibility verifier.

Loads the most recent trained model artifact from disk; falls back to a
non-blocking 'skipped' report if no artifact exists or if the artifact's
feature schema disagrees with the current code (i.e. someone added a
feature without retraining). The pipeline never crashes on a verifier
problem — math-only gating remains the safety floor.

Artifact format (produced by trainer.py):
    {
      "model": <pickled LightGBM Booster or sklearn estimator>,
      "calibrator": <fitted IsotonicRegression>,
      "threshold": float,
      "feature_schema_hash": str,
      "metadata": {... training run metadata ...},
    }
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any

from src.backend.agents.state import ExtractedInvoice
from src.backend.verifier.features import (
    FEATURE_NAMES,
    SCHEMA_HASH,
    extract_features,
)
from src.backend.verifier.types import VerifierReport

logger = logging.getLogger(__name__)

_DEFAULT_MODELS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "models"
_ARTIFACT_GLOB = "verifier_v*.pkl"
_TOP_FEATURE_COUNT = 3


class PlausibilityVerifier:
    """Loads a trained verifier and scores extractions.

    Construct via `from_latest()` — returns None if no artifact exists, so
    callers can write `verifier = PlausibilityVerifier.from_latest()`
    followed by `if verifier is None: ...` without try/except.
    """

    def __init__(
        self,
        model: Any,
        calibrator: Any,
        threshold: float,
        feature_schema_hash: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._model = model
        self._calibrator = calibrator
        self._threshold = float(threshold)
        self._schema_hash = feature_schema_hash
        self._metadata = metadata or {}

    @property
    def threshold(self) -> float:
        return self._threshold

    @property
    def metadata(self) -> dict[str, Any]:
        return dict(self._metadata)

    @classmethod
    def from_latest(
        cls,
        models_dir: Path | str | None = None,
    ) -> "PlausibilityVerifier | None":
        """Locate the most recent verifier_v*.pkl by mtime; load it.

        Returns None (not raises) if the directory or artifact is missing —
        the pipeline treats that as "verifier not yet trained" and runs
        math-only.
        """
        directory = Path(models_dir) if models_dir is not None else _DEFAULT_MODELS_DIR
        if not directory.exists():
            logger.info("verifier: models dir %s not found; skipping", directory)
            return None

        artifacts = sorted(
            directory.glob(_ARTIFACT_GLOB),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not artifacts:
            logger.info("verifier: no artifacts in %s; skipping", directory)
            return None

        latest = artifacts[0]
        try:
            with latest.open("rb") as f:
                payload = pickle.load(f)
        except Exception:
            logger.exception("verifier: failed to load %s; skipping", latest)
            return None

        try:
            instance = cls(
                model=payload["model"],
                calibrator=payload["calibrator"],
                threshold=payload["threshold"],
                feature_schema_hash=payload["feature_schema_hash"],
                metadata=payload.get("metadata", {}),
            )
        except KeyError:
            logger.exception("verifier: artifact %s missing required key", latest)
            return None

        if instance._schema_hash != SCHEMA_HASH:
            logger.warning(
                "verifier: artifact schema hash %s != current %s — model is "
                "stale; skipping. Retrain with `python scripts/train_verifier.py`.",
                instance._schema_hash,
                SCHEMA_HASH,
            )
            return None

        logger.info(
            "verifier: loaded %s (threshold=%.4f, trained_at=%s)",
            latest.name,
            instance._threshold,
            instance._metadata.get("trained_at", "unknown"),
        )
        return instance

    def evaluate(
        self,
        extraction: ExtractedInvoice | None,
        ocr_confidence: float | None,
    ) -> VerifierReport:
        """Score one extraction. Pure — no I/O, no global state."""
        if extraction is None:
            return VerifierReport.skipped_report(reason="no_extraction")

        try:
            feats = extract_features(extraction, ocr_confidence)
        except Exception:
            logger.exception("verifier: feature extraction failed")
            return VerifierReport.skipped_report(reason="feature_extraction_failed")

        try:
            raw_score = self._predict_proba(feats.values)
        except Exception:
            logger.exception("verifier: model inference failed")
            return VerifierReport.skipped_report(reason="model_inference_failed")

        try:
            calibrated = float(self._calibrator.transform([raw_score])[0])
        except Exception:
            logger.exception("verifier: calibrator failed; using raw score")
            calibrated = float(raw_score)

        ok = calibrated >= self._threshold
        top = self._top_features(feats.values, calibrated) if not ok else []
        return VerifierReport(
            ok=ok,
            score=round(calibrated, 4),
            threshold=round(self._threshold, 4),
            reason=None if ok else "low_plausibility",
            top_features=top,
            skipped=False,
        )

    def _predict_proba(self, values: tuple[float, ...]) -> float:
        """Return P(plausible) — i.e., positive class probability.

        LightGBM Booster.predict returns the positive-class probability
        directly when trained with binary objective. We accommodate sklearn
        estimators too via the predict_proba interface.
        """
        if hasattr(self._model, "predict_proba"):
            proba = self._model.predict_proba([list(values)])
            return float(proba[0][1])
        # LightGBM Booster
        result = self._model.predict([list(values)])
        return float(result[0])

    def _top_features(
        self, values: tuple[float, ...], score: float
    ) -> list[tuple[str, float]]:
        """Surface the top-N features by absolute deviation from the median
        training value. We don't run SHAP at inference (too expensive); we
        use the training-time feature_means stored in metadata as a baseline.

        If metadata lacks the baseline, returns empty list — the verifier
        still works, just without explanations.
        """
        baseline = self._metadata.get("feature_means")
        if not baseline or len(baseline) != len(values):
            return []
        deviations = [
            (FEATURE_NAMES[i], abs(values[i] - float(baseline[i])))
            for i in range(len(values))
        ]
        deviations.sort(key=lambda x: x[1], reverse=True)
        return [(name, round(dev, 4)) for name, dev in deviations[:_TOP_FEATURE_COUNT]]
