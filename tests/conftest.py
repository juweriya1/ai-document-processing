import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.backend.config import TEST_DATABASE_URL
from src.backend.db.models import Base
from src.backend.db.crud import create_document


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
