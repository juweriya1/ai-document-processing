import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.backend.config import TEST_DATABASE_URL
from src.backend.db.models import Base
from src.backend.db.crud import create_document, create_user, store_extracted_fields


@pytest.fixture
def db_engine():
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def sample_document(db_session):
    doc = create_document(
        db_session,
        filename="test_doc.pdf",
        original_filename="test.pdf",
        file_type="application/pdf",
        file_size=2048,
    )
    return doc


@pytest.fixture
def sample_reviewer(db_session):
    user = create_user(
        db_session,
        email="reviewer@example.com",
        password="reviewerpass123",
        name="Test Reviewer",
        role="reviewer",
    )
    return user


@pytest.fixture
def sample_extracted_fields(db_session, sample_document):
    fields_data = [
        {"field_name": "invoice_number", "field_value": "INV-2025-0001", "confidence": 0.95},
        {"field_name": "date", "field_value": "2025-01-15", "confidence": 0.92},
        {"field_name": "vendor_name", "field_value": "Acme Corporation", "confidence": 0.90},
        {"field_name": "total_amount", "field_value": "2450.00", "confidence": 0.88},
    ]
    fields = store_extracted_fields(db_session, sample_document.id, fields_data)
    return fields
