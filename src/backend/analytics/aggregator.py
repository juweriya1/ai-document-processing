from sqlalchemy.orm import Session

from src.backend.db.crud import (
    get_documents_with_confidence_stats,
    get_processing_stats,
    get_spend_by_month,
    get_spend_by_vendor,
)


def get_dashboard_summary(db: Session) -> dict:
    stats = get_processing_stats(db)
    total_docs = sum(stats.values())
    vendor_spend = get_spend_by_vendor(db)
    total_spend = sum(v["total_spend"] for v in vendor_spend)

    doc_stats = get_documents_with_confidence_stats(db)
    confidences = [d["avg_confidence"] for d in doc_stats if d["avg_confidence"] is not None]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    approved = stats.get("approved", 0)
    rejected = stats.get("rejected", 0)
    reviewed = approved + rejected
    compliance_score = (approved / reviewed * 100) if reviewed > 0 else 0.0

    return {
        "total_documents": total_docs,
        "total_spend": round(total_spend, 2),
        "avg_confidence": round(avg_confidence, 4),
        "compliance_score": round(compliance_score, 2),
        "documents_by_status": stats,
    }


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
