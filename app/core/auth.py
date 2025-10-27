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


class DataAccessScope(BaseModel):
    """User's data access scope configuration"""
    own_data: bool = True              # Can access own private data
    shared_data: bool = True           # Can access organization shared data
    all_users_data: bool = False       # Can access all users' data (admin only)

    model_config = {"frozen": True}


class UserContext(BaseModel):
    """User context extracted from JWT token"""
    user_id: str
    organization_id: str               # Organization ID
    email: str
    role: str = "member"               # User role: admin, member, viewer
    remaining_credits: int = 0
    permissions: List[Union[str, Dict[str, Any]]] = []
    data_access: DataAccessScope = DataAccessScope()  # Data access scope
    raw_token: str = ""                # Raw JWT token (for external service calls)

    model_config = {"frozen": True}

    # Internal cache for permission lookups (not serialized)
    _permission_cache: Optional[set] = None

    def get_accessible_scopes(self) -> List[str]:
        """Get list of data scopes this user can access"""
        scopes = []
        if self.data_access.own_data:
            scopes.append(f"user_{self.user_id}")
        if self.data_access.shared_data:
            scopes.append(f"org_{self.organization_id}_shared")
        if self.data_access.all_users_data:
            scopes.append(f"org_{self.organization_id}_all")
        return scopes

    def has_permission(self, resource: str, action: str) -> bool:
        """
        Check if user has specific permission (O(1) complexity via set lookup)

        Args:
            resource: Resource name (e.g., 'research', 'document')
            action: Action name (e.g., 'query', 'ingest', 'read', 'delete')

        Returns:
            True if user has permission, False otherwise

        Performance:
        - First call: O(n) to build set from permission list
        - Subsequent calls: O(1) set lookup
        """
        # Lazy initialization of permission set cache
        if self._permission_cache is None:
            # Use object.__setattr__ to bypass frozen model
            object.__setattr__(self, '_permission_cache', set())

            for perm in self.permissions:
                if isinstance(perm, str):
                    self._permission_cache.add(perm)
                elif isinstance(perm, dict):
                    perm_resource = perm.get("resource", "")
                    perm_action = perm.get("action", "")
                    if perm_resource and perm_action:
                        self._permission_cache.add(f"{perm_resource}:{perm_action}")

            logger.debug(f"🔧 Built permission cache for user {self.user_id}: {self._permission_cache}")

        # Check permission with O(1) set lookup
        # Priority order: wildcard > exact match > resource wildcard
        if "*" in self._permission_cache:
            return True
        if "admin:*" in self._permission_cache:
            return True
        if f"{resource}:{action}" in self._permission_cache:
            return True
        if f"{resource}:*" in self._permission_cache:
            return True

        return False


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
            organization_id="dev-org",
            email="dev@example.com",
            role="admin",
            remaining_credits=999999,
            permissions=["*"],
            data_access=DataAccessScope(
                own_data=True,
                shared_data=True,
                all_users_data=True
            )
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
    organization_id = payload.get("organization_id")
    email = payload.get("email")
    role = payload.get("role", "member")
    remaining_credits = payload.get("remaining_credits", 0)
    permissions = payload.get("permissions", [])
    data_access_dict = payload.get("data_access", {})

    # Debug logging
    logger.info(f"🔐 Token decoded for user: {user_id}")
    logger.info(f"🏢 Organization: {organization_id}")
    logger.info(f"📧 Email: {email}")
    logger.info(f"👤 Role: {role}")
    logger.info(f"💳 Credits: {remaining_credits}")
    logger.info(f"🔑 Permissions in token: {permissions}")
    logger.info(f"🔓 Data access: {data_access_dict}")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing user_id",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not organization_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing organization_id",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Parse data access scope
    data_access = DataAccessScope(**data_access_dict) if data_access_dict else DataAccessScope()

    return UserContext(
        user_id=user_id,
        organization_id=organization_id,
        email=email or "",
        role=role,
        remaining_credits=remaining_credits if remaining_credits is not None else 0,
        permissions=permissions,
        data_access=data_access,
        raw_token=token  # Store raw token for external service calls
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

    Performance:
        Uses O(1) set-based permission lookup via UserContext.has_permission()
        instead of O(n) list iteration. Significantly faster for users with
        many permissions.
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

        # Use optimized O(1) permission check
        if not user.has_permission(resource, action):
            logger.error(f"🚫 Permission denied: {resource}:{action}")
            logger.info(f"🔑 User permissions: {user.permissions}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {resource}:{action}",
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.info(f"✅ Permission granted: {resource}:{action}")
        return user

    return permission_checker
