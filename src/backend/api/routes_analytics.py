from fastapi import APIRouter, Depends, Query
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
from src.backend.auth.rbac import role_required
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