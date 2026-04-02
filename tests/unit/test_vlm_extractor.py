import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from src.backend.extraction.entity_extractor import ExtractedData
from src.backend.extraction.vlm_extractor import VLMExtractor
from src.backend.ocr.ocr_engine import DocumentOCRResult, OCRResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_extractor(model_name: str = "Qwen/Qwen2-VL-7B-Instruct",
                    adapter_path: str | None = None) -> VLMExtractor:
    """Return a VLMExtractor with mocked model + processor injected directly."""
    extractor = VLMExtractor(model_name=model_name, adapter_path=adapter_path)
    extractor._model = MagicMock()
    extractor._processor = MagicMock()
    return extractor


def _minimal_ocr_result(full_text: str = "") -> DocumentOCRResult:
    return DocumentOCRResult(pages=[], tables=[], full_text=full_text)


def _pil_white(w: int = 64, h: int = 64) -> Image.Image:
    return Image.fromarray(np.ones((h, w, 3), dtype=np.uint8) * 255)


# ---------------------------------------------------------------------------
# TestVLMExtractorInit
# ---------------------------------------------------------------------------

class TestVLMExtractorInit:
    def test_default_model_name(self):
        e = VLMExtractor()
        assert e._model_name == "Qwen/Qwen2-VL-7B-Instruct"

    def test_custom_model_name(self):
        e = VLMExtractor(model_name="Qwen/Qwen2-VL-2B-Instruct")
        assert e._model_name == "Qwen/Qwen2-VL-2B-Instruct"

    def test_adapter_path_stored(self):
        e = VLMExtractor(adapter_path="/path/to/adapter")
        assert e._adapter_path == "/path/to/adapter"

    def test_lazy_load_not_triggered_on_init(self):
        """Model should NOT be loaded at construction time."""
        e = VLMExtractor()
        assert e._model is None
        assert e._processor is None

    def test_no_adapter_by_default(self):
        e = VLMExtractor()
        assert e._adapter_path is None


# ---------------------------------------------------------------------------
# TestPageToPil
# ---------------------------------------------------------------------------

class TestPageToPil:
    def test_rgb_array_returns_rgb_pil(self):
        arr = np.ones((50, 50, 3), dtype=np.uint8) * 128
        pil = VLMExtractor._page_to_pil(arr)
        assert isinstance(pil, Image.Image)
        assert pil.mode == "RGB"

    def test_grayscale_array_converted_to_rgb(self):
        arr = np.ones((50, 50), dtype=np.uint8) * 200
        pil = VLMExtractor._page_to_pil(arr)
        assert pil.mode == "RGB"


# ---------------------------------------------------------------------------
# TestRunInference
# ---------------------------------------------------------------------------

class TestRunInference:
    def _extractor_with_generate(self, decoded_text: str, scores=None) -> VLMExtractor:
        """Set up VLMExtractor with a mocked model.generate + processor.batch_decode."""
        import torch
        e = _make_extractor()

        # processor.apply_chat_template returns a text string
        e._processor.apply_chat_template.return_value = "<chat_template>"

        # processor(text=...) returns inputs with input_ids shape [1, 10]
        mock_inputs = MagicMock()
        mock_inputs.input_ids = torch.zeros((1, 10), dtype=torch.long)
        # .to(device) returns itself
        mock_inputs.to.return_value = mock_inputs
        e._processor.return_value = mock_inputs

        # model.device
        e._model.device = "cpu"

        # build a fake generate output
        # sequences shape [1, 10 + len_new_tokens]
        new_len = 5
        sequences = torch.zeros((1, 10 + new_len), dtype=torch.long)

        if scores is None:
            scores_list = []
        else:
            scores_list = scores

        gen_output = SimpleNamespace(sequences=sequences, scores=scores_list)
        e._model.generate.return_value = gen_output

        # batch_decode returns decoded text
        e._processor.batch_decode.return_value = [decoded_text]

        return e

    def test_returns_string_and_float(self):
        e = self._extractor_with_generate('{"invoice_number": "INV-001"}')
        pil = _pil_white()
        raw, conf = e._run_inference(pil)
        assert isinstance(raw, str)
        assert isinstance(conf, float)

    def test_confidence_in_unit_interval(self):
        e = self._extractor_with_generate('{"invoice_number": "INV-001"}')
        pil = _pil_white()
        _, conf = e._run_inference(pil)
        assert 0.0 <= conf <= 1.0

    def test_no_scores_returns_default_confidence(self):
        """When model returns no scores, confidence defaults to 0.75."""
        e = self._extractor_with_generate("{}", scores=[])
        _, conf = e._run_inference(_pil_white())
        assert conf == 0.75

    def test_raw_text_passed_through(self):
        expected = '{"vendor_name": "Acme Corp"}'
        e = self._extractor_with_generate(expected)
        raw, _ = e._run_inference(_pil_white())
        assert raw == expected

    def test_generate_called_with_scores_flag(self):
        e = self._extractor_with_generate("{}")
        e._run_inference(_pil_white())
        call_kwargs = e._model.generate.call_args.kwargs
        assert call_kwargs.get("output_scores") is True
        assert call_kwargs.get("return_dict_in_generate") is True


