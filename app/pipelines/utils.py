"""
Utility functions for pipeline operations
"""
import logging
import time
import asyncio
from typing import Any, Callable, TypeVar, Optional, Dict, List
from functools import wraps
from datetime import datetime

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_async(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying async functions

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff: Backoff multiplier for delay
        exceptions: Tuple of exceptions to catch and retry

    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
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


def retry_sync(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying synchronous functions

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff: Backoff multiplier for delay
        exceptions: Tuple of exceptions to catch and retry

    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
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


def measure_time(func: Callable) -> Callable:
    """
    Decorator to measure execution time

    Args:
        func: Function to measure

    Returns:
        Decorated function that logs execution time
    """
    @wraps(func)
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

    @wraps(func)
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


def validate_file_size(file_obj: Any, max_size_mb: float = 50.0) -> bool:
    """
    Validate file size

    Args:
        file_obj: File object with seek and tell methods
        max_size_mb: Maximum file size in megabytes

    Returns:
        True if file size is valid

    Raises:
        ValueError: If file is too large
    """
    # Get file size
    file_obj.seek(0, 2)  # Seek to end
    file_size = file_obj.tell()
    file_obj.seek(0)  # Reset to beginning

    max_size_bytes = max_size_mb * 1024 * 1024

    if file_size > max_size_bytes:
        raise ValueError(
            f"File size ({file_size / 1024 / 1024:.2f}MB) exceeds "
            f"maximum allowed size ({max_size_mb}MB)"
        )

    return True


def validate_file_type(filename: str, allowed_extensions: List[str]) -> bool:
    """
    Validate file type by extension

    Args:
        filename: File name
        allowed_extensions: List of allowed extensions (e.g., ['.pdf', '.txt'])

    Returns:
        True if file type is valid

    Raises:
        ValueError: If file type is not allowed
    """
    file_ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
    file_ext = f".{file_ext}" if file_ext else ""

    if file_ext not in allowed_extensions:
        raise ValueError(
            f"File type '{file_ext}' not allowed. "
            f"Allowed types: {', '.join(allowed_extensions)}"
        )

    return True


def batch_process(
    items: List[Any],
    batch_size: int,
    process_func: Callable,
    progress_callback: Optional[Callable] = None
) -> List[Any]:
    """
    Process items in batches

    Args:
        items: List of items to process
        batch_size: Size of each batch
        process_func: Function to process each batch
        progress_callback: Optional callback for progress updates

    Returns:
        List of processed results
    """
    results = []
    total_items = len(items)

    for i in range(0, total_items, batch_size):
        batch = items[i:i + batch_size]
        batch_results = process_func(batch)
        results.extend(batch_results)

        if progress_callback:
            progress = min(100, (i + len(batch)) / total_items * 100)
            progress_callback(progress, f"Processed {i + len(batch)}/{total_items} items")

    return results


async def batch_process_async(
    items: List[Any],
    batch_size: int,
    process_func: Callable,
    progress_callback: Optional[Callable] = None
) -> List[Any]:
    """
    Process items in batches asynchronously

    Args:
        items: List of items to process
        batch_size: Size of each batch
        process_func: Async function to process each batch
        progress_callback: Optional callback for progress updates

    Returns:
        List of processed results
    """
    results = []
    total_items = len(items)

    for i in range(0, total_items, batch_size):
        batch = items[i:i + batch_size]
        batch_results = await process_func(batch)
        results.extend(batch_results)

        if progress_callback:
            progress = min(100, (i + len(batch)) / total_items * 100)
            progress_callback(progress, f"Processed {i + len(batch)}/{total_items} items")

    return results


def create_pipeline_metadata(
    pipeline_name: str,
    input_params: Dict[str, Any],
    start_time: datetime,
    end_time: Optional[datetime] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Create standardized pipeline metadata

    Args:
        pipeline_name: Name of the pipeline
        input_params: Input parameters used
        start_time: Pipeline start time
        end_time: Pipeline end time
        **kwargs: Additional metadata fields

    Returns:
        Metadata dictionary
    """
    metadata = {
        "pipeline_name": pipeline_name,
        "input_params": input_params,
        "started_at": start_time.isoformat(),
        "completed_at": end_time.isoformat() if end_time else None,
        "duration_seconds": (end_time - start_time).total_seconds() if end_time else None,
        **kwargs
    }

    return metadata


def format_error_response(
    error: Exception,
    pipeline_name: str,
    stage: Optional[str] = None
) -> Dict[str, Any]:
    """
    Format error response for pipeline failures

    Args:
        error: Exception that occurred
        pipeline_name: Name of the pipeline
        stage: Pipeline stage where error occurred

    Returns:
        Formatted error dictionary
    """
    error_response = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "pipeline": pipeline_name,
        "stage": stage,
        "timestamp": datetime.now().isoformat()
    }

    # Add traceback for debugging (only in development)
    import traceback
    import os
    if os.getenv("ENV", "development") == "development":
        error_response["traceback"] = traceback.format_exc()

    return error_response


def estimate_processing_time(
    num_items: int,
    avg_time_per_item: float,
    overhead_seconds: float = 5.0
) -> float:
    """
    Estimate total processing time

    Args:
        num_items: Number of items to process
        avg_time_per_item: Average processing time per item (seconds)
        overhead_seconds: Fixed overhead time

    Returns:
        Estimated total time in seconds
    """
    return overhead_seconds + (num_items * avg_time_per_item)


def calculate_batch_size(
    total_items: int,
    max_batch_size: int = 100,
    min_batch_size: int = 10,
    target_batches: int = 10
) -> int:
    """
    Calculate optimal batch size

    Args:
        total_items: Total number of items
        max_batch_size: Maximum batch size
        min_batch_size: Minimum batch size
        target_batches: Target number of batches

    Returns:
        Calculated batch size
    """
    if total_items <= max_batch_size:
        return total_items

    ideal_batch_size = max(min_batch_size, total_items // target_batches)
    return min(max_batch_size, ideal_batch_size)