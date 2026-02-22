import os

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.backend.auth.jwt_handler import get_current_user, verify_token
from src.backend.auth.rbac import role_required
from src.backend.config import UPLOAD_DIR
from src.backend.db.crud import create_document, get_document
from src.backend.db.database import get_db
from src.backend.ingestion.file_upload import FileUpload

router = APIRouter(prefix="/api/documents", tags=["documents"])

file_uploader = FileUpload()


class UploadResponse(BaseModel):
    id: str
    filename: str
    originalFilename: str
    fileType: str
    fileSize: int
    status: str


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