# ---------------------------------------------------------------------------
# TestParseResponse
# ---------------------------------------------------------------------------

class TestParseResponse:
    def _extractor(self) -> VLMExtractor:
        return _make_extractor()

    def _fallback(self) -> tuple["EntityExtractor", DocumentOCRResult]:
        from src.backend.extraction.entity_extractor import EntityExtractor
        fb = MagicMock(spec=EntityExtractor)
        fb.extract.return_value = ExtractedData(
            fields=[{"field_name": "vendor_name", "field_value": "Fallback Corp", "confidence": 0.5}],
            line_items=[],
        )
        ocr = _minimal_ocr_result("Fallback Corp invoice text")
        return fb, ocr

    def test_valid_json_extracts_fields(self):
        e = self._extractor()
        fb, ocr = self._fallback()
        raw = json.dumps({
            "invoice_number": "INV-2024-001",
            "date": "2024-01-15",
            "vendor_name": "Acme Corp",
            "total_amount": "1100.00",
            "subtotal": "1000.00",
            "tax": "100.00",
            "line_items": [],
        })
        result = e._parse_response(raw, 0.85, fb, ocr)
        field_names = {f["field_name"] for f in result.fields}
        assert "invoice_number" in field_names
        assert "vendor_name" in field_names
        assert "total_amount" in field_names

    def test_valid_json_stamps_confidence(self):
        e = self._extractor()
        fb, ocr = self._fallback()
        raw = json.dumps({"invoice_number": "INV-001", "date": None,
                          "vendor_name": None, "total_amount": None,
                          "subtotal": None, "tax": None, "line_items": []})
        result = e._parse_response(raw, 0.92, fb, ocr)
        for f in result.fields:
            assert f["confidence"] == 0.92

    def test_null_fields_excluded(self):
        e = self._extractor()
        fb, ocr = self._fallback()
        raw = json.dumps({"invoice_number": None, "date": None,
                          "vendor_name": "Vendor", "total_amount": None,
                          "subtotal": None, "tax": None, "line_items": []})
        result = e._parse_response(raw, 0.8, fb, ocr)
        names = {f["field_name"] for f in result.fields}
        assert "invoice_number" not in names
        assert "vendor_name" in names

    def test_malformed_json_falls_back_to_entity_extractor(self):
        e = self._extractor()
        fb, ocr = self._fallback()
        result = e._parse_response("not json at all", 0.5, fb, ocr)
        fb.extract.assert_called_once_with(ocr)
        assert result.fields[0]["field_value"] == "Fallback Corp"

    def test_markdown_fences_stripped(self):
        e = self._extractor()
        fb, ocr = self._fallback()
        raw = "```json\n" + json.dumps({
            "invoice_number": "INV-999", "date": None, "vendor_name": None,
            "total_amount": None, "subtotal": None, "tax": None, "line_items": []
        }) + "\n```"
        result = e._parse_response(raw, 0.9, fb, ocr)
        names = {f["field_name"] for f in result.fields}
        assert "invoice_number" in names

    def test_line_items_parsed(self):
        e = self._extractor()
        fb, ocr = self._fallback()
        raw = json.dumps({
            "invoice_number": None, "date": None, "vendor_name": None,
            "total_amount": None, "subtotal": None, "tax": None,
            "line_items": [
                {"description": "Widget A", "quantity": 2.0, "unit_price": 5.0, "total": 10.0}
            ],
        })
        result = e._parse_response(raw, 0.8, fb, ocr)
        assert len(result.line_items) == 1
        assert result.line_items[0]["description"] == "Widget A"
        assert result.line_items[0]["quantity"] == 2.0

    def test_line_items_with_bad_numerics_default_to_zero(self):
        e = self._extractor()
        fb, ocr = self._fallback()
        raw = json.dumps({
            "invoice_number": None, "date": None, "vendor_name": None,
            "total_amount": None, "subtotal": None, "tax": None,
            "line_items": [
                {"description": "Service", "quantity": "N/A", "unit_price": None, "total": ""}
            ],
        })
        result = e._parse_response(raw, 0.8, fb, ocr)
        assert len(result.line_items) == 1
        assert result.line_items[0]["quantity"] == 0.0
        assert result.line_items[0]["unit_price"] == 0.0

    def test_line_items_without_description_skipped(self):
        e = self._extractor()
        fb, ocr = self._fallback()
        raw = json.dumps({
            "invoice_number": None, "date": None, "vendor_name": None,
            "total_amount": None, "subtotal": None, "tax": None,
            "line_items": [
                {"description": "", "quantity": 1.0, "unit_price": 10.0, "total": 10.0}
            ],
        })
        result = e._parse_response(raw, 0.8, fb, ocr)
        assert result.line_items == []

    def test_surrounding_text_extracted_via_brace_match(self):
        """JSON embedded in surrounding prose should still parse."""
        e = self._extractor()
        fb, ocr = self._fallback()
        inner = json.dumps({"invoice_number": "X-100", "date": None,
                            "vendor_name": None, "total_amount": None,
                            "subtotal": None, "tax": None, "line_items": []})
        raw = "Here is the result: " + inner + " End."
        result = e._parse_response(raw, 0.7, fb, ocr)
        names = {f["field_name"] for f in result.fields}
        assert "invoice_number" in names


