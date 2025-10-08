"""Global DB service client for public data queries"""

import httpx
from typing import Dict, Any, Optional, List
import asyncio
from app.config.settings import settings
import logging

logger = logging.getLogger(__name__)


class GlobalDBServiceClient:
    """Client for communicating with OneDocs Global DB service (public data)"""

    def __init__(self):
        self.base_url = settings.GLOBAL_DB_SERVICE_URL
        self.timeout = settings.GLOBAL_DB_SERVICE_TIMEOUT
        self.default_bucket = settings.GLOBAL_DB_DEFAULT_BUCKET

    async def search_public(
        self,
        question: str,
        user_token: str,
        top_k: int = 5,
        min_relevance_score: float = 0.7,
        bucket: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search public documents via Global DB service

        Args:
            question: User's question
            user_token: JWT token for authentication
            top_k: Number of results to retrieve
            min_relevance_score: Minimum relevance score
            bucket: Bucket name (defaults to 'mevzuat')

        Returns:
            Response from Global DB service with answer and sources

        Raises:
            Exception: If communication fails
        """
        bucket = bucket or self.default_bucket

        payload = {
            "question": question,
            "bucket": bucket,
            "top_k": top_k,
            "min_relevance_score": min_relevance_score,
            "include_sources": True,
            "generate_answer": True
        }

        headers = {
            "Authorization": f"Bearer {user_token}",
            "Content-Type": "application/json"
        }

        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                logger.info(f"🌍 Calling Global DB service (attempt {attempt + 1}): bucket={bucket}, question={question[:50]}...")

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/query/search",
                        json=payload,
                        headers=headers
                    )

                    if response.status_code == 200:
                        result = response.json()

                        if result.get("success"):
                            logger.info(
                                f"✅ Global DB query successful: "
                                f"sources={result.get('total_sources', 0)}, "
                                f"time={result.get('processing_time', 0):.2f}s"
                            )
                            return result
                        else:
                            error_msg = result.get("error", "Unknown error")
                            logger.error(f"❌ Global DB query failed: {error_msg}")
                            return {
                                "success": False,
                                "error": error_msg,
                                "answer": "",
                                "sources": []
                            }

                    elif response.status_code == 401:
                        logger.error("🔒 Global DB authentication failed (invalid token)")
                        return {
                            "success": False,
                            "error": "Authentication failed",
                            "answer": "",
                            "sources": []
                        }

                    elif response.status_code == 403:
                        logger.error("🚫 Global DB access forbidden (insufficient permissions)")
                        return {
                            "success": False,
                            "error": "Access forbidden",
                            "answer": "",
                            "sources": []
                        }

                    else:
                        logger.error(f"❌ Global DB service error: {response.status_code}")
                        error_text = response.text[:200] if response.text else "No error details"
                        logger.error(f"Error details: {error_text}")

                        # Retry on 5xx errors
                        if response.status_code >= 500 and attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay * (attempt + 1))
                            continue

                        return {
                            "success": False,
                            "error": f"Service error: {response.status_code}",
                            "answer": "",
                            "sources": []
                        }

            except httpx.TimeoutException:
                logger.error(f"⏱️ Global DB service timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue

                return {
                    "success": False,
                    "error": "Request timeout",
                    "answer": "",
                    "sources": []
                }

            except httpx.RequestError as e:
                logger.error(f"❌ Global DB service request error: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue

                return {
                    "success": False,
                    "error": f"Request failed: {str(e)}",
                    "answer": "",
                    "sources": []
                }

            except Exception as e:
                logger.error(f"❌ Unexpected error in Global DB client: {str(e)}")
                return {
                    "success": False,
                    "error": f"Unexpected error: {str(e)}",
                    "answer": "",
                    "sources": []
                }

        # Max retries exceeded
        return {
            "success": False,
            "error": "Max retries exceeded",
            "answer": "",
            "sources": []
        }

    async def check_health(self) -> bool:
        """Check if Global DB service is healthy"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception as e:
            logger.error(f"❌ Global DB service health check failed: {str(e)}")
            return False


# Singleton instance
_global_db_client = None


def get_global_db_client() -> GlobalDBServiceClient:
    """Get or create Global DB service client singleton"""
    global _global_db_client
    if _global_db_client is None:
        _global_db_client = GlobalDBServiceClient()
    return _global_db_client
