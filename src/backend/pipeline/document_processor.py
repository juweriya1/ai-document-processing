from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.backend.db.crud import (
    get_document,
    store_extracted_fields,
    store_line_items,
    update_document_status,
)
from src.backend.extraction.local_extractor import LocalExtractor, LocalExtractorUnavailable
from src.backend.extraction.neural_fallback import NeuralFallback, NeuralUnavailableError
from src.backend.extraction.types import ExtractionResult, is_empty
from src.backend.ingestion.preprocessing import Preprocessing
from src.backend.pipeline.reason_codes import ReasonCode
from src.backend.pipeline.states import DocState, db_status_for
from src.backend.validation.auditor import AuditReport, FinancialAuditor
from src.backend.validation.schema_validator import validate_document_fields

logger = logging.getLogger(__name__)

LOCAL_CONFIDENCE_THRESHOLD = 0.85
MAX_VLM_RETRIES = 1


@dataclass
class TraceEntry:
    stage: str
    state: str
    ok: bool
    timestamp: str
    reason: str | None = None
    detail: dict = field(default_factory=dict)

    @classmethod
    def now(
        cls,
        stage: str,
        state: DocState,
        ok: bool,
        reason: ReasonCode | str | None = None,
        **detail: Any,
    ) -> "TraceEntry":
        return cls(
            stage=stage,
            state=state.value,
            ok=ok,
            timestamp=datetime.now(timezone.utc).isoformat(),
            reason=reason.value if isinstance(reason, ReasonCode) else reason,
            detail=detail,
        )


