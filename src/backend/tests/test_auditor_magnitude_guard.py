import asyncio
from decimal import Decimal

from src.backend.agents.nodes import auditor_node
from src.backend.agents.state import AgentState, ExtractedInvoice, LineItem
from src.backend.validation.auditor import (
    AuditReport,
    FinancialAuditor,
    detect_magnitude_slip,
)


def _mismatch(subtotal: str, tax: str, total: str) -> AuditReport:
    s = Decimal(subtotal)
    t = Decimal(tax)
    T = Decimal(total)
    return AuditReport(
        ok=False,
        subtotal=s,
        tax=t,
        total=T,
        delta=(s + t) - T,
        reason="math_mismatch",
    )


def test_magnitude_slip_detected_10x():
    report = _mismatch("200", "30", "2300")
    msg = detect_magnitude_slip(report)
    assert msg is not None
    assert "magnitude_error" in msg
    assert "10" in msg


def test_magnitude_slip_detected_0_1x():
    report = _mismatch("1500", "0", "150")
    msg = detect_magnitude_slip(report)
    assert msg is not None
    assert "magnitude_error" in msg


def test_magnitude_slip_detected_100x():
    report = _mismatch("20", "3", "2300")
    msg = detect_magnitude_slip(report)
    assert msg is not None
    assert "magnitude_error" in msg


def test_non_magnitude_mismatch_returns_none():
    report = _mismatch("200", "30", "235")
    assert detect_magnitude_slip(report) is None


def test_ok_report_returns_none():
    report = AuditReport(
        ok=True,
        subtotal=Decimal("200"),
        tax=Decimal("30"),
        total=Decimal("230"),
        delta=Decimal("0"),
        reason=None,
    )
    assert detect_magnitude_slip(report) is None


def test_partial_report_returns_none():
    report = AuditReport(
        ok=False,
        subtotal=None,
        tax=None,
        total=Decimal("230"),
        delta=None,
        reason="missing_total",
    )
    assert detect_magnitude_slip(report) is None


def test_zero_expected_returns_none():
    # subtotal+tax == 0 means we can't compute a meaningful ratio.
    report = AuditReport(
        ok=False,
        subtotal=Decimal("0"),
        tax=Decimal("0"),
        total=Decimal("100"),
        delta=Decimal("-100"),
        reason="math_mismatch",
    )
    assert detect_magnitude_slip(report) is None


def test_line_items_catch_slip_when_subtotal_tax_also_slipped():
    # Top-level check already catches 10x, but confirm line-item message when
    # top-level check fails (e.g. non-magnitude primary mismatch).
    report = _mismatch("100", "0", "1000")
    msg = detect_magnitude_slip(report, line_items=[{"total": "100"}])
    assert msg is not None
    assert "magnitude_error" in msg


def test_end_to_end_10x_slip_via_financial_auditor():
    auditor = FinancialAuditor()
    report = auditor.audit({
        "subtotal": "200.00",
        "tax": "30.00",
        "total_amount": "2300.00",
    })
    assert not report.ok
    assert report.reason == "math_mismatch"
    assert detect_magnitude_slip(report) is not None


def test_end_to_end_clean_pass_no_slip():
    auditor = FinancialAuditor()
    report = auditor.audit({
        "subtotal": "200.00",
        "tax": "30.00",
        "total_amount": "230.00",
    })
    assert report.ok
    assert detect_magnitude_slip(report) is None


def test_triangulation_identifies_subtotal_as_slipped_field():
    # subtotal=20 should have been 200. (total - tax) / subtotal = (230-30)/20 = 10
    report = _mismatch("20", "30", "230")
    msg = detect_magnitude_slip(report)
    assert msg is not None
    assert "decimal-point slip in subtotal" in msg
    assert "too small" in msg  # 20 is ~10x too small relative to total-tax


def test_triangulation_identifies_tax_as_slipped_field():
    # tax=3 should have been 30. (total - subtotal) / tax = (230-200)/3 = 10
    report = _mismatch("200", "3", "230")
    msg = detect_magnitude_slip(report)
    assert msg is not None
    assert "decimal-point slip in tax" in msg
    assert "too small" in msg


def test_triangulation_identifies_total_as_slipped_field():
    # total=2300 should have been 230. total / (subtotal + tax) = 2300/230 = 10
    report = _mismatch("200", "30", "2300")
    msg = detect_magnitude_slip(report)
    assert msg is not None
    assert "decimal-point slip in total" in msg
    assert "too large" in msg


