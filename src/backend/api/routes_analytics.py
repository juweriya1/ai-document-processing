from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.backend.analytics.aggregator import (
    get_compliance_breakdown,
    get_dashboard_summary,
    get_monthly_spend_trend,
    get_spend_breakdown_by_vendor,
    get_trust_overview,
)
from src.backend.analytics.anomaly_detector import detect_anomalies
from src.backend.analytics.insights_generator import generate_predictions
from src.backend.analytics.supplier_analyzer import (
    compute_supplier_metrics,
    get_supplier_list,
)
from src.backend.analytics.risk_scorer import score_suppliers
from src.backend.analytics.trust_engine import (
    compute_all_trust_scores,
    compute_trust_score,
)
from src.backend.analytics.vendor_risk import compute_vendor_risk_scores
from src.backend.analytics.widget_catalog import (
    catalog_for_role,
    default_layout_for_role,
    validate_layout,
)
from src.backend.auth.rbac import role_required
from src.backend.db import crud
from src.backend.db.database import get_db

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

_ALL_ROLES = ["enterprise_user", "admin", "reviewer"]
_PRIV_ROLES = ["reviewer", "admin"]


@router.get("/dashboard")
def dashboard(
    current_user: dict = Depends(role_required(_ALL_ROLES)),
    db: Session = Depends(get_db),
):
    summary = get_dashboard_summary(db)
    compliance = get_compliance_breakdown(db)
    anomalies = detect_anomalies(db)
    summary["anomaly_count"] = len(anomalies)
    summary["compliance"] = compliance
    return summary


@router.get("/spend/by-vendor")
def spend_by_vendor(
    current_user: dict = Depends(role_required(_ALL_ROLES)),
    db: Session = Depends(get_db),
):
    return get_spend_breakdown_by_vendor(db)


@router.get("/spend/by-month")
def spend_by_month(
    months: int = Query(default=12, ge=1, le=60),
    current_user: dict = Depends(role_required(_ALL_ROLES)),
    db: Session = Depends(get_db),
):
    return get_monthly_spend_trend(db, months=months)


@router.get("/trust/overview")
def trust_overview(
    current_user: dict = Depends(role_required(_ALL_ROLES)),
    db: Session = Depends(get_db),
):
    return get_trust_overview(db)


@router.get("/trust/document/{document_id}")
def trust_for_document(
    document_id: str,
    current_user: dict = Depends(role_required(_ALL_ROLES)),
    db: Session = Depends(get_db),
):
    return compute_trust_score(db, document_id)


@router.get("/trust/flagged")
def flagged_documents(
    current_user: dict = Depends(role_required(_ALL_ROLES)),
    db: Session = Depends(get_db),
):
    all_trust = compute_all_trust_scores(db)

    flagged = [
        d for d in all_trust
        if d["review_priority"] != "Auto-Approve Candidate"
    ]

    priority_order = {
        "Reject / Incomplete": 0,
        "Escalate": 1,
        "Needs Human Review": 2,
    }
    flagged.sort(key=lambda d: priority_order.get(d["review_priority"], 9))
    return flagged


@router.get("/vendor-risk")
def vendor_risk(
    current_user: dict = Depends(role_required(_PRIV_ROLES)),
    db: Session = Depends(get_db),
):
    return compute_vendor_risk_scores(db)


@router.get("/suppliers")
def suppliers(
    current_user: dict = Depends(role_required(_PRIV_ROLES)),
    db: Session = Depends(get_db),
):
    return get_supplier_list(db)


@router.post("/suppliers/refresh")
def refresh_suppliers(
    current_user: dict = Depends(role_required(["admin"])),
    db: Session = Depends(get_db),
):
    metrics = compute_supplier_metrics(db)
    scored = score_suppliers(db)
    return {
        "suppliers_updated": len(metrics),
        "risk_scores_computed": len(scored),
        "suppliers": scored,
    }


@router.get("/predictions")
def predictions(
    current_user: dict = Depends(role_required(_PRIV_ROLES)),
    db: Session = Depends(get_db),
):
    return generate_predictions(db)


@router.get("/anomalies")
def anomalies(
    current_user: dict = Depends(role_required(_PRIV_ROLES)),
    db: Session = Depends(get_db),
):
    return detect_anomalies(db)


class LayoutPayload(BaseModel):
    enabled: list[str]
    order: list[str]


