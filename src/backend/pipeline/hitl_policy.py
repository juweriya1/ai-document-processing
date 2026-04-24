"""hitl_policy.py — Risk-aware field selection for human review.

Reframes HITL as a selective-verification decision problem:
  - Each field has a confidence p (predicted correctness probability) and
    a criticality weight w (cost if wrong).
  - Expected loss if a field is skipped = (1 - p) * w.
  - A field is queued for review iff its expected loss exceeds a risk
    budget, or if validation already flagged it invalid.

Two policy levers:
  1. Per-field criticality (total_amount matters more than a note field).
  2. Global risk budget (how much residual error we tolerate per unit
     criticality). The effective confidence threshold for field f is
     t(f) = max(learned_threshold(f), 1 - risk_budget / criticality(f)),
     so critical fields are auto-approved only at very high confidence
     even before the calibrator has enough correction history.
"""
from __future__ import annotations

import os

# Per-field criticality weights. Higher = larger cost if wrong.
FIELD_CRITICALITY: dict[str, float] = {
    "total_amount": 5.0,
    "invoice_number": 4.0,
    "date": 3.0,
    "vendor_name": 2.0,
}
DEFAULT_CRITICALITY = 1.0

# Residual error we tolerate per unit criticality. At 0.10:
#   plain field (w=1) -> threshold 0.90
#   vendor_name (w=2) -> threshold 0.95
#   date        (w=3) -> threshold 0.967
#   invoice_no  (w=4) -> threshold 0.975
#   total_amt   (w=5) -> threshold 0.98
DEFAULT_RISK_BUDGET = float(os.getenv("HITL_RISK_BUDGET", "0.10"))


def criticality(field_name: str) -> float:
    return FIELD_CRITICALITY.get(field_name, DEFAULT_CRITICALITY)


def risk_score(field_name: str, confidence: float | None) -> float:
    """Expected loss if this field is not shown for review.

    Missing confidence is treated as maximum risk (must review).
    """
    if confidence is None:
        return float("inf")
    return max(0.0, 1.0 - confidence) * criticality(field_name)


def criticality_floor_threshold(
    field_name: str, risk_budget: float = DEFAULT_RISK_BUDGET
) -> float:
    """Minimum confidence to skip review, purely from criticality."""
    w = criticality(field_name)
    return max(0.0, min(0.99, 1.0 - (risk_budget / w)))


def effective_threshold(
    field_name: str,
    learned_threshold: float,
    risk_budget: float = DEFAULT_RISK_BUDGET,
) -> float:
    """Combine learned calibration with the criticality-based floor.

    We always demand the stricter of the two so critical fields are not
    auto-approved just because the correction history is thin.
    """
    return max(learned_threshold, criticality_floor_threshold(field_name, risk_budget))


def review_reason(
    status: str,
    confidence: float | None,
    field_name: str,
) -> str:
    """Short tag explaining why a field was queued for review."""
    if status == "invalid":
        return "validation_failed"
    if confidence is None:
        return "missing_confidence"
    if criticality(field_name) > DEFAULT_CRITICALITY:
        return "critical_field"
    return "low_confidence"
