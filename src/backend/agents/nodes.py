from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from src.backend.agents.state import AgentState, ExtractedInvoice, LineItem
from src.backend.db.crud import store_extracted_fields, store_line_items
from src.backend.db.database import SessionLocal
from src.backend.db.models import (
    Document as DocumentModel,
    ExtractedField as ExtractedFieldModel,
    LineItem as LineItemModel,
)
from src.backend.extraction.local_extractor import LocalExtractor, LocalExtractorUnavailable
from src.backend.extraction.neural_fallback import NeuralFallback, NeuralUnavailableError
from src.backend.extraction.types import ExtractionResult, is_empty
from src.backend.ingestion.preprocessing import Preprocessing
from src.backend.pipeline.document_processor import TraceEntry
from src.backend.pipeline.reason_codes import ReasonCode
from src.backend.pipeline.states import DocState, db_status_for
from src.backend.utils.currency import normalize_amount
from src.backend.validation.auditor import FinancialAuditor, detect_magnitude_slip

logger = logging.getLogger(__name__)

_GUIDANCE_LOG_CAP = 240  # chars of reconciliation_guidance to persist into the trace
LOCAL_CONFIDENCE_THRESHOLD = 0.85  # below this, escalate to Tier-2 even if math balances


def _invoice_to_fields(inv: ExtractedInvoice) -> dict[str, str | None]:
    return {
        "invoice_number": inv.invoice_number,
        "date": inv.date,
        "vendor_name": inv.vendor_name,
        "subtotal": inv.subtotal,
        "tax": inv.tax,
        "total_amount": inv.total_amount,
    }


def _extraction_to_invoice(result: ExtractionResult) -> ExtractedInvoice:
    """Map the dataclass ExtractionResult produced by LocalExtractor /
    NeuralFallback onto the Pydantic AgentState shape. Defensive about both
    unknown keys and partially-filled line item dicts."""
    f = result.fields or {}
    items = []
    for raw in result.line_items or []:
        if not isinstance(raw, dict):
            continue
        items.append(
            LineItem(
                description=raw.get("description"),
                quantity=raw.get("quantity"),
                unit_price=raw.get("unit_price"),
                total=raw.get("total"),
            )
        )
    return ExtractedInvoice(
        invoice_number=f.get("invoice_number"),
        date=f.get("date"),
        vendor_name=f.get("vendor_name"),
        subtotal=f.get("subtotal"),
        tax=f.get("tax"),
        total_amount=f.get("total_amount"),
        line_items=items,
    )


def _pick_page_image(pages: list[Any] | None) -> Any | None:
    """Return the first usable page image, preferring preprocessed over raw."""
    if not pages:
        return None
    for page in pages:
        img = getattr(page, "processed", None)
        if img is None:
            img = getattr(page, "original", None)
        if img is not None:
            return img
    return None


def _dec_str(x: Decimal | None) -> str | None:
    return None if x is None else str(x)


def _fmt_field(name: str, value: Decimal | None) -> str:
    """Render a field for inclusion in VLM guidance — avoids leaking bare `None`."""
    return f"{name}={value}" if value is not None else f"{name} was not extracted"


