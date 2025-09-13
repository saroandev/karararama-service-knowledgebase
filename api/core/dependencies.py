"""
Dependencies and decorators for API endpoints
"""
import asyncio
import logging
from functools import wraps
from app.config import settings

logger = logging.getLogger(__name__)


def retry_with_backoff(max_retries=3, backoff_factor=2):
    """Retry decorator with exponential backoff"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    wait_time = backoff_factor ** attempt
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
            return None

        return wrapper

    return decorator


def get_embedding_dimension():
    """Get embedding dimension based on configured model"""
    # Get dimension from settings, with backward compatibility
    return settings.EMBEDDING_DIMENSION