def test_triangulation_subtotal_slip_end_to_end():
    auditor = FinancialAuditor()
    # subtotal $150 when it should be $1,500 — 10x too small
    report = auditor.audit({
        "subtotal": "$150.00",
        "tax": "$255.00",
        "total_amount": "$1,755.00",
    })
    assert not report.ok
    msg = detect_magnitude_slip(report)
    assert msg is not None
    assert "subtotal" in msg.lower()


def test_line_item_fallback_only_fires_when_top_level_triangulation_fails():
    # subtotal + tax = 230, total = 2300 → top-level catches total-slip.
    # Line item message should NOT appear because the specific field was found.
    report = _mismatch("200", "30", "2300")
    msg = detect_magnitude_slip(report, line_items=[{"total": "23000"}])
    assert msg is not None
    # Should still be the top-level message naming the exact field:
    assert "slip in total" in msg
    assert "line item" not in msg.lower()


def test_multi_field_error_returns_none_not_a_false_slip_diagnosis():
    # subtotal=150, tax=20, total=1500 → no single 10x factor explains it:
    # (1500-20)/150 = 9.87 (close but outside 5% of 10)
    # (1500-150)/20 = 67.5 (not a match)
    # 1500/170 = 8.82 (outside tolerance)
    report = _mismatch("150", "20", "1500")
    # This is genuinely noisy; guard should return None instead of a false slip.
    msg = detect_magnitude_slip(report)
    assert msg is None, (
        "Guard should not claim a specific slipped field when no single field "
        "accounts for the mismatch within tolerance"
    )


def test_end_to_end_total_10x_slip():
    auditor = FinancialAuditor()
    report = auditor.audit({
        "subtotal": "$1,500.00",
        "tax": "$255.00",
        "total_amount": "$17,550.00",  # should be 1,755 — 10x slip
    })
    assert not report.ok
    msg = detect_magnitude_slip(report)
    assert msg is not None


def test_auditor_node_passing_math_sets_is_valid_true():
    state = AgentState(
        document_id="doc-1",
        file_path="uploads/test.pdf",
        extracted_data=ExtractedInvoice(
            subtotal="200.00", tax="30.00", total_amount="230.00",
        ),
    )
    out = asyncio.run(auditor_node(state))
    assert out.is_valid is True
    assert out.reconciliation_guidance is None
    assert out.reason == "local_ok"
    assert len(out.audit_log) == 1
    assert out.audit_log[0]["stage"] == "audit"
    assert out.audit_log[0]["ok"] is True


def test_auditor_node_magnitude_slip_populates_reconciliation_guidance():
    state = AgentState(
        document_id="doc-2",
        file_path="uploads/test.pdf",
        extracted_data=ExtractedInvoice(
            subtotal="200.00", tax="30.00", total_amount="2300.00",
            line_items=[LineItem(description="widget", total="230.00")],
        ),
    )
    out = asyncio.run(auditor_node(state))
    assert out.is_valid is False
    assert out.reconciliation_guidance is not None
    assert "magnitude_error" in out.reconciliation_guidance
    assert out.reason == "local_audit_fail"
    assert out.audit_log[-1]["detail"]["magnitude"] == "magnitude_error"


def test_auditor_node_no_extracted_data_yields_full_extraction_guidance():
    state = AgentState(
        document_id="doc-3",
        file_path="uploads/test.pdf",
        extracted_data=None,
    )
    out = asyncio.run(auditor_node(state))
    assert out.is_valid is False
    assert out.reason == "local_audit_fail"
    # VLM-ready guidance must be actionable copy, not a machine code.
    guidance = out.reconciliation_guidance or ""
    assert len(guidance) > 80, "guidance should be a full sentence Gemini can act on"
    assert "Local OCR extraction was unavailable" in guidance
    assert "full extraction" in guidance.lower()
    assert "subtotal + tax" in guidance


def test_auditor_node_escalates_when_ocr_confidence_is_low():
    # Math balances cleanly but OCR confidence is below the 0.85 gate.
    # Without the gate, a balanced-but-wrong extraction would silently verify.
    state = AgentState(
        document_id="doc-conf",
        file_path="uploads/x.pdf",
        extracted_data=ExtractedInvoice(
            subtotal="200.00", tax="30.00", total_amount="230.00",
        ),
        ocr_confidence=0.58,
    )
    out = asyncio.run(auditor_node(state))
    assert out.is_valid is False, (
        "Math balanced but OCR confidence 0.58 < 0.85 — must escalate to Tier-2"
    )
    assert out.reason == "local_low_confidence"
    guidance = out.reconciliation_guidance or ""
    assert "low_ocr_confidence" in guidance
    assert "0.580" in guidance or "0.58" in guidance
    assert out.audit_log[-1]["detail"]["low_confidence"] is True