class DocumentProcessor:
    """State-driven async orchestrator.

    RECEIVED → PREPROCESSED → LOCALLY_PARSED → [VLM_RECONCILED] → VERIFIED/FLAGGED
    Module bypass: any Tier-1 failure (import/runtime/empty/audit) escalates to Tier 2.
    Tier 2 failure → FLAGGED with trace. Never crashes the caller.
    """

    def __init__(
        self,
        db: Session,
        local: LocalExtractor | None = None,
        neural: NeuralFallback | None = None,
        preprocessor: Preprocessing | None = None,
        auditor: FinancialAuditor | None = None,
        confidence_threshold: float = LOCAL_CONFIDENCE_THRESHOLD,
    ) -> None:
        self.db = db
        self.local = local or LocalExtractor()
        self.neural = neural or NeuralFallback()
        self.preprocessor = preprocessor or Preprocessing()
        self.auditor = auditor or FinancialAuditor()
        self.threshold = confidence_threshold
        self._trace: list[TraceEntry] = []

    def _record(self, entry: TraceEntry) -> None:
        self._trace.append(entry)
        logger.info(
            "pipeline.trace stage=%s state=%s ok=%s reason=%s",
            entry.stage, entry.state, entry.ok, entry.reason,
        )

    def _checkpoint(self, document_id: str, state: DocState) -> None:
        update_document_status(self.db, document_id, db_status_for(state))
        doc = get_document(self.db, document_id)
        if doc is not None:
            doc.traceability_log = [asdict(e) for e in self._trace]
            self.db.commit()

    def _finalize(
        self,
        document_id: str,
        state: DocState,
        tier: str | None,
        confidence: float | None,
    ) -> None:
        doc = get_document(self.db, document_id)
        if doc is None:
            return
        doc.status = db_status_for(state)
        doc.fallback_tier = tier
        doc.confidence_score = confidence
        doc.traceability_log = [asdict(e) for e in self._trace]
        doc.processed_at = datetime.now(timezone.utc)
        self.db.commit()

    async def process(self, document_id: str) -> dict:
        self._trace = []
        doc = get_document(self.db, document_id)
        if doc is None:
            self._record(TraceEntry.now(
                "lookup", DocState.FAILED, False,
                reason=ReasonCode.DOCUMENT_NOT_FOUND, document_id=document_id,
            ))
            raise ValueError(f"Document {document_id} not found")

        if doc.status in ("verified", "review_pending", "failed", "approved", "rejected"):
            self._record(TraceEntry.now(
                "lookup", DocState.FAILED, False,
                reason=ReasonCode.INVALID_STATE, status=doc.status,
            ))
            raise ValueError(f"Document {document_id} cannot be processed (status={doc.status})")

        self._record(TraceEntry.now("received", DocState.RECEIVED, True))

        pages = await self._preprocess(document_id, doc.filename)
        if pages is None:
            self._finalize(document_id, DocState.FAILED, None, None)
            return self._result(document_id, DocState.FAILED, None, 0.0, [], [])

        self._checkpoint(document_id, DocState.PREPROCESSED)

        local_result, local_audit = await self._tier1(pages)

        use_tier2 = (
            local_result is None
            or not local_audit.ok
            or local_result.confidence < self.threshold
            or is_empty(local_result)
        )

        if not use_tier2:
            fields, items = self._persist_result(document_id, local_result)
            self._record(TraceEntry.now(
                "local.verified", DocState.VERIFIED, True,
                reason=ReasonCode.LOCAL_OK, confidence=local_result.confidence,
            ))
            self._finalize(document_id, DocState.VERIFIED, "local", local_result.confidence)
            return self._result(
                document_id, DocState.VERIFIED, "local", local_result.confidence, fields, items,
            )

        self._checkpoint(document_id, DocState.LOCALLY_PARSED)
        neural_result, neural_audit = await self._tier2(pages)

        if neural_result is None:
            final_state = DocState.FLAGGED
            result_to_store = local_result or ExtractionResult(tier="local_degraded")
            fields, items = self._persist_result(document_id, result_to_store)
            self._finalize(document_id, final_state, "local_degraded", result_to_store.confidence)
            return self._result(
                document_id, final_state, "local_degraded", result_to_store.confidence, fields, items,
            )

        self._checkpoint(document_id, DocState.VLM_RECONCILED)
        fields, items = self._persist_result(document_id, neural_result)

        if neural_audit.ok:
            self._record(TraceEntry.now(
                "vlm.verified", DocState.VERIFIED, True,
                reason=ReasonCode.VLM_OK, confidence=neural_result.confidence,
            ))
            self._finalize(document_id, DocState.VERIFIED, "vlm", neural_result.confidence)
            return self._result(
                document_id, DocState.VERIFIED, "vlm", neural_result.confidence, fields, items,
            )

        self._record(TraceEntry.now(
            "vlm.audit_fail", DocState.FLAGGED, False,
            reason=ReasonCode.VLM_AUDIT_FAIL, audit_reason=neural_audit.reason,
            delta=str(neural_audit.delta) if neural_audit.delta is not None else None,
        ))
        self._finalize(document_id, DocState.FLAGGED, "vlm", neural_result.confidence)
        return self._result(
            document_id, DocState.FLAGGED, "vlm", neural_result.confidence, fields, items,
        )

    async def _preprocess(self, document_id: str, filename: str) -> list[Any] | None:
        try:
            path = f"uploads/{filename}"
            pages = self.preprocessor.preprocess_document(path)
            self._record(TraceEntry.now(
                "preprocess", DocState.PREPROCESSED, True, page_count=len(pages),
            ))
            return pages
        except Exception as e:
            logger.exception("preprocess failed for %s", document_id)
            self._record(TraceEntry.now(
                "preprocess", DocState.FAILED, False,
                reason=ReasonCode.PREPROCESS_FAIL, error=str(e),
            ))
            return None

    async def _tier1(self, pages: list[Any]) -> tuple[ExtractionResult | None, AuditReport]:
        try:
            result = await self.local.extract(pages)
        except LocalExtractorUnavailable as e:
            self._record(TraceEntry.now(
                "tier1", DocState.PREPROCESSED, False,
                reason=ReasonCode.LOCAL_IMPORT_ERROR, error=str(e),
            ))
            return None, AuditReport(False, None, None, None, None, "local_unavailable")
        except Exception as e:
            logger.exception("tier1 runtime error")
            self._record(TraceEntry.now(
                "tier1", DocState.PREPROCESSED, False,
                reason=ReasonCode.LOCAL_RUNTIME_ERROR, error=str(e),
            ))
            return None, AuditReport(False, None, None, None, None, "local_runtime")

        if is_empty(result):
            self._record(TraceEntry.now(
                "tier1", DocState.LOCALLY_PARSED, False,
                reason=ReasonCode.LOCAL_EMPTY_EXTRACTION,
            ))
            return result, AuditReport(False, None, None, None, None, "empty")

        audit = self.auditor.audit(result.fields)
        reason = ReasonCode.LOCAL_OK if audit.ok else ReasonCode.LOCAL_AUDIT_FAIL
        if result.confidence < self.threshold and audit.ok:
            reason = ReasonCode.LOCAL_LOW_CONFIDENCE
        self._record(TraceEntry.now(
            "tier1", DocState.LOCALLY_PARSED, audit.ok,
            reason=reason, confidence=result.confidence,
            delta=str(audit.delta) if audit.delta is not None else None,
        ))
        return result, audit

    async def _tier2(self, pages: list[Any]) -> tuple[ExtractionResult | None, AuditReport]:
        image = None
        for page in pages:
            candidate = getattr(page, "processed", None)
            if candidate is None:
                candidate = getattr(page, "original", None)
            if candidate is not None:
                image = candidate
                break
        if image is None:
            self._record(TraceEntry.now(
                "tier2", DocState.LOCALLY_PARSED, False,
                reason=ReasonCode.VLM_RUNTIME_ERROR, error="no_image",
            ))
            return None, AuditReport(False, None, None, None, None, "no_image")

        for attempt in range(MAX_VLM_RETRIES + 1):
            try:
                result = await self.neural.extract(image)
            except NeuralUnavailableError as e:
                self._record(TraceEntry.now(
                    "tier2", DocState.LOCALLY_PARSED, False,
                    reason=ReasonCode.VLM_UNAVAILABLE, error=str(e), attempt=attempt,
                ))
                return None, AuditReport(False, None, None, None, None, "unavailable")
            except Exception as e:
                logger.exception("tier2 runtime error attempt=%s", attempt)
                if attempt < MAX_VLM_RETRIES:
                    self._record(TraceEntry.now(
                        "tier2.retry", DocState.LOCALLY_PARSED, False,
                        reason=ReasonCode.VLM_RETRIED, error=str(e), attempt=attempt,
                    ))
                    continue
                self._record(TraceEntry.now(
                    "tier2", DocState.LOCALLY_PARSED, False,
                    reason=ReasonCode.VLM_RUNTIME_ERROR, error=str(e), attempt=attempt,
                ))
                return None, AuditReport(False, None, None, None, None, "runtime")
            else:
                audit = self.auditor.audit(result.fields)
                self._record(TraceEntry.now(
                    "tier2", DocState.VLM_RECONCILED, audit.ok,
                    reason=ReasonCode.VLM_OK if audit.ok else ReasonCode.VLM_AUDIT_FAIL,
                    confidence=result.confidence, attempt=attempt,
                    delta=str(audit.delta) if audit.delta is not None else None,
                ))
                return result, audit
        return None, AuditReport(False, None, None, None, None, "exhausted")

    def _persist_result(
        self, document_id: str, result: ExtractionResult,
    ) -> tuple[list, list]:
        from src.backend.db.models import ExtractedField, LineItem

        self.db.query(ExtractedField).filter(ExtractedField.document_id == document_id).delete()
        self.db.query(LineItem).filter(LineItem.document_id == document_id).delete()
        self.db.commit()

        field_payload = [
            {"field_name": k, "field_value": v, "confidence": result.confidence}
            for k, v in result.fields.items()
        ]
        fields = store_extracted_fields(self.db, document_id, field_payload)
        items = store_line_items(self.db, document_id, result.line_items)

        try:
            validate_document_fields(self.db, document_id)
        except Exception as e:
            logger.warning("schema validation raised: %s", e)
        return fields, items

    def _result(
        self,
        document_id: str,
        state: DocState,
        tier: str | None,
        confidence: float | None,
        fields: list,
        items: list,
    ) -> dict:
        return {
            "document_id": document_id,
            "status": db_status_for(state),
            "state": state.value,
            "tier": tier,
            "confidence": confidence,
            "fields_extracted": len(fields),
            "line_items_extracted": len(items),
            "trace": [asdict(e) for e in self._trace],
        }

    def get_document_status(self, document_id: str) -> dict:
        doc = get_document(self.db, document_id)
        if doc is None:
            raise ValueError(f"Document {document_id} not found")
        return {
            "document_id": doc.id,
            "filename": doc.original_filename,
            "status": doc.status,
            "fallback_tier": getattr(doc, "fallback_tier", None),
            "confidence_score": getattr(doc, "confidence_score", None),
            "traceability_log": getattr(doc, "traceability_log", None),
            "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
        }
