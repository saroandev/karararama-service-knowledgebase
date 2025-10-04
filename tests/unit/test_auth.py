"""
Unit tests for authentication and authorization
"""
import pytest
from datetime import datetime, timedelta
import jwt
from fastapi import HTTPException

from app.core.auth import (
    decode_jwt_token,
    get_current_user,
    require_permission,
    UserContext
)
from app.config.settings import settings


class TestJWTDecoding:
    """Test JWT token decoding"""

    def test_decode_valid_token(self):
        """Test decoding a valid JWT token"""
        # Create a valid token
        payload = {
            "user_id": "test-user-123",
            "email": "test@example.com",
            "remaining_credits": 100,
            "permissions": ["rag:query", "rag:ingest"],
            "exp": (datetime.now() + timedelta(hours=1)).timestamp()
        }
        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        # Decode it
        decoded = decode_jwt_token(token)

        assert decoded["user_id"] == "test-user-123"
        assert decoded["email"] == "test@example.com"
        assert decoded["remaining_credits"] == 100
        assert "rag:query" in decoded["permissions"]

    def test_decode_expired_token(self):
        """Test decoding an expired token"""
        # Create an expired token
        payload = {
            "user_id": "test-user-123",
            "exp": (datetime.now() - timedelta(hours=1)).timestamp()
        }
        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        # Should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            decode_jwt_token(token)

        assert exc_info.value.status_code == 401
        assert "expired" in str(exc_info.value.detail).lower()

    def test_decode_invalid_token(self):
        """Test decoding an invalid token"""
        invalid_token = "invalid.token.here"

        with pytest.raises(HTTPException) as exc_info:
            decode_jwt_token(invalid_token)

        assert exc_info.value.status_code == 401

    def test_decode_wrong_secret(self):
        """Test decoding a token with wrong secret"""
        # Create token with different secret
        payload = {
            "user_id": "test-user-123",
            "exp": (datetime.now() + timedelta(hours=1)).timestamp()
        }
        token = jwt.encode(payload, "wrong-secret-key", algorithm=settings.JWT_ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            decode_jwt_token(token)

        assert exc_info.value.status_code == 401


class TestUserContext:
    """Test UserContext model"""

    def test_user_context_creation(self):
        """Test creating UserContext"""
        user = UserContext(
            user_id="user-123",
            email="user@example.com",
            remaining_credits=500,
            permissions=["rag:query", "rag:ingest"]
        )

        assert user.user_id == "user-123"
        assert user.email == "user@example.com"
        assert user.remaining_credits == 500
        assert len(user.permissions) == 2

    def test_user_context_default_values(self):
        """Test UserContext default values"""
        user = UserContext(
            user_id="user-123",
            email="user@example.com"
        )

        assert user.remaining_credits == 0
        assert user.permissions == []

    def test_user_context_immutable(self):
        """Test that UserContext is immutable (frozen)"""
        user = UserContext(
            user_id="user-123",
            email="user@example.com"
        )

        # Should raise ValidationError when trying to modify
        with pytest.raises(Exception):
            user.user_id = "new-id"


class TestPermissionChecking:
    """Test permission checking logic"""

    @pytest.mark.asyncio
    async def test_permission_check_string_exact_match(self):
        """Test permission check with exact string match"""
        user = UserContext(
            user_id="user-123",
            email="user@example.com",
            permissions=["rag:query", "rag:ingest"]
        )

        # Mock the permission checker
        checker = require_permission("rag", "query")

        # Should not raise exception
        result = await checker(user)
        assert result.user_id == user.user_id

    @pytest.mark.asyncio
    async def test_permission_check_wildcard_all(self):
        """Test permission check with global wildcard"""
        user = UserContext(
            user_id="user-123",
            email="user@example.com",
            permissions=["*"]
        )

        checker = require_permission("rag", "query")
        result = await checker(user)
        assert result.user_id == user.user_id

    @pytest.mark.asyncio
    async def test_permission_check_resource_wildcard(self):
        """Test permission check with resource wildcard"""
        user = UserContext(
            user_id="user-123",
            email="user@example.com",
            permissions=["rag:*"]
        )

        checker = require_permission("rag", "query")
        result = await checker(user)
        assert result.user_id == user.user_id

    @pytest.mark.asyncio
    async def test_permission_check_dict_format(self):
        """Test permission check with dict format"""
        user = UserContext(
            user_id="user-123",
            email="user@example.com",
            permissions=[
                {"resource": "rag", "action": "query"}
            ]
        )

        checker = require_permission("rag", "query")
        result = await checker(user)
        assert result.user_id == user.user_id

    @pytest.mark.asyncio
    async def test_permission_denied(self):
        """Test permission denied scenario"""
        user = UserContext(
            user_id="user-123",
            email="user@example.com",
            permissions=["rag:ingest"]  # Only has ingest, not query
        )

        checker = require_permission("rag", "query")

        with pytest.raises(HTTPException) as exc_info:
            await checker(user)

        assert exc_info.value.status_code == 403
        assert "denied" in str(exc_info.value.detail).lower()


class TestDevMode:
    """Test development mode (auth disabled)"""

    @pytest.mark.asyncio
    async def test_dev_mode_returns_mock_user(self, monkeypatch):
        """Test that dev mode returns a mock user"""
        # Temporarily disable auth
        monkeypatch.setattr(settings, "REQUIRE_AUTH", False)

        user = await get_current_user(None)

        assert user.user_id == "dev-user"
        assert user.email == "dev@example.com"
        assert user.remaining_credits == 999999
        assert "*" in user.permissions

    @pytest.mark.asyncio
    async def test_dev_mode_bypasses_permission_check(self, monkeypatch):
        """Test that dev mode bypasses permission checks"""
        monkeypatch.setattr(settings, "REQUIRE_AUTH", False)

        user = await get_current_user(None)
        checker = require_permission("rag", "query")

        # Should not raise exception even without permission
        result = await checker(user)
        assert result.user_id == "dev-user"


class TestAuthenticationErrors:
    """Test authentication error scenarios"""

    @pytest.mark.asyncio
    async def test_missing_token(self):
        """Test missing authentication token"""
        # Temporarily enable auth
        original_auth = settings.REQUIRE_AUTH
        settings.REQUIRE_AUTH = True

        try:
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(None)

            assert exc_info.value.status_code == 401
            assert "missing" in str(exc_info.value.detail).lower()
        finally:
            settings.REQUIRE_AUTH = original_auth

    def test_missing_user_id_in_token(self):
        """Test token without user_id"""
        payload = {
            "email": "test@example.com",
            "exp": (datetime.now() + timedelta(hours=1)).timestamp()
        }
        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            decode_jwt_token(token)
            # This would be caught in get_current_user when checking for user_id

        # The token decodes successfully but get_current_user should fail


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
