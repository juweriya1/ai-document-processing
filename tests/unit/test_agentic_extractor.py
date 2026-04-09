"""Unit tests for AgenticExtractor.

All heavy extractors are mocked via constructor injection — no GPU or DB needed.
"""

from unittest.mock import MagicMock, patch
import logging

import pytest

from src.backend.pipeline.agentic_extractor import AgenticExtractor
from src.backend.pipeline.orchestrator import ExtractorInterface


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_calibrator(thresholds: dict[str, float], default: float = 0.80) -> MagicMock:
    cal = MagicMock()
    cal.threshold.side_effect = lambda fn: thresholds.get(fn, default)
    return cal


def _make_fast_extractor(
    fields: list[dict], line_items: list[dict] | None = None
) -> MagicMock:
    ext = MagicMock(spec=ExtractorInterface)
    ext.extract.return_value = (fields, line_items or [])
    return ext


def _make_vlm_extractor(
    fields: list[dict], line_items: list[dict] | None = None
) -> MagicMock:
    ext = MagicMock(spec=ExtractorInterface)
    ext.extract.return_value = (fields, line_items or [])
    return ext


def _make_agentic(
    fast_fields: list[dict],
    fast_items: list[dict] | None = None,
    vlm_fields: list[dict] | None = None,
    vlm_items: list[dict] | None = None,
    thresholds: dict[str, float] | None = None,
    default_threshold: float = 0.80,
) -> AgenticExtractor:
    db = MagicMock()
    cal = _make_calibrator(thresholds or {}, default=default_threshold)
    fast = _make_fast_extractor(fast_fields, fast_items)
    vlm = _make_vlm_extractor(vlm_fields or [], vlm_items)
    return AgenticExtractor(db=db, extractor_fast=fast, extractor_vlm=vlm, calibrator=cal)


# ---------------------------------------------------------------------------
# TestAgenticExtractorInit
# ---------------------------------------------------------------------------

class TestAgenticExtractorInit:
    def test_default_extractors_none_before_lazy_init(self):
        db = MagicMock()
        e = AgenticExtractor(db=db)
        assert e._extractor_fast is None
        assert e._extractor_vlm is None
        assert e._calibrator is None

    def test_stats_initialised_to_zero(self):
        db = MagicMock()
        e = AgenticExtractor(db=db)
        assert e.stats == {"fast_path": 0, "vlm_path": 0}

    def test_injected_fast_extractor_stored(self):
        fast = MagicMock()
        e = AgenticExtractor(db=MagicMock(), extractor_fast=fast)
        assert e._extractor_fast is fast

    def test_injected_vlm_extractor_stored(self):
        vlm = MagicMock()
        e = AgenticExtractor(db=MagicMock(), extractor_vlm=vlm)
        assert e._extractor_vlm is vlm

    def test_injected_calibrator_stored(self):
        cal = MagicMock()
        e = AgenticExtractor(db=MagicMock(), calibrator=cal)
        assert e._calibrator is cal


# ---------------------------------------------------------------------------
# TestFastPathRouting
# ---------------------------------------------------------------------------

class TestFastPathRouting:
    def test_all_high_confidence_takes_fast_path(self):
        fields = [
            {"field_name": "vendor_name", "field_value": "Acme", "confidence": 0.95},
            {"field_name": "total_amount", "field_value": "100.00", "confidence": 0.92},
        ]
        e = _make_agentic(fast_fields=fields, thresholds={"vendor_name": 0.80, "total_amount": 0.80})
        e.extract("doc-1", "inv.pdf")
        e._extractor_vlm.extract.assert_not_called()

    def test_fast_path_returns_fast_extractor_results(self):
        fields = [{"field_name": "date", "field_value": "2024-01-01", "confidence": 0.95}]
        items = [{"description": "Item A", "quantity": 1.0, "unit_price": 10.0, "total": 10.0}]
        e = _make_agentic(fast_fields=fields, fast_items=items)
        out_fields, out_items = e.extract("doc-1", "inv.pdf")
        assert out_fields == fields
        assert out_items == items

    def test_fast_path_increments_fast_stat(self):
        fields = [{"field_name": "date", "field_value": "2024-01-01", "confidence": 0.95}]
        e = _make_agentic(fast_fields=fields)
        e.extract("doc-1", "inv.pdf")
        assert e.stats["fast_path"] == 1
        assert e.stats["vlm_path"] == 0

    def test_empty_fast_results_takes_fast_path(self):
        e = _make_agentic(fast_fields=[])
        out_fields, out_items = e.extract("doc-empty", "inv.pdf")
        e._extractor_vlm.extract.assert_not_called()
        assert out_fields == []

    def test_field_at_exact_threshold_takes_fast_path(self):
        # confidence == threshold (not strictly below) → fast path
        fields = [{"field_name": "vendor_name", "field_value": "Corp", "confidence": 0.80}]
        e = _make_agentic(fast_fields=fields, thresholds={"vendor_name": 0.80})
        e.extract("doc-1", "inv.pdf")
        e._extractor_vlm.extract.assert_not_called()