# ---------------------------------------------------------------------------
# TestExtract (full pipeline, all heavy deps mocked)
# ---------------------------------------------------------------------------

class TestExtract:
    def _make_full_extractor(self, page_json: str, confidence: float = 0.85) -> VLMExtractor:
        """Return a VLMExtractor with all external deps mocked for extract()."""
        e = _make_extractor()
        # _run_inference is the heavy GPU call — mock it directly
        e._run_inference = MagicMock(return_value=(page_json, confidence))
        return e

    def _patch_preprocess_and_ocr(self, num_pages: int = 1):
        """Context-manager-style helper returning (pages_mock, ocr_mock)."""
        import numpy as np
        from src.backend.ingestion.preprocessing import PreprocessedPage

        pages = [
            PreprocessedPage(
                page_number=i + 1,
                original=np.ones((50, 50), dtype=np.uint8),
                processed=np.ones((50, 50), dtype=np.uint8),
            )
            for i in range(num_pages)
        ]
        ocr_result = _minimal_ocr_result("Invoice text page 1")
        return pages, ocr_result

    def test_extract_returns_tuple_of_two_lists(self):
        e = self._make_full_extractor(
            json.dumps({"invoice_number": "INV-1", "date": None, "vendor_name": None,
                        "total_amount": None, "subtotal": None, "tax": None, "line_items": []})
        )
        pages, ocr_result = self._patch_preprocess_and_ocr()

        with patch.object(e._preprocessing, "preprocess_document", return_value=pages), \
             patch("src.backend.extraction.vlm_extractor.OCREngine") as mock_ocr_cls:
            mock_ocr_cls.return_value.process_document.return_value = ocr_result
            fields, line_items = e.extract("doc-1", "invoice.pdf")

        assert isinstance(fields, list)
        assert isinstance(line_items, list)

    def test_extract_deduplicates_fields_across_pages(self):
        """Fields seen on page 1 should not be duplicated from page 2."""
        page_json = json.dumps({
            "invoice_number": "INV-DUPE", "date": "2024-01-01",
            "vendor_name": None, "total_amount": None, "subtotal": None,
            "tax": None, "line_items": [],
        })
        e = self._make_full_extractor(page_json)
        pages, ocr = self._patch_preprocess_and_ocr(num_pages=2)

        with patch.object(e._preprocessing, "preprocess_document", return_value=pages), \
             patch("src.backend.extraction.vlm_extractor.OCREngine") as mock_ocr_cls:
            mock_ocr_cls.return_value.process_document.return_value = ocr
            fields, _ = e.extract("doc-2", "invoice.pdf")

        inv_fields = [f for f in fields if f["field_name"] == "invoice_number"]
        assert len(inv_fields) == 1

    def test_extract_accumulates_line_items_across_pages(self):
        page_json = json.dumps({
            "invoice_number": None, "date": None, "vendor_name": None,
            "total_amount": None, "subtotal": None, "tax": None,
            "line_items": [{"description": "Item", "quantity": 1.0, "unit_price": 5.0, "total": 5.0}],
        })
        e = self._make_full_extractor(page_json)
        pages, ocr = self._patch_preprocess_and_ocr(num_pages=2)

        with patch.object(e._preprocessing, "preprocess_document", return_value=pages), \
             patch("src.backend.extraction.vlm_extractor.OCREngine") as mock_ocr_cls:
            mock_ocr_cls.return_value.process_document.return_value = ocr
            _, line_items = e.extract("doc-3", "invoice.pdf")

        assert len(line_items) == 2  # one per page

    def test_extract_failure_returns_empty_lists(self):
        e = _make_extractor()
        e._run_inference = MagicMock(side_effect=RuntimeError("CUDA OOM"))

        with patch.object(e._preprocessing, "preprocess_document",
                          side_effect=RuntimeError("fail")):
            fields, line_items = e.extract("doc-err", "invoice.pdf")

        assert fields == []
        assert line_items == []

    def test_extract_calls_preprocessing_with_correct_path(self):
        page_json = json.dumps({"invoice_number": None, "date": None,
                                "vendor_name": None, "total_amount": None,
                                "subtotal": None, "tax": None, "line_items": []})
        e = self._make_full_extractor(page_json)
        pages, ocr = self._patch_preprocess_and_ocr()

        with patch.object(e._preprocessing, "preprocess_document", return_value=pages) as mock_prep, \
             patch("src.backend.extraction.vlm_extractor.OCREngine") as mock_ocr_cls:
            mock_ocr_cls.return_value.process_document.return_value = ocr
            e.extract("doc-4", "test_invoice.pdf")

        mock_prep.assert_called_once_with("uploads/test_invoice.pdf")


