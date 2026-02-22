import os
from unittest.mock import MagicMock

import numpy as np
import pytest

from src.backend.ocr.ocr_engine import DocumentOCRResult, OCREngine, OCRResult
from src.backend.ingestion.preprocessing import PreprocessedPage


class TestOCRResult:
    def test_dataclass_fields(self):
        result = OCRResult(text="hello", confidence=0.95, page_number=1)
        assert result.text == "hello"
        assert result.confidence == 0.95
        assert result.bounding_boxes == []
        assert result.page_number == 1


class TestDocumentOCRResult:
    def test_dataclass_fields(self):
        page = OCRResult(text="page one", confidence=0.9, page_number=1)
        doc = DocumentOCRResult(pages=[page], tables=[], full_text="page one")
        assert len(doc.pages) == 1
        assert doc.full_text == "page one"
        assert doc.tables == []


class TestOCREngineExtractText:
    def test_extract_text_from_image_empty(self):
        engine = OCREngine()
        engine._reader = MagicMock()
        engine._reader.readtext.return_value = []

        white_image = np.ones((100, 100), dtype=np.uint8) * 255
        result = engine.extract_text_from_image(white_image)

        assert result.text == ""
        assert result.confidence == 0.0
        assert result.bounding_boxes == []

    def test_extract_text_from_image_with_results(self):
        engine = OCREngine()
        engine._reader = MagicMock()
        engine._reader.readtext.return_value = [
            ([[0, 0], [100, 0], [100, 30], [0, 30]], "Invoice", 0.95),
            ([[0, 40], [100, 40], [100, 70], [0, 70]], "INV-2025-001", 0.88),
        ]

        image = np.ones((100, 200), dtype=np.uint8) * 255
        result = engine.extract_text_from_image(image, page_number=1)

        assert "Invoice" in result.text
        assert "INV-2025-001" in result.text
        assert 0.0 < result.confidence <= 1.0
        assert len(result.bounding_boxes) == 2
        assert result.page_number == 1

    def test_extract_text_from_color_image(self):
        engine = OCREngine()
        engine._reader = MagicMock()
        engine._reader.readtext.return_value = [
            ([[0, 0], [50, 0], [50, 20], [0, 20]], "Test", 0.90),
        ]

        color_image = np.ones((100, 200, 3), dtype=np.uint8) * 255
        result = engine.extract_text_from_image(color_image)

        assert result.text == "Test"
        assert result.confidence == 0.90


class TestOCREngineExtractTables:
    def test_extract_tables_from_pdf_fixture(self):
        fixture_path = os.path.join(
            os.path.dirname(__file__), "..", "fixtures", "sample_invoice.pdf"
        )
        if not os.path.exists(fixture_path):
            pytest.skip("sample_invoice.pdf fixture not available")

        engine = OCREngine()
        tables = engine.extract_tables_from_pdf(fixture_path)
        assert isinstance(tables, list)

    def test_extract_tables_nonexistent_file(self):
        engine = OCREngine()
        tables = engine.extract_tables_from_pdf("/nonexistent/file.pdf")
        assert tables == []


class TestOCREngineProcessDocument:
    def test_process_document_combines_pages(self):
        engine = OCREngine()
        engine._reader = MagicMock()
        engine._reader.readtext.side_effect = [
            [([[0, 0], [10, 0], [10, 10], [0, 10]], "Page one", 0.9)],
            [([[0, 0], [10, 0], [10, 10], [0, 10]], "Page two", 0.85)],
        ]

        pages = [
            PreprocessedPage(
                page_number=1,
                original=np.ones((50, 50), dtype=np.uint8),
                processed=np.ones((50, 50), dtype=np.uint8),
            ),
            PreprocessedPage(
                page_number=2,
                original=np.ones((50, 50), dtype=np.uint8),
                processed=np.ones((50, 50), dtype=np.uint8),
            ),
        ]

        result = engine.process_document(pages)
        assert len(result.pages) == 2
        assert "Page one" in result.full_text
        assert "Page two" in result.full_text
        assert result.pages[0].page_number == 1
        assert result.pages[1].page_number == 2
