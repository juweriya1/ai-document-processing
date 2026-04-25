"""
BI feed endpoints. Feeds the Power BI .pbix at docs/powerbi/fyp_dashboard.pbix.
All rows are PII-free and safe for Publish-to-Web distribution.
"""
import csv
import io
import os

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from src.backend.analytics.trust_engine import compute_all_trust_scores
from src.backend.analytics.vendor_risk import compute_vendor_risk_scores
from src.backend.auth.rbac import role_required
from src.backend.db import crud
from src.backend.db.database import get_db

router = APIRouter(prefix="/api/bi", tags=["bi"])

_PRIV_ROLES = ["reviewer", "admin"]
_ALL_ROLES = ["enterprise_user", "reviewer", "admin"]


def _extract_field(doc, name):
    for f in (doc.extracted_fields or []):
        if f.field_name == name:
            return f.field_value
    return None


def _extract_amount(doc):
    v = _extract_field(doc, "total_amount")
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "").replace("$", ""))
    except (ValueError, TypeError):
        return None


def _build_invoice_rows(db: Session) -> list[dict]:
    trust_by_id = {t["document_id"]: t for t in compute_all_trust_scores(db)}
    docs = crud.list_documents(db, skip=0, limit=10000)
    rows = []
    for d in docs:
        t = trust_by_id.get(d.id, {})
        rows.append({
            "document_id":     d.id,
            "filename":        d.original_filename,
            "status":          d.status,
            "uploaded_at":     d.uploaded_at.isoformat() if d.uploaded_at else None,
            "processed_at":    d.processed_at.isoformat() if d.processed_at else None,
            "approved_at":     d.approved_at.isoformat() if d.approved_at else None,
            "vendor_name":     _extract_field(d, "vendor_name"),
            "total_amount":    _extract_amount(d),
            "trust_score":     t.get("trust_score"),
            "review_priority": t.get("review_priority"),
            "fallback_tier":   getattr(d, "fallback_tier", None),
            "doc_confidence":  getattr(d, "confidence_score", None),
        })
    return rows


@router.get("/invoices.json")
def bi_invoices_json(
    _current=Depends(role_required(_PRIV_ROLES)),
    db: Session = Depends(get_db),
):
    return _build_invoice_rows(db)


@router.get("/line-items.json")
def bi_line_items_json(
    _current=Depends(role_required(_PRIV_ROLES)),
    db: Session = Depends(get_db),
):
    items = crud.list_all_line_items(db)
    return [
        {
            "document_id": li.document_id,
            "description": li.description,
            "quantity":    li.quantity,
            "unit_price":  li.unit_price,
            "total":       li.total,
        }
        for li in items
    ]


@router.get("/corrections.json")
def bi_corrections_json(
    _current=Depends(role_required(_PRIV_ROLES)),
    db: Session = Depends(get_db),
):
    cors = crud.list_all_corrections(db)
    return [
        {
            "document_id":     c.document_id,
            "field_name":      c.field.field_name if c.field else None,
            "original_value":  c.original_value,
            "corrected_value": c.corrected_value,
            "reviewed_by":     c.reviewed_by,
            "created_at":      c.created_at.isoformat() if c.created_at else None,
        }
        for c in cors
    ]


@router.get("/vendor-risk.json")
def bi_vendor_risk_json(
    _current=Depends(role_required(_PRIV_ROLES)),
    db: Session = Depends(get_db),
):
    return compute_vendor_risk_scores(db)


@router.get("/invoices.csv")
def bi_invoices_csv(
    _current=Depends(role_required(_PRIV_ROLES)),
    db: Session = Depends(get_db),
):
    rows = _build_invoice_rows(db)
    if not rows:
        return Response("", media_type="text/csv")
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return Response(buf.getvalue(), media_type="text/csv")


@router.get("/config")
def bi_config(
    _current=Depends(role_required(_ALL_ROLES)),
):
    return {
        "power_bi_embed_url": os.getenv("POWER_BI_PUBLIC_URL") or None,
        "last_refreshed_at":  os.getenv("POWER_BI_LAST_REFRESH") or None,
        "refresh_cadence":    "manual (free tier Publish-to-Web)",
    }
