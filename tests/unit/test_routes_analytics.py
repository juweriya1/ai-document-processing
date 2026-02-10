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
    update_document_status,
    upsert_supplier_metric,
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
def test_admin(test_db):
    return create_user(test_db, email="admin@test.com", password="pass123", name="Admin", role="admin")


@pytest.fixture
def admin_token(test_admin):
    return create_access_token(
        data={"sub": test_admin.email, "role": test_admin.role, "user_id": test_admin.id}
    )


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
def test_document_with_fields(test_db):
    doc = create_document(test_db, "test.pdf", "test.pdf", "application/pdf", 1024)
    store_extracted_fields(test_db, doc.id, [
        {"field_name": "invoice_number", "field_value": "INV-2025-0001", "confidence": 0.95},
        {"field_name": "date", "field_value": "2025-01-15", "confidence": 0.92},
        {"field_name": "vendor_name", "field_value": "Acme Corp", "confidence": 0.90},
        {"field_name": "total_amount", "field_value": "1500.00", "confidence": 0.88},
    ])
    update_document_status(test_db, doc.id, "approved")
    return doc


class TestDashboard:
    def test_dashboard_empty(self, client, reviewer_token):
        resp = client.get(
            "/api/analytics/dashboard",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_documents" in data
        assert "total_spend" in data
        assert "compliance_score" in data
        assert "anomaly_count" in data

    def test_dashboard_with_data(self, client, reviewer_token, test_document_with_fields):
        resp = client.get(
            "/api/analytics/dashboard",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_documents"] == 1
        assert data["total_spend"] == 1500.0

    def test_dashboard_enterprise_user_allowed(self, client, user_token):
        resp = client.get(
            "/api/analytics/dashboard",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 200

    def test_dashboard_no_auth(self, client):
        resp = client.get("/api/analytics/dashboard")
        assert resp.status_code == 401


class TestSpendByVendor:
    def test_empty(self, client, reviewer_token):
        resp = client.get(
            "/api/analytics/spend/by-vendor",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_with_data(self, client, reviewer_token, test_document_with_fields):
        resp = client.get(
            "/api/analytics/spend/by-vendor",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["vendor_name"] == "Acme Corp"


class TestSpendByMonth:
    def test_empty(self, client, reviewer_token):
        resp = client.get(
            "/api/analytics/spend/by-month",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_with_months_param(self, client, reviewer_token, test_document_with_fields):
        resp = client.get(
            "/api/analytics/spend/by-month?months=6",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 200


class TestSuppliers:
    def test_suppliers_empty(self, client, reviewer_token):
        resp = client.get(
            "/api/analytics/suppliers",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_suppliers_with_data(self, client, reviewer_token, test_db):
        upsert_supplier_metric(test_db, "Test Vendor", 5, 0.90, 25.0)
        resp = client.get(
            "/api/analytics/suppliers",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["supplier_name"] == "Test Vendor"
        assert data[0]["risk_level"] == "low"

    def test_suppliers_enterprise_user_forbidden(self, client, user_token):
        resp = client.get(
            "/api/analytics/suppliers",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 403


class TestRefreshSuppliers:
    def test_refresh_admin_allowed(self, client, admin_token, test_document_with_fields):
        resp = client.post(
            "/api/analytics/suppliers/refresh",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "suppliers_updated" in data
        assert "risk_scores_computed" in data

    def test_refresh_reviewer_forbidden(self, client, reviewer_token):
        resp = client.post(
            "/api/analytics/suppliers/refresh",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 403

    def test_refresh_enterprise_user_forbidden(self, client, user_token):
        resp = client.post(
            "/api/analytics/suppliers/refresh",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 403


class TestPredictions:
    def test_predictions_empty(self, client, reviewer_token):
        resp = client.get(
            "/api/analytics/predictions",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "risk_scores" in data
        assert "spend_forecast" in data
        assert "anomalies" in data
        assert "insights" in data

    def test_predictions_enterprise_user_forbidden(self, client, user_token):
        resp = client.get(
            "/api/analytics/predictions",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 403


class TestAnomalies:
    def test_anomalies_empty(self, client, reviewer_token):
        resp = client.get(
            "/api/analytics/anomalies",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_anomalies_enterprise_user_forbidden(self, client, user_token):
        resp = client.get(
            "/api/analytics/anomalies",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 403
