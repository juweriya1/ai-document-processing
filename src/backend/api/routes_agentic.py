"""FastAPI entry point for the LangGraph-driven Agentic Financial Auditor.

Runs alongside the legacy /api/documents/{id}/process route (DocumentProcessor)
so the jury can see both paths end-to-end. This one executes the compiled
StateGraph with Decimal auditing + Magnitude Guard + Gemini reconciliation
loop (up to MAX_RECONCILE_ATTEMPTS=3 before routing to HITL).

Response shape is deliberately a superset of the legacy /process response so
the existing React ProcessingPage continues to work without frontend changes:
it still reads `document_id`, `status`, `fields_extracted`, `line_items_
extracted`. The additive fields (`is_valid`, `tier`, `attempts`, `trace`,
`confidence_score`, `extracted_data`) are available for richer UI later.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.backend.agents.graph import compiled_graph
from src.backend.agents.state import AgentState
from src.backend.auth.rbac import role_required
from src.backend.db.crud import get_document
from src.backend.db.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agentic", tags=["agentic"])

# Map internal DocState DB values to the values the React ProcessingPage
# stepper understands. "verified" means automated math passed, but the
# enterprise workflow still routes through human sign-off, so we surface it
# as "review_pending" to match the frontend's pipeline step list.
_FRONTEND_STATUS_MAP = {
    "verified": "review_pending",
    "locally_parsed": "extracting",
    "vlm_reconciled": "extracting",
}


def _translate_status(backend_status: str | None) -> str:
    if backend_status is None:
        return "failed"
    return _FRONTEND_STATUS_MAP.get(backend_status, backend_status)


def _get(final: Any, key: str) -> Any:
    """LangGraph returns a dict on ainvoke when state is a Pydantic model in
    some versions and the model itself in others. Accept both."""
    if isinstance(final, dict):
        return final.get(key)
    return getattr(final, key, None)


def _count_fields(extracted: Any) -> int:
    if extracted is None:
        return 0
    data = extracted.model_dump() if hasattr(extracted, "model_dump") else extracted
    return sum(1 for k, v in data.items() if k != "line_items" and v)


def _count_line_items(extracted: Any) -> int:
    if extracted is None:
        return 0
    data = extracted.model_dump() if hasattr(extracted, "model_dump") else extracted
    return len(data.get("line_items") or [])


def _resolve_response_status(is_valid: bool, tier: str | None, audit_log: list[dict] | None) -> str:
    """Map the agent's final state onto the frontend's status vocabulary.

    - Verified (math passed) → review_pending (ready for human sign-off).
    - HITL (Gemini unavailable / retry-exhausted) → review_pending.
    - Preprocess failure (no extraction produced) → failed.
    """
    if is_valid:
        return "review_pending"
    if _preprocess_failed(audit_log):
        return "failed"
    return "review_pending"


def _preprocess_failed(audit_log: list[dict] | None) -> bool:
    if not audit_log:
        return False
    for entry in audit_log:
        if entry.get("stage") == "preprocess" and entry.get("ok") is False:
            return True
    return False


@router.post("/{document_id}/process")
async def process_document_agentic(
    document_id: str,
    current_user: dict = Depends(role_required(["enterprise_user", "admin", "reviewer"])),
    db: Session = Depends(get_db),
):
    doc = get_document(db, document_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )

    initial = AgentState(
        document_id=document_id,
        file_path=f"uploads/{doc.filename}",
    )

    try:
        final = await compiled_graph.ainvoke(initial)
    except Exception as e:
        logger.exception("agentic graph execution failed for %s", document_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"agent_execution_failed: {e}",
        )

    extracted = _get(final, "extracted_data")
    tier = _get(final, "tier")
    is_valid = bool(_get(final, "is_valid"))
    attempts = int(_get(final, "attempts") or 0)
    audit_log = _get(final, "audit_log") or []
    reason = _get(final, "reason")

    return {
        # --- Frontend contract (ProcessingPage.handleProcess) ---
        "document_id": document_id,
        "status": _resolve_response_status(is_valid, tier, audit_log),
        "fields_extracted": _count_fields(extracted),
        "line_items_extracted": _count_line_items(extracted),
        # --- Agentic extensions (additive, safe for current frontend) ---
        "is_valid": is_valid,
        "tier": tier,
        "attempts": attempts,
        "last_reason": reason,
        "extracted_data": (
            extracted.model_dump() if hasattr(extracted, "model_dump") else extracted
        ),
        "trace_length": len(audit_log),
        "trace": audit_log,
    }


@router.get("/{document_id}/status")
def get_agentic_status(
    document_id: str,
    current_user: dict = Depends(role_required(["enterprise_user", "admin", "reviewer"])),
    db: Session = Depends(get_db),
):
    doc = get_document(db, document_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    return {
        "document_id": doc.id,
        "filename": doc.original_filename,
        "status": _translate_status(doc.status),
        "fallback_tier": doc.fallback_tier,
        "confidence_score": doc.confidence_score,
        "traceability_log": doc.traceability_log,
        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
    }