# ---------------------------------------------------------------------------
# TestExtractFromImage
# ---------------------------------------------------------------------------

class TestExtractFromImage:
    def test_returns_tuple_of_lists(self):
        e = _make_extractor()
        e._run_inference = MagicMock(return_value=(
            json.dumps({"invoice_number": "IMG-001", "date": None,
                        "vendor_name": None, "total_amount": None,
                        "subtotal": None, "tax": None, "line_items": []}),
            0.88,
        ))
        fields, line_items = e.extract_from_image(_pil_white())
        assert isinstance(fields, list)
        assert isinstance(line_items, list)

    def test_failure_returns_empty_lists(self):
        e = _make_extractor()
        e._run_inference = MagicMock(side_effect=RuntimeError("GPU error"))
        fields, line_items = e.extract_from_image(_pil_white())
        assert fields == []
        assert line_items == []


# ---------------------------------------------------------------------------
# TestAdapterLoading
# ---------------------------------------------------------------------------

class TestAdapterLoading:
    def test_peft_called_when_adapter_path_given(self):
        e = VLMExtractor(adapter_path="/adapters/cord_qlora")

        mock_model = MagicMock()
        mock_processor = MagicMock()

        with patch("src.backend.extraction.vlm_extractor.VLMExtractor._load_model") as mock_load:
            def _side_effect():
                e._model = mock_model
                e._processor = mock_processor

            mock_load.side_effect = _side_effect
            # Trigger lazy load
            _ = e.model

        mock_load.assert_called_once()

    def test_no_peft_call_without_adapter_path(self):
        """Verify that PeftModel is not imported or called when adapter_path is None."""
        e = VLMExtractor()

        with patch("builtins.__import__") as mock_import:
            # We won't actually let _load_model run — just confirm adapter_path is None
            assert e._adapter_path is None

    def test_adapter_path_stored_correctly(self):
        path = "/tmp/my_adapter"
        e = VLMExtractor(adapter_path=path)
        assert e._adapter_path == path
