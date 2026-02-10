from sqlalchemy.orm import Session

from src.backend.db.crud import (
    create_correction,
    get_corrections_by_document,
    get_extracted_fields,
    get_field_by_id,
    update_field_validation_status,
    update_field_value,
)


def submit_correction(
    db: Session,
    document_id: str,
    field_id: str,
    corrected_value: str,
    reviewed_by: str | None = None,
) -> dict:
    field = get_field_by_id(db, field_id)
    if field is None:
        raise ValueError(f"Field {field_id} not found")
    if field.document_id != document_id:
        raise ValueError(f"Field {field_id} does not belong to document {document_id}")

    original_value = field.field_value
    correction = create_correction(
        db,
        document_id=document_id,
        field_id=field_id,
        original_value=original_value,
        corrected_value=corrected_value,
        reviewed_by=reviewed_by,
    )

    update_field_value(db, field_id, corrected_value)
    update_field_validation_status(db, field_id, "corrected", None)

    return {
        "correction_id": correction.id,
        "field_id": field_id,
        "original_value": original_value,
        "corrected_value": corrected_value,
    }


def get_document_corrections(db: Session, document_id: str) -> list[dict]:
    corrections = get_corrections_by_document(db, document_id)
    return [
        {
            "id": c.id,
            "field_id": c.field_id,
            "original_value": c.original_value,
            "corrected_value": c.corrected_value,
            "reviewed_by": c.reviewed_by,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in corrections
    ]


def get_validation_summary(db: Session, document_id: str) -> dict:
    fields = get_extracted_fields(db, document_id)
    total = len(fields)
    valid = sum(1 for f in fields if f.status == "valid")
    invalid = sum(1 for f in fields if f.status == "invalid")
    corrected = sum(1 for f in fields if f.status == "corrected")
    pending = sum(1 for f in fields if f.status == "pending")

    return {
        "total_fields": total,
        "valid": valid,
        "invalid": invalid,
        "corrected": corrected,
        "pending": pending,
        "all_resolved": invalid == 0 and pending == 0,
    }
