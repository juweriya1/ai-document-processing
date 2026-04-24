"""DEPRECATED test module — legacy stack retired 2026-04-24.

Legacy OCREngine (EasyOCR / GOT-OCR / Docling) retired. PaddleOCR-v5 via
LocalExtractor is the Tier-1 extractor now.
"""
import pytest

pytest.skip(
    "Legacy module retired; superseded by the agentic pipeline tests.",
    allow_module_level=True,
)

# =============================================================================
# Original content preserved below as comments for reference.
# =============================================================================

# import os
# from unittest.mock import MagicMock, patch
#
# import numpy as np
# import pytest
#
# from src.backend.ocr.ocr_engine import DocumentOCRResult, OCREngine, OCRResult
# from src.backend.ingestion.preprocessing import PreprocessedPage
#
#
# class TestOCRResult:
#     def test_dataclass_fields(self):
#         result = OCRResult(text="hello", confidence=0.95, page_number=1)
#         assert result.text == "hello"
#         assert result.confidence == 0.95
#         assert result.bounding_boxes == []
#         assert result.page_number == 1
#
#
# class TestDocumentOCRResult:
#     def test_dataclass_fields(self):
#         page = OCRResult(text="page one", confidence=0.9, page_number=1)
#         doc = DocumentOCRResult(pages=[page], tables=[], full_text="page one")
#         assert len(doc.pages) == 1
#         assert doc.full_text == "page one"
#         assert doc.tables == []
#
#
# class TestEstimateConfidence:
#     def test_long_text_returns_high_confidence(self):
#         text = "a" * 101
#         assert OCREngine._estimate_confidence(text) == 0.90
#
#     def test_medium_text_returns_medium_confidence(self):
#         text = "a" * 50
#         assert OCREngine._estimate_confidence(text) == 0.75
#
#     def test_short_text_returns_low_confidence(self):
#         assert OCREngine._estimate_confidence("hi") == 0.50
#
#     def test_empty_text_returns_low_confidence(self):
#         assert OCREngine._estimate_confidence("") == 0.50
#
#     def test_exactly_100_chars_medium(self):
#         assert OCREngine._estimate_confidence("a" * 100) == 0.75
#
#     def test_exactly_10_chars_medium(self):
#         assert OCREngine._estimate_confidence("a" * 10) == 0.75
#
#
# class TestGOTOCRPath:
#     def _engine_with_mock_got(self, chat_return: str) -> OCREngine:
#         engine = OCREngine(use_got_ocr=True)
#         engine._got_model = MagicMock()
#         engine._got_tokenizer = MagicMock()
#         engine._got_model.chat.return_value = chat_return
#         return engine
#
#     def test_extract_text_returns_ocr_result(self):
#         long_text = (
#             "Invoice #INV-2024-0001\nVendor: Acme Corp Ltd\nDate: 2024-01-15\n"
#             "Subtotal: $1,000.00\nTax (8%): $80.00\nShipping: $20.00\nTotal Due: $1,100.00"
#         )
#         assert len(long_text) > 100  # ensures 0.90 confidence branch
#         engine = self._engine_with_mock_got(long_text)
#         image = np.ones((100, 200), dtype=np.uint8) * 255
#         result = engine.extract_text_from_image(image, page_number=1)
#
#         assert "Invoice" in result.text
#         assert "INV-2024-0001" in result.text
#         assert result.confidence == 0.90
#         assert result.bounding_boxes == []
#         assert result.page_number == 1
#
#     def test_extract_text_empty_response(self):
#         engine = self._engine_with_mock_got("")
#         image = np.ones((100, 100), dtype=np.uint8) * 255
#         result = engine.extract_text_from_image(image)
#
#         assert result.text == ""
#         assert result.confidence == 0.50
#         assert result.bounding_boxes == []
#
#     def test_extract_text_medium_response(self):
#         engine = self._engine_with_mock_got("Total: $500")  # 11 chars
#         image = np.ones((100, 100), dtype=np.uint8) * 255
#         result = engine.extract_text_from_image(image)
#
#         assert result.confidence == 0.75
#
#     def test_extract_text_color_image_converted(self):
#         engine = self._engine_with_mock_got("Test text for color image conversion check ok.")
#         color_image = np.ones((100, 200, 3), dtype=np.uint8) * 255
#         result = engine.extract_text_from_image(color_image)
#
#         assert "Test" in result.text
#         engine._got_model.chat.assert_called_once()
#
#     def test_got_ocr_failure_returns_empty(self):
#         engine = OCREngine(use_got_ocr=True)
#         engine._got_model = MagicMock()
#         engine._got_tokenizer = MagicMock()
#         engine._got_model.chat.side_effect = RuntimeError("CUDA OOM")
#
#         image = np.ones((100, 100), dtype=np.uint8) * 255
#         result = engine.extract_text_from_image(image)
#
#         assert result.text == ""
#         assert result.confidence == 0.50
#
#
# class TestDoclingTableExtraction:
#     def test_extract_tables_with_docling_mock(self):
#         engine = OCREngine(use_got_ocr=True)
#
#         mock_cell = MagicMock()
#         mock_cell.text = "Widget A"
#         mock_header = MagicMock()
#         mock_header.text = "Description"
#
#         mock_table = MagicMock()
#         mock_table.data.grid = [[mock_header], [mock_cell]]
#
#         mock_doc = MagicMock()
#         mock_doc.tables = [mock_table]
#
#         mock_result = MagicMock()
#         mock_result.document = mock_doc
#
#         with patch("src.backend.ocr.ocr_engine._DOCLING_AVAILABLE", True), \
#              patch("src.backend.ocr.ocr_engine._DoclingConverter") as mock_converter_cls:
#             mock_converter_cls.return_value.convert.return_value = mock_result
#             tables = engine.extract_tables_from_pdf("/fake/invoice.pdf")
#
#         assert len(tables) == 1
#         assert tables[0][0] == ["Description"]
#         assert tables[0][1] == ["Widget A"]
#
#     def test_extract_tables_docling_failure_returns_empty(self):
#         engine = OCREngine(use_got_ocr=True)
#
#         with patch("src.backend.ocr.ocr_engine._DOCLING_AVAILABLE", True), \
#              patch("src.backend.ocr.ocr_engine._DoclingConverter") as mock_converter_cls:
#             mock_converter_cls.return_value.convert.side_effect = Exception("parse error")
#             tables = engine.extract_tables_from_pdf("/fake/invoice.pdf")
#
#         assert tables == []
#
#     def test_extract_tables_docling_not_available(self, monkeypatch):
#         monkeypatch.setattr("src.backend.ocr.ocr_engine._DOCLING_AVAILABLE", False)
#         engine = OCREngine(use_got_ocr=True)
#         tables = engine.extract_tables_from_pdf("/fake/invoice.pdf")
#         assert tables == []
#
#     def test_extract_tables_with_real_fixture(self):
#         fixture_path = os.path.join(
#             os.path.dirname(__file__), "..", "fixtures", "sample_invoice.pdf"
#         )
#         if not os.path.exists(fixture_path):
#             pytest.skip("sample_invoice.pdf fixture not available")
#         try:
#             import docling  # noqa: F401
#         except ImportError:
#             pytest.skip("docling not installed")
#
#         engine = OCREngine(use_got_ocr=True)
#         tables = engine.extract_tables_from_pdf(fixture_path)
#         assert isinstance(tables, list)
#
#
# class TestEasyOCRFallbackPath:
#     def test_extract_text_easyocr_empty(self):
#         engine = OCREngine(use_got_ocr=False)
#         engine._reader = MagicMock()
#         engine._reader.readtext.return_value = []
#
#         white_image = np.ones((100, 100), dtype=np.uint8) * 255
#         result = engine.extract_text_from_image(white_image)
#
#         assert result.text == ""
#         assert result.confidence == 0.0
#         assert result.bounding_boxes == []
#
#     def test_extract_text_easyocr_with_results(self):
#         engine = OCREngine(use_got_ocr=False)
#         engine._reader = MagicMock()
#         engine._reader.readtext.return_value = [
#             ([[0, 0], [100, 0], [100, 30], [0, 30]], "Invoice", 0.95),
#             ([[0, 40], [100, 40], [100, 70], [0, 70]], "INV-2025-001", 0.88),
#         ]
#
#         image = np.ones((100, 200), dtype=np.uint8) * 255
#         result = engine.extract_text_from_image(image, page_number=1)
#
#         assert "Invoice" in result.text
#         assert "INV-2025-001" in result.text
#         assert 0.0 < result.confidence <= 1.0
#         assert len(result.bounding_boxes) == 2
#         assert result.page_number == 1
#
#     def test_extract_tables_pdfplumber_nonexistent(self):
#         engine = OCREngine(use_got_ocr=False)
#         tables = engine.extract_tables_from_pdf("/nonexistent/file.pdf")
#         assert tables == []
#
#     def test_extract_tables_pdfplumber_fixture(self):
#         fixture_path = os.path.join(
#             os.path.dirname(__file__), "..", "fixtures", "sample_invoice.pdf"
#         )
#         if not os.path.exists(fixture_path):
#             pytest.skip("sample_invoice.pdf fixture not available")
#
#         engine = OCREngine(use_got_ocr=False)
#         tables = engine.extract_tables_from_pdf(fixture_path)
#         assert isinstance(tables, list)
#
#
# class TestProcessDocument:
#     def test_process_document_got_ocr_combines_pages(self):
#         engine = OCREngine(use_got_ocr=True)
#         engine._got_model = MagicMock()
#         engine._got_tokenizer = MagicMock()
#         engine._got_model.chat.side_effect = [
#             "Page one content with enough text here.",
#             "Page two content with enough text here.",
#         ]
#
#         pages = [
#             PreprocessedPage(
#                 page_number=1,
#                 original=np.ones((50, 50), dtype=np.uint8),
#                 processed=np.ones((50, 50), dtype=np.uint8),
#             ),
#             PreprocessedPage(
#                 page_number=2,
#                 original=np.ones((50, 50), dtype=np.uint8),
#                 processed=np.ones((50, 50), dtype=np.uint8),
#             ),
#         ]
#
#         result = engine.process_document(pages)
#
#         assert len(result.pages) == 2
#         assert "Page one" in result.full_text
#         assert "Page two" in result.full_text
#         assert result.pages[0].page_number == 1
#         assert result.pages[1].page_number == 2
#         assert result.tables == []
#
#     def test_process_document_easyocr_combines_pages(self):
#         engine = OCREngine(use_got_ocr=False)
#         engine._reader = MagicMock()
#         engine._reader.readtext.side_effect = [
#             [([[0, 0], [10, 0], [10, 10], [0, 10]], "Page one", 0.9)],
#             [([[0, 0], [10, 0], [10, 10], [0, 10]], "Page two", 0.85)],
#         ]
#
#         pages = [
#             PreprocessedPage(
#                 page_number=1,
#                 original=np.ones((50, 50), dtype=np.uint8),
#                 processed=np.ones((50, 50), dtype=np.uint8),
#             ),
#             PreprocessedPage(
#                 page_number=2,
#                 original=np.ones((50, 50), dtype=np.uint8),
#                 processed=np.ones((50, 50), dtype=np.uint8),
#             ),
#         ]
#
#         result = engine.process_document(pages)
#         assert len(result.pages) == 2
#         assert "Page one" in result.full_text
#         assert "Page two" in result.full_text
#         assert result.pages[0].page_number == 1
#         assert result.pages[1].page_number == 2
#
#     def test_process_document_no_pdf_path_skips_tables(self):
#         engine = OCREngine(use_got_ocr=True)
#         engine._got_model = MagicMock()
#         engine._got_tokenizer = MagicMock()
#         engine._got_model.chat.return_value = "some text"
#
#         pages = [
#             PreprocessedPage(
#                 page_number=1,
#                 original=np.ones((50, 50), dtype=np.uint8),
#                 processed=np.ones((50, 50), dtype=np.uint8),
#             )
#         ]
#
#         result = engine.process_document(pages, pdf_path=None)
#         assert result.tables == []
#
#     def test_process_document_full_text_uses_double_newline(self):
#         engine = OCREngine(use_got_ocr=True)
#         engine._got_model = MagicMock()
#         engine._got_tokenizer = MagicMock()
#         engine._got_model.chat.side_effect = ["Page A text.", "Page B text."]
#
#         pages = [
#             PreprocessedPage(
#                 page_number=1,
#                 original=np.ones((50, 50), dtype=np.uint8),
#                 processed=np.ones((50, 50), dtype=np.uint8),
#             ),
#             PreprocessedPage(
#                 page_number=2,
#                 original=np.ones((50, 50), dtype=np.uint8),
#                 processed=np.ones((50, 50), dtype=np.uint8),
#             ),
#         ]
#
#         result = engine.process_document(pages)
#         assert "\n\n" in result.full_text
#
#     def test_process_document_with_tables(self):
#         engine = OCREngine(use_got_ocr=True)
#         engine._got_model = MagicMock()
#         engine._got_tokenizer = MagicMock()
#         engine._got_model.chat.return_value = "Invoice text"
#
#         pages = [
#             PreprocessedPage(
#                 page_number=1,
#                 original=np.ones((50, 50), dtype=np.uint8),
#                 processed=np.ones((50, 50), dtype=np.uint8),
#             )
#         ]
#
#         mock_cell = MagicMock()
#         mock_cell.text = "Total"
#         mock_table = MagicMock()
#         mock_table.data.grid = [[mock_cell]]
#         mock_doc = MagicMock()
#         mock_doc.tables = [mock_table]
#         mock_result = MagicMock()
#         mock_result.document = mock_doc
#
#         with patch("src.backend.ocr.ocr_engine._DOCLING_AVAILABLE", True), \
#              patch("src.backend.ocr.ocr_engine._DoclingConverter") as mock_conv:
#             mock_conv.return_value.convert.return_value = mock_result
#             result = engine.process_document(pages, pdf_path="/fake/invoice.pdf")
#
#         assert len(result.tables) == 1
#         assert result.tables[0] == [["Total"]]
