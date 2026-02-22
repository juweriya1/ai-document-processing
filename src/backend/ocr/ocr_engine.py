from dataclasses import dataclass, field
import logging

import numpy as np

from src.backend.ingestion.preprocessing import PreprocessedPage

logger = logging.getLogger(__name__)


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
    def __init__(self, languages: list[str] | None = None):
        self._languages = languages or ["en"]
        self._reader = None

    @property
    def reader(self):
        if self._reader is None:
            import easyocr
            self._reader = easyocr.Reader(self._languages, gpu=False)
        return self._reader

    def extract_text_from_image(self, image: np.ndarray, page_number: int = 1) -> OCRResult:
        gray = image
        if len(image.shape) == 3:
            import cv2
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        results = self.reader.readtext(gray)

        if not results:
            return OCRResult(text="", confidence=0.0, bounding_boxes=[], page_number=page_number)

        texts = []
        confidences = []
        bboxes = []
        for bbox, text, conf in results:
            texts.append(text)
            confidences.append(conf)
            flat_bbox = [int(coord) for point in bbox for coord in point]
            bboxes.append(flat_bbox)

        full_text = " ".join(texts)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return OCRResult(
            text=full_text,
            confidence=avg_confidence,
            bounding_boxes=bboxes,
            page_number=page_number,
        )

    def extract_tables_from_pdf(self, pdf_path: str) -> list[list[list[str]]]:
        import pdfplumber

        all_tables = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_tables = page.extract_tables()
                    if page_tables:
                        for table in page_tables:
                            cleaned = []
                            for row in table:
                                cleaned.append([cell if cell is not None else "" for cell in row])
                            all_tables.append(cleaned)
        except Exception as e:
            logger.warning("Failed to extract tables from %s: %s", pdf_path, e)

        return all_tables

    def process_document(
        self, pages: list[PreprocessedPage], pdf_path: str | None = None
    ) -> DocumentOCRResult:
        ocr_pages = []
        for page in pages:
            result = self.extract_text_from_image(page.processed, page_number=page.page_number)
            ocr_pages.append(result)

        tables = []
        if pdf_path:
            tables = self.extract_tables_from_pdf(pdf_path)

        full_text = "\n".join(page.text for page in ocr_pages)

        return DocumentOCRResult(
            pages=ocr_pages,
            tables=tables,
            full_text=full_text,
        )
