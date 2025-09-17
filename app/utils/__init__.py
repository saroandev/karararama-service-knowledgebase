"""
Utilities package for common helper functions and decorators

This package provides:
- Centralized logging configuration
- Common decorators (retry, cache, measure_time)
- Input validators
- General helper functions
"""

# Import commonly used utilities for easy access
from app.utils.logging import (
    setup_logger,
    get_logger,
    log_function_call,
    log_error
)

from app.utils.decorators import (
    retry,
    async_retry,
    cache,
    measure_time,
    validate_input,
    rate_limit
)

from app.utils.validators import (
    validate_pdf_file,
    validate_query,
    validate_file_size,
    validate_config,
    validate_embedding_dimension
)

from app.utils.helpers import (
    generate_document_id,
    generate_chunk_id,
    format_timestamp,
    calculate_file_hash,
    sanitize_filename,
    get_file_extension,
    batch_iterator,
    merge_dicts
)

__all__ = [
    # Logging
    'setup_logger',
    'get_logger',
    'log_function_call',
    'log_error',
    # Decorators
    'retry',
    'async_retry',
    'cache',
    'measure_time',
    'validate_input',
    'rate_limit',
    # Validators
    'validate_pdf_file',
    'validate_query',
    'validate_file_size',
    'validate_config',
    'validate_embedding_dimension',
    # Helpers
    'generate_document_id',
    'generate_chunk_id',
    'format_timestamp',
    'calculate_file_hash',
    'sanitize_filename',
    'get_file_extension',
    'batch_iterator',
    'merge_dicts'
]