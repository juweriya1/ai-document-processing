import pytest
from datetime import datetime, timezone

from src.backend.db.crud import (
    create_document,
    create_user,
    store_extracted_fields,
    store_line_items,
    update_document_status,
    create_correction,
    get_processing_stats,
    get_spend_by_vendor,
    get_spend_by_month,
    get_documents_with_confidence_stats,
)
from src.backend.analytics.aggregator import (
    get_dashboard_summary,
    get_spend_breakdown_by_vendor,
    get_monthly_spend_trend,
    get_compliance_breakdown,
)


class TestGetProcessingStats:
    def test_empty_database(self, db_session):
        stats = get_processing_stats(db_session)
        assert stats == {}

    def test_counts_by_status(self, db_session):
        for i in range(3):
            create_document(db_session, f"f{i}.pdf", f"f{i}.pdf", "application/pdf", 100)
        docs = db_session.query(__import__("src.backend.db.models", fromlist=["Document"]).Document).all()
        update_document_status(db_session, docs[0].id, "approved")
        update_document_status(db_session, docs[1].id, "approved")
        update_document_status(db_session, docs[2].id, "rejected")

        stats = get_processing_stats(db_session)
        assert stats["approved"] == 2
        assert stats["rejected"] == 1


class TestGetSpendByVendor:
    def test_empty_database(self, db_session):
        result = get_spend_by_vendor(db_session)
        assert result == []

    def test_single_vendor(self, db_session, sample_document, sample_extracted_fields):
        result = get_spend_by_vendor(db_session)
        assert len(result) == 1
        assert result[0]["vendor_name"] == "Acme Corporation"
        assert result[0]["total_spend"] == 2450.0
        assert result[0]["document_count"] == 1

    def test_multiple_vendors(self, db_session):
        doc1 = create_document(db_session, "d1.pdf", "d1.pdf", "application/pdf", 100)
        store_extracted_fields(db_session, doc1.id, [
            {"field_name": "vendor_name", "field_value": "Vendor A", "confidence": 0.9},
            {"field_name": "total_amount", "field_value": "1000.00", "confidence": 0.9},
        ])
        doc2 = create_document(db_session, "d2.pdf", "d2.pdf", "application/pdf", 100)
        store_extracted_fields(db_session, doc2.id, [
            {"field_name": "vendor_name", "field_value": "Vendor B", "confidence": 0.85},
            {"field_name": "total_amount", "field_value": "2000.00", "confidence": 0.85},
        ])

        result = get_spend_by_vendor(db_session)
        assert len(result) == 2
        vendors = {r["vendor_name"]: r for r in result}
        assert vendors["Vendor A"]["total_spend"] == 1000.0
        assert vendors["Vendor B"]["total_spend"] == 2000.0


class TestGetSpendByMonth:
    def test_empty_database(self, db_session):
        result = get_spend_by_month(db_session)
        assert result == []

    def test_with_approved_documents(self, db_session):
        doc = create_document(db_session, "d1.pdf", "d1.pdf", "application/pdf", 100)
        store_extracted_fields(db_session, doc.id, [
            {"field_name": "total_amount", "field_value": "500.00", "confidence": 0.9},
        ])
        update_document_status(db_session, doc.id, "approved")

        result = get_spend_by_month(db_session)
        assert len(result) == 1
        assert result[0]["total_spend"] == 500.0


class TestGetDocumentsWithConfidenceStats:
    def test_empty_database(self, db_session):
        result = get_documents_with_confidence_stats(db_session)
        assert result == []

    def test_with_document_and_fields(self, db_session, sample_document, sample_extracted_fields):
        result = get_documents_with_confidence_stats(db_session)
        assert len(result) == 1
        doc_stat = result[0]
        assert doc_stat["document_id"] == sample_document.id
        assert doc_stat["avg_confidence"] is not None
        assert doc_stat["total_amount"] == 2450.0
        assert doc_stat["correction_count"] == 0


class TestDashboardSummary:
    def test_empty_database(self, db_session):
        summary = get_dashboard_summary(db_session)
        assert summary["total_documents"] == 0
        assert summary["total_spend"] == 0.0
        assert summary["compliance_score"] == 0.0

    def test_with_data(self, db_session, sample_document, sample_extracted_fields):
        update_document_status(db_session, sample_document.id, "approved")
        summary = get_dashboard_summary(db_session)
        assert summary["total_documents"] == 1
        assert summary["total_spend"] == 2450.0
        assert summary["compliance_score"] == 100.0
        assert summary["avg_confidence"] > 0


class TestSpendBreakdownByVendor:
    def test_delegates_to_crud(self, db_session, sample_document, sample_extracted_fields):
        result = get_spend_breakdown_by_vendor(db_session)
        assert len(result) == 1
        assert result[0]["vendor_name"] == "Acme Corporation"


class TestMonthlySpendTrend:
    def test_empty(self, db_session):
        result = get_monthly_spend_trend(db_session)
        assert result == []

    def test_limits_months(self, db_session):
        for i in range(3):
            doc = create_document(db_session, f"d{i}.pdf", f"d{i}.pdf", "application/pdf", 100)
            store_extracted_fields(db_session, doc.id, [
                {"field_name": "total_amount", "field_value": "100.00", "confidence": 0.9},
            ])
            update_document_status(db_session, doc.id, "approved")

        result = get_monthly_spend_trend(db_session, months=1)
        assert len(result) <= 1


class TestComplianceBreakdown:
    def test_empty_database(self, db_session):
        result = get_compliance_breakdown(db_session)
        assert result["total_documents"] == 0
        assert result["correction_rate"] == 0.0

    def test_with_corrections(self, db_session, sample_document, sample_extracted_fields):
        field = sample_extracted_fields[0]
        create_correction(
            db_session, sample_document.id, field.id,
            field.field_value, "INV-2025-9999",
        )
        result = get_compliance_breakdown(db_session)
        assert result["total_documents"] == 1
        assert result["with_corrections"] == 1
        assert result["correction_rate"] == 100.0

    def test_without_corrections(self, db_session, sample_document, sample_extracted_fields):
        result = get_compliance_breakdown(db_session)
        assert result["total_documents"] == 1
        assert result["with_corrections"] == 0
        assert result["correction_rate"] == 0.0