# ---------------------------------------------------------------------------
# TestVLMPathRouting
# ---------------------------------------------------------------------------

class TestVLMPathRouting:
    def test_low_confidence_field_escalates_to_vlm(self):
        fields = [{"field_name": "vendor_name", "field_value": "Acme", "confidence": 0.60}]
        e = _make_agentic(fast_fields=fields, thresholds={"vendor_name": 0.80})
        e.extract("doc-1", "inv.pdf")
        e._extractor_vlm.extract.assert_called_once_with("doc-1", "inv.pdf")

    def test_vlm_path_increments_vlm_stat(self):
        fields = [{"field_name": "vendor_name", "field_value": "Acme", "confidence": 0.60}]
        e = _make_agentic(fast_fields=fields, thresholds={"vendor_name": 0.80})
        e.extract("doc-1", "inv.pdf")
        assert e.stats["vlm_path"] == 1
        assert e.stats["fast_path"] == 0

    def test_vlm_replaces_low_conf_fast_field_when_vlm_higher(self):
        fast_fields = [{"field_name": "vendor_name", "field_value": "Old Corp", "confidence": 0.60}]
        vlm_fields = [{"field_name": "vendor_name", "field_value": "New Corp", "confidence": 0.92}]
        e = _make_agentic(
            fast_fields=fast_fields, vlm_fields=vlm_fields,
            thresholds={"vendor_name": 0.80},
        )
        out_fields, _ = e.extract("doc-1", "inv.pdf")
        vendor = next(f for f in out_fields if f["field_name"] == "vendor_name")
        assert vendor["field_value"] == "New Corp"
        assert vendor["confidence"] == 0.92

    def test_vlm_does_not_replace_when_vlm_confidence_is_lower(self):
        fast_fields = [{"field_name": "vendor_name", "field_value": "Fast Corp", "confidence": 0.60}]
        vlm_fields = [{"field_name": "vendor_name", "field_value": "VLM Corp", "confidence": 0.55}]
        e = _make_agentic(
            fast_fields=fast_fields, vlm_fields=vlm_fields,
            thresholds={"vendor_name": 0.80},
        )
        out_fields, _ = e.extract("doc-1", "inv.pdf")
        vendor = next(f for f in out_fields if f["field_name"] == "vendor_name")
        assert vendor["field_value"] == "Fast Corp"

    def test_vlm_only_field_appended_to_merged_results(self):
        fast_fields = [{"field_name": "date", "field_value": "2024-01-01", "confidence": 0.60}]
        vlm_fields = [
            {"field_name": "date", "field_value": "2024-01-15", "confidence": 0.95},
            {"field_name": "invoice_number", "field_value": "INV-999", "confidence": 0.88},
        ]
        e = _make_agentic(
            fast_fields=fast_fields, vlm_fields=vlm_fields,
            thresholds={"date": 0.80},
        )
        out_fields, _ = e.extract("doc-1", "inv.pdf")
        names = {f["field_name"] for f in out_fields}
        assert "invoice_number" in names  # VLM-only field was appended

    def test_vlm_line_items_used_when_available(self):
        fast_fields = [{"field_name": "total_amount", "field_value": "50", "confidence": 0.50}]
        fast_items = [{"description": "Fast item", "quantity": 1.0, "unit_price": 50.0, "total": 50.0}]
        vlm_items = [{"description": "VLM item", "quantity": 2.0, "unit_price": 25.0, "total": 50.0}]
        e = _make_agentic(
            fast_fields=fast_fields, fast_items=fast_items,
            vlm_items=vlm_items, thresholds={"total_amount": 0.80},
        )
        _, out_items = e.extract("doc-1", "inv.pdf")
        assert out_items[0]["description"] == "VLM item"

    def test_fast_line_items_used_when_vlm_line_items_empty(self):
        fast_fields = [{"field_name": "total_amount", "field_value": "50", "confidence": 0.50}]
        fast_items = [{"description": "Fast item", "quantity": 1.0, "unit_price": 50.0, "total": 50.0}]
        e = _make_agentic(
            fast_fields=fast_fields, fast_items=fast_items,
            vlm_items=[], thresholds={"total_amount": 0.80},
        )
        _, out_items = e.extract("doc-1", "inv.pdf")
        assert out_items[0]["description"] == "Fast item"


# ---------------------------------------------------------------------------
# TestVLMFallback
# ---------------------------------------------------------------------------

