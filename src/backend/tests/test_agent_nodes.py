"""Unit tests for ocr_node and reconciler_node.

Uses monkeypatch against `src.backend.agents.nodes.{LocalExtractor,NeuralFallback}`
to swap in test doubles — matches the pattern in test_document_processor.py and
avoids requiring real PaddleOCR / Gemini at test time.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np
import pytest

from src.backend.agents import nodes
from src.backend.agents.nodes import ocr_node, reconciler_node
from src.backend.agents.state import AgentState, ExtractedInvoice, LineItem
from src.backend.extraction.local_extractor import LocalExtractorUnavailable
from src.backend.extraction.neural_fallback import NeuralUnavailableError
from src.backend.extraction.types import ExtractionResult


@dataclass
class _FakePage:
    processed: object | None = None
    original: object | None = None


def _dummy_image() -> np.ndarray:
    return np.zeros((8, 8, 3), dtype=np.uint8)


def _state_with_pages(image=None) -> AgentState:
    return AgentState(
        document_id="doc-ocr-1",
        file_path="uploads/x.pdf",
        pages=[_FakePage(processed=image if image is not None else _dummy_image())],
    )


# ---------------------------------------------------------------------------
# ocr_node
# ---------------------------------------------------------------------------


class _FakeLocal:
    """Minimal LocalExtractor double — matches the `extract(pages)` contract."""

    def __init__(self, result: ExtractionResult | None = None, exc: Exception | None = None):
        self._result = result
        self._exc = exc

    async def extract(self, pages):
        if self._exc is not None:
            raise self._exc
        return self._result


def _install_fake_local(monkeypatch, *, result=None, exc=None):
    monkeypatch.setattr(
        nodes, "LocalExtractor",
        lambda *args, **kwargs: _FakeLocal(result=result, exc=exc),
    )


def test_ocr_node_passing_extraction_populates_state(monkeypatch):
    result = ExtractionResult(
        fields={
            "invoice_number": "INV-001",
            "date": "2026-04-24",
            "vendor_name": "Acme",
            "subtotal": "200.00",
            "tax": "30.00",
            "total_amount": "230.00",
        },
        line_items=[{"description": "widget", "quantity": "1", "unit_price": "200.00", "total": "200.00"}],
        confidence=0.92,
        raw_text="...",
        tier="local",
    )
    _install_fake_local(monkeypatch, result=result)

    out = asyncio.run(ocr_node(_state_with_pages()))

    assert out.extracted_data is not None
    assert out.extracted_data.invoice_number == "INV-001"
    assert out.extracted_data.subtotal == "200.00"
    assert len(out.extracted_data.line_items) == 1
    assert out.extracted_data.line_items[0].description == "widget"
    assert out.tier == "local"
    assert out.reason == "local_ok"
    assert out.audit_log[-1]["stage"] == "ocr"
    assert out.audit_log[-1]["ok"] is True
    assert out.audit_log[-1]["detail"]["confidence"] == 0.92


def test_ocr_node_local_extractor_unavailable_routes_to_vlm(monkeypatch):
    _install_fake_local(monkeypatch, exc=LocalExtractorUnavailable("paddleocr not installed"))

    out = asyncio.run(ocr_node(_state_with_pages()))

    assert out.extracted_data is None
    assert out.tier == "vlm"
    assert out.reason == "local_import_error"
    assert out.audit_log[-1]["ok"] is False
    assert out.audit_log[-1]["reason"] == "local_import_error"
    assert "paddleocr" in out.audit_log[-1]["detail"]["error"]


def test_ocr_node_runtime_error_routes_to_vlm_and_does_not_crash(monkeypatch):
    _install_fake_local(monkeypatch, exc=RuntimeError("cuda oom"))

    out = asyncio.run(ocr_node(_state_with_pages()))

    assert out.extracted_data is None
    assert out.tier == "vlm"
    assert out.reason == "local_runtime_error"
    assert out.audit_log[-1]["detail"]["error"] == "cuda oom"


def test_ocr_node_empty_extraction_routes_to_vlm(monkeypatch):
    empty = ExtractionResult(
        fields={"invoice_number": None, "subtotal": None, "tax": None, "total_amount": None},
        line_items=[],
        confidence=0.1,
        raw_text="",
        tier="local",
    )
    _install_fake_local(monkeypatch, result=empty)

    out = asyncio.run(ocr_node(_state_with_pages()))

    assert out.extracted_data is None
    assert out.tier == "vlm"
    assert out.reason == "local_empty_extraction"


def test_ocr_node_malformed_line_items_are_skipped(monkeypatch):
    result = ExtractionResult(
        fields={"subtotal": "10", "tax": "1", "total_amount": "11"},
        line_items=[
            {"description": "ok", "total": "11"},
            "not a dict",             # should be skipped, not crash
            {"foo": "bar"},            # dict with unknown keys → LineItem with None fields
        ],
        confidence=0.8,
        raw_text="",
        tier="local",
    )
    _install_fake_local(monkeypatch, result=result)

    out = asyncio.run(ocr_node(_state_with_pages()))
    assert out.extracted_data is not None
    # The non-dict entry was filtered; both dicts were mapped.
    assert len(out.extracted_data.line_items) == 2
    assert out.extracted_data.line_items[0].description == "ok"
    assert out.extracted_data.line_items[1].description is None


# ---------------------------------------------------------------------------
# reconciler_node
# ---------------------------------------------------------------------------


class _FakeNeural:
    def __init__(self, result: ExtractionResult | None = None, exc: Exception | None = None):
        self._result = result
        self._exc = exc
        self.last_guidance: str | None = None

    async def reconcile(self, image, error_context):
        self.last_guidance = error_context
        if self._exc is not None:
            raise self._exc
        return self._result


def _install_fake_neural(monkeypatch, *, result=None, exc=None) -> _FakeNeural:
    fake = _FakeNeural(result=result, exc=exc)
    monkeypatch.setattr(nodes, "NeuralFallback", lambda *a, **kw: fake)
    return fake


def _state_pending_reconciliation(guidance="magnitude_error: likely slip in total") -> AgentState:
    return AgentState(
        document_id="doc-rec-1",
        file_path="uploads/x.pdf",
        pages=[_FakePage(processed=_dummy_image())],
        extracted_data=ExtractedInvoice(subtotal="20", tax="30", total_amount="2300"),
        attempts=0,
        is_valid=False,
        tier="local",
        reason="local_audit_fail",
        reconciliation_guidance=guidance,
    )


def test_reconciler_node_passes_guidance_verbatim_to_neural(monkeypatch):
    clean = ExtractionResult(
        fields={"subtotal": "200", "tax": "30", "total_amount": "230"},
        line_items=[],
        confidence=0.88,
        raw_text="",
        tier="vlm",
    )
    fake = _install_fake_neural(monkeypatch, result=clean)
    state = _state_pending_reconciliation(
        guidance="magnitude_error: likely decimal-point slip in total (reported 2300, expected 230)"
    )

    out = asyncio.run(reconciler_node(state))

    # The reconciler must hand the auditor's guidance straight through to BAML.
    assert fake.last_guidance == state.reconciliation_guidance
    assert out.extracted_data is not None
    assert out.extracted_data.subtotal == "200"
    assert out.attempts == 1
    assert out.reason == "vlm_retried"
    # Guidance is consumed — cleared for the next auditor pass to set fresh.
    assert out.reconciliation_guidance is None
    entry = out.audit_log[-1]
    assert entry["stage"] == "reconcile"
    assert entry["reason"] == "vlm_retried"
    assert entry["detail"]["guidance_used"].startswith("magnitude_error")


def test_reconciler_node_vlm_unavailable_routes_to_hitl(monkeypatch):
    _install_fake_neural(monkeypatch, exc=NeuralUnavailableError("GOOGLE_API_KEY not set"))
    state = _state_pending_reconciliation()

    out = asyncio.run(reconciler_node(state))

    assert out.tier == "hitl"
    assert out.reason == "vlm_unavailable"
    assert out.attempts == 1  # still increments — avoids infinite retry on persistent unavailability
    assert out.extracted_data is state.extracted_data  # unchanged
    assert out.audit_log[-1]["detail"]["error"] == "GOOGLE_API_KEY not set"


def test_reconciler_node_no_image_routes_straight_to_hitl(monkeypatch):
    # Nothing to send to Gemini if we have no page image.
    state = AgentState(
        document_id="doc-rec-2",
        file_path="uploads/x.pdf",
        pages=[],
        extracted_data=ExtractedInvoice(subtotal="20", tax="30", total_amount="2300"),
        reconciliation_guidance="x",
    )

    out = asyncio.run(reconciler_node(state))

    assert out.tier == "hitl"
    assert out.reason == "vlm_runtime_error"
    assert out.audit_log[-1]["detail"]["error"] == "no_image_on_pages"


def test_reconciler_node_runtime_error_keeps_tier_vlm_for_possible_retry(monkeypatch):
    # A transient runtime error shouldn't force HITL — the graph router can
    # still attempt another reconciliation pass if attempts < cap.
    _install_fake_neural(monkeypatch, exc=RuntimeError("transient 503"))
    state = _state_pending_reconciliation()

    out = asyncio.run(reconciler_node(state))

    assert out.tier == "vlm"
    assert out.reason == "vlm_runtime_error"
    assert out.attempts == 1


def test_as_float_strips_currency_markers_gemini_returns():
    """Regression: live Gemini returns line-item totals like "$19.00" or
    "Rs. 1,500/-"; the persist path must coerce those into plain floats for
    the line_items.total Float column, or the whole pipeline crashes at the
    INSERT. This bug was caught by the live VLM smoke test."""
    from src.backend.agents.nodes import _as_float

    assert _as_float("$19.00") == 19.0
    assert _as_float("Rs. 1,50,000/-") == 150000.0
    assert _as_float("€42.50") == 42.5
    assert _as_float(None) is None
    assert _as_float("") is None
    assert _as_float("not a number") is None
    assert _as_float(12) == 12.0
    assert _as_float(3.14) == 3.14


def test_reconciler_node_uses_fallback_guidance_when_none_set(monkeypatch):
    # Defensive: if guidance is somehow missing, still call reconcile with a
    # sensible default rather than crashing.
    result = ExtractionResult(
        fields={"subtotal": "10", "tax": "0", "total_amount": "10"},
        line_items=[],
        confidence=0.5, raw_text="", tier="vlm",
    )
    fake = _install_fake_neural(monkeypatch, result=result)
    state = _state_pending_reconciliation(guidance=None)

    asyncio.run(reconciler_node(state))

    assert fake.last_guidance is not None
    assert "full re-extraction" in fake.last_guidance.lower()
