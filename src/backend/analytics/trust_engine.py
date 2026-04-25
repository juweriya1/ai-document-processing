"""
Trust Engine
============
Computes a Document Trust Score (0–100) for every document in the DB.

Score formula (additive penalties from 100):
  – Low OCR confidence          → up to -30 pts   (weight: 30)
  – Invalid extracted fields    → up to -20 pts   (7 pts each, cap 20)
  – Missing required fields     → up to -25 pts   (8 pts each, cap 25)
  – Human corrections applied   → up to -15 pts   (5 pts each, cap 15)
  – Line-item / total mismatch  → -12 pts         (binary)
  – Very low confidence (<0.5)  → additional -8   (binary)

Each document also gets:
  – a reasons list (explainability)
  – a review_priority label
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.backend.db.crud import (
    get_corrections_by_document,
    get_extracted_fields,
    get_line_items,
)
from src.backend.db.models import Document

REQUIRED_FIELDS = {"invoice_number", "date", "vendor_name", "total_amount"}


def _line_item_mismatch(fields: list, line_items: list) -> bool:
    total_field = next((f for f in fields if f.field_name == "total_amount"), None)
    if not total_field or not total_field.field_value or not line_items:
        return False
    try:
        declared_total = float(total_field.field_value)
        items_sum = sum(li.total or 0.0 for li in line_items)
        return abs(items_sum - declared_total) >= 0.01
    except (ValueError, TypeError):
        return False


def compute_trust_score(db: Session, document_id: str) -> dict:
    """Return trust score dict for a single document."""
    fields = get_extracted_fields(db, document_id)
    line_items = get_line_items(db, document_id)
    corrections = get_corrections_by_document(db, document_id)

    reasons: list[str] = []
    penalties: dict[str, float] = {}

    # ── 1. OCR / extraction confidence ────────────────────────────────────
    confidences = [f.confidence for f in fields if f.confidence is not None]
    avg_conf = sum(confidences) / len(confidences) if confidences else None

    if avg_conf is None:
        confidence_penalty = 15.0
        reasons.append("Confidence data unavailable (no fields extracted)")
    else:
        raw = (1.0 - avg_conf) * 30.0
        confidence_penalty = min(30.0, max(0.0, raw))
        if confidence_penalty > 20:
            reasons.append(
                f"Low extraction confidence ({avg_conf * 100:.1f}%) — high OCR uncertainty"
            )
        elif confidence_penalty > 8:
            reasons.append(
                f"Moderate extraction confidence ({avg_conf * 100:.1f}%)"
            )

        if avg_conf < 0.5:
            penalties["very_low_confidence"] = 8.0
            reasons.append("Confidence critically below 50% — result reliability is low")

    penalties["low_confidence"] = confidence_penalty

    # ── 2. Invalid fields ─────────────────────────────────────────────────
    invalid_fields = [f for f in fields if f.status == "invalid"]
    invalid_penalty = min(20.0, len(invalid_fields) * 7.0)
    if invalid_fields:
        names = ", ".join(f.field_name for f in invalid_fields[:4])
        reasons.append(
            f"{len(invalid_fields)} invalid field(s): {names}"
        )
    penalties["invalid_fields"] = invalid_penalty

    # ── 3. Missing required fields ────────────────────────────────────────
    present_names = {f.field_name for f in fields if f.field_value and f.field_value.strip()}
    missing_required = REQUIRED_FIELDS - present_names
    missing_penalty = min(25.0, len(missing_required) * 8.0)
    if missing_required:
        reasons.append(f"Missing required field(s): {', '.join(sorted(missing_required))}")
    penalties["missing_required"] = missing_penalty

    # ── 4. Human corrections ──────────────────────────────────────────────
    correction_count = len(corrections)
    correction_penalty = min(15.0, correction_count * 5.0)
    if correction_count > 0:
        reasons.append(
            f"{correction_count} human correction(s) required during review"
        )
    penalties["corrections"] = correction_penalty

    # ── 5. Line-item / total mismatch ─────────────────────────────────────
    mismatch = _line_item_mismatch(fields, line_items)
    mismatch_penalty = 12.0 if mismatch else 0.0
    if mismatch:
        reasons.append("Line-item sum does not match declared invoice total")
    penalties["line_item_mismatch"] = mismatch_penalty

    # ── Final score ───────────────────────────────────────────────────────
    total_penalty = sum(penalties.values())
    score = max(0, min(100, round(100.0 - total_penalty)))

    # ── Review priority ───────────────────────────────────────────────────
    priority = _classify_priority(score, invalid_fields, missing_required, correction_count, mismatch)

    return {
        "document_id": document_id,
        "trust_score": score,
        "avg_confidence": round(avg_conf, 4) if avg_conf is not None else None,
        "invalid_field_count": len(invalid_fields),
        "missing_required_count": len(missing_required),
        "correction_count": correction_count,
        "line_item_mismatch": mismatch,
        "penalties": {k: round(v, 1) for k, v in penalties.items()},
        "reasons": reasons if reasons else ["All quality checks passed"],
        "review_priority": priority,
    }


def _classify_priority(
    trust_score: int,
    invalid_fields: list,
    missing_required: set,
    correction_count: int,
    line_item_mismatch: bool,
) -> str:
    # Hard reject: critical required fields missing or catastrophic score
    if len(missing_required) >= 2 or trust_score < 25:
        return "Reject / Incomplete"

    # Escalate: serious issues
    if (
        trust_score < 50
        or line_item_mismatch
        or len(invalid_fields) >= 2
        or correction_count >= 3
    ):
        return "Escalate"

    # Needs review: moderate issues
    if (
        trust_score < 80
        or len(invalid_fields) >= 1
        or correction_count >= 1
        or len(missing_required) >= 1
    ):
        return "Needs Human Review"

    # Clean document
    return "Auto-Approve Candidate"


def compute_all_trust_scores(db: Session) -> list[dict]:
    """Compute trust scores for all documents with extracted fields."""
    docs = db.query(Document).all()
    results = []
    for doc in docs:
        score_data = compute_trust_score(db, doc.id)
        score_data["filename"] = doc.original_filename
        score_data["status"] = doc.status
        score_data["uploaded_at"] = (
            doc.uploaded_at.isoformat() if doc.uploaded_at else None
        )
        results.append(score_data)
    return results


def get_trust_score_distribution(scores: list[dict]) -> list[dict]:
    """Bucket trust scores into ranges for histogram visualisation."""
    buckets = [
        {"label": "0–20 (Critical)", "range": (0, 20), "count": 0, "color": "#ef4444"},
        {"label": "21–40 (Poor)", "range": (21, 40), "count": 0, "color": "#f97316"},
        {"label": "41–60 (Fair)", "range": (41, 60), "count": 0, "color": "#eab308"},
        {"label": "61–80 (Good)", "range": (61, 80), "count": 0, "color": "#22c55e"},
        {"label": "81–100 (High)", "range": (81, 100), "count": 0, "color": "#38bdf8"},
    ]
    for doc in scores:
        s = doc.get("trust_score", 0)
        for b in buckets:
            lo, hi = b["range"]
            if lo <= s <= hi:
                b["count"] += 1
                break
    return buckets


def get_priority_distribution(scores: list[dict]) -> list[dict]:
    """Count documents per review priority label."""
    counts: dict[str, int] = {}
    for doc in scores:
        p = doc.get("review_priority", "Unknown")
        counts[p] = counts.get(p, 0) + 1

    priority_order = [
        ("Auto-Approve Candidate", "#22c55e"),
        ("Needs Human Review",     "#eab308"),
        ("Escalate",               "#f97316"),
        ("Reject / Incomplete",    "#ef4444"),
    ]
    return [
        {"label": label, "count": counts.get(label, 0), "color": color}
        for label, color in priority_order
    ]
