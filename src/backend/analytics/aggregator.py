from sqlalchemy.orm import Session

from src.backend.analytics.trust_engine import (
    compute_all_trust_scores,
    get_priority_distribution,
    get_trust_score_distribution,
)
from src.backend.db.crud import (
    get_documents_with_confidence_stats,
    get_processing_stats,
    get_spend_by_month,
    get_spend_by_vendor,
)
from src.backend.db.models import ExtractedField


def get_dashboard_summary(db: Session) -> dict:
    stats = get_processing_stats(db)
    total_docs = sum(stats.values())

    vendor_spend = get_spend_by_vendor(db)
    total_spend = sum(v["total_spend"] for v in vendor_spend)

    all_trust = compute_all_trust_scores(db)
    trust_scores = [d["trust_score"] for d in all_trust]
    avg_trust = round(sum(trust_scores) / len(trust_scores), 1) if trust_scores else None

    from src.backend.analytics.vendor_risk import compute_vendor_risk_scores
    vendor_risks = compute_vendor_risk_scores(db)
    high_risk_vendors = [v for v in vendor_risks if v["risk_level"] == "high"]

    needs_review = [
        d for d in all_trust if d["review_priority"] != "Auto-Approve Candidate"
    ]
    escalations = [d for d in all_trust if d["review_priority"] == "Escalate"]
    rejects = [d for d in all_trust if d["review_priority"] == "Reject / Incomplete"]
    compliance_exceptions = [d for d in all_trust if d["invalid_field_count"] > 0]
    validation_breakdown = _get_validation_breakdown(db)

    if total_docs > 0:
        compliance_score = round(
            (total_docs - len(compliance_exceptions)) / total_docs * 100, 2
        )
    else:
        compliance_score = 0.0

    doc_confidence_stats = get_documents_with_confidence_stats(db)
    confidences = [d["avg_confidence"] for d in doc_confidence_stats if d.get("avg_confidence") is not None]
    avg_confidence = round(sum(confidences) / len(confidences), 3) if confidences else 0.0

    return {
        "total_documents": total_docs,
        "total_spend": round(total_spend, 2),
        "avg_trust_score": avg_trust,
        "avg_confidence": avg_confidence,
        "compliance_score": compliance_score,
        "high_risk_vendor_count": len(high_risk_vendors),
        "docs_requiring_review": len(needs_review),
        "escalation_count": len(escalations),
        "reject_count": len(rejects),
        "compliance_exception_count": len(compliance_exceptions),
        "documents_by_status": stats,
        "validation_failure_breakdown": validation_breakdown,
    }


def _get_validation_breakdown(db: Session) -> list[dict]:
    invalid_fields = (
        db.query(ExtractedField)
        .filter(ExtractedField.status == "invalid")
        .all()
    )
    counts: dict[str, int] = {}
    for f in invalid_fields:
        counts[f.field_name] = counts.get(f.field_name, 0) + 1
    return [
        {"field_name": k, "count": v}
        for k, v in sorted(counts.items(), key=lambda x: -x[1])
    ]


def get_spend_breakdown_by_vendor(db: Session) -> list[dict]:
    return get_spend_by_vendor(db)


def get_monthly_spend_trend(db: Session, months: int = 12) -> list[dict]:
    all_months = get_spend_by_month(db)
    return all_months[-months:] if len(all_months) > months else all_months


def get_compliance_breakdown(db: Session) -> dict:
    doc_stats = get_documents_with_confidence_stats(db)
    total = len(doc_stats)
    if total == 0:
        return {
            "total_documents": 0,
            "with_corrections": 0,
            "without_corrections": 0,
            "correction_rate": 0.0,
            "avg_corrections_per_document": 0.0,
        }

    with_corrections = sum(1 for d in doc_stats if d["correction_count"] > 0)
    total_corrections = sum(d["correction_count"] for d in doc_stats)

    return {
        "total_documents": total,
        "with_corrections": with_corrections,
        "without_corrections": total - with_corrections,
        "correction_rate": round(with_corrections / total * 100, 2),
        "avg_corrections_per_document": round(total_corrections / total, 2),
    }


def get_trust_overview(db: Session) -> dict:
    all_trust = compute_all_trust_scores(db)
    if not all_trust:
        return {
            "documents": [],
            "trust_distribution": get_trust_score_distribution([]),
            "priority_distribution": get_priority_distribution([]),
            "avg_trust_score": None,
            "message": "No documents processed yet.",
        }

    trust_scores = [d["trust_score"] for d in all_trust]
    avg_trust = round(sum(trust_scores) / len(trust_scores), 1)

    return {
        "documents": all_trust,
        "trust_distribution": get_trust_score_distribution(all_trust),
        "priority_distribution": get_priority_distribution(all_trust),
        "avg_trust_score": avg_trust,
    }