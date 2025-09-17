"""
Utility functions for pipeline operations

This module re-exports utilities from app.utils for backward compatibility.
New code should import directly from app.utils.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

# Import from centralized utils
from app.utils.decorators import (
    retry as retry_sync,
    async_retry as retry_async,
    measure_time
)
from app.utils.validators import (
    validate_file_size,
    validate_file_type as _validate_file_type
)
from app.utils.helpers import (
    batch_iterator,
    format_timestamp,
    calculate_file_hash,
    estimate_tokens
)

logger = logging.getLogger(__name__)


# Backward compatibility wrapper for validate_file_type
def validate_file_type(filename: str, allowed_extensions: List[str]) -> bool:
    """
    Validate file type by extension (backward compatibility wrapper)

    Args:
        filename: File name
        allowed_extensions: List of allowed extensions

    Returns:
        True if file type is valid

    Raises:
        ValueError: If file type is not allowed
    """
    # Convert to format expected by new validator
    from pathlib import Path
    ext = Path(filename).suffix.lower()

    if ext not in allowed_extensions:
        raise ValueError(
            f"File type '{ext}' not allowed. "
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