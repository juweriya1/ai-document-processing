from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

import cv2
import numpy as np

from src.backend.extraction.heuristics import OCRBlock, apply_heuristics
from src.backend.extraction.types import ExtractionResult, completeness
from src.backend.validation.auditor import FinancialAuditor

logger = logging.getLogger(__name__)

MAX_EDGE = 1600


class LocalExtractorUnavailable(RuntimeError):
    pass


def _poly_to_bbox(poly: Any) -> tuple[float, float, float, float] | None:
    """Convert a 4-point polygon (np.ndarray or list) to axis-aligned bbox."""
    try:
        arr = np.asarray(poly, dtype=float)
    except (TypeError, ValueError):
        return None
    if arr.ndim == 1 and arr.size == 4:
        x1, y1, x2, y2 = arr.tolist()
        return float(x1), float(y1), float(x2), float(y2)
    if arr.ndim == 2 and arr.shape[1] == 2 and arr.shape[0] >= 3:
        xs = arr[:, 0]
        ys = arr[:, 1]
        return float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())
    return None


class LocalExtractor:
    """Tier-1 extractor. Wraps PaddleOCR (v3 / v2 compatible) lazily.

    On any ImportError the extractor marks itself unavailable and raises
    LocalExtractorUnavailable — the orchestrator then escalates to Tier 2.

    The loaded PaddleOCR engine is cached at the CLASS level (not the
    instance), so the cost of `PaddleOCR(...)` — which is several seconds
    even with weights already on disk — is paid exactly once per process.
    Every subsequent `LocalExtractor()` reuses the warmed engine. Critical
    for sub-3s Tier-1 latency, since ocr_node instantiates a fresh wrapper
    on every request.
    """

    # Class-level cache — shared across all instances in this process.
    _shared_engine: Any | None = None
    _shared_api: str | None = None
    _shared_unavailable: bool = False
    _shared_load_error: str | None = None
    # PaddleOCR's Predictor holds inference-time state (cached tensors) that
    # is not thread-safe under concurrent predict() calls on a single engine.
    # Serialize the forward pass with a class-level lock so multiple threads
    # can still run preprocessing (cv2) + postprocessing (parsing) in parallel
    # while only the ~1-2s of raw inference is mutually exclusive. For true
    # CPU-level parallelism on the forward pass, switch to ProcessPoolExecutor
    # (future work, ~3s process-startup cost per worker).
    _predict_lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._engine: Any | None = None
        self._available: bool | None = None
        self._api: str | None = None

    def _load(self) -> None:
        # Fast path — engine already loaded in this process.
        if LocalExtractor._shared_engine is not None:
            self._engine = LocalExtractor._shared_engine
            self._api = LocalExtractor._shared_api
            self._available = True
            return

        # Sticky failure — a prior load attempt in this process failed; don't
        # retry on every request (it'll just fail again and burn time).
        if LocalExtractor._shared_unavailable:
            raise LocalExtractorUnavailable(
                LocalExtractor._shared_load_error or "PaddleOCR unavailable on previous load"
            )

        try:
            from paddleocr import PaddleOCR
        except ImportError as e:
            LocalExtractor._shared_unavailable = True
            LocalExtractor._shared_load_error = str(e)
            self._available = False
            logger.warning("PaddleOCR not installed: %s", e)
            raise LocalExtractorUnavailable(str(e)) from e

        # PaddleOCR v5 ships two detection variants:
        #   PP-OCRv5_server_det  — ~85MB, 15-25s per page on CPU, higher F1
        #   PP-OCRv5_mobile_det  — ~5MB,  1-3s  per page on CPU, ~2-4% lower F1
        # The mobile variant is the right default for CPU-only demo hardware.
        # Recognition stays on the mobile variant that's already fast enough.
        try:
            self._engine = PaddleOCR(
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name="en_PP-OCRv5_mobile_rec",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
            self._api = "v3"
        except TypeError:
            # Older PaddleOCR releases used different kwargs. Fall back to
            # minimal args — the mobile models are still the default on v3/v2.
            try:
                self._engine = PaddleOCR(
                    lang="en",
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                )
                self._api = "v3"
            except TypeError:
                try:
                    self._engine = PaddleOCR(use_angle_cls=True, lang="en")
                    self._api = "v2"
                except Exception as e:
                    LocalExtractor._shared_unavailable = True
                    LocalExtractor._shared_load_error = str(e)
                    self._available = False
                    logger.exception("PaddleOCR v2 init failed")
                    raise LocalExtractorUnavailable(str(e)) from e
        except Exception as e:
            LocalExtractor._shared_unavailable = True
            LocalExtractor._shared_load_error = str(e)
            self._available = False
            logger.exception("PaddleOCR init failed")
            raise LocalExtractorUnavailable(str(e)) from e

        # Publish to the class-level cache so future instances reuse this.
        LocalExtractor._shared_engine = self._engine
        LocalExtractor._shared_api = self._api
        self._available = True

    @staticmethod
    def _prepare(image):
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        elif image.ndim == 3 and image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        h, w = image.shape[:2]
        if max(h, w) <= MAX_EDGE:
            return image, 1.0
        scale = MAX_EDGE / max(h, w)
        resized = cv2.resize(image, (int(w * scale), int(h * scale)))
        return resized, scale

    def _parse_v3(self, results: list) -> tuple[list[str], list[float], list[OCRBlock]]:
        texts: list[str] = []
        scores: list[float] = []
        blocks: list[OCRBlock] = []
        for r in results:
            rec_texts = r.get("rec_texts", []) if hasattr(r, "get") else getattr(r, "rec_texts", [])
            rec_scores = r.get("rec_scores", []) if hasattr(r, "get") else getattr(r, "rec_scores", [])
            rec_polys = (
                r.get("rec_polys", None) if hasattr(r, "get") else getattr(r, "rec_polys", None)
            )
            if rec_polys is None:
                rec_polys = (
                    r.get("dt_polys", None) if hasattr(r, "get") else getattr(r, "dt_polys", None)
                )
            if rec_polys is None:
                rec_polys = (
                    r.get("rec_boxes", None) if hasattr(r, "get") else getattr(r, "rec_boxes", None)
                )

            for idx, t in enumerate(rec_texts or []):
                if not t:
                    continue
                text = str(t)
                texts.append(text)
                try:
                    score = float(rec_scores[idx])
                    scores.append(score)
                except (TypeError, ValueError, IndexError):
                    score = 0.0
                bbox = None
                if rec_polys is not None:
                    try:
                        bbox = _poly_to_bbox(rec_polys[idx])
                    except (IndexError, TypeError):
                        bbox = None
                if bbox is not None:
                    x1, y1, x2, y2 = bbox
                    blocks.append(OCRBlock(text, score, x1, y1, x2, y2))
        return texts, scores, blocks

    def _parse_v2(self, results: list) -> tuple[list[str], list[float], list[OCRBlock]]:
        texts: list[str] = []
        scores: list[float] = []
        blocks: list[OCRBlock] = []
        if not results:
            return texts, scores, blocks
        page = results[0] or []
        for block in page:
            try:
                box, (text, conf) = block
            except (ValueError, TypeError):
                continue
            if not text:
                continue
            text_s = str(text)
            texts.append(text_s)
            conf_f = float(conf) if isinstance(conf, (int, float)) else 0.0
            if isinstance(conf, (int, float)):
                scores.append(conf_f)
            bbox = _poly_to_bbox(box)
            if bbox is not None:
                x1, y1, x2, y2 = bbox
                blocks.append(OCRBlock(text_s, conf_f, x1, y1, x2, y2))
        return texts, scores, blocks

    def _blocks_to_reading_order_text(self, blocks: list[OCRBlock]) -> str:
        if not blocks:
            return ""
        heights = [b.height for b in blocks]
        row_tol = max(8.0, sum(heights) / len(heights) * 0.6)
        ordered = sorted(blocks, key=lambda b: (b.cy, b.x1))
        lines: list[list[OCRBlock]] = []
        for b in ordered:
            if lines and abs(b.cy - lines[-1][0].cy) <= row_tol:
                lines[-1].append(b)
            else:
                lines.append([b])
        out_lines = []
        for line in lines:
            line.sort(key=lambda b: b.x1)
            out_lines.append(" ".join(b.text for b in line))
        return "\n".join(out_lines)

    def _extract_sync(self, pages: list[Any]) -> ExtractionResult:
        """Blocking body of extract(). Runs on a worker thread via asyncio.to_thread
        so the event loop stays responsive for other concurrent requests (status
        polls, Gemini calls for sibling batch docs).

        cv2 preprocessing and result parsing run outside the predict lock, so
        multiple threads parallelize those phases; only the engine.predict call
        itself is serialized (PaddleOCR Predictors are not thread-safe).
        """
        self._load()
        assert self._engine is not None

        all_texts: list[str] = []
        all_scores: list[float] = []
        all_blocks: list[OCRBlock] = []

        for page in pages:
            image = getattr(page, "processed", None)
            if image is None:
                image = getattr(page, "original", None)
            if image is None:
                continue
            try:
                # Preprocessing (cv2): C++ under the hood, releases GIL.
                resized, _ = self._prepare(image)
                # Inference: serialized on a class-level threading.Lock.
                # Measured: PaddlePaddle's runtime internally serializes
                # predict() calls even without this lock — the CPU backend
                # uses a shared thread pool, so thread-level Tier-1 parallelism
                # is capped at ~1x either way. We keep the lock for safety
                # (older PaddleOCR v2 API is known to corrupt engine state
                # under concurrent ocr() calls). For true CPU parallelism on
                # the forward pass, swap to ProcessPoolExecutor (each process
                # gets its own PaddlePaddle runtime, pays ~3s model load).
                with LocalExtractor._predict_lock:
                    if self._api == "v3":
                        out = self._engine.predict(resized)
                    else:
                        out = self._engine.ocr(resized, cls=True)
                # Parsing: pure Python, runs outside the lock.
                if self._api == "v3":
                    texts, scores, blocks = self._parse_v3(out)
                else:
                    texts, scores, blocks = self._parse_v2(out)
            except Exception as e:
                logger.exception("PaddleOCR inference failed on page")
                raise LocalExtractorUnavailable(f"inference_failed: {e}") from e
            all_texts.extend(texts)
            all_scores.extend(scores)
            all_blocks.extend(blocks)

        layout_text = self._blocks_to_reading_order_text(all_blocks)
        raw_text = layout_text if layout_text else "\n".join(all_texts)
        fields = apply_heuristics(raw_text, blocks=all_blocks)
        ocr_mean = sum(all_scores) / len(all_scores) if all_scores else 0.0

        result = ExtractionResult(
            fields=fields,
            line_items=[],
            confidence=ocr_mean,
            raw_text=raw_text,
            tier="local",
        )
        comp = completeness(result)
        audit = FinancialAuditor().audit(fields)
        math_verified = (
            audit.ok
            and audit.reason is None
            and audit.total is not None
            and audit.subtotal is not None
            and audit.tax is not None
        )
        if math_verified:
            # Math-verified triple is a strong signal; weight OCR quality + floor it.
            base = 0.3 * comp + 0.7 * ocr_mean
            result.confidence = round(max(base, 0.86), 4)
        else:
            result.confidence = round(0.6 * comp + 0.4 * ocr_mean, 4)
        return result

    async def extract(self, pages: list[Any]) -> ExtractionResult:
        """Async wrapper — offloads the blocking OCR loop to a worker thread.

        Public contract unchanged: callers still `await extractor.extract(pages)`.
        The win is that while one doc is doing CPU-bound OCR, the event loop
        can service Gemini calls (I/O-bound) for sibling docs in the same batch,
        producing genuine overlap instead of serialization.
        """
        return await asyncio.to_thread(self._extract_sync, pages)
