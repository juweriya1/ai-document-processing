import pytest

from src.backend.db.crud import store_extracted_fields, store_line_items
from src.backend.validation.schema_validator import (
    validate_document_fields,
    validate_field,
    validate_line_item_reconciliation,
)


class TestValidateField:
    def test_valid_invoice_number(self):
        status, error = validate_field("invoice_number", "INV-2025-0001")
        assert status == "valid"
        assert error is None

    def test_invalid_invoice_number_format(self):
        status, error = validate_field("invoice_number", "INVOICE-123")
        assert status == "invalid"
        assert "INV-YYYY-NNNN" in error

    def test_missing_required_invoice_number(self):
        status, error = validate_field("invoice_number", None)
        assert status == "invalid"
        assert "required" in error

    def test_empty_required_field(self):
        status, error = validate_field("vendor_name", "   ")
        assert status == "invalid"
        assert "required" in error

    def test_valid_date(self):
        status, error = validate_field("date", "2025-01-15")
        assert status == "valid"
        assert error is None

    def test_invalid_date_format(self):
        status, error = validate_field("date", "15/01/2025")
        assert status == "invalid"
        assert "YYYY-MM-DD" in error

    def test_valid_vendor_name(self):
        status, error = validate_field("vendor_name", "Acme Corporation")
        assert status == "valid"
        assert error is None

    def test_valid_total_amount(self):
        status, error = validate_field("total_amount", "2450.00")
        assert status == "valid"
        assert error is None

    def test_invalid_total_amount_non_numeric(self):
        status, error = validate_field("total_amount", "not-a-number")
        assert status == "invalid"
        assert "valid number" in error

    def test_unknown_field_passes_validation(self):
        status, error = validate_field("custom_field", "anything")
        assert status == "valid"
        assert error is None

    def test_optional_empty_field_unknown_rule(self):
        status, error = validate_field("notes", "")
        assert status == "valid"
        assert error is None

    def test_valid_negative_amount(self):
        status, error = validate_field("total_amount", "-150.50")
        assert status == "valid"
        assert error is None


class TestLineItemReconciliation:
    def test_matching_totals(self):
        class MockItem:
            def __init__(self, total):
                self.total = total

        items = [MockItem(100.00), MockItem(200.00), MockItem(150.00)]
        status, error = validate_line_item_reconciliation("450.00", items)
        assert status == "valid"
        assert error is None

    def test_mismatched_totals(self):
        class MockItem:
            def __init__(self, total):
                self.total = total

        items = [MockItem(100.00), MockItem(200.00)]
        status, error = validate_line_item_reconciliation("500.00", items)
        assert status == "invalid"
        assert "does not match" in error

    def test_no_line_items(self):
        status, error = validate_line_item_reconciliation("100.00", [])
        assert status == "valid"

    def test_no_total_amount(self):
        class MockItem:
            def __init__(self, total):
                self.total = total

        status, error = validate_line_item_reconciliation(None, [MockItem(100)])
        assert status == "valid"


class TestValidateDocumentFields:
    def test_validate_all_valid_fields(self, db_session, sample_document):
        fields_data = [
            {"field_name": "invoice_number", "field_value": "INV-2025-0001", "confidence": 0.95},
            {"field_name": "date", "field_value": "2025-01-15", "confidence": 0.92},
            {"field_name": "vendor_name", "field_value": "Acme Corp", "confidence": 0.90},
            {"field_name": "total_amount", "field_value": "1500.00", "confidence": 0.88},
        ]
        store_extracted_fields(db_session, sample_document.id, fields_data)
        results = validate_document_fields(db_session, sample_document.id)
        assert len(results) == 4
        assert all(r["status"] == "valid" for r in results)

    def test_validate_with_invalid_fields(self, db_session, sample_document):
        fields_data = [
            {"field_name": "invoice_number", "field_value": "BAD-FORMAT", "confidence": 0.95},
            {"field_name": "date", "field_value": "not-a-date", "confidence": 0.92},
        ]
        store_extracted_fields(db_session, sample_document.id, fields_data)
        results = validate_document_fields(db_session, sample_document.id)
        assert len(results) == 2
        assert all(r["status"] == "invalid" for r in results)

    def test_validate_with_line_item_mismatch(self, db_session, sample_document):
        fields_data = [
            {"field_name": "total_amount", "field_value": "500.00", "confidence": 0.90},
        ]
        store_extracted_fields(db_session, sample_document.id, fields_data)
        store_line_items(db_session, sample_document.id, [
            {"description": "Item A", "quantity": 1, "unit_price": 100.00, "total": 100.00},
            {"description": "Item B", "quantity": 2, "unit_price": 50.00, "total": 100.00},
        ])
        results = validate_document_fields(db_session, sample_document.id)
        total_result = next(r for r in results if r["field_name"] == "total_amount")
        assert total_result["status"] == "invalid"
        assert "does not match" in total_result["error_message"]

    def test_validate_with_matching_line_items(self, db_session, sample_document):
        fields_data = [
            {"field_name": "total_amount", "field_value": "200.00", "confidence": 0.90},
        ]
        store_extracted_fields(db_session, sample_document.id, fields_data)
        store_line_items(db_session, sample_document.id, [
            {"description": "Item A", "quantity": 1, "unit_price": 100.00, "total": 100.00},
            {"description": "Item B", "quantity": 1, "unit_price": 100.00, "total": 100.00},
        ])
        results = validate_document_fields(db_session, sample_document.id)
        total_result = next(r for r in results if r["field_name"] == "total_amount")
        assert total_result["status"] == "valid"
