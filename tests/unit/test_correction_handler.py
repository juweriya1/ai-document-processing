import pytest

from src.backend.db.crud import (
    create_user,
    get_field_by_id,
    store_extracted_fields,
    update_field_validation_status,
)
from src.backend.validation.correction_handler import (
    get_document_corrections,
    get_validation_summary,
    submit_correction,
)


class TestSubmitCorrection:
    def test_submit_correction_updates_field(self, db_session, sample_document):
        fields = store_extracted_fields(db_session, sample_document.id, [
            {"field_name": "invoice_number", "field_value": "BAD-FORMAT", "confidence": 0.5},
        ])
        field = fields[0]
        update_field_validation_status(db_session, field.id, "invalid", "Bad format")

        result = submit_correction(
            db_session, sample_document.id, field.id, "INV-2025-0001",
        )
        assert result["original_value"] == "BAD-FORMAT"
        assert result["corrected_value"] == "INV-2025-0001"
        assert result["correction_id"].startswith("cor_")

        updated = get_field_by_id(db_session, field.id)
        assert updated.field_value == "INV-2025-0001"
        assert updated.status == "corrected"
        assert updated.error_message is None

    def test_submit_correction_with_reviewer(self, db_session, sample_document, sample_reviewer):
        fields = store_extracted_fields(db_session, sample_document.id, [
            {"field_name": "vendor_name", "field_value": "", "confidence": 0.3},
        ])
        field = fields[0]

        result = submit_correction(
            db_session, sample_document.id, field.id,
            "Acme Corp", reviewed_by=sample_reviewer.id,
        )
        assert result["corrected_value"] == "Acme Corp"

    def test_submit_correction_nonexistent_field_raises(self, db_session, sample_document):
        with pytest.raises(ValueError, match="not found"):
            submit_correction(db_session, sample_document.id, "fld_000000", "value")

    def test_submit_correction_wrong_document_raises(self, db_session, sample_document):
        fields = store_extracted_fields(db_session, sample_document.id, [
            {"field_name": "date", "field_value": "bad-date", "confidence": 0.5},
        ])
        with pytest.raises(ValueError, match="does not belong"):
            submit_correction(db_session, "doc_other", fields[0].id, "2025-01-01")

    def test_multiple_corrections_for_same_field(self, db_session, sample_document):
        fields = store_extracted_fields(db_session, sample_document.id, [
            {"field_name": "total_amount", "field_value": "abc", "confidence": 0.4},
        ])
        field = fields[0]

        submit_correction(db_session, sample_document.id, field.id, "100.00")
        submit_correction(db_session, sample_document.id, field.id, "200.00")

        updated = get_field_by_id(db_session, field.id)
        assert updated.field_value == "200.00"


class TestGetDocumentCorrections:
    def test_get_corrections_empty(self, db_session, sample_document):
        results = get_document_corrections(db_session, sample_document.id)
        assert results == []

    def test_get_corrections_after_submit(self, db_session, sample_document):
        fields = store_extracted_fields(db_session, sample_document.id, [
            {"field_name": "date", "field_value": "bad", "confidence": 0.5},
        ])
        submit_correction(db_session, sample_document.id, fields[0].id, "2025-06-01")

        results = get_document_corrections(db_session, sample_document.id)
        assert len(results) == 1
        assert results[0]["original_value"] == "bad"
        assert results[0]["corrected_value"] == "2025-06-01"
        assert results[0]["created_at"] is not None


class TestGetValidationSummary:
    def test_summary_all_valid(self, db_session, sample_document, sample_extracted_fields):
        for f in sample_extracted_fields:
            update_field_validation_status(db_session, f.id, "valid")

        summary = get_validation_summary(db_session, sample_document.id)
        assert summary["total_fields"] == 4
        assert summary["valid"] == 4
        assert summary["invalid"] == 0
        assert summary["all_resolved"] is True

    def test_summary_with_invalid_fields(self, db_session, sample_document, sample_extracted_fields):
        update_field_validation_status(db_session, sample_extracted_fields[0].id, "valid")
        update_field_validation_status(db_session, sample_extracted_fields[1].id, "invalid", "bad date")
        update_field_validation_status(db_session, sample_extracted_fields[2].id, "valid")
        update_field_validation_status(db_session, sample_extracted_fields[3].id, "corrected")

        summary = get_validation_summary(db_session, sample_document.id)
        assert summary["valid"] == 2
        assert summary["invalid"] == 1
        assert summary["corrected"] == 1
        assert summary["all_resolved"] is False

    def test_summary_empty_document(self, db_session, sample_document):
        summary = get_validation_summary(db_session, sample_document.id)
        assert summary["total_fields"] == 0
        assert summary["all_resolved"] is True
