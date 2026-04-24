from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.backend.auth.rbac import role_required
from src.backend.db.crud import (
    get_document,
    get_extracted_fields,
    update_document_status,
)
from src.backend.db.database import get_db
from src.backend.pipeline.confidence_calibrator import ConfidenceCalibrator
from src.backend.pipeline.hitl_policy import (
    criticality as field_criticality,
    effective_threshold,
    review_reason,
    risk_score,
)
from src.backend.validation.correction_handler import (
    get_document_corrections,
    get_validation_summary,
    submit_correction,
)
from src.backend.validation.schema_validator import validate_document_fields

CALIBRATOR_PATH = "adapters/calibrator_thresholds.json"

router = APIRouter(prefix="/api/documents", tags=["validation"])


class FieldResponse(BaseModel):
    id: str
    fieldName: str
    fieldValue: str | None
    confidence: float | None
    status: str
    errorMessage: str | None
    riskScore: float | None = None
    reviewReason: str | None = None
    criticality: float | None = None
    effectiveThreshold: float | None = None


class CorrectionRequest(BaseModel):
    fieldId: str
    correctedValue: str


class CorrectionResponse(BaseModel):
    correctionId: str
    fieldId: str
    originalValue: str | None
    correctedValue: str


class RejectRequest(BaseModel):
    reason: str


@router.get("/{document_id}/fields", response_model=list[FieldResponse])
def get_fields(
    document_id: str,
    hitl: bool = Query(False, description="Only return fields that need human review"),
    current_user: dict = Depends(role_required(["enterprise_user", "admin", "reviewer"])),
    db: Session = Depends(get_db),
):
    doc = get_document(db, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    all_fields = get_extracted_fields(db, document_id)

    calibrator = ConfidenceCalibrator()
    try:
        calibrator.load(CALIBRATOR_PATH)
    except FileNotFoundError:
        pass  # no calibration data yet — falls back to criticality floor

    # Score every field, then let the policy decide which to queue.
    annotated = []
    for f in all_fields:
        thr = effective_threshold(f.field_name, calibrator.threshold(f.field_name))
        rs = risk_score(f.field_name, f.confidence)
        needs_review = (
            f.status == "invalid"
            or f.confidence is None
            or f.confidence < thr
        )
        annotated.append(
            {
                "field": f,
                "threshold": thr,
                "risk": rs,
                "needs_review": needs_review,
                "reason": review_reason(f.status, f.confidence, f.field_name)
                if needs_review
                else "auto_approved",
            }
        )

    if hitl:
        # Highest-risk items first so reviewers tackle what matters most.
        selected = sorted(
            [a for a in annotated if a["needs_review"]],
            key=lambda a: (
                float("inf") if a["risk"] == float("inf") else a["risk"]
            ),
            reverse=True,
        )
    else:
        selected = annotated

    # Residual-error estimate: expected cost of the fields we skipped.
    expected_residual = sum(
        a["risk"] for a in annotated
        if not a["needs_review"] and a["risk"] != float("inf")
    )

    total = len(all_fields)
    shown = len(selected) if hitl else total

    def _serialize_risk(r: float) -> float | None:
        return None if r == float("inf") else round(r, 4)

    response_fields = [
        FieldResponse(
            id=a["field"].id,
            fieldName=a["field"].field_name,
            fieldValue=a["field"].field_value,
            confidence=a["field"].confidence,
            status=a["field"].status,
            errorMessage=a["field"].error_message,
            riskScore=_serialize_risk(a["risk"]),
            reviewReason=a["reason"],
            criticality=field_criticality(a["field"].field_name),
            effectiveThreshold=round(a["threshold"], 4),
        )
        for a in selected
    ]

    return JSONResponse(
        content=[r.model_dump() for r in response_fields],
        headers={
            "X-HITL-Total-Fields": str(total),
            "X-HITL-Shown-Fields": str(shown),
            "X-HITL-Skipped-Fields": str(total - shown),
            "X-HITL-Expected-Residual-Errors": f"{expected_residual:.3f}",
            "Access-Control-Expose-Headers": (
                "X-HITL-Total-Fields, X-HITL-Shown-Fields, "
                "X-HITL-Skipped-Fields, X-HITL-Expected-Residual-Errors"
            ),
        },
    )


@router.post("/{document_id}/validate")
def validate_fields(
    document_id: str,
    current_user: dict = Depends(role_required(["reviewer", "admin"])),
    db: Session = Depends(get_db),
):
    doc = get_document(db, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    results = validate_document_fields(db, document_id)
    summary = get_validation_summary(db, document_id)
    return {"results": results, "summary": summary}


@router.post("/{document_id}/corrections", response_model=CorrectionResponse)
def submit_field_correction(
    document_id: str,
    req: CorrectionRequest,
    current_user: dict = Depends(role_required(["enterprise_user", "reviewer", "admin"])),
    db: Session = Depends(get_db),
):
    doc = get_document(db, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    try:
        result = submit_correction(
            db, document_id, req.fieldId, req.correctedValue,
            reviewed_by=current_user.get("user_id"),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Auto-calibrate every 10 corrections to keep thresholds fresh
    from src.backend.db.models import Correction
    correction_count = db.query(Correction).count()
    if correction_count % 10 == 0:
        try:
            calibrator = ConfidenceCalibrator()
            calibrator.fit(db)
            calibrator.save(CALIBRATOR_PATH)
        except Exception:
            pass  # calibration is best-effort, never block the correction

    return CorrectionResponse(
        correctionId=result["correction_id"],
        fieldId=result["field_id"],
        originalValue=result["original_value"],
        correctedValue=result["corrected_value"],
    )


@router.get("/{document_id}/corrections")
def get_corrections(
    document_id: str,
    current_user: dict = Depends(role_required(["reviewer", "admin"])),
    db: Session = Depends(get_db),
):
    doc = get_document(db, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return get_document_corrections(db, document_id)


@router.post("/{document_id}/approve")
def approve_document(
    document_id: str,
    current_user: dict = Depends(role_required(["reviewer", "admin"])),
    db: Session = Depends(get_db),
):
    doc = get_document(db, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    summary = get_validation_summary(db, document_id)
    if not summary["all_resolved"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve: {summary['invalid']} invalid and {summary['pending']} pending fields remain",
        )

    doc.status = "approved"
    doc.approved_by = current_user.get("user_id")
    doc.approved_at = datetime.now(timezone.utc)
    db.commit()

    return {"document_id": document_id, "status": "approved"}


@router.post("/{document_id}/reject")
def reject_document(
    document_id: str,
    req: RejectRequest,
    current_user: dict = Depends(role_required(["reviewer", "admin"])),
    db: Session = Depends(get_db),
):
    doc = get_document(db, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    doc.status = "rejected"
    doc.rejected_reason = req.reason
    db.commit()

    return {"document_id": document_id, "status": "rejected", "reason": req.reason}
