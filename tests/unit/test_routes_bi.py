import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.backend.auth.jwt_handler import create_access_token
from src.backend.config import TEST_DATABASE_URL
from src.backend.db.crud import create_user
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


def _token(user):
    return create_access_token(
        data={"sub": user.email, "role": user.role, "user_id": user.id}
    )


def _auth(user):
    return {"Authorization": f"Bearer {_token(user)}"}


class TestBIInvoices:
    def test_reviewer_can_access(self, client, test_db):
        reviewer = create_user(test_db, email="r@test.com", password="x", name="R", role="reviewer")
        resp = client.get("/api/bi/invoices.json", headers=_auth(reviewer))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_admin_can_access(self, client, test_db):
        admin = create_user(test_db, email="a@test.com", password="x", name="A", role="admin")
        resp = client.get("/api/bi/invoices.json", headers=_auth(admin))
        assert resp.status_code == 200

    def test_enterprise_user_denied(self, client, test_db):
        eu = create_user(test_db, email="eu@test.com", password="x", name="EU", role="enterprise_user")
        resp = client.get("/api/bi/invoices.json", headers=_auth(eu))
        assert resp.status_code == 403


class TestBIConfig:
    def test_all_roles_can_read_config(self, client, test_db):
        eu = create_user(test_db, email="eu2@test.com", password="x", name="EU", role="enterprise_user")
        resp = client.get("/api/bi/config", headers=_auth(eu))
        assert resp.status_code == 200
        body = resp.json()
        assert "power_bi_embed_url" in body
        assert "refresh_cadence" in body


class TestBILineItems:
    def test_empty_when_no_items(self, client, test_db):
        reviewer = create_user(test_db, email="r2@test.com", password="x", name="R", role="reviewer")
        resp = client.get("/api/bi/line-items.json", headers=_auth(reviewer))
        assert resp.status_code == 200
        assert resp.json() == []


class TestBICorrections:
    def test_empty_when_no_corrections(self, client, test_db):
        reviewer = create_user(test_db, email="r3@test.com", password="x", name="R", role="reviewer")
        resp = client.get("/api/bi/corrections.json", headers=_auth(reviewer))
        assert resp.status_code == 200
        assert resp.json() == []


class TestBICSV:
    def test_empty_csv_returns_empty_body(self, client, test_db):
        reviewer = create_user(test_db, email="r4@test.com", password="x", name="R", role="reviewer")
        resp = client.get("/api/bi/invoices.csv", headers=_auth(reviewer))
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
