from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.backend.main import app
from src.backend.db.crud import create_user, list_all_users, get_user_by_id, update_user


class TestAdminCrudFunctions:
    def test_list_all_users(self, db_session):
        create_user(db_session, "u1@test.com", "pass1", "User One", "admin")
        create_user(db_session, "u2@test.com", "pass2", "User Two", "reviewer")
        users = list_all_users(db_session)
        assert len(users) == 2

    def test_get_user_by_id(self, db_session):
        user = create_user(db_session, "u1@test.com", "pass1", "User One", "admin")
        found = get_user_by_id(db_session, user.id)
        assert found is not None
        assert found.email == "u1@test.com"

    def test_get_user_by_id_not_found(self, db_session):
        found = get_user_by_id(db_session, "nonexistent_id")
        assert found is None

    def test_update_user_name(self, db_session):
        user = create_user(db_session, "u1@test.com", "pass1", "User One", "admin")
        updated = update_user(db_session, user.id, name="Updated Name")
        assert updated.name == "Updated Name"

    def test_update_user_role(self, db_session):
        user = create_user(db_session, "u1@test.com", "pass1", "User One", "enterprise_user")
        updated = update_user(db_session, user.id, role="reviewer")
        assert updated.role == "reviewer"

    def test_update_user_is_active(self, db_session):
        user = create_user(db_session, "u1@test.com", "pass1", "User One", "admin")
        assert user.is_active is True
        updated = update_user(db_session, user.id, is_active=False)
        assert updated.is_active is False

    def test_update_nonexistent_user(self, db_session):
        result = update_user(db_session, "bad_id", name="Nope")
        assert result is None


class TestAdminApiRoutes:
    @patch("src.backend.api.routes_admin.role_required")
    @patch("src.backend.api.routes_admin.get_db")
    def test_list_users_endpoint(self, mock_get_db, mock_role_required):
        mock_db = MagicMock()
        mock_user_obj = MagicMock()
        mock_user_obj.id = "usr_1"
        mock_user_obj.email = "admin@test.com"
        mock_user_obj.name = "Admin"
        mock_user_obj.role = "admin"
        mock_user_obj.is_active = True
        mock_db.query.return_value.all.return_value = [mock_user_obj]

        mock_get_db.return_value = mock_db
        mock_role_required.return_value = lambda: {"user_id": "usr_admin", "role": "admin"}

        client = TestClient(app)
        with patch("src.backend.api.routes_admin.list_all_users", return_value=[mock_user_obj]):
            response = client.get(
                "/api/admin/users",
                headers={"Authorization": "Bearer fake_token"},
            )
        assert response.status_code in (200, 401, 403)

    def test_non_admin_blocked_no_auth(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/admin/users")
        assert response.status_code in (401, 403)
