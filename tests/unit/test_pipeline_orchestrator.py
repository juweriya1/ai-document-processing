import pytest

from src.backend.db.crud import get_document, update_document_status
from src.backend.pipeline.orchestrator import (
    ExtractorInterface,
    MockExtractor,
    PipelineOrchestrator,
)


class TestMockExtractor:
    def test_extract_returns_fields_and_items(self):
        extractor = MockExtractor()
        fields, items = extractor.extract("doc_123", "test.pdf")
        assert len(fields) == 4
        assert len(items) == 3
        assert fields[0]["field_name"] == "invoice_number"
        assert items[0]["description"] == "Widget A"

    def test_extract_fields_have_required_keys(self):
        extractor = MockExtractor()
        fields, _ = extractor.extract("doc_123", "test.pdf")
        for field in fields:
            assert "field_name" in field
            assert "field_value" in field
            assert "confidence" in field

    def test_extract_line_items_have_required_keys(self):
        extractor = MockExtractor()
        _, items = extractor.extract("doc_123", "test.pdf")
        for item in items:
            assert "description" in item
            assert "quantity" in item
            assert "unit_price" in item
            assert "total" in item


class TestPipelineOrchestrator:
    def test_process_document_success(self, db_session, sample_document):
        orchestrator = PipelineOrchestrator(db_session)
        result = orchestrator.process_document(sample_document.id)
        assert result["document_id"] == sample_document.id
        assert result["status"] == "review_pending"
        assert result["fields_extracted"] == 4
        assert result["line_items_extracted"] == 3
        assert len(result["validation_results"]) == 4

    def test_process_document_sets_processed_at(self, db_session, sample_document):
        orchestrator = PipelineOrchestrator(db_session)
        orchestrator.process_document(sample_document.id)
        doc = get_document(db_session, sample_document.id)
        assert doc.processed_at is not None

    def test_process_nonexistent_document_raises(self, db_session):
        orchestrator = PipelineOrchestrator(db_session)
        with pytest.raises(ValueError, match="not found"):
            orchestrator.process_document("doc_nonexistent")

    def test_process_already_processed_raises(self, db_session, sample_document):
        update_document_status(db_session, sample_document.id, "review_pending")
        orchestrator = PipelineOrchestrator(db_session)
        with pytest.raises(ValueError, match="cannot be processed"):
            orchestrator.process_document(sample_document.id)

    def test_custom_extractor_injection(self, db_session, sample_document):
        class CustomExtractor(ExtractorInterface):
            def extract(self, document_id, filename):
                fields = [
                    {"field_name": "invoice_number", "field_value": "INV-2025-9999", "confidence": 0.99},
                ]
                return fields, []

        orchestrator = PipelineOrchestrator(db_session, extractor=CustomExtractor())
        result = orchestrator.process_document(sample_document.id)
        assert result["fields_extracted"] == 1
        assert result["line_items_extracted"] == 0

    def test_get_document_status(self, db_session, sample_document):
        orchestrator = PipelineOrchestrator(db_session)
        status = orchestrator.get_document_status(sample_document.id)
        assert status["document_id"] == sample_document.id
        assert status["status"] == "uploaded"
        assert status["filename"] == "test.pdf"

    def test_get_document_status_nonexistent_raises(self, db_session):
        orchestrator = PipelineOrchestrator(db_session)
        with pytest.raises(ValueError, match="not found"):
            orchestrator.get_document_status("doc_nonexistent")

    def test_process_failed_document_allowed(self, db_session, sample_document):
        update_document_status(db_session, sample_document.id, "failed")
        orchestrator = PipelineOrchestrator(db_session)
        result = orchestrator.process_document(sample_document.id)
        assert result["status"] == "review_pending"
