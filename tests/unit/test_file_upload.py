import os
import tempfile

import pytest

from src.backend.ingestion.file_upload import FileUpload
from src.backend.config import MAX_FILE_SIZE_MB


class MockUploadFile:
    def __init__(self, filename: str, content: bytes, content_type: str):
        self.filename = filename
        self.file = self
        self.content_type = content_type
        self._content = content
        self.size = len(content)

    def read(self):
        return self._content

    async def aread(self):
        return self._content


class TestFileUpload:
    def setup_method(self):
        self.upload_dir = tempfile.mkdtemp()
        self.uploader = FileUpload(upload_dir=self.upload_dir)

    def test_accept_pdf(self):
        f = MockUploadFile("invoice.pdf", b"%PDF-1.4 test content", "application/pdf")
        result = self.uploader.save_uploaded_file(f)
        assert result.original_filename == "invoice.pdf"
        assert result.file_type == "application/pdf"

    def test_accept_png(self):
        f = MockUploadFile("scan.png", b"\x89PNG fake image data", "image/png")
        result = self.uploader.save_uploaded_file(f)
        assert result.original_filename == "scan.png"

    def test_accept_jpg(self):
        f = MockUploadFile("photo.jpg", b"\xff\xd8\xff fake jpeg", "image/jpeg")
        result = self.uploader.save_uploaded_file(f)
        assert result.original_filename == "photo.jpg"

    def test_reject_exe(self):
        f = MockUploadFile("malware.exe", b"MZ executable", "application/octet-stream")
        with pytest.raises(ValueError, match="File type not allowed"):
            self.uploader.save_uploaded_file(f)

    def test_reject_oversized(self):
        big_content = b"x" * (MAX_FILE_SIZE_MB * 1024 * 1024 + 1)
        f = MockUploadFile("big.pdf", big_content, "application/pdf")
        with pytest.raises(ValueError, match="exceeds maximum"):
            self.uploader.save_uploaded_file(f)

    def test_file_saved_to_disk(self):
        f = MockUploadFile("invoice.pdf", b"%PDF-1.4 test content", "application/pdf")
        result = self.uploader.save_uploaded_file(f)
        saved_path = os.path.join(self.upload_dir, result.stored_filename)
        assert os.path.exists(saved_path)
        with open(saved_path, "rb") as fh:
            assert fh.read() == b"%PDF-1.4 test content"

    def test_unique_filenames(self):
        f1 = MockUploadFile("invoice.pdf", b"%PDF content1", "application/pdf")
        f2 = MockUploadFile("invoice.pdf", b"%PDF content2", "application/pdf")
        r1 = self.uploader.save_uploaded_file(f1)
        r2 = self.uploader.save_uploaded_file(f2)
        assert r1.stored_filename != r2.stored_filename
