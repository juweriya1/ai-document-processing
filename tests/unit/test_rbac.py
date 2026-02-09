import pytest
from types import SimpleNamespace

from src.backend.auth.rbac import require_role


class TestRBAC:
    def test_admin_accesses_admin_routes(self):
        user = SimpleNamespace(role="admin")
        checker = require_role(["admin"])
        result = checker(user)
        assert result == user

    def test_reviewer_blocked_from_admin(self):
        user = SimpleNamespace(role="reviewer")
        checker = require_role(["admin"])
        with pytest.raises(Exception):
            checker(user)

    def test_enterprise_user_can_upload(self):
        user = SimpleNamespace(role="enterprise_user")
        checker = require_role(["enterprise_user", "admin"])
        result = checker(user)
        assert result == user

    def test_enterprise_user_blocked_from_review(self):
        user = SimpleNamespace(role="enterprise_user")
        checker = require_role(["reviewer", "admin"])
        with pytest.raises(Exception):
            checker(user)
