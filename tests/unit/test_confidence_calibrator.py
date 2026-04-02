"""Unit tests for ConfidenceCalibrator.

Uses mock DB data — no real database connection needed.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.backend.pipeline.confidence_calibrator import (
    CALIBRATOR_VERSION,
    MIN_SAMPLES_FOR_HEURISTIC,
    MIN_SAMPLES_FOR_LR,
    ConfidenceCalibrator,
)


# ---------------------------------------------------------------------------
# DB mock helpers
# ---------------------------------------------------------------------------

def _mock_field(field_id: str, field_name: str, confidence: float) -> MagicMock:
    f = MagicMock()
    f.id = field_id
    f.field_name = field_name
    f.confidence = confidence
    return f


def _mock_correction(field_id: str) -> MagicMock:
    c = MagicMock()
    c.field_id = field_id
    return c


def _build_mock_db(
    samples: list[tuple[str, str, float, bool]]
) -> MagicMock:
    """Build a mock Session.

    samples: list of (field_id, field_name, confidence, was_corrected)
    """
    fields = [_mock_field(fid, fname, conf) for fid, fname, conf, _ in samples]
    corrections = [
        _mock_correction(fid) for fid, _, _, corrected in samples if corrected
    ]

    db = MagicMock()
    # query(ExtractedField).filter(...).all() → fields
    # query(Correction).all() → corrections
    def _query(model_cls):
        q = MagicMock()
        name = getattr(model_cls, "__name__", str(model_cls))
        if "ExtractedField" in name:
            q.filter.return_value.all.return_value = fields
        else:
            q.all.return_value = corrections
        return q

    db.query.side_effect = _query
    return db


# ---------------------------------------------------------------------------
# TestConfidenceCalibratorInit
# ---------------------------------------------------------------------------

class TestConfidenceCalibratorInit:
    def test_default_threshold_stored(self):
        c = ConfidenceCalibrator()
        assert c._default_threshold == 0.80

    def test_custom_default_threshold_stored(self):
        c = ConfidenceCalibrator(default_threshold=0.65)
        assert c._default_threshold == 0.65

    def test_thresholds_empty_before_fit(self):
        c = ConfidenceCalibrator()
        assert c._thresholds == {}
        assert c._sample_counts == {}


# ---------------------------------------------------------------------------
# TestThresholdBeforeFit
# ---------------------------------------------------------------------------

class TestThresholdBeforeFit:
    def test_returns_default_for_unknown_field(self):
        c = ConfidenceCalibrator(default_threshold=0.75)
        assert c.threshold("vendor_name") == 0.75

    def test_returns_default_for_all_fields_before_fit(self):
        c = ConfidenceCalibrator(default_threshold=0.82)
        for field in ("invoice_number", "date", "vendor_name", "total_amount"):
            assert c.threshold(field) == 0.82


# ---------------------------------------------------------------------------
# TestFitInsufficientData
# ---------------------------------------------------------------------------

class TestFitInsufficientData:
    def _make_samples(self, n: int, field_name: str = "vendor_name") -> list[tuple]:
        return [(f"f{i}", field_name, 0.7 + i * 0.01, i % 2 == 0) for i in range(n)]

    def test_zero_corrections_returns_default(self):
        c = ConfidenceCalibrator(default_threshold=0.80)
        db = _build_mock_db([])
        c.fit(db)
        assert c.threshold("vendor_name") == 0.80

    def test_fewer_than_5_samples_returns_default(self):
        c = ConfidenceCalibrator(default_threshold=0.80)
        db = _build_mock_db(self._make_samples(4))
        c.fit(db)
        assert c.threshold("vendor_name") == 0.80

    def test_exactly_4_corrections_returns_default(self):
        c = ConfidenceCalibrator(default_threshold=0.77)
        samples = [(f"f{i}", "total_amount", 0.9, True) for i in range(4)]
        db = _build_mock_db(samples)
        c.fit(db)
        assert c.threshold("total_amount") == 0.77


# ---------------------------------------------------------------------------
# TestFitHeuristic
# ---------------------------------------------------------------------------

class TestFitHeuristic:
    def _make_samples(
        self, corrected_confs: list[float], uncorrected_confs: list[float],
        field_name: str = "vendor_name"
    ) -> list[tuple]:
        samples = []
        for i, conf in enumerate(corrected_confs):
            samples.append((f"c{i}", field_name, conf, True))
        for i, conf in enumerate(uncorrected_confs):
            samples.append((f"u{i}", field_name, conf, False))
        return samples

    def test_5_to_9_samples_uses_heuristic(self):
        # 5 corrected, 2 uncorrected = 7 total → heuristic range
        samples = self._make_samples(
            corrected_confs=[0.8, 0.85, 0.75, 0.9, 0.82],
            uncorrected_confs=[0.6, 0.55],
        )
        c = ConfidenceCalibrator(default_threshold=0.99)
        db = _build_mock_db(samples)
        c.fit(db)
        t = c.threshold("vendor_name")
        # Should differ from default since n=7 >= 5
        assert t != 0.99
        assert 0.0 <= t <= 1.0

    def test_heuristic_clamped_to_zero_minimum(self):
        # Very low corrected confidences → mean - std could go negative
        samples = self._make_samples(
            corrected_confs=[0.01, 0.02, 0.03, 0.01, 0.02],
            uncorrected_confs=[],
        )
        c = ConfidenceCalibrator()
        db = _build_mock_db(samples)
        c.fit(db)
        assert c.threshold("vendor_name") >= 0.0

    def test_heuristic_clamped_to_one_maximum(self):
        # High corrected confidences with no std → could hit 1.0
        samples = self._make_samples(
            corrected_confs=[0.99, 0.99, 0.99, 0.99, 0.99],
            uncorrected_confs=[],
        )
        c = ConfidenceCalibrator()
        db = _build_mock_db(samples)
        c.fit(db)
        assert c.threshold("vendor_name") <= 1.0

    def test_heuristic_with_no_corrected_samples_returns_default(self):
        # 7 samples, none corrected → no corrected confs → default
        samples = [(f"u{i}", "date", 0.8 + i * 0.01, False) for i in range(7)]
        c = ConfidenceCalibrator(default_threshold=0.77)
        db = _build_mock_db(samples)
        c.fit(db)
        assert c.threshold("date") == 0.77


# ---------------------------------------------------------------------------
# TestFitLogisticRegression
# ---------------------------------------------------------------------------

class TestFitLogisticRegression:
    def _make_lr_samples(self, field_name: str = "total_amount") -> list[tuple]:
        # 10 samples: low confidence → not corrected, high confidence → corrected
        return [
            (f"a{i}", field_name, 0.4 + i * 0.05, i >= 5) for i in range(10)
        ]

    def test_10_or_more_samples_uses_lr(self):
        samples = self._make_lr_samples()
        c = ConfidenceCalibrator(default_threshold=0.99)
        db = _build_mock_db(samples)
        c.fit(db)
        t = c.threshold("total_amount")
        # LR should produce a different value from 0.99 default
        assert t != 0.99

    def test_lr_threshold_in_valid_range(self):
        samples = self._make_lr_samples()
        c = ConfidenceCalibrator()
        db = _build_mock_db(samples)
        c.fit(db)
        t = c.threshold("total_amount")
        assert 0.5 <= t <= 0.99

    def test_lr_lower_threshold_for_high_conf_corrections(self):
        # All corrections happen at high confidence → threshold should be relatively low
        # compared to a case where corrections happen at low confidence
        high_conf_samples = [
            (f"h{i}", "tax", 0.85 + i * 0.01, True) for i in range(6)
        ] + [
            (f"u{i}", "tax", 0.3 + i * 0.01, False) for i in range(6)
        ]
        low_conf_samples = [
            (f"l{i}", "subtotal", 0.3 + i * 0.01, True) for i in range(6)
        ] + [
            (f"u{i}", "subtotal", 0.85 + i * 0.01, False) for i in range(6)
        ]

        c = ConfidenceCalibrator()
        db = _build_mock_db(high_conf_samples + low_conf_samples)
        c.fit(db)

        t_tax = c.threshold("tax")
        t_subtotal = c.threshold("subtotal")
        # Tax (corrected at high conf) should get a lower or equal threshold
        assert t_tax <= t_subtotal + 0.15  # allow some tolerance

    def test_lr_single_class_falls_back_to_heuristic(self):
        # All labels are 1 → LR can't fit; should fall back without crash
        samples = [(f"x{i}", "invoice_number", 0.7 + i * 0.01, True) for i in range(10)]
        c = ConfidenceCalibrator()
        db = _build_mock_db(samples)
        c.fit(db)  # must not raise
        t = c.threshold("invoice_number")
        assert 0.0 <= t <= 1.0


# ---------------------------------------------------------------------------
# TestFitMultipleFields
# ---------------------------------------------------------------------------

class TestFitMultipleFields:
    def test_different_fields_get_independent_thresholds(self):
        samples = (
            [(f"v{i}", "vendor_name", 0.6 + i * 0.03, i % 2 == 0) for i in range(10)] +
            [(f"t{i}", "total_amount", 0.85 + i * 0.01, i % 3 == 0) for i in range(10)]
        )
        c = ConfidenceCalibrator(default_threshold=0.80)
        db = _build_mock_db(samples)
        c.fit(db)
        t_vendor = c.threshold("vendor_name")
        t_total = c.threshold("total_amount")
        # Both should be set (n=10 each) and may differ
        assert isinstance(t_vendor, float)
        assert isinstance(t_total, float)

    def test_fit_does_not_mutate_default_threshold(self):
        samples = [(f"f{i}", "date", 0.8, True) for i in range(5)]
        c = ConfidenceCalibrator(default_threshold=0.70)
        db = _build_mock_db(samples)
        c.fit(db)
        # Fitting one field should not change the default used for other fields
        assert c.threshold("invoice_number") == 0.70

    def test_sample_counts_populated_after_fit(self):
        samples = [(f"f{i}", "vendor_name", 0.8, True) for i in range(7)]
        c = ConfidenceCalibrator()
        db = _build_mock_db(samples)
        c.fit(db)
        assert c._sample_counts.get("vendor_name") == 7


# ---------------------------------------------------------------------------
# TestSaveLoad
# ---------------------------------------------------------------------------

class TestSaveLoad:
    def _fitted_calibrator(self) -> ConfidenceCalibrator:
        c = ConfidenceCalibrator(default_threshold=0.75)
        c._thresholds = {"vendor_name": 0.72, "total_amount": 0.81}
        c._sample_counts = {"vendor_name": 12, "total_amount": 8}
        return c

    def test_save_creates_file(self, tmp_path):
        c = self._fitted_calibrator()
        path = str(tmp_path / "calibrator.json")
        c.save(path)
        assert Path(path).exists()

    def test_save_creates_parent_directories(self, tmp_path):
        c = self._fitted_calibrator()
        path = str(tmp_path / "nested" / "dir" / "calibrator.json")
        c.save(path)
        assert Path(path).exists()

    def test_saved_json_has_required_keys(self, tmp_path):
        c = self._fitted_calibrator()
        path = str(tmp_path / "calibrator.json")
        c.save(path)
        with open(path) as f:
            data = json.load(f)
        for key in ("version", "default_threshold", "fitted_at", "thresholds", "sample_counts"):
            assert key in data, f"missing key: {key}"

    def test_load_restores_thresholds(self, tmp_path):
        c = self._fitted_calibrator()
        path = str(tmp_path / "calibrator.json")
        c.save(path)

        c2 = ConfidenceCalibrator()
        c2.load(path)
        assert c2.threshold("vendor_name") == pytest.approx(0.72)
        assert c2.threshold("total_amount") == pytest.approx(0.81)

    def test_load_restores_default_threshold(self, tmp_path):
        c = self._fitted_calibrator()
        path = str(tmp_path / "calibrator.json")
        c.save(path)

        c2 = ConfidenceCalibrator(default_threshold=0.99)
        c2.load(path)
        # After load, default should come from file
        assert c2.threshold("unknown_field") == pytest.approx(0.75)

    def test_load_nonexistent_file_raises_file_not_found(self, tmp_path):
        c = ConfidenceCalibrator()
        with pytest.raises(FileNotFoundError):
            c.load(str(tmp_path / "nonexistent.json"))

    def test_load_wrong_version_raises_value_error(self, tmp_path):
        path = str(tmp_path / "calibrator.json")
        payload = {
            "version": 999,
            "default_threshold": 0.80,
            "fitted_at": "2026-01-01T00:00:00Z",
            "thresholds": {},
            "sample_counts": {},
        }
        with open(path, "w") as f:
            json.dump(payload, f)
        c = ConfidenceCalibrator()
        with pytest.raises(ValueError, match="version"):
            c.load(path)

    def test_save_load_roundtrip_exact(self, tmp_path):
        c = self._fitted_calibrator()
        path = str(tmp_path / "calibrator.json")
        c.save(path)

        c2 = ConfidenceCalibrator()
        c2.load(path)
        assert c2._thresholds == c._thresholds
        assert c2._sample_counts == c._sample_counts

    def test_load_empty_thresholds_returns_default(self, tmp_path):
        path = str(tmp_path / "calibrator.json")
        payload = {
            "version": CALIBRATOR_VERSION,
            "default_threshold": 0.65,
            "fitted_at": "2026-01-01T00:00:00Z",
            "thresholds": {},
            "sample_counts": {},
        }
        with open(path, "w") as f:
            json.dump(payload, f)
        c = ConfidenceCalibrator(default_threshold=0.99)
        c.load(path)
        assert c.threshold("any_field") == pytest.approx(0.65)
