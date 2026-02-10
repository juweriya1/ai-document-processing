import pytest

from src.backend.db.crud import (
    create_document,
    store_extracted_fields,
    create_correction,
    upsert_supplier_metric,
    get_all_supplier_metrics,
)
from src.backend.analytics.supplier_analyzer import (
    compute_supplier_metrics,
    get_supplier_list,
    _risk_level,
)


class TestComputeSupplierMetrics:
    def test_empty_database(self, db_session):
        result = compute_supplier_metrics(db_session)
        assert result == []

    def test_single_vendor(self, db_session, sample_document, sample_extracted_fields):
        result = compute_supplier_metrics(db_session)
        assert len(result) == 1
        assert result[0]["supplier_name"] == "Acme Corporation"
        assert result[0]["total_documents"] == 1
        assert result[0]["avg_confidence"] > 0
        assert result[0]["total_corrections"] == 0

    def test_multiple_vendors(self, db_session):
        doc1 = create_document(db_session, "d1.pdf", "d1.pdf", "application/pdf", 100)
        store_extracted_fields(db_session, doc1.id, [
            {"field_name": "vendor_name", "field_value": "Alpha Inc", "confidence": 0.95},
            {"field_name": "total_amount", "field_value": "500.00", "confidence": 0.90},
        ])
        doc2 = create_document(db_session, "d2.pdf", "d2.pdf", "application/pdf", 100)
        store_extracted_fields(db_session, doc2.id, [
            {"field_name": "vendor_name", "field_value": "Beta Corp", "confidence": 0.80},
            {"field_name": "total_amount", "field_value": "1000.00", "confidence": 0.75},
        ])

        result = compute_supplier_metrics(db_session)
        assert len(result) == 2
        names = {r["supplier_name"] for r in result}
        assert "Alpha Inc" in names
        assert "Beta Corp" in names

    def test_persists_to_db(self, db_session, sample_document, sample_extracted_fields):
        compute_supplier_metrics(db_session)
        metrics = get_all_supplier_metrics(db_session)
        assert len(metrics) == 1
        assert metrics[0].supplier_name == "Acme Corporation"

    def test_counts_corrections(self, db_session, sample_document, sample_extracted_fields):
        field = sample_extracted_fields[0]
        create_correction(
            db_session, sample_document.id, field.id,
            field.field_value, "INV-2025-9999",
        )
        result = compute_supplier_metrics(db_session)
        assert result[0]["total_corrections"] == 1


class TestGetSupplierList:
    def test_empty(self, db_session):
        result = get_supplier_list(db_session)
        assert result == []

    def test_returns_persisted_metrics(self, db_session):
        upsert_supplier_metric(db_session, "Test Vendor", 5, 0.90, 25.0)
        result = get_supplier_list(db_session)
        assert len(result) == 1
        assert result[0]["supplier_name"] == "Test Vendor"
        assert result[0]["risk_level"] == "low"

    def test_risk_levels_assigned(self, db_session):
        upsert_supplier_metric(db_session, "Low Risk", 10, 0.95, 15.0)
        upsert_supplier_metric(db_session, "Medium Risk", 3, 0.70, 45.0)
        upsert_supplier_metric(db_session, "High Risk", 1, 0.50, 75.0)
        result = get_supplier_list(db_session)
        levels = {r["supplier_name"]: r["risk_level"] for r in result}
        assert levels["Low Risk"] == "low"
        assert levels["Medium Risk"] == "medium"
        assert levels["High Risk"] == "high"


class TestRiskLevel:
    def test_none_score(self):
        assert _risk_level(None) == "unknown"

    def test_low(self):
        assert _risk_level(10.0) == "low"
        assert _risk_level(29.9) == "low"

    def test_medium(self):
        assert _risk_level(30.0) == "medium"
        assert _risk_level(59.9) == "medium"

    def test_high(self):
        assert _risk_level(60.0) == "high"
        assert _risk_level(100.0) == "high"
