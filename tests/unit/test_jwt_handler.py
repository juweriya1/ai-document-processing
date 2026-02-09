import pytest
from datetime import timedelta

from src.backend.auth.jwt_handler import create_access_token, verify_token


class TestJWTHandler:
    def test_create_returns_string(self):
        token = create_access_token(data={"sub": "user@example.com", "role": "admin"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_valid_token(self):
        token = create_access_token(data={"sub": "user@example.com", "role": "admin"})
        payload = verify_token(token)
        assert payload["sub"] == "user@example.com"
        assert payload["role"] == "admin"

    def test_verify_invalid_token_raises(self):
        with pytest.raises(Exception):
            verify_token("invalid.token.string")

    def test_expired_token_raises(self):
        token = create_access_token(
            data={"sub": "user@example.com"},
            expires_delta=timedelta(seconds=-1),
        )
        with pytest.raises(Exception):
            verify_token(token)