def test_auditor_node_escalates_on_partial_data():
    # Total is present but subtotal/tax missing. FinancialAuditor returns
    # ok=True with reason="partial_data", but we never actually verified
    # subtotal + tax == total. Must escalate so Tier-2 can find the missing data.
    state = AgentState(
        document_id="doc-partial",
        file_path="uploads/x.pdf",
        extracted_data=ExtractedInvoice(
            subtotal=None, tax=None, total_amount="230.00",
        ),
        ocr_confidence=0.92,  # confidence is fine; it's the data that's incomplete
    )
    out = asyncio.run(auditor_node(state))
    assert out.is_valid is False
    assert out.reason == "local_audit_fail"
    guidance = out.reconciliation_guidance or ""
    assert "partial_data" in guidance
    assert "subtotal" in guidance and "tax" in guidance
    assert out.audit_log[-1]["detail"]["partial_data"] is True


def test_auditor_node_high_confidence_full_data_still_verifies():
    # Regression guard for the happy path: the new gates must not break
    # the Tier-1 pass when everything is actually fine.
    state = AgentState(
        document_id="doc-clean",
        file_path="uploads/x.pdf",
        extracted_data=ExtractedInvoice(
            subtotal="200.00", tax="30.00", total_amount="230.00",
        ),
        ocr_confidence=0.92,
    )
    out = asyncio.run(auditor_node(state))
    assert out.is_valid is True
    assert out.reason == "local_ok"
    assert out.reconciliation_guidance is None


def test_auditor_node_accepts_partial_data_after_vlm_reconciliation():
    # Real-world case: a small-merchant receipt has no separate tax line —
    # tax is baked into the per-item price. PaddleOCR already failed, Gemini
    # reconciled and confidently returned tax=None. We must NOT loop
    # escalating back to Gemini asking the same question; accept that
    # "tax is genuinely absent" is a valid finding.
    state = AgentState(
        document_id="doc-vlm-partial",
        file_path="uploads/x.pdf",
        extracted_data=ExtractedInvoice(
            subtotal="3015.00", tax=None, total_amount="3015.00",
        ),
        ocr_confidence=0.87,  # Gemini-level confidence
        tier="vlm",           # already been through reconciler once
        attempts=1,
    )
    out = asyncio.run(auditor_node(state))
    assert out.is_valid is True, (
        "After VLM reconciliation, partial_data should be accepted — Gemini "
        "has already been asked and confidently returned tax=None. Looping "
        "would waste 15-20s per extra attempt with no benefit."
    )
    assert out.reason == "local_ok"


def test_auditor_node_low_confidence_after_vlm_is_not_re_escalated():
    # Gemini returned a low-confidence answer (rare but possible on hard
    # documents). Escalating to Gemini-again wouldn't help. Accept and move
    # to HITL via the downstream path, don't loop.
    state = AgentState(
        document_id="doc-vlm-lowconf",
        file_path="uploads/x.pdf",
        extracted_data=ExtractedInvoice(
            subtotal="200.00", tax="30.00", total_amount="230.00",
        ),
        ocr_confidence=0.55,  # low, but we're already on Tier-2
        tier="vlm",
        attempts=1,
    )
    out = asyncio.run(auditor_node(state))
    assert out.is_valid is True, (
        "Low confidence after VLM must not trigger another VLM retry — we've "
        "already asked the strongest model available."
    )


def test_auditor_node_partial_data_with_only_subtotal_missing_still_escalates():
    state = AgentState(
        document_id="doc-p2",
        file_path="uploads/x.pdf",
        extracted_data=ExtractedInvoice(
            subtotal=None, tax="30.00", total_amount="230.00",
        ),
        ocr_confidence=0.92,
    )
    out = asyncio.run(auditor_node(state))
    assert out.is_valid is False
    assert "subtotal" in (out.reconciliation_guidance or "")
    assert "tax" not in (out.reconciliation_guidance or "").split("missing ")[1].split(" —")[0]


def test_auditor_node_non_magnitude_mismatch_emits_vlm_ready_guidance():
    state = AgentState(
        document_id="doc-4",
        file_path="uploads/test.pdf",
        extracted_data=ExtractedInvoice(
            subtotal="200.00", tax="30.00", total_amount="235.00",
        ),
    )
    out = asyncio.run(auditor_node(state))
    assert out.is_valid is False
    guidance = out.reconciliation_guidance or ""
    assert "Math reconciliation failed" in guidance
    assert "magnitude_error" not in guidance
    # Full numeric context is in the guidance, no bare None leakage.
    assert "200.00" in guidance and "30.00" in guidance and "235.00" in guidance
    assert "None" not in guidance
    assert out.audit_log[-1]["detail"]["magnitude"] is None
