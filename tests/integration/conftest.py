import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.backend.config import TEST_DATABASE_URL
from src.backend.db.database import get_db
from src.backend.db.models import Base
from src.backend.main import app


SAMPLE_PDF = os.path.join(
    os.path.dirname(__file__), "..", "fixtures", "sample_invoice.pdf"
)


@pytest.fixture
def test_db():
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(test_db):
    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register_and_login(client: TestClient, email: str, password: str, name: str, role: str) -> dict:
    reg = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "name": name, "role": role},
    )
    assert reg.status_code == 201, f"Register failed: {reg.text}"
    login = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, f"Login failed: {login.text}"
    data = login.json()
    return {"user": data["user"], "token": data["accessToken"]}


@pytest.fixture
def admin_user(client):
    return register_and_login(client, "admin@test.com", "adminpass123", "Admin User", "admin")


@pytest.fixture
def reviewer_user(client):
    return register_and_login(client, "reviewer@test.com", "reviewpass123", "Reviewer User", "reviewer")


@pytest.fixture
def enterprise_user(client):
    return register_and_login(client, "user@test.com", "userpass123", "Enterprise User", "enterprise_user")


def upload_sample_pdf(client: TestClient, token: str) -> dict:
    with open(SAMPLE_PDF, "rb") as f:
        resp = client.post(
            "/api/documents/upload",
            headers=auth_header(token),
            files={"file": ("sample_invoice.pdf", f, "application/pdf")},
        )
    assert resp.status_code == 201, f"Upload failed: {resp.text}"
    return resp.json()


def process_document(client: TestClient, token: str, doc_id: str) -> dict:
    resp = client.post(
        f"/api/documents/{doc_id}/process",
        headers=auth_header(token),
    )
    assert resp.status_code == 200, f"Process failed: {resp.text}"
    return resp.json()


def upload_and_process(client: TestClient, token: str) -> tuple[dict, dict]:
    upload_data = upload_sample_pdf(client, token)
    process_data = process_document(client, token, upload_data["id"])
    return upload_data, process_data
