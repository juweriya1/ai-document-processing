"""
Vendor Risk Engine
==================
Computes a Vendor Risk Score (0–100) for every vendor found in approved/
reviewed documents.  Higher score = higher risk.

Risk dimensions (all derived from real DB records):

  1. Correction Rate       – avg corrections per document          → up to 25 pts
  2. Invalid Field Rate    – share of docs with ≥1 invalid field   → up to 25 pts
  3. Low-Trust Rate        – share of docs with trust_score < 50   → up to 20 pts
  4. Amount Volatility     – coefficient of variation of invoice $  → up to 20 pts
  5. Missing Field Rate    – share of docs missing required fields  → up to 10 pts

Explainability: every vendor receives a reasons list.
"""

from __future__ import annotations

import numpy as np
from sqlalchemy.orm import Session

from src.backend.analytics.trust_engine import compute_trust_score
from src.backend.db.crud import (
    get_corrections_by_document,
    get_extracted_fields,
)
from src.backend.db.models import Document

REQUIRED_FIELDS = {"invoice_number", "date", "vendor_name", "total_amount"}


def _safe_cv(values: list[float]) -> float:
    """Coefficient of variation; 0 if not enough data."""
    arr = [v for v in values if v > 0]
    if len(arr) < 2:
        return 0.0
    mean = np.mean(arr)
    std = np.std(arr)
    return float(std / mean) if mean > 0 else 0.0


def _vendor_name_for_doc(fields: list) -> str | None:
    vendor_field = next((f for f in fields if f.field_name == "vendor_name"), None)
    if vendor_field and vendor_field.field_value:
        return vendor_field.field_value.strip()
    return None


def _amount_for_doc(fields: list) -> float | None:
    amount_field = next((f for f in fields if f.field_name == "total_amount"), None)
    if amount_field and amount_field.field_value:
        try:
            return float(amount_field.field_value)
        except (ValueError, TypeError):
            pass
    return None


def compute_vendor_risk_scores(db: Session) -> list[dict]:
    """Aggregate all documents by vendor and compute risk scores."""
    all_docs = db.query(Document).all()

    # Group docs by vendor
    vendor_groups: dict[str, list[dict]] = {}
    for doc in all_docs:
        fields = get_extracted_fields(db, doc.id)
        vendor = _vendor_name_for_doc(fields)
        if not vendor:
            continue

        corrections = get_corrections_by_document(db, doc.id)
        trust_data = compute_trust_score(db, doc.id)
        amount = _amount_for_doc(fields)

        invalid_count = sum(1 for f in fields if f.status == "invalid")
        present_names = {
            f.field_name for f in fields if f.field_value and f.field_value.strip()
        }
        missing_required_count = len(REQUIRED_FIELDS - present_names)

        vendor_groups.setdefault(vendor, []).append(
            {
                "document_id": doc.id,
                "filename": doc.original_filename,
                "status": doc.status,
                "correction_count": len(corrections),
                "invalid_field_count": invalid_count,
                "missing_required_count": missing_required_count,
                "trust_score": trust_data["trust_score"],
                "amount": amount,
            }
        )

    results = []
    for vendor_name, docs in vendor_groups.items():
        results.append(_score_vendor(vendor_name, docs))

    # Sort by risk descending
    results.sort(key=lambda x: x["risk_score"], reverse=True)
    return results


def _score_vendor(vendor_name: str, docs: list[dict]) -> dict:
    total = len(docs)
    reasons: list[str] = []
    penalties: dict[str, float] = {}

    # ── 1. Correction Rate ────────────────────────────────────────────────
    total_corrections = sum(d["correction_count"] for d in docs)
    avg_corrections = total_corrections / total
    correction_penalty = min(25.0, avg_corrections * 12.0)
    if avg_corrections >= 2:
        reasons.append(
            f"High correction rate: avg {avg_corrections:.1f} corrections per document"
        )
    elif avg_corrections >= 1:
        reasons.append(
            f"Repeated human corrections: avg {avg_corrections:.1f} per document"
        )
    penalties["correction_rate"] = round(correction_penalty, 2)

    # ── 2. Invalid Field Rate ─────────────────────────────────────────────
    docs_with_invalid = sum(1 for d in docs if d["invalid_field_count"] > 0)
    invalid_rate = docs_with_invalid / total
    invalid_penalty = min(25.0, invalid_rate * 25.0)
    if invalid_rate >= 0.5:
        reasons.append(
            f"{docs_with_invalid}/{total} documents had invalid fields ({invalid_rate*100:.0f}%)"
        )
    elif invalid_rate > 0:
        reasons.append(f"Some documents contained invalid fields ({invalid_rate*100:.0f}%)")
    penalties["invalid_field_rate"] = round(invalid_penalty, 2)

    # ── 3. Low-Trust Rate ─────────────────────────────────────────────────
    docs_low_trust = sum(1 for d in docs if d["trust_score"] < 50)
    low_trust_rate = docs_low_trust / total
    low_trust_penalty = min(20.0, low_trust_rate * 20.0)
    if docs_low_trust > 0:
        reasons.append(
            f"{docs_low_trust}/{total} documents scored below 50 on trust"
        )
    penalties["low_trust_rate"] = round(low_trust_penalty, 2)

    # ── 4. Amount Volatility ──────────────────────────────────────────────
    amounts = [d["amount"] for d in docs if d["amount"] is not None]
    cv = _safe_cv(amounts)
    amount_penalty = min(20.0, cv * 20.0)
    if cv > 0.5:
        reasons.append(
            f"High invoice amount variability (CV={cv:.2f}) — possible duplicate or outlier invoices"
        )
    elif cv > 0.3:
        reasons.append(f"Moderate invoice amount variability (CV={cv:.2f})")
    penalties["amount_volatility"] = round(amount_penalty, 2)

    # ── 5. Missing Required Field Rate ───────────────────────────────────
    docs_missing = sum(1 for d in docs if d["missing_required_count"] > 0)
    missing_rate = docs_missing / total
    missing_penalty = min(10.0, missing_rate * 10.0)
    if docs_missing > 0:
        reasons.append(
            f"{docs_missing}/{total} documents had missing required fields"
        )
    penalties["missing_field_rate"] = round(missing_penalty, 2)

    total_penalty = sum(penalties.values())
    risk_score = max(0, min(100, round(total_penalty)))

    risk_level = _risk_level(risk_score)
    recommended_action = _recommended_action(risk_score, reasons)

    return {
        "vendor_name": vendor_name,
        "total_documents": total,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "avg_trust_score": round(
            sum(d["trust_score"] for d in docs) / total, 1
        ),
        "total_corrections": total_corrections,
        "penalty_breakdown": penalties,
        "reasons": reasons if reasons else ["No significant risk signals detected"],
        "recommended_action": recommended_action,
        "document_ids": [d["document_id"] for d in docs],
    }


def _risk_level(score: float) -> str:
    if score < 30:
        return "low"
    if score < 60:
        return "medium"
    return "high"


def _recommended_action(score: float, reasons: list[str]) -> str:
    if score >= 70:
        return "Escalate for compliance review — multiple risk factors present"
    if score >= 50:
        return "Flag for senior reviewer — moderate risk detected"
    if score >= 30:
        return "Standard review recommended"
    return "Low risk — standard processing"