async def auditor_node(state: AgentState) -> AgentState:
    """Decimal-math audit node with Magnitude Guard.

    Runs FinancialAuditor against the current `extracted_data`. On failure,
    runs `detect_magnitude_slip` to flag power-of-10 decimal slips and packs
    a targeted `error_context` string that the reconciler feeds to Gemini.
    """
    if state.extracted_data is None:
        entry = TraceEntry.now(
            "audit", DocState.LOCALLY_PARSED, False,
            reason=ReasonCode.LOCAL_AUDIT_FAIL,
            attempt=state.attempts,
            note="no_extracted_data",
        )
        return state.model_copy(update={
            "is_valid": False,
            "reconciliation_guidance": (
                "Local OCR extraction was unavailable for this document. "
                "Perform a full extraction from scratch: capture invoice_number, "
                "date, vendor_name, subtotal, tax, total_amount, and every line "
                "item. Preserve currency markers exactly (Rs., /-, lakh-style "
                "commas, $, etc.) and verify that subtotal + tax == total."
            ),
            "reason": ReasonCode.LOCAL_AUDIT_FAIL.value,
            "audit_log": [*state.audit_log, asdict(entry)],
        })

    auditor = FinancialAuditor()
    fields = _invoice_to_fields(state.extracted_data)
    report = auditor.audit(fields)

    if report.ok:
        # Quality gates beyond the raw math check:
        #   (a) `partial_data` — subtotal OR tax was None, so the equation was
        #       never actually verified. Only the total is trustworthy.
        #   (b) low OCR confidence — PaddleOCR itself is unsure; the digits may
        #       be wrong even if they happen to arithmetically balance.
        # These only escalate from Tier-1 (tier="local"). Once a Tier-2 pass
        # has produced the current extraction, we trust its result: Gemini
        # confirming "there is no tax line" is a legitimate finding, not
        # something to keep re-asking. Otherwise the graph loops on receipts
        # whose fields are genuinely absent (common on Pakistani restaurant
        # receipts where tax is baked into the per-dish price).
        already_vlm_reconciled = state.tier == "vlm"
        partial_data = report.reason == "partial_data"
        low_confidence = (
            state.ocr_confidence is not None
            and state.ocr_confidence < LOCAL_CONFIDENCE_THRESHOLD
        )
        if not already_vlm_reconciled and (partial_data or low_confidence):
            reasons = []
            if partial_data:
                missing = []
                if report.subtotal is None:
                    missing.append("subtotal")
                if report.tax is None:
                    missing.append("tax")
                reasons.append(
                    f"partial_data: local extraction returned a total "
                    f"({report.total}) but was missing "
                    f"{' and '.join(missing)} — the math invariant "
                    f"subtotal + tax = total was never actually verified"
                )
            if low_confidence:
                reasons.append(
                    f"low_ocr_confidence: {state.ocr_confidence:.3f} < "
                    f"{LOCAL_CONFIDENCE_THRESHOLD} — the local OCR engine was "
                    f"unsure about the digits it read, so re-extraction by a "
                    f"stronger model is warranted even though the math checks out"
                )
            guidance = (
                "Re-extract the invoice fields from scratch. The local extractor "
                "passed math reconciliation but failed a data-quality gate:\n\n"
                + "\n\n".join(reasons)
                + "\n\nFocus on reading every digit of subtotal, tax, and total "
                "accurately. Preserve currency markers exactly."
            )
            entry = TraceEntry.now(
                "audit", DocState.LOCALLY_PARSED, False,
                reason=(
                    ReasonCode.LOCAL_LOW_CONFIDENCE if low_confidence
                    else ReasonCode.LOCAL_AUDIT_FAIL
                ),
                attempt=state.attempts,
                subtotal=_dec_str(report.subtotal),
                tax=_dec_str(report.tax),
                total=_dec_str(report.total),
                audit_reason=report.reason,
                ocr_confidence=state.ocr_confidence,
                partial_data=partial_data,
                low_confidence=low_confidence,
            )
            return state.model_copy(update={
                "is_valid": False,
                "reason": (
                    ReasonCode.LOCAL_LOW_CONFIDENCE.value if low_confidence
                    else ReasonCode.LOCAL_AUDIT_FAIL.value
                ),
                "reconciliation_guidance": guidance,
                "audit_log": [*state.audit_log, asdict(entry)],
            })

        entry = TraceEntry.now(
            "audit", DocState.LOCALLY_PARSED, True,
            reason=ReasonCode.LOCAL_OK,
            attempt=state.attempts,
            subtotal=_dec_str(report.subtotal),
            tax=_dec_str(report.tax),
            total=_dec_str(report.total),
            delta=_dec_str(report.delta),
            audit_reason=report.reason,
            ocr_confidence=state.ocr_confidence,
        )
        return state.model_copy(update={
            "is_valid": True,
            "reason": ReasonCode.LOCAL_OK.value,
            "reconciliation_guidance": None,
            "audit_log": [*state.audit_log, asdict(entry)],
        })

    line_item_dicts = [li.model_dump() for li in state.extracted_data.line_items]
    slip = detect_magnitude_slip(report, line_items=line_item_dicts)

    if slip is not None:
        guidance = slip
        magnitude = "magnitude_error"
    elif report.reason == "missing_total":
        guidance = (
            "The extracted invoice has no parseable total amount. Observed "
            f"{_fmt_field('subtotal', report.subtotal)} and "
            f"{_fmt_field('tax', report.tax)}. Re-scan the document and "
            "identify the total — it is typically labeled 'Total', 'Grand "
            "Total', 'Amount Due', 'Net Payable', or similar. Preserve the "
            "original currency markers exactly."
        )
        magnitude = None
    elif report.reason == "unreadable_total":
        guidance = (
            "A total field was located on the invoice but it could not be "
            "parsed as a number — it may contain stray characters or an OCR "
            "digit misread. Re-scan the total field carefully, preserving "
            "currency markers (Rs., /-, lakh-style commas, $, etc.) exactly "
            "as they appear on the document."
        )
        magnitude = None
    else:
        expected = (report.subtotal or Decimal(0)) + (report.tax or Decimal(0))
        guidance = (
            f"Math reconciliation failed: {_fmt_field('subtotal', report.subtotal)} "
            f"+ {_fmt_field('tax', report.tax)} = {expected}, but the extracted "
            f"total is {report.total} (delta={report.delta}). This is not a "
            "clean power-of-10 slip, so more than one field may be mis-"
            "extracted. Re-scan subtotal, tax, and total digit by digit and "
            "verify that subtotal + tax == total before returning values."
        )
        magnitude = None

    entry = TraceEntry.now(
        "audit", DocState.LOCALLY_PARSED, False,
        reason=ReasonCode.LOCAL_AUDIT_FAIL,
        attempt=state.attempts,
        audit_reason=report.reason,
        magnitude=magnitude,
        subtotal=_dec_str(report.subtotal),
        tax=_dec_str(report.tax),
        total=_dec_str(report.total),
        delta=_dec_str(report.delta),
    )
    return state.model_copy(update={
        "is_valid": False,
        "reason": ReasonCode.LOCAL_AUDIT_FAIL.value,
        "reconciliation_guidance": guidance,
        "audit_log": [*state.audit_log, asdict(entry)],
    })


