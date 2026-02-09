from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.backend.auth.rbac import role_required
from src.backend.db.crud import create_document
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
