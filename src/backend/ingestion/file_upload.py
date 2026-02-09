import os
import uuid
from dataclasses import dataclass

from src.backend.config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB


@dataclass
class DocumentMeta:
    stored_filename: str
    original_filename: str
    file_type: str
    file_size: int
    file_path: str


class FileUpload:
    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = upload_dir
        os.makedirs(upload_dir, exist_ok=True)

    def validate_file_type(self, filename: str) -> str:
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"File type not allowed: {ext}")
        return ext

    def validate_file_size(self, content: bytes) -> None:
        max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
        if len(content) > max_bytes:
            raise ValueError(f"File size exceeds maximum of {MAX_FILE_SIZE_MB}MB")

    def get_stored_filename(self, ext: str) -> str:
        return f"doc_{uuid.uuid4().hex[:12]}{ext}"

    def save_uploaded_file(self, file) -> DocumentMeta:
        ext = self.validate_file_type(file.filename)
        content = file.read() if hasattr(file, 'read') and callable(file.read) else b""
        self.validate_file_size(content)

        stored_filename = self.get_stored_filename(ext)
        file_path = os.path.join(self.upload_dir, stored_filename)

        with open(file_path, "wb") as f:
            f.write(content)

        return DocumentMeta(
            stored_filename=stored_filename,
            original_filename=file.filename,
            file_type=file.content_type,
            file_size=len(content),
            file_path=file_path,
        )