async def ocr_node(state: AgentState) -> AgentState:
    """Tier-1 local extraction via PaddleOCR (LocalExtractor).

    On LocalExtractorUnavailable or any runtime error, leaves
    `extracted_data=None` and flips `tier="vlm"` so the auditor_node's
    no-data branch kicks in and routes the graph straight to reconciliation
    (the "Module Bypass" rule from CLAUDE.md — never crash, always produce a
    result). Empty extractions are treated as a soft failure with the same
    bypass behavior.
    """
    t0 = time.perf_counter()
    try:
        extractor = LocalExtractor()
        result = await extractor.extract(state.pages or [])
    except LocalExtractorUnavailable as e:
        entry = TraceEntry.now(
            "ocr", DocState.PREPROCESSED, False,
            reason=ReasonCode.LOCAL_IMPORT_ERROR,
            attempt=state.attempts,
            error=str(e),
            elapsed_ms=round((time.perf_counter() - t0) * 1000, 1),
        )
        return state.model_copy(update={
            "extracted_data": None,
            "tier": "vlm",
            "reason": ReasonCode.LOCAL_IMPORT_ERROR.value,
            "audit_log": [*state.audit_log, asdict(entry)],
        })
    except Exception as e:
        logger.exception("ocr_node runtime error")
        entry = TraceEntry.now(
            "ocr", DocState.PREPROCESSED, False,
            reason=ReasonCode.LOCAL_RUNTIME_ERROR,
            attempt=state.attempts,
            error=str(e),
            elapsed_ms=round((time.perf_counter() - t0) * 1000, 1),
        )
        return state.model_copy(update={
            "extracted_data": None,
            "tier": "vlm",
            "reason": ReasonCode.LOCAL_RUNTIME_ERROR.value,
            "audit_log": [*state.audit_log, asdict(entry)],
        })
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    logger.info("ocr_node elapsed=%.1fms confidence=%.3f", elapsed_ms, result.confidence)

    if is_empty(result):
        entry = TraceEntry.now(
            "ocr", DocState.LOCALLY_PARSED, False,
            reason=ReasonCode.LOCAL_EMPTY_EXTRACTION,
            attempt=state.attempts,
            confidence=result.confidence,
            page_count=len(state.pages or []),
            elapsed_ms=elapsed_ms,
        )
        return state.model_copy(update={
            "extracted_data": None,
            "tier": "vlm",
            "reason": ReasonCode.LOCAL_EMPTY_EXTRACTION.value,
            "audit_log": [*state.audit_log, asdict(entry)],
        })

    invoice = _extraction_to_invoice(result)
    entry = TraceEntry.now(
        "ocr", DocState.LOCALLY_PARSED, True,
        reason=ReasonCode.LOCAL_OK,
        attempt=state.attempts,
        confidence=result.confidence,
        fields_found=sum(1 for v in result.fields.values() if v),
        line_items_found=len(result.line_items),
        elapsed_ms=elapsed_ms,
    )
    return state.model_copy(update={
        "extracted_data": invoice,
        "ocr_confidence": float(result.confidence),
        "tier": "local",
        "reason": ReasonCode.LOCAL_OK.value,
        "audit_log": [*state.audit_log, asdict(entry)],
    })


