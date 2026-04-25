"""Tests for PlausibilityVerifier inference, focused on cold-start and
artifact-loading behavior. Inference is exercised via a stub model so we
don't depend on a trained artifact existing.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import pytest

from src.backend.agents.state import ExtractedInvoice, LineItem
from src.backend.verifier.features import SCHEMA_HASH
from src.backend.verifier.predictor import PlausibilityVerifier
from src.backend.verifier.types import VerifierReport


class _StubModel:
    """Minimal stand-in for a LightGBM Booster — returns a fixed score."""

    def __init__(self, score: float) -> None:
        self._score = score

    def predict(self, X):
        return [self._score for _ in X]


class _StubCalibrator:
    """Identity calibrator — passes raw scores through."""

    def transform(self, x):
        return list(x)


def _write_artifact(
    path: Path,
    score: float = 0.7,
    threshold: float = 0.5,
    schema_hash: str | None = None,
) -> None:
    payload = {
        "model": _StubModel(score),
        "calibrator": _StubCalibrator(),
        "threshold": threshold,
        "feature_schema_hash": schema_hash if schema_hash is not None else SCHEMA_HASH,
        "feature_names": [],
        "metadata": {"trained_at": "test", "feature_means": [0.0] * 38},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        pickle.dump(payload, f)


@pytest.fixture
def invoice() -> ExtractedInvoice:
    return ExtractedInvoice(
        invoice_number="INV-001",
        date="01/01/2024",
        vendor_name="Test Co",
        subtotal="100.00",
        tax="15.00",
        total_amount="115.00",
        line_items=[LineItem(description="x", quantity="1", unit_price="100", total="100")],
    )


def test_cold_start_returns_none_when_no_models_dir(tmp_path):
    missing = tmp_path / "does_not_exist"
    verifier = PlausibilityVerifier.from_latest(missing)
    assert verifier is None


def test_cold_start_returns_none_when_dir_empty(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    verifier = PlausibilityVerifier.from_latest(tmp_path)
    assert verifier is None


def test_loads_artifact_and_evaluates(tmp_path, invoice):
    artifact = tmp_path / "verifier_v1.pkl"
    _write_artifact(artifact, score=0.9, threshold=0.5)

    verifier = PlausibilityVerifier.from_latest(tmp_path)
    assert verifier is not None
    assert verifier.threshold == pytest.approx(0.5)

    report = verifier.evaluate(invoice, ocr_confidence=0.95)
    assert isinstance(report, VerifierReport)
    assert report.skipped is False
    assert report.ok is True
    assert report.score == pytest.approx(0.9)


def test_low_score_flips_ok_false(tmp_path, invoice):
    artifact = tmp_path / "verifier_v1.pkl"
    _write_artifact(artifact, score=0.2, threshold=0.5)
    verifier = PlausibilityVerifier.from_latest(tmp_path)

    report = verifier.evaluate(invoice, ocr_confidence=0.9)
    assert report.ok is False
    assert report.reason == "low_plausibility"


def test_evaluate_none_extraction_returns_skipped(tmp_path, invoice):
    artifact = tmp_path / "verifier_v1.pkl"
    _write_artifact(artifact)
    verifier = PlausibilityVerifier.from_latest(tmp_path)

    report = verifier.evaluate(None, ocr_confidence=None)
    assert report.skipped is True
    assert report.ok is True  # skipped is non-blocking


def test_stale_schema_hash_skipped(tmp_path, invoice):
    artifact = tmp_path / "verifier_v1.pkl"
    _write_artifact(artifact, schema_hash="old_hash_xxxxxxx")
    verifier = PlausibilityVerifier.from_latest(tmp_path)
    # The loader refuses to serve a stale model (feature schema changed).
    assert verifier is None


def test_loads_latest_when_multiple_versions(tmp_path, invoice):
    import time
    v1 = tmp_path / "verifier_v1.pkl"
    v2 = tmp_path / "verifier_v2.pkl"
    _write_artifact(v1, score=0.1)
    time.sleep(0.05)  # mtime granularity
    _write_artifact(v2, score=0.95)

    verifier = PlausibilityVerifier.from_latest(tmp_path)
    report = verifier.evaluate(invoice, ocr_confidence=0.9)
    assert report.score == pytest.approx(0.95)


def test_skipped_report_has_ok_true():
    """The skipped sentinel must never block extractions — pipeline depends
    on this in the cold-start path.
    """
    rep = VerifierReport.skipped_report(reason="no_model_loaded")
    assert rep.ok is True
    assert rep.skipped is True
    assert rep.score is None


def test_corrupt_artifact_returns_none(tmp_path):
    """A pickle file that doesn't contain the expected keys should not
    crash the loader — it returns None and pipeline runs math-only.
    """
    bad = tmp_path / "verifier_v1.pkl"
    bad.write_bytes(b"not a valid pickle")
    verifier = PlausibilityVerifier.from_latest(tmp_path)
    assert verifier is None
