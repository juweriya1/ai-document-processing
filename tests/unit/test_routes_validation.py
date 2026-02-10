import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.backend.auth.jwt_handler import create_access_token
from src.backend.config import TEST_DATABASE_URL
from src.backend.db.crud import (
    create_document,
    create_user,
    store_extracted_fields,
    update_field_validation_status,
)
from src.backend.db.database import get_db
from src.backend.db.models import Base
from src.backend.main import app


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


@pytest.fixture
def test_reviewer(test_db):
    return create_user(test_db, email="reviewer@test.com", password="pass123", name="Reviewer", role="reviewer")


@pytest.fixture
def reviewer_token(test_reviewer):
    return create_access_token(
        data={"sub": test_reviewer.email, "role": test_reviewer.role, "user_id": test_reviewer.id}
    )


@pytest.fixture
def test_enterprise_user(test_db):
    return create_user(test_db, email="user@test.com", password="pass123", name="User", role="enterprise_user")


@pytest.fixture
def user_token(test_enterprise_user):
    return create_access_token(
        data={"sub": test_enterprise_user.email, "role": test_enterprise_user.role, "user_id": test_enterprise_user.id}
    )


@pytest.fixture
def test_document(test_db):
    return create_document(
        test_db,
        filename="test.pdf",
        original_filename="test.pdf",
        file_type="application/pdf",
        file_size=1024,
    )


@pytest.fixture
def test_fields(test_db, test_document):
    fields_data = [
        {"field_name": "invoice_number", "field_value": "INV-2025-0001", "confidence": 0.95},
        {"field_name": "date", "field_value": "2025-01-15", "confidence": 0.92},
        {"field_name": "vendor_name", "field_value": "Acme Corp", "confidence": 0.90},
        {"field_name": "total_amount", "field_value": "1500.00", "confidence": 0.88},
    ]
    return store_extracted_fields(test_db, test_document.id, fields_data)


class TestGetFields:
    def test_get_fields_success(self, client, reviewer_token, test_document, test_fields):
        resp = client.get(
            f"/api/documents/{test_document.id}/fields",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 4
        assert data[0]["fieldName"] == "invoice_number"

    def test_get_fields_not_found(self, client, reviewer_token):
        resp = client.get(
            "/api/documents/doc_nonexist/fields",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 404

    def test_get_fields_no_auth(self, client, test_document):
        resp = client.get(f"/api/documents/{test_document.id}/fields")
        assert resp.status_code == 401

    def test_get_fields_enterprise_user_allowed(self, client, user_token, test_document, test_fields):
        resp = client.get(
            f"/api/documents/{test_document.id}/fields",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 200


class TestValidateFields:
    def test_validate_success(self, client, reviewer_token, test_document, test_fields):
        resp = client.post(
            f"/api/documents/{test_document.id}/validate",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "summary" in data
        assert data["summary"]["total_fields"] == 4

    def test_validate_not_found(self, client, reviewer_token):
        resp = client.post(
            "/api/documents/doc_nonexist/validate",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 404

    def test_validate_enterprise_user_forbidden(self, client, user_token, test_document):
        resp = client.post(
            f"/api/documents/{test_document.id}/validate",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 403


class TestSubmitCorrection:
    def test_submit_correction_success(self, client, reviewer_token, test_document, test_fields):
        field = test_fields[0]
        resp = client.post(
            f"/api/documents/{test_document.id}/corrections",
            headers={"Authorization": f"Bearer {reviewer_token}"},
            json={"fieldId": field.id, "correctedValue": "INV-2025-9999"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["correctedValue"] == "INV-2025-9999"
        assert data["correctionId"].startswith("cor_")

    def test_submit_correction_bad_field(self, client, reviewer_token, test_document):
        resp = client.post(
            f"/api/documents/{test_document.id}/corrections",
            headers={"Authorization": f"Bearer {reviewer_token}"},
            json={"fieldId": "fld_bad", "correctedValue": "value"},
        )
        assert resp.status_code == 400


class TestGetCorrections:
    def test_get_corrections_empty(self, client, reviewer_token, test_document):
        resp = client.get(
            f"/api/documents/{test_document.id}/corrections",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []


class TestApproveDocument:
    def test_approve_all_valid(self, client, reviewer_token, test_document, test_fields, test_db):
        for f in test_fields:
            update_field_validation_status(test_db, f.id, "valid")

        resp = client.post(
            f"/api/documents/{test_document.id}/approve",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_approve_with_invalid_fields_rejected(self, client, reviewer_token, test_document, test_fields, test_db):
        update_field_validation_status(test_db, test_fields[0].id, "invalid", "bad")

        resp = client.post(
            f"/api/documents/{test_document.id}/approve",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 400
        assert "invalid" in resp.json()["detail"].lower() or "pending" in resp.json()["detail"].lower()


class TestRejectDocument:
    def test_reject_success(self, client, reviewer_token, test_document):
        resp = client.post(
            f"/api/documents/{test_document.id}/reject",
            headers={"Authorization": f"Bearer {reviewer_token}"},
            json={"reason": "Data quality too low"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"
        assert data["reason"] == "Data quality too low"

    def test_reject_not_found(self, client, reviewer_token):
        resp = client.post(
            "/api/documents/doc_nonexist/reject",
            headers={"Authorization": f"Bearer {reviewer_token}"},
            json={"reason": "Bad data"},
        )
        assert resp.status_code == 404
