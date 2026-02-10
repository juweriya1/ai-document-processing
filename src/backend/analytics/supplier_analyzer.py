from sqlalchemy.orm import Session

from src.backend.db.crud import (
    get_all_supplier_metrics,
    get_corrections_by_document,
    get_extracted_fields,
    upsert_supplier_metric,
)
from src.backend.db.models import Document


def compute_supplier_metrics(db: Session) -> list[dict]:
    all_docs = db.query(Document).all()
    vendor_docs: dict[str, list[dict]] = {}

    for doc in all_docs:
        fields = get_extracted_fields(db, doc.id)
        vendor_field = next(
            (f for f in fields if f.field_name == "vendor_name"), None
        )
        if not vendor_field or not vendor_field.field_value:
            continue

        confidences = [f.confidence for f in fields if f.confidence is not None]
        avg_conf = sum(confidences) / len(confidences) if confidences else None
        corrections = get_corrections_by_document(db, doc.id)

        vendor_docs.setdefault(vendor_field.field_value, []).append({
            "document_id": doc.id,
            "status": doc.status,
            "avg_confidence": avg_conf,
            "correction_count": len(corrections),
        })

    results = []
    for vendor_name, docs in vendor_docs.items():
        total_documents = len(docs)
        confidences = [d["avg_confidence"] for d in docs if d["avg_confidence"] is not None]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        metric = upsert_supplier_metric(
            db,
            supplier_name=vendor_name,
            total_documents=total_documents,
            avg_confidence=round(avg_confidence, 4),
        )
        results.append({
            "supplier_name": vendor_name,
            "total_documents": total_documents,
            "avg_confidence": round(avg_confidence, 4),
            "risk_score": metric.risk_score,
            "total_corrections": sum(d["correction_count"] for d in docs),
        })

    return results


def get_supplier_list(db: Session) -> list[dict]:
    metrics = get_all_supplier_metrics(db)
    return [
        {
            "supplier_name": m.supplier_name,
            "total_documents": m.total_documents,
            "avg_confidence": m.avg_confidence,
            "risk_score": m.risk_score,
            "risk_level": _risk_level(m.risk_score),
        }
        for m in metrics
    ]


def _risk_level(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score < 30:
        return "low"
    if score < 60:
        return "medium"
    return "high"
