"""
Common decorators for the application
"""
import time
import asyncio
import functools
import logging
from typing import Any, Callable, Optional, TypeVar, Union, Dict
from datetime import datetime, timedelta
from collections import OrderedDict
import hashlib
import json

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying functions on failure

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Backoff multiplier for delay
        exceptions: Tuple of exceptions to catch and retry

    Example:
        @retry(max_attempts=3, delay=1.0)
        def unstable_api_call():
            return requests.get('https://api.example.com')
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}")

            raise last_exception

        return wrapper
    return decorator


def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying async functions on failure

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Backoff multiplier for delay
        exceptions: Tuple of exceptions to catch and retry

    Example:
        @async_retry(max_attempts=3, delay=1.0)
        async def unstable_async_api_call():
            return await aiohttp.get('https://api.example.com')
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}")

            raise last_exception

        return wrapper
    return decorator


class LRUCache:
    """Simple LRU cache implementation"""

    def __init__(self, max_size: int = 128):
        self.cache = OrderedDict()
        self.max_size = max_size

    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

    def put(self, key: str, value: Any):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value

        # Remove oldest if cache is full
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)

    def clear(self):
        self.cache.clear()


def cache(max_size: int = 128, ttl: Optional[int] = None):
    """
    Simple caching decorator with optional TTL

    Args:
        max_size: Maximum cache size
        ttl: Time to live in seconds (optional)

    Example:
        @cache(max_size=100, ttl=3600)
        def expensive_computation(x, y):
            return x ** y
    """
    def decorator(func: Callable) -> Callable:
        lru_cache = LRUCache(max_size=max_size)
        cache_times = {}

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from arguments
            key_parts = [func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = hashlib.md5("|".join(key_parts).encode()).hexdigest()

            # Check if cached value exists and is still valid
            cached_value = lru_cache.get(cache_key)
            if cached_value is not None:
                if ttl is None or (
                    cache_key in cache_times and
                    time.time() - cache_times[cache_key] < ttl
                ):
                    logger.debug(f"Cache hit for {func.__name__}")
                    return cached_value

            # Compute and cache result
            result = func(*args, **kwargs)
            lru_cache.put(cache_key, result)
            if ttl is not None:
                cache_times[cache_key] = time.time()

            return result

        # Add method to clear cache
        wrapper.clear_cache = lru_cache.clear

        return wrapper
    return decorator


def measure_time(func: Callable) -> Callable:
    """
    Decorator to measure and log execution time

    Example:
        @measure_time
        def slow_function():
            time.sleep(2)
    """
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            elapsed = time.time() - start_time
            logger.info(f"{func.__name__} completed in {elapsed:.2f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"{func.__name__} failed after {elapsed:.2f}s: {e}")
            raise

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            logger.info(f"{func.__name__} completed in {elapsed:.2f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"{func.__name__} failed after {elapsed:.2f}s: {e}")
            raise

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


def validate_input(**validators):
    """
    Decorator to validate function inputs

    Args:
        **validators: Dictionary of parameter names to validation functions

    Example:
        @validate_input(
            x=lambda x: x > 0,
            y=lambda y: isinstance(y, str)
        )
        def process(x: int, y: str):
            return f"{y}: {x}"
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get function signature
            import inspect
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            # Validate each parameter
            for param_name, validator in validators.items():
                if param_name in bound.arguments:
                    value = bound.arguments[param_name]
                    try:
                        if not validator(value):
                            raise ValueError(f"Validation failed for {param_name}={value}")
                    except Exception as e:
                        raise ValueError(f"Invalid {param_name}: {e}")

            return func(*args, **kwargs)

        return wrapper
    return decorator


class RateLimiter:
    """Simple rate limiter using token bucket algorithm"""

    def __init__(self, rate: int, per: float):
        self.rate = rate
        self.per = per
        self.allowance = rate
        self.last_check = time.time()

    def allow(self) -> bool:
        current = time.time()
        time_passed = current - self.last_check
        self.last_check = current
        self.allowance += time_passed * (self.rate / self.per)

        if self.allowance > self.rate:
            self.allowance = self.rate

        if self.allowance < 1.0:
            return False

        self.allowance -= 1.0
        return True


def rate_limit(rate: int = 10, per: float = 60.0):
    """
    Rate limiting decorator

    Args:
        rate: Number of allowed calls
        per: Time period in seconds

    Example:
        @rate_limit(rate=10, per=60)  # 10 calls per minute
        def api_call():
            return requests.get('https://api.example.com')
    """
    def decorator(func: Callable) -> Callable:
        limiter = RateLimiter(rate, per)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not limiter.allow():
                raise RuntimeError(
                    f"Rate limit exceeded for {func.__name__}. "
                    f"Maximum {rate} calls per {per} seconds."
                )
            return func(*args, **kwargs)

        return wrapper
    return decorator


def deprecated(message: str = None):
    """
    Mark a function as deprecated

    Args:
        message: Optional deprecation message

    Example:
        @deprecated("Use new_function instead")
        def old_function():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import warnings
            warning_msg = f"{func.__name__} is deprecated"
            if message:
                warning_msg += f": {message}"
            warnings.warn(warning_msg, DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def singleton(cls):
    """
    Singleton decorator for classes

    Example:
        @singleton
        class DatabaseConnection:
            def __init__(self):
                self.connection = connect()
    """
    instances = {}

    @functools.wraps(cls)
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance