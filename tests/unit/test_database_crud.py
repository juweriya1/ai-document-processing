import pytest
from sqlalchemy import text

from src.backend.db.crud import (
    create_document,
    create_user,
    get_document,
    get_user_by_email,
    store_extracted_fields,
)
from src.backend.db.models import Document, ExtractedField, User


class TestDocumentCRUD:
    def test_create_document(self, db_session):
        doc = create_document(
            db_session,
            filename="invoice_001.pdf",
            original_filename="invoice.pdf",
            file_type="application/pdf",
            file_size=1024,
        )
        assert doc.id.startswith("doc_")
        assert doc.filename == "invoice_001.pdf"
        assert doc.original_filename == "invoice.pdf"
        assert doc.status == "uploaded"

    def test_get_document(self, db_session, sample_document):
        fetched = get_document(db_session, sample_document.id)
        assert fetched is not None
        assert fetched.id == sample_document.id
        assert fetched.filename == sample_document.filename

    def test_get_nonexistent_document_returns_none(self, db_session):
        fetched = get_document(db_session, "doc_nonexistent")
        assert fetched is None

    def test_store_extracted_fields(self, db_session, sample_document):
        fields = [
            {"field_name": "invoice_number", "field_value": "INV-001", "confidence": 0.95},
            {"field_name": "total_amount", "field_value": "1500.00", "confidence": 0.88},
        ]
        stored = store_extracted_fields(db_session, sample_document.id, fields)
        assert len(stored) == 2
        assert stored[0].field_name == "invoice_number"
        assert stored[1].confidence == 0.88


class TestUserCRUD:
    def test_create_user(self, db_session):
        user = create_user(
            db_session,
            email="test@example.com",
            password="securepassword123",
            name="Test User",
            role="enterprise_user",
        )
        assert user.id.startswith("usr_")
        assert user.email == "test@example.com"
        assert user.password_hash != "securepassword123"

    def test_get_user_by_email(self, db_session):
        create_user(
            db_session,
            email="findme@example.com",
            password="password123",
            name="Find Me",
            role="reviewer",
        )
        found = get_user_by_email(db_session, "findme@example.com")
        assert found is not None
        assert found.name == "Find Me"
        assert found.role == "reviewer"
