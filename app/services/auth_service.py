"""Auth service client for usage tracking and communication"""

import httpx
from datetime import datetime
from typing import Dict, Any, Optional
import asyncio
from app.config.settings import settings
from app.core.exceptions import AuthServiceError
import logging

logger = logging.getLogger(__name__)


class AuthServiceClient:
    """Client for communicating with onedocs-auth service"""

    def __init__(self):
        self.base_url = settings.AUTH_SERVICE_URL
        self.timeout = settings.AUTH_SERVICE_TIMEOUT

    async def consume_usage(
        self,
        user_id: str,
        service_type: str,
        tokens_used: int = 0,
        processing_time: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Notify auth service about usage consumption

        Args:
            user_id: User identifier
            service_type: Type of service (e.g., 'rag_query', 'rag_ingest')
            tokens_used: Number of tokens consumed
            processing_time: Processing time in seconds
            metadata: Additional metadata

        Returns:
            Response from auth service with updated credits

        Raises:
            AuthServiceError: If communication fails
        """
        payload = {
            "user_id": user_id,
            "service_type": service_type,
            "tokens_used": tokens_used,
            "processing_time": processing_time,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }

        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/api/v1/usage/consume",
                        json=payload
                    )

                    if response.status_code == 200:
                        result = response.json()
                        # tokens_used now represents document count for ingest
                        logger.info(
                            f"✅ Usage consumed: user={user_id}, "
                            f"service={service_type}, documents={tokens_used}"
                        )
                        return result

                    elif response.status_code == 403:
                        logger.warning(f"⚠️ User {user_id} has insufficient credits")
                        return {
                            "success": False,
                            "error": "Insufficient credits",
                            "remaining_credits": 0
                        }

                    else:
                        logger.error(f"❌ Auth service error: {response.status_code}")

                        # Retry on 5xx errors
                        if response.status_code >= 500 and attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay * (attempt + 1))
                            continue

                        raise AuthServiceError(
                            f"Auth service error: {response.status_code}"
                        )

            except httpx.TimeoutException:
                logger.error(f"⏱️ Auth service timeout (attempt {attempt + 1})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                raise AuthServiceError("Auth service timeout")

            except httpx.RequestError as e:
                logger.error(f"❌ Auth service request error: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                raise AuthServiceError(f"Auth service request failed: {str(e)}")

        raise AuthServiceError("Auth service communication failed after retries")

    async def check_health(self) -> bool:
        """Check if auth service is healthy"""
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception as e:
            logger.error(f"❌ Auth service health check failed: {str(e)}")
            return False


# Singleton instance
_auth_service_client = None


def get_auth_service_client() -> AuthServiceClient:
    """Get or create auth service client singleton"""
    global _auth_service_client
    if _auth_service_client is None:
        _auth_service_client = AuthServiceClient()
    return _auth_service_client
