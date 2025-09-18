"""
Validator Factory for managing validator instances
"""
import threading
import logging
from typing import Optional
from contextlib import asynccontextmanager

from app.core.validation.document_validator import DocumentValidator

logger = logging.getLogger(__name__)


class ValidatorFactory:
    """
    Factory for creating and managing validator instances.
    Implements singleton pattern with object pooling for thread-safety and performance.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern implementation"""
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize factory with validator pool"""
        if not hasattr(self, '_initialized'):
            self._pool_size = 5  # Maximum validators in pool
            self._pool = []
            self._pool_lock = threading.Lock()
            self._active_validators = 0
            self._max_active = 20  # Maximum concurrent validators
            self._initialized = True
            logger.info(f"ValidatorFactory initialized with pool size: {self._pool_size}")

    def get_validator(self) -> DocumentValidator:
        """
        Get a validator instance from pool or create new one.

        Returns:
            DocumentValidator instance

        Raises:
            RuntimeError: If maximum active validators limit reached
        """
        with self._pool_lock:
            # Try to get from pool first
            if self._pool:
                validator = self._pool.pop()
                logger.debug(f"Reusing validator from pool. Pool size: {len(self._pool)}")
                return validator

            # Check if we can create a new validator
            if self._active_validators >= self._max_active:
                raise RuntimeError(
                    f"Maximum active validators limit reached ({self._max_active}). "
                    "Please try again later."
                )

            # Create new validator
            validator = self._create_validator()
            self._active_validators += 1
            logger.debug(f"Created new validator. Active count: {self._active_validators}")
            return validator

    def release_validator(self, validator: DocumentValidator) -> None:
        """
        Return validator to pool for reuse.

        Args:
            validator: DocumentValidator instance to release
        """
        if validator is None:
            return

        with self._pool_lock:
            # Return to pool if there's space
            if len(self._pool) < self._pool_size:
                self._pool.append(validator)
                logger.debug(f"Validator returned to pool. Pool size: {len(self._pool)}")
            else:
                # Pool is full, just decrease active count
                self._active_validators = max(0, self._active_validators - 1)
                logger.debug(f"Validator released. Active count: {self._active_validators}")

    def _create_validator(self) -> DocumentValidator:
        """
        Create a new validator instance.

        Returns:
            New DocumentValidator instance
        """
        return DocumentValidator()

    def get_pool_status(self) -> dict:
        """
        Get current pool status for monitoring.

        Returns:
            Dictionary with pool statistics
        """
        with self._pool_lock:
            return {
                "pool_size": len(self._pool),
                "max_pool_size": self._pool_size,
                "active_validators": self._active_validators,
                "max_active": self._max_active,
                "available": len(self._pool) > 0 or self._active_validators < self._max_active
            }

    def reset_pool(self) -> None:
        """Reset the validator pool (useful for testing or maintenance)"""
        with self._pool_lock:
            self._pool.clear()
            self._active_validators = 0
            logger.info("Validator pool reset")


# Global factory instance
validator_factory = ValidatorFactory()


@asynccontextmanager
async def get_document_validator():
    """
    Async context manager for safe validator lifecycle management.

    Usage:
        async with get_document_validator() as validator:
            result = await validator.validate(file, milvus_manager)

    Yields:
        DocumentValidator instance

    Ensures validator is properly returned to pool after use.
    """
    validator = None
    try:
        validator = validator_factory.get_validator()
        yield validator
    except Exception as e:
        logger.error(f"Error during validation: {e}", exc_info=True)
        raise
    finally:
        if validator:
            validator_factory.release_validator(validator)


def get_validator() -> DocumentValidator:
    """
    Get a validator instance (for FastAPI dependency injection).

    Returns:
        DocumentValidator instance

    Note: When using this function, ensure to call release_validator
          when done, or use the context manager instead.
    """
    return validator_factory.get_validator()


def release_validator(validator: Optional[DocumentValidator]) -> None:
    """
    Release a validator back to the pool.

    Args:
        validator: DocumentValidator instance to release
    """
    if validator:
        validator_factory.release_validator(validator)