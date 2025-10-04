"""Custom exceptions for authentication and authorization"""

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


class AuthenticationError(HTTPException):
    """Raised when authentication fails"""
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


class InsufficientCreditsError(HTTPException):
    """Raised when user has insufficient credits"""
    def __init__(self, detail: str = "Insufficient credits"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


class AuthServiceError(HTTPException):
    """Raised when auth service communication fails"""
    def __init__(self, detail: str = "Auth service unavailable"):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail
        )


class QuotaExceededError(HTTPException):
    """Raised when user exceeds their quota"""
    def __init__(self, detail: str = "Quota exceeded"):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail
        )


# Exception handlers for FastAPI
async def authentication_error_handler(request: Request, exc: AuthenticationError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "error_type": "authentication_error"
        },
        headers=exc.headers
    )


async def insufficient_credits_error_handler(request: Request, exc: InsufficientCreditsError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "error_type": "insufficient_credits"
        }
    )


async def auth_service_error_handler(request: Request, exc: AuthServiceError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "error_type": "auth_service_error"
        }
    )


async def quota_exceeded_error_handler(request: Request, exc: QuotaExceededError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "error_type": "quota_exceeded"
        }
    )
