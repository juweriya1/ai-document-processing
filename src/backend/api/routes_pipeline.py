"""Legacy /api/documents/{id}/process route — now a thin proxy.

The original PipelineOrchestrator (EasyOCR + EntityExtractor) has been retired.
This file preserves the historical URL so the existing React frontend keeps
working without a client-side change, but every request is transparently
delegated to the agentic pipeline (PaddleOCR-v5 → FinancialAuditor →
Gemini 2.5 Flash via BAML, orchestrated by LangGraph).

The response shape from `process_document_agentic` is already a superset of
what the legacy route returned — it carries `document_id`, `status`,
`fields_extracted`, `line_items_extracted` plus the agentic extensions
(`is_valid`, `tier`, `attempts`, `trace`, `extracted_data`). Validated end-to-
end by tests/unit/test_routes_agentic.py.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.backend.api.routes_agentic import (
    get_agentic_status,
    process_document_agentic,
)
from src.backend.auth.rbac import role_required
from src.backend.db.database import get_db

router = APIRouter(prefix="/api/documents", tags=["pipeline"])


@router.post("/{document_id}/process")
async def process_document(
    document_id: str,
    current_user: dict = Depends(role_required(["enterprise_user", "admin", "reviewer"])),
    db: Session = Depends(get_db),
):
    return await process_document_agentic(
        document_id=document_id,
        current_user=current_user,
        db=db,
    )


@router.get("/{document_id}/status")
def get_status(
    document_id: str,
    current_user: dict = Depends(role_required(["enterprise_user", "admin", "reviewer"])),
    db: Session = Depends(get_db),
):
    return get_agentic_status(
        document_id=document_id,
        current_user=current_user,
        db=db,
    )
