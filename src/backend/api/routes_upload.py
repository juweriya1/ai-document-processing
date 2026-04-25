import os

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.backend.auth.jwt_handler import get_current_user, verify_token
from src.backend.auth.rbac import role_required
from src.backend.config import UPLOAD_DIR
from src.backend.db.crud import create_document, get_document, list_documents_for_user
from src.backend.db.database import get_db
from src.backend.ingestion.file_upload import FileUpload

router = APIRouter(prefix="/api/documents", tags=["documents"])

_PRIVILEGED_ROLES = {"admin", "reviewer"}

file_uploader = FileUpload()


class UploadResponse(BaseModel):
    id: str
    filename: str
    originalFilename: str
    fileType: str
    fileSize: int
    status: str


class DocumentSummary(BaseModel):
    """Compact document view for list endpoints — keeps payloads small for
    the documents-list page even at limit=200."""

    id: str
    originalFilename: str
    fileType: str
    fileSize: int
    status: str
    uploadedAt: str | None = None
    processedAt: str | None = None
    fallbackTier: str | None = None
    confidenceScore: float | None = None
    batchId: str | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentSummary]
    total: int
    skip: int
    limit: int


@router.post("/upload", status_code=status.HTTP_201_CREATED, response_model=UploadResponse)
def upload_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(role_required(["enterprise_user", "admin", "reviewer"])),
    db: Session = Depends(get_db),
):
    try:
        meta = file_uploader.save_uploaded_file(file)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    doc = create_document(
        db,
        filename=meta.stored_filename,
        original_filename=meta.original_filename,
        file_type=meta.file_type,
        file_size=meta.file_size,
        uploaded_by=current_user.get("user_id"),
    )

    return UploadResponse(
        id=doc.id,
        filename=doc.filename,
        originalFilename=doc.original_filename,
        fileType=doc.file_type,
        fileSize=doc.file_size,
        status=doc.status,
    )


MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def _to_summary(doc) -> DocumentSummary:
    return DocumentSummary(
        id=doc.id,
        originalFilename=doc.original_filename,
        fileType=doc.file_type,
        fileSize=doc.file_size,
        status=doc.status,
        uploadedAt=doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        processedAt=doc.processed_at.isoformat() if doc.processed_at else None,
        fallbackTier=doc.fallback_tier,
        confidenceScore=doc.confidence_score,
        batchId=doc.batch_id,
    )


@router.get("", response_model=DocumentListResponse)
def list_documents_endpoint(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    batch_id: str | None = Query(default=None, alias="batchId"),
    current_user: dict = Depends(role_required(["enterprise_user", "admin", "reviewer"])),
    db: Session = Depends(get_db),
):
    """List documents the current user can see.

    enterprise_user: only documents they uploaded.
    admin / reviewer: every document. The role check is intentionally
    redundant with role_required — the service-level filter is what
    enforces uploader scoping for non-privileged roles.
    """
    user_role = current_user.get("role")
    user_id = current_user.get("user_id")
    rows, total = list_documents_for_user(
        db,
        user_id=user_id,
        include_all=user_role in _PRIVILEGED_ROLES,
        skip=skip,
        limit=limit,
        batch_id=batch_id,
    )
    return DocumentListResponse(
        documents=[_to_summary(r) for r in rows],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{document_id}", response_model=DocumentSummary)
def get_document_metadata(
    document_id: str,
    current_user: dict = Depends(role_required(["enterprise_user", "admin", "reviewer"])),
    db: Session = Depends(get_db),
):
    """Return document metadata. enterprise_user can only access docs
    they uploaded; admin / reviewer can access any. 404 hides existence
    from non-owners (avoid leaking IDs)."""
    doc = get_document(db, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    user_role = current_user.get("role")
    if user_role not in _PRIVILEGED_ROLES and doc.uploaded_by != current_user.get("user_id"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return _to_summary(doc)


@router.get("/{document_id}/file")
def get_document_file(
    document_id: str,
    token: str | None = Query(default=None),
    current_user: dict | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user is None and token:
        current_user = verify_token(token)
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    doc = get_document(db, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    file_path = os.path.join(UPLOAD_DIR, doc.filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

    ext = os.path.splitext(doc.filename)[1].lower()
    media_type = MEDIA_TYPES.get(ext, "application/octet-stream")

    return FileResponse(file_path, media_type=media_type, filename=doc.original_filename)
