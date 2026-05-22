"""
tests/unit/test_auth_security.py
──────────────────────────────────
Unit tests for JWT generation, password hashing, token decoding, and role validation.
All tests are pure unit tests — no database, no network, no Redis.
"""
import pytest
from datetime import timedelta
from unittest.mock import patch
from jose import JWTError
import uuid

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    decode_token,
    _make_token,
)

pytestmark = pytest.mark.unit


# ─── Password Hashing ────────────────────────────────────────────────────────

class TestPasswordHashing:
    """Test bcrypt password hashing and verification."""

    def test_hash_returns_string(self):
        result = hash_password("my_secure_password")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_hash_is_not_plaintext(self):
        plain = "my_secure_password"
        hashed = hash_password(plain)
        assert plain not in hashed

    def test_hash_is_bcrypt_format(self):
        hashed = hash_password("password123")
        assert hashed.startswith("$2")  # bcrypt signature

    def test_different_calls_produce_different_hashes(self):
        """bcrypt uses random salt — same password hashes differently each time."""
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        assert h1 != h2

    def test_verify_correct_password_returns_true(self):
        plain = "correct_password"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_wrong_password_returns_false(self):
        hashed = hash_password("real_password")
        assert verify_password("wrong_password", hashed) is False

    def test_verify_empty_password_returns_false(self):
        hashed = hash_password("some_password")
        assert verify_password("", hashed) is False

    def test_verify_arabic_password(self):
        arabic_password = "كلمة_مرور_عربية_123"
        hashed = hash_password(arabic_password)
        assert verify_password(arabic_password, hashed) is True
        assert verify_password("wrong", hashed) is False


# ─── JWT Access Token ─────────────────────────────────────────────────────────

class TestAccessToken:
    """Test JWT access token creation and decoding."""

    def test_create_access_token_returns_string(self):
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        token = create_access_token(user_id, tenant_id, "admin")
        assert isinstance(token, str)
        assert len(token) > 50  # JWTs are never this short

    def test_access_token_contains_correct_claims(self):
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        token = create_access_token(user_id, tenant_id, "agent")
        payload = decode_access_token(token)

        assert payload["sub"] == str(user_id)
        assert payload["tenant_id"] == str(tenant_id)
        assert payload["role"] == "agent"
        assert payload["type"] == "access"

    def test_access_token_has_expiry(self):
        token = create_access_token(uuid.uuid4(), uuid.uuid4(), "admin")
        payload = decode_token(token)
        assert "exp" in payload
        assert "iat" in payload

    def test_access_token_all_roles(self):
        for role in ["admin", "agent", "operator"]:
            token = create_access_token(uuid.uuid4(), uuid.uuid4(), role)
            payload = decode_access_token(token)
            assert payload["role"] == role

    def test_decode_access_token_rejects_refresh_token(self):
        """An access token decoder must reject a refresh token."""
        token = create_refresh_token(uuid.uuid4())
        with pytest.raises(JWTError):
            decode_access_token(token)

    def test_access_token_invalid_signature_raises(self):
        token = create_access_token(uuid.uuid4(), uuid.uuid4(), "admin")
        tampered = token[:-5] + "XXXXX"  # corrupt the signature
        with pytest.raises(JWTError):
            decode_token(tampered)

    def test_access_token_expired_raises(self):
        """Override expiry to -1 minute to simulate an expired token."""
        with patch("app.core.security.settings") as mock_settings:
            mock_settings.SECRET_KEY = "test-secret-key-12345"
            mock_settings.JWT_ALGORITHM = "HS256"
            mock_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = -1
            expired_token = _make_token(
                {"sub": str(uuid.uuid4()), "type": "access"},
                timedelta(minutes=-1),
            )
        with pytest.raises(JWTError):
            decode_token(expired_token)


# ─── JWT Refresh Token ────────────────────────────────────────────────────────

class TestRefreshToken:
    """Test JWT refresh token creation and decoding."""

    def test_create_refresh_token_returns_string(self):
        token = create_refresh_token(uuid.uuid4())
        assert isinstance(token, str)
        assert len(token) > 50

    def test_refresh_token_contains_correct_claims(self):
        user_id = uuid.uuid4()
        token = create_refresh_token(user_id)
        payload = decode_refresh_token(token)

        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"
        # Refresh tokens must NOT contain tenant_id or role for security
        assert "tenant_id" not in payload
        assert "role" not in payload

    def test_refresh_token_rejects_access_token(self):
        """A refresh token decoder must reject an access token."""
        token = create_access_token(uuid.uuid4(), uuid.uuid4(), "admin")
        with pytest.raises(JWTError):
            decode_refresh_token(token)

    def test_refresh_token_invalid_string_raises(self):
        with pytest.raises(JWTError):
            decode_token("not.a.real.token")

    def test_refresh_token_empty_string_raises(self):
        with pytest.raises(JWTError):
            decode_token("")