class TestVLMFallback:
    def _extractor_with_vlm_error(self) -> AgenticExtractor:
        fast_fields = [{"field_name": "vendor_name", "field_value": "Corp", "confidence": 0.50}]
        db = MagicMock()
        cal = _make_calibrator({"vendor_name": 0.80})
        fast = _make_fast_extractor(fast_fields)
        vlm = MagicMock(spec=ExtractorInterface)
        vlm.extract.side_effect = RuntimeError("CUDA OOM")
        return AgenticExtractor(db=db, extractor_fast=fast, extractor_vlm=vlm, calibrator=cal)

    def test_vlm_exception_returns_fast_results(self):
        e = self._extractor_with_vlm_error()
        out_fields, _ = e.extract("doc-1", "inv.pdf")
        assert out_fields[0]["field_value"] == "Corp"

    def test_vlm_exception_logged(self, caplog):
        e = self._extractor_with_vlm_error()
        with caplog.at_level(logging.ERROR):
            e.extract("doc-1", "inv.pdf")
        assert any("VLM extractor failed" in r.message for r in caplog.records)

    def test_vlm_exception_does_not_increment_vlm_stat(self):
        e = self._extractor_with_vlm_error()
        e.extract("doc-1", "inv.pdf")
        assert e.stats["vlm_path"] == 0


# ---------------------------------------------------------------------------
# TestMergeResults
# ---------------------------------------------------------------------------

class TestMergeResults:
    def _extractor(self) -> AgenticExtractor:
        return AgenticExtractor(db=MagicMock(), calibrator=MagicMock())

    def test_all_fast_fields_preserved_when_no_low_conf(self):
        fast = [
            {"field_name": "vendor_name", "field_value": "A", "confidence": 0.9},
            {"field_name": "date", "field_value": "2024-01-01", "confidence": 0.95},
        ]
        e = self._extractor()
        merged, _ = e._merge_results(fast, [], [], [], set())
        assert len(merged) == 2

    def test_high_confidence_fast_field_not_replaced_by_vlm(self):
        fast = [{"field_name": "date", "field_value": "Fast date", "confidence": 0.95}]
        vlm = [{"field_name": "date", "field_value": "VLM date", "confidence": 0.90}]
        e = self._extractor()
        # "date" is NOT in low_conf_names, so VLM should not replace it
        merged, _ = e._merge_results(fast, [], vlm, [], set())
        assert merged[0]["field_value"] == "Fast date"

    def test_merge_preserves_fast_fields_first(self):
        fast = [
            {"field_name": "vendor_name", "field_value": "Fast", "confidence": 0.50},
            {"field_name": "date", "field_value": "2024-01-01", "confidence": 0.92},
        ]
        vlm = [{"field_name": "vendor_name", "field_value": "VLM", "confidence": 0.95}]
        e = self._extractor()
        merged, _ = e._merge_results(fast, [], vlm, [], {"vendor_name"})
        # vendor_name replaced, date preserved, and merged starts with vendor_name
        names = [f["field_name"] for f in merged]
        assert "vendor_name" in names
        assert "date" in names

    def test_merge_with_empty_fast_fields(self):
        vlm = [{"field_name": "vendor_name", "field_value": "VLM Corp", "confidence": 0.88}]
        e = self._extractor()
        merged, _ = e._merge_results([], [], vlm, [], set())
        # VLM fields appended even when fast is empty
        assert len(merged) == 1
        assert merged[0]["field_value"] == "VLM Corp"

    def test_merge_with_empty_vlm_fields(self):
        fast = [{"field_name": "vendor_name", "field_value": "Fast", "confidence": 0.50}]
        e = self._extractor()
        merged, _ = e._merge_results(fast, [], [], [], {"vendor_name"})
        # No VLM output → keep fast result as-is
        assert merged[0]["field_value"] == "Fast"


# ---------------------------------------------------------------------------
# TestStats
# ---------------------------------------------------------------------------

class TestStats:
    def test_stats_returns_copy_not_reference(self):
        e = _make_agentic(fast_fields=[{"field_name": "date", "field_value": "x", "confidence": 0.95}])
        s = e.stats
        s["fast_path"] = 999
        assert e.stats["fast_path"] == 0  # mutation of returned copy should not affect internal state

    def test_multiple_docs_accumulate_stats(self):
        # Two high-conf docs → both take fast path
        fields = [{"field_name": "date", "field_value": "2024-01-01", "confidence": 0.95}]
        e = _make_agentic(fast_fields=fields)
        e.extract("doc-1", "inv.pdf")
        e.extract("doc-2", "inv.pdf")
        assert e.stats["fast_path"] == 2

    def test_mixed_routing_accumulates_correctly(self):
        db = MagicMock()
        cal_high = _make_calibrator({"date": 0.80})

        fast_high = _make_fast_extractor([
            {"field_name": "date", "field_value": "2024-01-01", "confidence": 0.95}
        ])
        vlm_mock = _make_vlm_extractor([])

        e_high = AgenticExtractor(db=db, extractor_fast=fast_high,
                                   extractor_vlm=vlm_mock, calibrator=cal_high)
        e_high.extract("doc-1", "inv.pdf")
        assert e_high.stats["fast_path"] == 1
        assert e_high.stats["vlm_path"] == 0

        # Now simulate a low-conf doc on the same extractor instance
        # by patching the fast extractor's return value
        fast_high.extract.return_value = (
            [{"field_name": "date", "field_value": "2024-01-01", "confidence": 0.50}], []
        )
        e_high.extract("doc-2", "inv.pdf")
        assert e_high.stats["vlm_path"] == 1
        assert e_high.stats["fast_path"] == 1  # unchanged