@router.get("/widgets/catalog")
def widgets_catalog(
    current_user: dict = Depends(role_required(_ALL_ROLES)),
):
    return catalog_for_role(current_user["role"])


@router.get("/widgets/preferences")
def widgets_preferences(
    current_user: dict = Depends(role_required(_ALL_ROLES)),
    db: Session = Depends(get_db),
):
    saved = crud.get_user_insights_layout(db, current_user["user_id"])
    if saved:
        return saved
    return default_layout_for_role(current_user["role"])


@router.put("/widgets/preferences")
def save_widgets_preferences(
    payload: LayoutPayload,
    current_user: dict = Depends(role_required(_ALL_ROLES)),
    db: Session = Depends(get_db),
):
    layout = validate_layout(payload.enabled, payload.order, current_user["role"])
    crud.set_user_insights_layout(db, current_user["user_id"], layout)
    return layout


@router.get("/sla")
def sla_metrics(
    current_user: dict = Depends(role_required(_ALL_ROLES)),
    db: Session = Depends(get_db),
):
    from datetime import timedelta

    from src.backend.db.models import Document

    target = timedelta(hours=24)
    docs = db.query(Document).all()
    process_times = [
        (d.processed_at - d.uploaded_at).total_seconds()
        for d in docs
        if d.processed_at and d.uploaded_at
    ]
    approve_times = [
        (d.approved_at - d.uploaded_at).total_seconds()
        for d in docs
        if d.approved_at and d.uploaded_at
    ]
    breaches = sum(
        1 for d in docs
        if d.approved_at and d.uploaded_at and (d.approved_at - d.uploaded_at) > target
    )
    return {
        "avg_process_seconds": round(sum(process_times) / len(process_times), 2) if process_times else 0,
        "avg_approve_seconds": round(sum(approve_times) / len(approve_times), 2) if approve_times else 0,
        "breach_count":        breaches,
        "total_approved":      len(approve_times),
        "target_hours":        24,
    }


@router.get("/throughput")
def throughput(
    current_user: dict = Depends(role_required(_ALL_ROLES)),
    db: Session = Depends(get_db),
):
    from collections import Counter
    from datetime import datetime, timedelta, timezone

    from src.backend.db.models import Document

    start = datetime.now(timezone.utc) - timedelta(days=30)
    docs = (
        db.query(Document)
        .filter(Document.uploaded_at >= start)
        .all()
    )
    counts = Counter(
        d.uploaded_at.date().isoformat() for d in docs if d.uploaded_at
    )
    return sorted(
        [{"date": date, "count": count} for date, count in counts.items()],
        key=lambda row: row["date"],
    )


@router.get("/correction-patterns")
def correction_patterns(
    current_user: dict = Depends(role_required(_PRIV_ROLES)),
    db: Session = Depends(get_db),
):
    from collections import Counter

    cors = crud.list_all_corrections(db)
    counts = Counter(c.field.field_name for c in cors if c.field)
    return [
        {"field_name": name, "correction_count": count}
        for name, count in counts.most_common(10)
    ]


@router.get("/ocr-drift")
def ocr_drift(
    current_user: dict = Depends(role_required(_PRIV_ROLES)),
    db: Session = Depends(get_db),
):
    """Per-day average document-level confidence over last 30 days.

    If the Document model on this branch lacks a confidence_score column
    (some branches carry it, some don't), fall back to averaging per-document
    field confidences so the chart still has something to render.
    """
    from datetime import datetime, timedelta, timezone

    from src.backend.db.models import Document

    start = datetime.now(timezone.utc) - timedelta(days=30)
    docs = (
        db.query(Document)
        .filter(Document.uploaded_at >= start)
        .all()
    )

    by_day: dict[str, list[float]] = {}
    for d in docs:
        if not d.uploaded_at:
            continue
        score = getattr(d, "confidence_score", None)
        if score is None:
            fields = [f.confidence for f in (d.extracted_fields or []) if f.confidence is not None]
            if not fields:
                continue
            score = sum(fields) / len(fields)
        key = d.uploaded_at.date().isoformat()
        by_day.setdefault(key, []).append(float(score))

    return sorted(
        [
            {"date": date, "avg_confidence": round(sum(scores) / len(scores), 3)}
            for date, scores in by_day.items()
        ],
        key=lambda row: row["date"],
    )