async def reconciler_node(state: AgentState) -> AgentState:
    """Tier-2 targeted re-scan via Gemini 2.5 Flash through BAML.

    Consumes `state.reconciliation_guidance` verbatim as the `error_context`
    argument of the BAML `ReconcileInvoice` function. On success, replaces
    `extracted_data` with the Gemini result, increments `attempts`, and clears
    `reconciliation_guidance` (the next auditor_node pass will set a new one
    if math still fails). On unavailability (missing key / missing SDK),
    flips `tier="hitl"` to exit the reconciliation loop at the next route.
    """
    image = _pick_page_image(state.pages)
    if image is None:
        entry = TraceEntry.now(
            "reconcile", DocState.LOCALLY_PARSED, False,
            reason=ReasonCode.VLM_RUNTIME_ERROR,
            attempt=state.attempts,
            error="no_image_on_pages",
        )
        return state.model_copy(update={
            "tier": "hitl",
            "reason": ReasonCode.VLM_RUNTIME_ERROR.value,
            "audit_log": [*state.audit_log, asdict(entry)],
        })

    guidance = state.reconciliation_guidance or (
        "Prior extraction failed reconciliation but produced no diagnostic. "
        "Perform a full re-extraction of the invoice with careful attention "
        "to decimal placement and currency markers; ensure subtotal + tax = total."
    )

    t0 = time.perf_counter()
    try:
        neural = NeuralFallback()
        result = await neural.reconcile(image, guidance)
    except NeuralUnavailableError as e:
        entry = TraceEntry.now(
            "reconcile", DocState.LOCALLY_PARSED, False,
            reason=ReasonCode.VLM_UNAVAILABLE,
            attempt=state.attempts,
            error=str(e),
            guidance_used=guidance[:_GUIDANCE_LOG_CAP],
            elapsed_ms=round((time.perf_counter() - t0) * 1000, 1),
        )
        return state.model_copy(update={
            "tier": "hitl",
            "reason": ReasonCode.VLM_UNAVAILABLE.value,
            "attempts": state.attempts + 1,
            "audit_log": [*state.audit_log, asdict(entry)],
        })
    except Exception as e:
        logger.exception("reconciler_node runtime error")
        entry = TraceEntry.now(
            "reconcile", DocState.LOCALLY_PARSED, False,
            reason=ReasonCode.VLM_RUNTIME_ERROR,
            attempt=state.attempts,
            error=str(e),
            guidance_used=guidance[:_GUIDANCE_LOG_CAP],
            elapsed_ms=round((time.perf_counter() - t0) * 1000, 1),
        )
        return state.model_copy(update={
            "tier": "vlm",
            "reason": ReasonCode.VLM_RUNTIME_ERROR.value,
            "attempts": state.attempts + 1,
            "audit_log": [*state.audit_log, asdict(entry)],
        })
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    logger.info("reconciler_node elapsed=%.1fms confidence=%.3f", elapsed_ms, result.confidence)

    invoice = _extraction_to_invoice(result)
    entry = TraceEntry.now(
        "reconcile", DocState.VLM_RECONCILED, True,
        reason=ReasonCode.VLM_RETRIED,
        attempt=state.attempts,
        confidence=result.confidence,
        fields_found=sum(1 for v in result.fields.values() if v),
        line_items_found=len(result.line_items),
        guidance_used=guidance[:_GUIDANCE_LOG_CAP],
        elapsed_ms=elapsed_ms,
    )
    return state.model_copy(update={
        "extracted_data": invoice,
        "ocr_confidence": float(result.confidence),
        "tier": "vlm",
        "attempts": state.attempts + 1,
        "reason": ReasonCode.VLM_RETRIED.value,
        "reconciliation_guidance": None,  # consumed — next auditor pass sets fresh guidance if still broken
        "audit_log": [*state.audit_log, asdict(entry)],
    })


