from __future__ import annotations

import io
import logging
import os
from typing import Any

from src.backend.extraction.types import ExtractionResult, completeness

logger = logging.getLogger(__name__)


class NeuralUnavailableError(RuntimeError):
    pass


def _numpy_to_png_bytes(image: Any) -> bytes:
    from PIL import Image
    import numpy as np

    arr = image
    if arr.ndim == 2:
        pil = Image.fromarray(arr)
    else:
        if arr.shape[2] == 3:
            pil = Image.fromarray(arr[:, :, ::-1])
        else:
            pil = Image.fromarray(arr)
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return buf.getvalue()


class NeuralFallback:
    """Tier-2 extractor. BAML-driven Gemini 2.5 Flash extraction with a
    direct-Gemini fallback path if BAML client isn't generated yet.

    Never crashes the pipeline: missing key / missing SDK raises
    NeuralUnavailableError for the orchestrator to translate into FLAGGED.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self._baml: Any | None = None
        self._baml_async: Any | None = None
        self._gemini: Any | None = None

    def _ensure_api_key(self) -> None:
        if not self._api_key:
            raise NeuralUnavailableError("GOOGLE_API_KEY not set")

    def _load_baml(self) -> Any | None:
        if self._baml is not None:
            return self._baml
        try:
            from baml_client import b  # type: ignore
            self._baml = b
            return b
        except ImportError:
            logger.info("baml_client not generated; falling back to direct Gemini")
            return None

    def _load_baml_async(self) -> Any | None:
        if self._baml_async is not None:
            return self._baml_async
        try:
            from baml_client.async_client import b as b_async  # type: ignore
            self._baml_async = b_async
            return b_async
        except ImportError:
            logger.info("baml_client async client not generated; reconcile will fall back")
            return None

    def _load_gemini(self) -> Any:
        if self._gemini is not None:
            return self._gemini
        try:
            from google import genai  # type: ignore
        except ImportError as e:
            raise NeuralUnavailableError(f"google-genai not installed: {e}") from e
        self._gemini = genai.Client(api_key=self._api_key)
        return self._gemini

    async def extract(self, page_image: Any) -> ExtractionResult:
        self._ensure_api_key()
        png = _numpy_to_png_bytes(page_image)

        baml = self._load_baml()
        if baml is not None:
            try:
                from baml_py import Image as BamlImage  # type: ignore
                img = BamlImage.from_base64("image/png", _to_b64(png))
                raw = baml.ExtractInvoice(image=img)
                fields = _coerce_fields(raw)
            except Exception as e:
                logger.exception("BAML call failed; falling back to direct Gemini")
                fields = self._direct_gemini(png)
        else:
            fields = self._direct_gemini(png)

        result = ExtractionResult(
            fields=fields,
            line_items=[],
            confidence=0.0,
            raw_text="",
            tier="vlm",
        )
        comp = completeness(result)
        # Tier 2 has no block-level OCR confidence; use completeness + audit-weight later
        result.confidence = round(0.8 * comp + 0.2, 4)
        return result

    async def reconcile(self, page_image: Any, error_context: str) -> ExtractionResult:
        """Targeted Gemini re-scan driven by an auditor-produced guidance string.

        Calls BAML's ReconcileInvoice with the `error_context` argument the
        agentic auditor_node produced (e.g. "magnitude_error: likely decimal-
        point slip in subtotal ..."). Same graceful-bypass contract as
        `extract()`: raises NeuralUnavailableError on missing key / SDK, never
        on a failed inference.
        """
        self._ensure_api_key()
        png = _numpy_to_png_bytes(page_image)

        baml = self._load_baml_async()
        line_items: list[dict] = []
        if baml is not None:
            try:
                from baml_py import Image as BamlImage  # type: ignore
                img = BamlImage.from_base64("image/png", _to_b64(png))
                raw = await baml.ReconcileInvoice(image=img, error_context=error_context)
                fields = _coerce_fields(raw)
                line_items = _coerce_line_items(getattr(raw, "line_items", None))
            except Exception as e:
                # BAML's retry policy already tried the primary model up to its
                # max, then fell back to the secondary model (see
                # baml_src/clients.baml). If we land here, every model in the
                # fallback chain failed — surface that as unavailable so the
                # reconciler_node routes to HITL rather than burning another
                # round against the same overloaded backend via direct Gemini.
                logger.warning("BAML ReconcileInvoice exhausted fallback chain: %s", e)
                raise NeuralUnavailableError(f"gemini_unavailable_all_fallbacks: {e}") from e
        else:
            # BAML client not generated — use direct Gemini as a last resort.
            fields = self._direct_gemini_reconcile(png, error_context)

        result = ExtractionResult(
            fields=fields,
            line_items=line_items,
            confidence=0.0,
            raw_text="",
            tier="vlm",
        )
        comp = completeness(result)
        result.confidence = round(0.8 * comp + 0.2, 4)
        return result

    def _direct_gemini_reconcile(self, png: bytes, error_context: str) -> dict[str, str | None]:
        client = self._load_gemini()
        prompt = (
            "You are performing a TARGETED RE-SCAN of a financial document. A "
            "prior extraction failed strict-Decimal math reconciliation with "
            f"this diagnostic:\n\n{error_context}\n\n"
            "Re-extract the invoice as strict JSON with keys: invoice_number, "
            "date (YYYY-MM-DD), vendor_name, subtotal, tax, total_amount. Pay "
            "EXTRA attention to the field(s) named in the diagnostic above. "
            "Watch for decimal-point placement, currency markers ($, €, £), "
            "and OCR digit confusions (0↔O, 1↔l, 8↔B). Preserve currency "
            "markers exactly. Your output must satisfy "
            "subtotal + tax == total_amount. Respond with JSON only."
        )
        try:
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    {"parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": "image/png", "data": _to_b64(png)}},
                    ]}
                ],
            )
            text = getattr(resp, "text", None) or ""
        except Exception as e:
            raise NeuralUnavailableError(f"gemini_call_failed: {e}") from e
        return _parse_gemini_json(text)

    def _direct_gemini(self, png: bytes) -> dict[str, str | None]:
        client = self._load_gemini()
        prompt = (
            "Extract the following fields from this invoice as strict JSON: "
            "invoice_number, date (YYYY-MM-DD), vendor_name, subtotal, tax, total_amount. "
            "Preserve currency markers ($, €, £) and thousands separators. "
            "Use null for missing fields. Respond with JSON only, no prose."
        )
        try:
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    {"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/png", "data": _to_b64(png)}}]}
                ],
            )
            text = getattr(resp, "text", None) or ""
        except Exception as e:
            raise NeuralUnavailableError(f"gemini_call_failed: {e}") from e
        return _parse_gemini_json(text)


def _to_b64(data: bytes) -> str:
    import base64
    return base64.b64encode(data).decode("ascii")


def _coerce_fields(obj: Any) -> dict[str, str | None]:
    keys = ("invoice_number", "date", "vendor_name", "subtotal", "tax", "total_amount")
    out: dict[str, str | None] = {}
    for k in keys:
        v = getattr(obj, k, None)
        if v is None and isinstance(obj, dict):
            v = obj.get(k)
        out[k] = str(v) if v not in (None, "") else None
    return out


def _coerce_line_items(items: Any) -> list[dict]:
    """Convert BAML LineItem[] (or dicts) into plain list[dict] matching the
    ExtractionResult.line_items contract."""
    if not items:
        return []
    out: list[dict] = []
    for it in items:
        if hasattr(it, "model_dump"):
            out.append(it.model_dump())
        elif isinstance(it, dict):
            out.append({k: v for k, v in it.items() if k in {"description", "quantity", "unit_price", "total"}})
    return out


def _parse_gemini_json(text: str) -> dict[str, str | None]:
    import json
    import re
    if not text:
        return {}
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: (str(v) if v not in (None, "") else None) for k, v in data.items()}
