"""
Error handling utilities for API endpoints
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def get_user_friendly_error_message(error: Exception) -> str:
    """
    Convert technical exceptions to user-friendly error messages.

    Args:
        error: The exception that occurred

    Returns:
        User-friendly error message string
    """
    error_type = type(error).__name__
    error_msg = str(error).lower()

    # Specific error mappings
    error_mappings = {
        # Async/Context manager errors
        "AttributeError": {
            "__aenter__": "Internal validation system error. Please try again.",
            "__aexit__": "Validation cleanup error. Please try again.",
            "nonetype": "System initialization error. Please contact support."
        },

        # Connection errors
        "ConnectionError": "Database connection failed. Please check if all services are running.",
        "ConnectionRefusedError": "Cannot connect to database. Services may be down.",
        "TimeoutError": "Request timed out. The file may be too large or the system is busy.",

        # Resource errors
        "MemoryError": "Out of memory. The file is too large to process.",
        "RuntimeError": {
            "maximum active validators": "System is at maximum capacity. Please try again in a few moments.",
            "pool exhausted": "Resource pool exhausted. Please wait and retry."
        },

        # File errors
        "FileNotFoundError": "File not found. Please check the file path.",
        "PermissionError": "Permission denied. Cannot access the file or resource.",
        "IOError": "File read/write error. Please check file integrity.",

        # Validation errors
        "ValidationError": "Document validation failed. Please check the file format and content.",
        "ValueError": {
            "invalid": "Invalid input provided. Please check your data.",
            "empty": "Empty or missing required data.",
            "format": "Incorrect data format."
        },

        # PDF specific errors
        "PDFException": "PDF processing error. The file may be corrupted or encrypted.",
        "PDFSyntaxError": "Invalid PDF format. Please provide a valid PDF file.",

        # Database errors
        "IntegrityError": "Database integrity error. Document may already exist.",
        "DataError": "Database data error. Invalid data format.",

        # Network errors
        "HTTPException": "HTTP error occurred. Please check your request.",
        "RequestException": "Network request failed. Please check your connection."
    }

    # Check for specific error type matches
    if error_type in error_mappings:
        mapping = error_mappings[error_type]

        # If mapping is a string, return it directly
        if isinstance(mapping, str):
            return mapping

        # If mapping is a dict, check for specific error message patterns
        if isinstance(mapping, dict):
            for pattern, message in mapping.items():
                if pattern in error_msg:
                    return message

    # Check for common patterns across all errors
    common_patterns = {
        "connection": "Connection error. Please check if all services are running.",
        "timeout": "Operation timed out. Please try again with a smaller file.",
        "memory": "Memory error. The system ran out of resources.",
        "permission": "Permission denied. Cannot access the requested resource.",
        "not found": "Resource not found. Please check your input.",
        "already exists": "Document already exists in the database.",
        "invalid": "Invalid input or file format.",
        "corrupt": "The file appears to be corrupted.",
        "encrypt": "The file is encrypted and cannot be processed.",
        "password": "The file is password protected.",
        "quota": "Storage quota exceeded.",
        "rate limit": "Rate limit exceeded. Please slow down.",
        "service unavailable": "Service temporarily unavailable. Please try again later."
    }

    for pattern, message in common_patterns.items():
        if pattern in error_msg:
            return message

    # Default message if no specific match found
    if error_type in ["Exception", "BaseException"]:
        return "An unexpected error occurred. Please try again or contact support if the issue persists."

    return f"Processing failed ({error_type}). Please check your file and try again."


def format_error_details(
    error: Exception,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Format error details for logging and debugging.

    Args:
        error: The exception that occurred
        context: Additional context information

    Returns:
        Dictionary with formatted error details
    """
    import traceback

    error_details = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "user_message": get_user_friendly_error_message(error),
        "traceback": traceback.format_exc().split('\n')
    }

    # Add context if provided
    if context:
        error_details["context"] = context

    # Extract specific error attributes if available
    if hasattr(error, 'args') and error.args:
        error_details["error_args"] = error.args

    if hasattr(error, '__cause__') and error.__cause__:
        error_details["cause"] = str(error.__cause__)

    if hasattr(error, '__context__') and error.__context__:
        error_details["context_error"] = str(error.__context__)

    return error_details


def log_error_with_context(
    logger_instance: logging.Logger,
    error: Exception,
    operation: str,
    context: Optional[Dict[str, Any]] = None,
    level: str = "ERROR"
) -> None:
    """
    Log error with detailed context and formatting.

    Args:
        logger_instance: Logger instance to use
        error: The exception that occurred
        operation: Name of the operation that failed
        context: Additional context information
        level: Log level (ERROR, WARNING, etc.)
    """
    error_details = format_error_details(error, context)

    # Create detailed log message
    log_message = (
        f"{operation} failed - "
        f"Type: {error_details['error_type']}, "
        f"Message: {error_details['error_message']}"
    )

    # Add context to log if available
    if context:
        context_str = ", ".join([f"{k}={v}" for k, v in context.items()])
        log_message += f", Context: {context_str}"

    # Log at appropriate level
    if level == "ERROR":
        logger_instance.error(log_message)
    elif level == "WARNING":
        logger_instance.warning(log_message)
    else:
        logger_instance.info(log_message)

    # Log full traceback at DEBUG level
    logger_instance.debug(f"Full traceback:\n{''.join(error_details['traceback'])}")