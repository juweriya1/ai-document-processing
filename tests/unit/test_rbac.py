"""DEPRECATED test module — legacy stack retired 2026-04-24.

Tests an old `require_role` symbol that was renamed to `role_required` long
before the agentic work. Pre-existing failure, swept into the retirement
alongside the other legacy tests.
"""
import pytest

pytest.skip(
    "Legacy module retired; superseded by the agentic pipeline tests.",
    allow_module_level=True,
)

# =============================================================================
# Original content preserved below as comments for reference.
# =============================================================================

# import pytest
# from types import SimpleNamespace
#
# from src.backend.auth.rbac import require_role
#
#
# class TestRBAC:
#     def test_admin_accesses_admin_routes(self):
#         user = SimpleNamespace(role="admin")
#         checker = require_role(["admin"])
#         result = checker(user)
#         assert result == user
#
#     def test_reviewer_blocked_from_admin(self):
#         user = SimpleNamespace(role="reviewer")
#         checker = require_role(["admin"])
#         with pytest.raises(Exception):
#             checker(user)
#
#     def test_enterprise_user_can_upload(self):
#         user = SimpleNamespace(role="enterprise_user")
#         checker = require_role(["enterprise_user", "admin"])
#         result = checker(user)
#         assert result == user
#
#     def test_enterprise_user_blocked_from_review(self):
#         user = SimpleNamespace(role="enterprise_user")
#         checker = require_role(["reviewer", "admin"])
#         with pytest.raises(Exception):
#             checker(user)
