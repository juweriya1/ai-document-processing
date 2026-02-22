import pytest

from src.backend.extraction.entity_extractor import EntityExtractor, ExtractedData, _normalize_date
from src.backend.ocr.ocr_engine import DocumentOCRResult, OCRResult


@pytest.fixture
def extractor():
    return EntityExtractor()


class TestExtractInvoiceNumber:
    def test_standard_format(self):
        value, conf = EntityExtractor._extract_invoice_number("Invoice #INV-2025-00123")
        assert value is not None
        assert "INV-2025-00123" in value
        assert conf == 0.92

    def test_inv_prefix(self):
        value, conf = EntityExtractor._extract_invoice_number("INV-2025-001 for services rendered")
        assert value is not None
        assert "INV-2025-001" in value
        assert conf == 0.92

    def test_numeric_only(self):
        value, conf = EntityExtractor._extract_invoice_number("Invoice: 20250012")
        assert value is not None
        assert "20250012" in value

    def test_no_match(self):
        value, conf = EntityExtractor._extract_invoice_number("No invoice info here")
        assert value is None
        assert conf == 0.0


class TestExtractDate:
    def test_iso_format(self):
        value, conf = EntityExtractor._extract_date("Date: 2025-01-15")
        assert value == "2025-01-15"
        assert conf > 0.0

    def test_slash_format(self):
        value, conf = EntityExtractor._extract_date("Invoice Date: 01/15/2025")
        assert value is not None
        assert "2025" in value
        assert conf > 0.0

    def test_written_format(self):
        value, conf = EntityExtractor._extract_date("Date: January 15, 2025")
        assert value is not None
        assert "2025" in value

    def test_no_match(self):
        value, conf = EntityExtractor._extract_date("No date information")
        assert value is None
        assert conf == 0.0


class TestExtractVendorName:
    def test_with_org_entity(self, extractor):
        text = "Bill From: Acme Corporation\nAddress: 123 Main St\nInvoice #12345"
        value, conf = extractor._extract_vendor_name(text)
        assert value is not None
        assert conf > 0.0
        assert conf <= 1.0

    def test_no_org_entities(self, extractor):
        value, conf = extractor._extract_vendor_name("hello world 123")
        assert conf == 0.0


class TestExtractAmounts:
    def test_total_amount(self):
        text = "Subtotal: $1,200.00\nTax: $96.00\nTotal Amount Due: $1,296.00"
        result = EntityExtractor._extract_amounts(text)
        assert result.get("total_amount") is not None
        assert float(result["total_amount"]) == 1296.00

    def test_subtotal(self):
        text = "Subtotal: $500.00\nTotal: $550.00"
        result = EntityExtractor._extract_amounts(text)
        assert result.get("subtotal") == "500.00"

    def test_tax(self):
        text = "Subtotal: $1000.00\nTax: $80.00\nTotal: $1080.00"
        result = EntityExtractor._extract_amounts(text)
        assert result.get("tax") == "80.00"

    def test_fallback_to_largest(self):
        text = "items: $50.00, $100.00, $200.00"
        result = EntityExtractor._extract_amounts(text)
        assert result.get("total_amount") == "200.00"


class TestExtractLineItems:
    def test_with_valid_table(self):
        tables = [
            [
                ["Description", "Qty", "Unit Price", "Total"],
                ["Widget A", "10", "100.00", "1000.00"],
                ["Widget B", "5", "200.00", "1000.00"],
            ]
        ]
        items = EntityExtractor._extract_line_items(tables)
        assert len(items) == 2
        assert items[0]["description"] == "Widget A"
        assert items[0]["quantity"] == 10.0
        assert items[0]["unit_price"] == 100.0
        assert items[0]["total"] == 1000.0

    def test_with_empty_table(self):
        items = EntityExtractor._extract_line_items([])
        assert items == []

    def test_single_row_table_skipped(self):
        tables = [[["Header only"]]]
        items = EntityExtractor._extract_line_items(tables)
        assert items == []

    def test_no_matching_headers(self):
        tables = [
            [
                ["Column A", "Column B"],
                ["val1", "val2"],
            ]
        ]
        items = EntityExtractor._extract_line_items(tables)
        assert items == []


class TestFullExtraction:
    def test_extract_from_mock_ocr_result(self, extractor):
        pages = [OCRResult(
            text="Invoice #INV-2025-00100\nDate: 2025-03-15\nBill From: Acme Corp\nTotal: $1,500.00",
            confidence=0.90,
            page_number=1,
        )]
        tables = [
            [
                ["Description", "Quantity", "Price", "Total"],
                ["Service A", "2", "500.00", "1000.00"],
                ["Service B", "1", "500.00", "500.00"],
            ]
        ]
        ocr_result = DocumentOCRResult(
            pages=pages,
            tables=tables,
            full_text=pages[0].text,
        )

        result = extractor.extract(ocr_result)

        assert isinstance(result, ExtractedData)
        field_names = [f["field_name"] for f in result.fields]
        assert "invoice_number" in field_names
        assert "date" in field_names
        assert "total_amount" in field_names

        for field in result.fields:
            assert 0.0 <= field["confidence"] <= 1.0

        assert len(result.line_items) == 2
        assert result.line_items[0]["description"] == "Service A"


class TestNormalizeDate:
    def test_iso_format_passthrough(self):
        assert _normalize_date("2025-01-15") == "2025-01-15"

    def test_slash_format(self):
        assert _normalize_date("01/15/2025") == "2025-01-15"

    def test_written_format(self):
        result = _normalize_date("January 15, 2025")
        assert result == "2025-01-15"

    def test_abbreviated_month(self):
        result = _normalize_date("Jan 15, 2025")
        assert result == "2025-01-15"
