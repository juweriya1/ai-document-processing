from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.backend.auth.rbac import role_required
from src.backend.db.database import get_db
from src.backend.pipeline.orchestrator import PipelineOrchestrator

router = APIRouter(prefix="/api/documents", tags=["pipeline"])


@router.post("/{document_id}/process")
def process_document(
    document_id: str,
    current_user: dict = Depends(role_required(["enterprise_user", "admin", "reviewer"])),
    db: Session = Depends(get_db),
):
    orchestrator = PipelineOrchestrator(db)
    try:
        result = orchestrator.process_document(document_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return result


@router.get("/{document_id}/status")
def get_status(
    document_id: str,
    current_user: dict = Depends(role_required(["enterprise_user", "admin", "reviewer"])),
    db: Session = Depends(get_db),
):
    orchestrator = PipelineOrchestrator(db)
    try:
        result = orchestrator.get_document_status(document_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return result
