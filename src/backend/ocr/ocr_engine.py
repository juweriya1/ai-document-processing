from dataclasses import dataclass, field
import logging
import os
import tempfile

import numpy as np

from src.backend.ingestion.preprocessing import PreprocessedPage

logger = logging.getLogger(__name__)

try:
    from docling.document_converter import DocumentConverter as _DoclingConverter
    _DOCLING_AVAILABLE = True
except ImportError:
    _DoclingConverter = None  # type: ignore[assignment,misc]
    _DOCLING_AVAILABLE = False


@dataclass
class OCRResult:
    text: str
    confidence: float
    bounding_boxes: list[list[int]] = field(default_factory=list)
    page_number: int = 1


@dataclass
class DocumentOCRResult:
    pages: list[OCRResult]
    tables: list[list[list[str]]]
    full_text: str


class OCREngine:
    """OCR engine using GOT-OCR 2.0 for text recognition and Docling for layout/table extraction.

    Args:
        languages: Language codes for EasyOCR fallback (default: ["en"]).
        use_got_ocr: If True (default), use GOT-OCR 2.0 + Docling. If False, fall back to
            EasyOCR + pdfplumber (used for baseline benchmarking and CPU-only environments).
    """

    def __init__(self, languages: list[str] | None = None, use_got_ocr: bool = False):
        self._languages = languages or ["en"]
        self._use_got_ocr = use_got_ocr
        # GOT-OCR 2.0 components (lazy-loaded)
        self._got_model = None
        self._got_tokenizer = None
        # EasyOCR fallback (lazy-loaded)
        self._reader = None

    # ------------------------------------------------------------------
    # GOT-OCR 2.0 path
    # ------------------------------------------------------------------

    def _load_got_ocr_model(self) -> tuple:
        """Load GOT-OCR 2.0 model and tokenizer from HuggingFace."""
        from transformers import AutoTokenizer, AutoModel  # type: ignore[import]
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Loading GOT-OCR 2.0 on device: %s", device)

        tokenizer = AutoTokenizer.from_pretrained(
            "stepfun-ai/GOT-OCR2_0", trust_remote_code=True
        )
        model = AutoModel.from_pretrained(
            "stepfun-ai/GOT-OCR2_0",
            trust_remote_code=True,
            low_cpu_mem_usage=True,
            device_map=device,
            use_safetensors=True,
            pad_token_id=tokenizer.eos_token_id,
        )
        model = model.eval()
        return model, tokenizer

    @property
    def got_model(self):
        """Lazy-load GOT-OCR 2.0 model (both model + tokenizer loaded together)."""
        if self._got_model is None:
            self._got_model, self._got_tokenizer = self._load_got_ocr_model()
        return self._got_model

    @property
    def got_tokenizer(self):
        """Lazy-load GOT-OCR 2.0 tokenizer (triggers model load if needed)."""
        _ = self.got_model
        return self._got_tokenizer

    @staticmethod
    def _estimate_confidence(text: str) -> float:
        """Estimate per-page extraction confidence from text density.

        This is a heuristic placeholder. Phase 7C (ConfidenceCalibrator) will learn
        per-field thresholds from the HITL corrections table.
        """
        n = len(text.strip())
        if n > 100:
            return 0.90
        elif n >= 10:
            return 0.75
        return 0.50

    def _ocr_page_with_got(self, image: np.ndarray, page_number: int = 1) -> OCRResult:
        logger.info("USING GOT OCR")
        """Run GOT-OCR 2.0 on a single page image.

        GOT-OCR requires a file path as input, so we write the image to a temporary
        file, run inference, then clean up.
        """
        from PIL import Image  # type: ignore[import]

        pil_image = Image.fromarray(image)
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
            pil_image.save(tmp_path)
            text = self.got_model.chat(
                self.got_tokenizer, tmp_path, ocr_type="format"
            )
        except Exception as e:
            logger.warning("GOT-OCR 2.0 failed on page %d: %s", page_number, e)
            text = ""
        finally:
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        return OCRResult(
            text=text,
            confidence=self._estimate_confidence(text),
            bounding_boxes=[],
            page_number=page_number,
        )

    def _extract_tables_with_docling(self, pdf_path: str) -> list[list[list[str]]]:
        """Extract tables from PDF using Docling's layout analysis."""
        if not _DOCLING_AVAILABLE:
            logger.warning("Docling not installed — skipping table extraction. Run: pip install docling")
            return []

        all_tables = []
        try:
            converter = _DoclingConverter()
            result = converter.convert(pdf_path)
            for table in result.document.tables:
                rows = []
                for row in table.data.grid:
                    cells = []
                    for cell in row:
                        try:
                            cells.append(str(cell.text) if cell.text is not None else "")
                        except AttributeError:
                            cells.append(str(cell) if cell is not None else "")
                    rows.append(cells)
                if rows:
                    all_tables.append(rows)
        except Exception as e:
            logger.warning("Docling table extraction failed for %s: %s", pdf_path, e)

        return all_tables

    # ------------------------------------------------------------------
    # EasyOCR fallback path (baseline for benchmarking)
    # ------------------------------------------------------------------

    @property
    def reader(self):
        """Lazy-load EasyOCR reader (fallback / baseline mode)."""
        if self._reader is None:
            import easyocr  # type: ignore[import]
            self._reader = easyocr.Reader(self._languages, gpu=False)
        return self._reader

    def _ocr_page_with_easyocr(self, image: np.ndarray, page_number: int = 1) -> OCRResult:
        logger.info("USING EASYOCR")
        import cv2

        logger.info("EASYOCR INPUT SHAPE: %s", image.shape)
        logger.info("EASYOCR MIN/MAX: %s / %s", image.min(), image.max())

        # SAVE IMAGE TO SEE WHAT OCR IS RECEIVING
        cv2.imwrite(f"/tmp/debug_page_{page_number}.png", image)
        logger.info("EASYOCR INPUT TYPE: %s", type(image))

        if image is None:
            logger.error("EASYOCR received None image")
            return OCRResult(text="", confidence=0.0, bounding_boxes=[], page_number=page_number)

        logger.info("EASYOCR INPUT SHAPE: %s", getattr(image, "shape", None))

        try:
            logger.info(
                "EASYOCR INPUT MIN/MAX: %s / %s",
                image.min(),
                image.max()
            )
        except Exception as e:
            logger.warning("Could not compute min/max: %s", e)
        """Run EasyOCR on a single page image (baseline/fallback mode)."""
        gray = image
        if len(image.shape) == 3:
            import cv2  # type: ignore[import]
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        results = self.reader.readtext(gray)
        logger.info("EASYOCR RAW RESULT COUNT: %s", len(results))

        if not results:
            return OCRResult(text="", confidence=0.0, bounding_boxes=[], page_number=page_number)

        texts, confidences, bboxes = [], [], []
        for bbox, text, conf in results:
            texts.append(text)
            confidences.append(conf)
            bboxes.append([int(coord) for point in bbox for coord in point])

        logger.info("EASYOCR FINAL TEXT LENGTH: %s", len(" ".join(texts)))

        return OCRResult(
            text=" ".join(texts),
            confidence=sum(confidences) / len(confidences),
            bounding_boxes=bboxes,
            page_number=page_number,
        )

    def _extract_tables_with_pdfplumber(self, pdf_path: str) -> list[list[list[str]]]:
        """Extract tables from PDF using pdfplumber (baseline/fallback mode)."""
        import pdfplumber  # type: ignore[import]

        all_tables = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_tables = page.extract_tables()
                    if page_tables:
                        for table in page_tables:
                            cleaned = [
                                [cell if cell is not None else "" for cell in row]
                                for row in table
                            ]
                            all_tables.append(cleaned)
        except Exception as e:
            logger.warning("pdfplumber failed to extract tables from %s: %s", pdf_path, e)

        return all_tables

    # ------------------------------------------------------------------
    # Public interface (unchanged from baseline — downstream code unaffected)
    # ------------------------------------------------------------------

    def extract_text_from_image(self, image: np.ndarray, page_number: int = 1) -> OCRResult:
        """Extract text from a single page image.

        Uses GOT-OCR 2.0 when use_got_ocr=True (default), otherwise EasyOCR.
        """
        if self._use_got_ocr:
            return self._ocr_page_with_got(image, page_number)
        return self._ocr_page_with_easyocr(image, page_number)

    def extract_tables_from_pdf(self, pdf_path: str) -> list[list[list[str]]]:
        """Extract tables from a PDF file.

        Uses Docling when use_got_ocr=True (default), otherwise pdfplumber.
        """
        if self._use_got_ocr:
            return self._extract_tables_with_docling(pdf_path)
        return self._extract_tables_with_pdfplumber(pdf_path)

    # def process_document(
    #     self, pages: list[PreprocessedPage], pdf_path: str | None = None
    # ) -> DocumentOCRResult:

    #     logger.info("PAGES RECEIVED: %s", len(pages))
    #     logger.info("PDF PATH: %s", pdf_path)

    #     ocr_pages = []

    #     for page in pages:
    #         logger.info("OCR PAGE INPUT SHAPE: %s", getattr(page.processed, "shape", None))

    #         result = self.extract_text_from_image(
    #             page.processed,
    #             page_number=page.page_number
    #         )

    #         logger.info("OCR PAGE RESULT LENGTH: %s", len(result.text or ""))
    #         logger.info(
    #             "PAGE %s OCR TEXT PREVIEW: %s",
    #             page.page_number,
    #             result.text[:100]
    #         )
    #         ocr_pages.append(result)

    #     logger.info("OCR TOTAL PAGES PROCESSED: %s", len(ocr_pages))

    #     if ocr_pages:
    #         logger.info("SAMPLE OCR TEXT: %s", ocr_pages[0].text[:200])
    #     else:
    #         logger.info("SAMPLE OCR TEXT: EMPTY")

    #     tables = []

    #     if pdf_path:
    #         tables = self.extract_tables_from_pdf(pdf_path)

    #     full_text = "\n\n".join(page.text for page in ocr_pages)

    #     return DocumentOCRResult(
    #         pages=ocr_pages,
    #         tables=tables,
    #         full_text=full_text,
    #     )

    def _extract_text_with_pdfplumber(self, pdf_path: str) -> str:
        import pdfplumber
        texts = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        texts.append(text)
        except Exception as e:
            logger.warning("pdfplumber text extraction failed: %s", e)
        return "\n\n".join(texts)

    def process_document(self, pages, pdf_path=None):
        ocr_pages = [
            self.extract_text_from_image(page.processed, page.page_number)
            for page in pages
        ]

        full_text = "\n\n".join(page.text for page in ocr_pages)

        # ✅ ADD THIS: if OCR produced little/no text and we have a PDF, use pdfplumber for text too
        if pdf_path and len(full_text.strip()) < 50:
            full_text = self._extract_text_with_pdfplumber(pdf_path)

        tables = self.extract_tables_from_pdf(pdf_path) if pdf_path else []
        return DocumentOCRResult(pages=ocr_pages, tables=tables, full_text=full_text)