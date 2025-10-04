"""Authentication and authorization utilities"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from fastapi import Security, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt
import logging
from app.config.settings import settings

logger = logging.getLogger(__name__)

# HTTPBearer security scheme - Creates 🔒 Authorize button in Swagger UI
security = HTTPBearer(auto_error=False)


class UserContext(BaseModel):
    """User context extracted from JWT token"""
    user_id: str
    email: str
    remaining_credits: int = 0
    permissions: List[Union[str, Dict[str, Any]]] = []

    model_config = {"frozen": True}


def decode_jwt_token(token: str) -> dict:
    """
    Decode and validate JWT token

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid, expired, or malformed
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )

        # Check token expiry
        exp = payload.get("exp")
        if exp:
            exp_time = datetime.fromtimestamp(exp)
            if exp_time < datetime.now():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> UserContext:
    """
    FastAPI dependency to extract and validate current user from JWT token.

    Args:
        credentials: HTTP Bearer credentials from Authorization header

    Returns:
        UserContext with user information

    Raises:
        HTTPException: If authentication fails
    """
    # If auth is not required (development mode), return mock user
    if not settings.REQUIRE_AUTH:
        logger.info("🔓 Auth disabled, using mock user")
        return UserContext(
            user_id="dev-user",
            email="dev@example.com",
            remaining_credits=999999,
            permissions=["*"]
        )

    # Check if token is provided
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Decode and validate token
    token = credentials.credentials
    payload = decode_jwt_token(token)

    # Extract user information from token payload
    user_id = payload.get("user_id") or payload.get("sub")
    email = payload.get("email")
    remaining_credits = payload.get("remaining_credits", 0)
    permissions = payload.get("permissions", [])

    # Debug logging
    logger.info(f"🔐 Token decoded for user: {user_id}")
    logger.info(f"📧 Email: {email}")
    logger.info(f"💳 Credits: {remaining_credits}")
    logger.info(f"🔑 Permissions in token: {permissions}")
    logger.info(f"🔑 Permissions type: {type(permissions)}")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing user_id",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UserContext(
        user_id=user_id,
        email=email or "",
        remaining_credits=remaining_credits,
        permissions=permissions
    )


def require_permission(resource: str, action: str):
    """
    Dependency factory to check if user has required permission.

    Args:
        resource: Resource name (e.g., 'rag', 'document')
        action: Action name (e.g., 'query', 'ingest', 'read', 'delete')

    Returns:
        Dependency function that validates user permissions

    Usage:
        @router.post("/api/resource")
        async def endpoint(
            user: UserContext = Depends(require_permission("resource", "action"))
        ):
            ...
    """
    async def permission_checker(
        user: UserContext = Depends(get_current_user)
    ) -> UserContext:
        """Check if user has the required permission."""
        # If auth is disabled, allow everything
        if not settings.REQUIRE_AUTH:
            return user

        logger.info(f"🔍 Checking permission: {resource}:{action}")
        logger.info(f"👤 User: {user.user_id}")
        logger.info(f"🔑 User permissions: {user.permissions}")

        # Check permissions
        has_permission = False

        for i, perm in enumerate(user.permissions):
            logger.debug(f"  Checking permission[{i}]: {perm} (type: {type(perm)})")
            # Handle both string format "resource:action" and dict format
            if isinstance(perm, str):
                if perm == "*":
                    has_permission = True
                    break
                elif perm == f"{resource}:{action}":
                    has_permission = True
                    break
                elif perm == f"{resource}:*":
                    has_permission = True
                    break

            elif isinstance(perm, dict):
                perm_resource = perm.get("resource")
                perm_action = perm.get("action")

                # Global wildcard
                if perm_resource == "*" and perm_action == "*":
                    has_permission = True
                    break

                # Resource wildcard (e.g., "*:*")
                if perm_resource == "*":
                    has_permission = True
                    break

                # Admin wildcard (admin:* grants all permissions)
                if perm_resource == "admin" and perm_action == "*":
                    logger.info(f"✅ Permission granted via admin:* → {resource}:{action}")
                    has_permission = True
                    break

                # Action wildcard (e.g., "research:*")
                if perm_action == "*" and perm_resource == resource:
                    logger.info(f"✅ Permission matched: {perm_resource}:* → {resource}:{action}")
                    has_permission = True
                    break

                # Exact match (e.g., "research:query")
                if perm_resource == resource and perm_action == action:
                    has_permission = True
                    break

        if not has_permission:
            logger.error(f"🚫 Permission denied: {resource}:{action}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {resource}:{action}",
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.info(f"✅ Permission granted: {resource}:{action}")
        return user

    return permission_checker
