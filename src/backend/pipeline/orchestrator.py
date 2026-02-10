from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.backend.db.crud import (
    get_document,
    store_extracted_fields,
    store_line_items,
    update_document_status,
)
from src.backend.validation.schema_validator import validate_document_fields


class ExtractorInterface:
    def extract(self, document_id: str, filename: str) -> tuple[list[dict], list[dict]]:
        raise NotImplementedError


class MockExtractor(ExtractorInterface):
    def extract(self, document_id: str, filename: str) -> tuple[list[dict], list[dict]]:
        fields = [
            {"field_name": "invoice_number", "field_value": "INV-2025-0001", "confidence": 0.95},
            {"field_name": "date", "field_value": "2025-01-15", "confidence": 0.92},
            {"field_name": "vendor_name", "field_value": "Acme Corporation", "confidence": 0.90},
            {"field_name": "total_amount", "field_value": "2450.00", "confidence": 0.88},
        ]
        line_items = [
            {"description": "Widget A", "quantity": 10, "unit_price": 100.00, "total": 1000.00},
            {"description": "Widget B", "quantity": 5, "unit_price": 200.00, "total": 1000.00},
            {"description": "Shipping", "quantity": 1, "unit_price": 450.00, "total": 450.00},
        ]
        return fields, line_items


class PipelineOrchestrator:
    def __init__(self, db: Session, extractor: ExtractorInterface | None = None):
        self.db = db
        self.extractor = extractor or MockExtractor()

    def process_document(self, document_id: str) -> dict:
        doc = get_document(self.db, document_id)
        if doc is None:
            raise ValueError(f"Document {document_id} not found")

        if doc.status not in ("uploaded", "failed"):
            raise ValueError(
                f"Document {document_id} cannot be processed (status: {doc.status})"
            )

        update_document_status(self.db, document_id, "preprocessing")
        update_document_status(self.db, document_id, "extracting")

        fields_data, line_items_data = self.extractor.extract(document_id, doc.filename)

        stored_fields = store_extracted_fields(self.db, document_id, fields_data)
        stored_items = store_line_items(self.db, document_id, line_items_data)

        update_document_status(self.db, document_id, "validating")

        validation_results = validate_document_fields(self.db, document_id)

        has_invalid = any(r["status"] == "invalid" for r in validation_results)
        final_status = "review_pending" if has_invalid else "review_pending"

        update_document_status(self.db, document_id, final_status)

        doc.processed_at = datetime.now(timezone.utc)
        self.db.commit()

        return {
            "document_id": document_id,
            "status": final_status,
            "fields_extracted": len(stored_fields),
            "line_items_extracted": len(stored_items),
            "validation_results": validation_results,
        }

    def get_document_status(self, document_id: str) -> dict:
        doc = get_document(self.db, document_id)
        if doc is None:
            raise ValueError(f"Document {document_id} not found")

        return {
            "document_id": doc.id,
            "filename": doc.original_filename,
            "status": doc.status,
            "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
        }
