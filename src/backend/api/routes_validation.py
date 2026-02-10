from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.backend.auth.rbac import role_required
from src.backend.db.crud import (
    get_document,
    get_extracted_fields,
    update_document_status,
)
from src.backend.db.database import get_db
from src.backend.validation.correction_handler import (
    get_document_corrections,
    get_validation_summary,
    submit_correction,
)
from src.backend.validation.schema_validator import validate_document_fields

router = APIRouter(prefix="/api/documents", tags=["validation"])


class FieldResponse(BaseModel):
    id: str
    fieldName: str
    fieldValue: str | None
    confidence: float | None
    status: str
    errorMessage: str | None


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
    current_user: dict = Depends(role_required(["enterprise_user", "admin", "reviewer"])),
    db: Session = Depends(get_db),
):
    doc = get_document(db, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    fields = get_extracted_fields(db, document_id)
    return [
        FieldResponse(
            id=f.id,
            fieldName=f.field_name,
            fieldValue=f.field_value,
            confidence=f.confidence,
            status=f.status,
            errorMessage=f.error_message,
        )
        for f in fields
    ]


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
    current_user: dict = Depends(role_required(["reviewer", "admin"])),
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
