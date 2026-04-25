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


def _auth(user):
    token = create_access_token(
        data={"sub": user.email, "role": user.role, "user_id": user.id}
    )
    return {"Authorization": f"Bearer {token}"}


class TestWidgetsCatalog:
    def test_enterprise_user_gets_filtered_catalog(self, client, test_db):
        user = create_user(test_db, email="eu@test.com", password="x", name="EU", role="enterprise_user")
        resp = client.get("/api/analytics/widgets/catalog", headers=_auth(user))
        assert resp.status_code == 200
        keys = {w["key"] for w in resp.json()}
        assert "table_flagged" not in keys  # reviewer/admin only

    def test_admin_gets_all_widgets(self, client, test_db):
        admin = create_user(test_db, email="a@test.com", password="x", name="A", role="admin")
        resp = client.get("/api/analytics/widgets/catalog", headers=_auth(admin))
        assert resp.status_code == 200
        keys = {w["key"] for w in resp.json()}
        assert "table_flagged" in keys


class TestWidgetsPreferences:
    def test_default_layout_when_unset(self, client, test_db):
        user = create_user(test_db, email="u1@test.com", password="x", name="U", role="reviewer")
        resp = client.get("/api/analytics/widgets/preferences", headers=_auth(user))
        assert resp.status_code == 200
        body = resp.json()
        assert "enabled" in body
        assert "order" in body

    def test_put_persists_and_strips_unknown_keys(self, client, test_db):
        user = create_user(test_db, email="u2@test.com", password="x", name="U", role="admin")
        payload = {
            "enabled": ["kpi_total_spend", "not_a_widget"],
            "order":   ["kpi_total_spend", "not_a_widget"],
        }
        resp = client.put(
            "/api/analytics/widgets/preferences",
            json=payload,
            headers=_auth(user),
        )
        assert resp.status_code == 200
        saved = resp.json()
        assert "not_a_widget" not in saved["enabled"]
        assert "not_a_widget" not in saved["order"]
        assert "kpi_total_spend" in saved["enabled"]

        # GET round-trip returns the persisted layout
        resp2 = client.get("/api/analytics/widgets/preferences", headers=_auth(user))
        assert resp2.status_code == 200
        assert resp2.json() == saved

    def test_put_strips_widgets_not_allowed_for_role(self, client, test_db):
        user = create_user(test_db, email="u3@test.com", password="x", name="U", role="enterprise_user")
        payload = {
            "enabled": ["table_flagged", "kpi_total_spend"],
            "order":   ["table_flagged", "kpi_total_spend"],
        }
        resp = client.put(
            "/api/analytics/widgets/preferences",
            json=payload,
            headers=_auth(user),
        )
        assert resp.status_code == 200
        saved = resp.json()
        assert "table_flagged" not in saved["enabled"]
        assert "kpi_total_spend" in saved["enabled"]