async def preprocess_node(state: AgentState) -> AgentState:
    """Run ingestion.Preprocessing on state.file_path and populate state.pages.

    The preprocessor is CPU-bound (OpenCV deskew + denoise + PDF rasterization),
    so we offload it to a thread so the event loop stays responsive for other
    in-flight requests while a single document preprocesses.
    """
    try:
        pages = await asyncio.to_thread(
            Preprocessing().preprocess_document, state.file_path
        )
    except FileNotFoundError as e:
        logger.warning("preprocess_node: file not found %s", state.file_path)
        entry = TraceEntry.now(
            "preprocess", DocState.FAILED, False,
            reason=ReasonCode.PREPROCESS_FAIL,
            error=f"file_not_found: {e}",
        )
        return state.model_copy(update={
            "tier": "hitl",
            "reason": ReasonCode.PREPROCESS_FAIL.value,
            "audit_log": [*state.audit_log, asdict(entry)],
        })
    except Exception as e:
        logger.exception("preprocess_node failed for %s", state.file_path)
        entry = TraceEntry.now(
            "preprocess", DocState.FAILED, False,
            reason=ReasonCode.PREPROCESS_FAIL,
            error=str(e),
        )
        return state.model_copy(update={
            "tier": "hitl",
            "reason": ReasonCode.PREPROCESS_FAIL.value,
            "audit_log": [*state.audit_log, asdict(entry)],
        })

    entry = TraceEntry.now(
        "preprocess", DocState.PREPROCESSED, True,
        page_count=len(pages),
    )
    return state.model_copy(update={
        "pages": pages,
        "audit_log": [*state.audit_log, asdict(entry)],
    })


def _as_float(value: Any) -> float | None:
    """Coerce a Gemini-returned string like "$19.00" or "Rs. 1,500/-" into a
    plain float for SQLAlchemy's line_items.quantity/unit_price/total columns.
    Returns None for unparseable or missing values — line_items never blocks
    persistence on a single bad numeric cell."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    dec = normalize_amount(value)
    return float(dec) if dec is not None else None


def _last_confidence(audit_log: list[dict]) -> float | None:
    """Extract the most recent OCR/reconcile confidence from the trace.

    Persisted on Document.confidence_score for dashboards and reviewer UI.
    Returns None if no node in the trace reported a confidence value.
    """
    for entry in reversed(audit_log):
        detail = entry.get("detail") or {}
        conf = detail.get("confidence")
        if conf is not None:
            try:
                return float(conf)
            except (TypeError, ValueError):
                continue
    return None


_FINANCIAL_FIELDS = frozenset({"subtotal", "tax", "total_amount"})
_AUDIT_FAIL_REASONS = frozenset(
    {"math_mismatch", "missing_total", "unreadable_total"}
)


def _last_audit_entry(audit_log: list[dict]) -> dict | None:
    for entry in reversed(audit_log):
        if entry.get("stage") == "audit":
            return entry
    return None


def _per_field_confidence(
    state: AgentState,
    field_name: str,
    value: Any,
    base: float | None,
) -> float:
    """Derive a per-field confidence from available state signals.

    PaddleOCR / Gemini emit only document-level confidences, so we modulate
    that scalar per field using three signals:
      - value presence (missing => 0.0)
      - tier (vlm pins to a mid-high range since Gemini is stronger but
        returns no per-field score)
      - last audit outcome (financial fields implicated in a math failure
        are capped so the HITL queue surfaces them)
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return 0.0

    conf = base if base is not None else 0.80
    conf = max(0.0, min(0.99, float(conf)))

    if state.tier == "vlm":
        conf = min(0.95, max(conf, 0.90))

    audit = _last_audit_entry(state.audit_log)
    if (
        audit is not None
        and audit.get("ok") is False
        and field_name in _FINANCIAL_FIELDS
    ):
        reason = (audit.get("detail") or {}).get("audit_reason")
        if reason in _AUDIT_FAIL_REASONS:
            conf = min(conf, 0.55)

    return round(conf, 3)


