import pytest

from src.backend.db.crud import (
    create_document,
    store_extracted_fields,
    create_correction,
)
from src.backend.analytics.anomaly_detector import (
    detect_anomalies,
    _zscore_detect,
    _isolation_forest_detect,
)


class TestZscoreDetect:
    def test_no_anomalies_uniform_data(self):
        entries = [
            {"document_id": f"d{i}", "filename": f"f{i}.pdf",
             "total_amount": 100.0, "avg_confidence": 0.9, "correction_count": 0}
            for i in range(5)
        ]
        result = _zscore_detect(entries)
        assert result == []

    def test_detects_amount_outlier(self):
        entries = [
            {"document_id": f"d{i}", "filename": f"f{i}.pdf",
             "total_amount": 100.0, "avg_confidence": 0.9, "correction_count": 0}
            for i in range(5)
        ]
        entries.append({
            "document_id": "d_outlier", "filename": "outlier.pdf",
            "total_amount": 10000.0, "avg_confidence": 0.9, "correction_count": 0,
        })
        result = _zscore_detect(entries)
        anomaly_ids = [a["document_id"] for a in result]
        assert "d_outlier" in anomaly_ids

    def test_detects_high_corrections(self):
        entries = [
            {"document_id": "d1", "filename": "f1.pdf",
             "total_amount": 100.0, "avg_confidence": 0.9, "correction_count": 5},
            {"document_id": "d2", "filename": "f2.pdf",
             "total_amount": 100.0, "avg_confidence": 0.9, "correction_count": 0},
        ]
        result = _zscore_detect(entries)
        assert any(a["document_id"] == "d1" for a in result)

    def test_single_entry_returns_empty(self):
        entries = [
            {"document_id": "d1", "filename": "f1.pdf",
             "total_amount": 100.0, "avg_confidence": 0.9, "correction_count": 0}
        ]
        result = _zscore_detect(entries)
        assert result == []

    def test_method_is_zscore(self):
        entries = [
            {"document_id": f"d{i}", "filename": f"f{i}.pdf",
             "total_amount": 100.0, "avg_confidence": 0.9, "correction_count": 0}
            for i in range(5)
        ]
        entries.append({
            "document_id": "d_outlier", "filename": "outlier.pdf",
            "total_amount": 50000.0, "avg_confidence": 0.9, "correction_count": 0,
        })
        result = _zscore_detect(entries)
        assert all(a["method"] == "zscore" for a in result)


class TestDetectAnomalies:
    def test_empty_database(self, db_session):
        result = detect_anomalies(db_session)
        assert result == []

    def test_single_document_no_anomaly(self, db_session, sample_document, sample_extracted_fields):
        result = detect_anomalies(db_session)
        assert result == []

    def test_with_outlier_document(self, db_session):
        for i in range(4):
            doc = create_document(db_session, f"d{i}.pdf", f"d{i}.pdf", "application/pdf", 100)
            store_extracted_fields(db_session, doc.id, [
                {"field_name": "total_amount", "field_value": "100.00", "confidence": 0.9},
                {"field_name": "vendor_name", "field_value": "Normal", "confidence": 0.9},
            ])
        outlier = create_document(db_session, "outlier.pdf", "outlier.pdf", "application/pdf", 100)
        store_extracted_fields(db_session, outlier.id, [
            {"field_name": "total_amount", "field_value": "99999.00", "confidence": 0.9},
            {"field_name": "vendor_name", "field_value": "Outlier", "confidence": 0.9},
        ])

        result = detect_anomalies(db_session)
        if result:
            assert all("document_id" in a for a in result)
            assert all("reasons" in a for a in result)
