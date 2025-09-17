"""
Centralized logging configuration and utilities
"""
import logging
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from functools import wraps
import traceback

# Default log format
DEFAULT_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
JSON_FORMAT = '{"time": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging"""

    def format(self, record):
        log_obj = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }

        # Add exception info if present
        if record.exc_info:
            log_obj['exception'] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_obj.update(record.extra_fields)

        return json.dumps(log_obj)


def setup_logger(
    name: str = 'rag_system',
    level: str = 'INFO',
    log_file: Optional[str] = None,
    use_json: bool = False,
    console: bool = True
) -> logging.Logger:
    """
    Setup and configure logger

    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path to write logs
        use_json: Use JSON formatting for logs
        console: Whether to output to console

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    logger.handlers.clear()

    # Create formatter
    if use_json:
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(DEFAULT_FORMAT)

    # Add console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Add file handler if specified
    if log_file:
        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger with the given name

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def log_function_call(logger: Optional[logging.Logger] = None):
    """
    Decorator to log function calls with arguments and return values

    Args:
        logger: Logger instance to use

    Example:
        @log_function_call()
        def process_data(data):
            return data * 2
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_logger = logger or logging.getLogger(func.__module__)

            # Log function entry
            func_logger.debug(
                f"Calling {func.__name__} with args={args}, kwargs={kwargs}"
            )

            try:
                # Execute function
                result = func(*args, **kwargs)

                # Log successful completion
                func_logger.debug(
                    f"{func.__name__} completed successfully, returned: {result}"
                )

                return result

            except Exception as e:
                # Log error
                func_logger.error(
                    f"{func.__name__} failed with error: {e}",
                    exc_info=True
                )
                raise

        return wrapper
    return decorator


def log_error(logger: logging.Logger, message: str, error: Exception, **extra_fields):
    """
    Log error with structured information

    Args:
        logger: Logger instance
        message: Error message
        error: Exception object
        **extra_fields: Additional fields to include in log
    """
    error_info = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'traceback': traceback.format_exc()
    }

    if extra_fields:
        error_info.update(extra_fields)

    # Create log record with extra fields
    log_record = logger.makeRecord(
        logger.name,
        logging.ERROR,
        '(unknown file)',
        0,
        message,
        (),
        None
    )
    log_record.extra_fields = error_info

    logger.handle(log_record)


def create_operation_logger(operation_name: str) -> 'OperationLogger':
    """
    Create a logger for tracking long-running operations

    Args:
        operation_name: Name of the operation

    Returns:
        OperationLogger instance
    """
    return OperationLogger(operation_name)


class OperationLogger:
    """Logger for tracking long-running operations with progress"""

    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.logger = get_logger(self.__class__.__name__)
        self.start_time = None
        self.metadata = {}

    def start(self, **metadata):
        """Start operation logging"""
        self.start_time = datetime.utcnow()
        self.metadata = metadata

        self.logger.info(
            f"Operation '{self.operation_name}' started",
            extra={'extra_fields': self.metadata}
        )

    def update(self, message: str, **extra_fields):
        """Update operation progress"""
        elapsed = (datetime.utcnow() - self.start_time).total_seconds() if self.start_time else 0

        log_data = {
            'operation': self.operation_name,
            'elapsed_seconds': elapsed,
            **extra_fields
        }

        self.logger.info(message, extra={'extra_fields': log_data})

    def complete(self, **result_fields):
        """Mark operation as complete"""
        elapsed = (datetime.utcnow() - self.start_time).total_seconds() if self.start_time else 0

        log_data = {
            'operation': self.operation_name,
            'elapsed_seconds': elapsed,
            'status': 'completed',
            **self.metadata,
            **result_fields
        }

        self.logger.info(
            f"Operation '{self.operation_name}' completed in {elapsed:.2f} seconds",
            extra={'extra_fields': log_data}
        )

    def error(self, error: Exception, **error_fields):
        """Mark operation as failed"""
        elapsed = (datetime.utcnow() - self.start_time).total_seconds() if self.start_time else 0

        log_data = {
            'operation': self.operation_name,
            'elapsed_seconds': elapsed,
            'status': 'failed',
            'error_type': type(error).__name__,
            'error_message': str(error),
            **self.metadata,
            **error_fields
        }

        self.logger.error(
            f"Operation '{self.operation_name}' failed after {elapsed:.2f} seconds",
            extra={'extra_fields': log_data},
            exc_info=True
        )


# Configure default logger on import
default_logger = setup_logger(
    name='rag_system',
    level='INFO',
    console=True
)