def _resolve_final_state(state: AgentState) -> DocState:
    if state.is_valid:
        return DocState.VERIFIED
    return DocState.FLAGGED


def _persist_to_db(state: AgentState, final_state: DocState) -> dict[str, Any]:
    """Synchronous DB write — called from persist_node via asyncio.to_thread."""
    db = SessionLocal()
    written = {"fields": 0, "line_items": 0, "document_updated": False}
    try:
        doc = db.query(DocumentModel).filter(DocumentModel.id == state.document_id).first()
        if doc is None:
            logger.warning("persist_node: document %s not found", state.document_id)
            return written

        # Replace prior extraction outputs so re-runs don't accumulate.
        db.query(ExtractedFieldModel).filter(
            ExtractedFieldModel.document_id == state.document_id
        ).delete()
        db.query(LineItemModel).filter(
            LineItemModel.document_id == state.document_id
        ).delete()
        db.commit()

        confidence = _last_confidence(state.audit_log)
        base_conf = (
            confidence
            if confidence is not None
            else state.ocr_confidence
        )

        if state.extracted_data is not None:
            field_names = (
                "invoice_number", "date", "vendor_name",
                "subtotal", "tax", "total_amount",
            )
            payload = []
            for name in field_names:
                value = getattr(state.extracted_data, name)
                payload.append({
                    "field_name": name,
                    "field_value": value,
                    "confidence": _per_field_confidence(state, name, value, base_conf),
                })
            written["fields"] = len(store_extracted_fields(db, state.document_id, payload))

            # DB columns are Float; Gemini returns strings with currency
            # markers ("$19.00"). Strip and parse via normalize_amount.
            line_items = [
                {
                    "description": li.description,
                    "quantity": _as_float(li.quantity),
                    "unit_price": _as_float(li.unit_price),
                    "total": _as_float(li.total),
                }
                for li in state.extracted_data.line_items
            ]
            if line_items:
                written["line_items"] = len(
                    store_line_items(db, state.document_id, line_items)
                )

        doc.status = db_status_for(final_state)
        doc.fallback_tier = state.tier
        if confidence is not None:
            doc.confidence_score = confidence
        doc.traceability_log = list(state.audit_log)
        doc.processed_at = datetime.now(timezone.utc)
        db.commit()
        written["document_updated"] = True
    except Exception:
        logger.exception("persist_node DB write failed for %s", state.document_id)
        db.rollback()
        raise
    finally:
        db.close()
    return written


async def persist_node(state: AgentState) -> AgentState:
    """Terminal node. Writes extracted fields, line items, Document.status,
    Document.traceability_log, Document.fallback_tier, Document.confidence_score.

    Database calls run in a worker thread so the compiled graph stays async.
    On DB failure we append a PERSIST_FAIL trace entry and still return the
    state — the graph never crashes the caller; FLAGGED is worst-case.
    """
    final_state = _resolve_final_state(state)

    try:
        written = await asyncio.to_thread(_persist_to_db, state, final_state)
        entry = TraceEntry.now(
            "persist", final_state, True,
            reason=(ReasonCode.LOCAL_OK if state.is_valid else ReasonCode.LOCAL_AUDIT_FAIL),
            status=db_status_for(final_state),
            tier=state.tier,
            fields_written=written["fields"],
            line_items_written=written["line_items"],
        )
    except Exception as e:
        logger.exception("persist_node failed")
        entry = TraceEntry.now(
            "persist", final_state, False,
            reason=ReasonCode.PERSIST_FAIL,
            error=str(e),
            tier=state.tier,
        )

    return state.model_copy(update={
        "audit_log": [*state.audit_log, asdict(entry)],
    })
