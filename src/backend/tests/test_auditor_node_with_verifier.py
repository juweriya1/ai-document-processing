"""Tests for the auditor_node verifier integration.

Covers the dual-gate behavior: math auditor + plausibility verifier. The
verifier is mocked via monkeypatching `_get_verifier` so we don't depend on
a trained model artifact existing in the test environment.

Uses asyncio.run() to invoke async nodes — matches the convention in
test_agent_nodes.py (this codebase uses raw asyncio rather than
pytest-asyncio).
"""

from __future__ import annotations

import asyncio

import pytest

from src.backend.agents import nodes
from src.backend.agents.nodes import auditor_node
from src.backend.agents.state import AgentState, ExtractedInvoice, LineItem
from src.backend.verifier.types import VerifierReport


def _state(invoice: ExtractedInvoice, tier: str = "local", confidence: float = 0.95) -> AgentState:
    return AgentState(
        document_id="doc-1",
        file_path="x.pdf",
        extracted_data=invoice,
        ocr_confidence=confidence,
        tier=tier,
    )


def _clean_invoice() -> ExtractedInvoice:
    return ExtractedInvoice(
        invoice_number="INV-1",
        date="01/01/2024",
        vendor_name="Test Co",
        subtotal="100.00",
        tax="15.00",
        total_amount="115.00",
        line_items=[LineItem(description="x", quantity="1", unit_price="100", total="100")],
    )


class _FakeVerifier:
    def __init__(self, report: VerifierReport) -> None:
        self._report = report

    def evaluate(self, _extraction, _conf) -> VerifierReport:
        return self._report

    @property
    def threshold(self) -> float:
        return 0.5


def _install_verifier(monkeypatch, report: VerifierReport | None) -> None:
    """Install a fake verifier (or None for cold-start path)."""
    fake = _FakeVerifier(report) if report is not None else None
    monkeypatch.setattr(nodes, "_get_verifier", lambda: fake)
    monkeypatch.setattr(nodes, "_VERIFIER_LOADED", True)
    monkeypatch.setattr(nodes, "_VERIFIER", fake)


def test_math_pass_verifier_pass_marks_valid(monkeypatch):
    rep = VerifierReport(ok=True, score=0.92, threshold=0.5, reason=None)
    _install_verifier(monkeypatch, rep)

    state = asyncio.run(auditor_node(_state(_clean_invoice())))
    assert state.is_valid is True
    assert state.verifier_report["ok"] is True
    assert state.verifier_report["score"] == 0.92


def test_math_pass_verifier_fail_routes_to_tier2(monkeypatch):
    rep = VerifierReport(ok=False, score=0.2, threshold=0.5, reason="low_plausibility")
    _install_verifier(monkeypatch, rep)

    state = asyncio.run(auditor_node(_state(_clean_invoice(), tier="local")))
    assert state.is_valid is False
    assert state.reason == "verifier_low_plausibility"
    assert "low_plausibility" in (state.reconciliation_guidance or "")


def test_math_pass_verifier_fail_after_vlm_does_not_loop(monkeypatch):
    """If we already ran Tier-2 reconciliation and the verifier still
    disagrees, we trust the reconciliation — otherwise we'd loop forever."""
    rep = VerifierReport(ok=False, score=0.3, threshold=0.5, reason="low_plausibility")
    _install_verifier(monkeypatch, rep)

    state = asyncio.run(auditor_node(_state(_clean_invoice(), tier="vlm")))
    assert state.is_valid is True


def test_cold_start_no_verifier_falls_back_to_math_only(monkeypatch):
    """When no verifier model exists, _get_verifier returns None and the
    pipeline is math-only — valid extraction passes."""
    _install_verifier(monkeypatch, None)

    state = asyncio.run(auditor_node(_state(_clean_invoice())))
    assert state.is_valid is True
    assert state.verifier_report is not None
    assert state.verifier_report["skipped"] is True


def test_math_fail_dominates_verifier_pass(monkeypatch):
    """Math failure must still route to Tier 2 even if the verifier
    ironically says the extraction is plausible."""
    rep = VerifierReport(ok=True, score=0.99, threshold=0.5, reason=None)
    _install_verifier(monkeypatch, rep)

    bad = _clean_invoice().model_copy(update={"total_amount": "999.99"})
    state = asyncio.run(auditor_node(_state(bad)))
    assert state.is_valid is False
    assert state.reason == "local_audit_fail"


def test_low_confidence_takes_precedence_over_verifier_skip(monkeypatch):
    """Low OCR confidence escalates regardless of verifier state."""
    _install_verifier(monkeypatch, None)  # cold start, skipped

    state = asyncio.run(auditor_node(_state(_clean_invoice(), confidence=0.5)))
    assert state.is_valid is False
    assert state.reason == "local_low_confidence"
