"""
Configuration validators for the RAG system.

This module provides validation functions to ensure configuration values are valid.
"""

import os
from typing import Any, Optional


class ConfigValidationError(Exception):
    """Custom exception for configuration validation errors"""
    pass


def validate_port(value: Any, name: str = "port") -> int:
    """
    Validate that a value is a valid port number.

    Args:
        value: The value to validate
        name: Name of the configuration for error messages

    Returns:
        Valid port number as integer

    Raises:
        ConfigValidationError: If the value is not a valid port
    """
    try:
        port = int(value)
        if not 1 <= port <= 65535:
            raise ConfigValidationError(f"{name} must be between 1 and 65535, got {port}")
        return port
    except (TypeError, ValueError):
        raise ConfigValidationError(f"{name} must be a valid integer, got {value}")


def validate_url(value: str, name: str = "url") -> str:
    """
    Validate that a value is a valid URL or endpoint.

    Args:
        value: The URL string to validate
        name: Name of the configuration for error messages

    Returns:
        Valid URL string

    Raises:
        ConfigValidationError: If the value is not a valid URL
    """
    if not value or not isinstance(value, str):
        raise ConfigValidationError(f"{name} must be a non-empty string")

    # Basic validation - can be enhanced with urllib.parse if needed
    if not value.strip():
        raise ConfigValidationError(f"{name} cannot be empty")

    return value.strip()


def validate_positive_int(value: Any, name: str = "value", min_value: int = 1) -> int:
    """
    Validate that a value is a positive integer.

    Args:
        value: The value to validate
        name: Name of the configuration for error messages
        min_value: Minimum acceptable value (default: 1)

    Returns:
        Valid positive integer

    Raises:
        ConfigValidationError: If the value is not a positive integer
    """
    try:
        int_value = int(value)
        if int_value < min_value:
            raise ConfigValidationError(f"{name} must be at least {min_value}, got {int_value}")
        return int_value
    except (TypeError, ValueError):
        raise ConfigValidationError(f"{name} must be a valid integer, got {value}")


def validate_float_range(value: Any, name: str = "value",
                         min_value: float = 0.0, max_value: float = 1.0) -> float:
    """
    Validate that a value is a float within a specific range.

    Args:
        value: The value to validate
        name: Name of the configuration for error messages
        min_value: Minimum acceptable value
        max_value: Maximum acceptable value

    Returns:
        Valid float within range

    Raises:
        ConfigValidationError: If the value is not a valid float in range
    """
    try:
        float_value = float(value)
        if not min_value <= float_value <= max_value:
            raise ConfigValidationError(
                f"{name} must be between {min_value} and {max_value}, got {float_value}"
            )
        return float_value
    except (TypeError, ValueError):
        raise ConfigValidationError(f"{name} must be a valid float, got {value}")


def validate_boolean(value: Any, name: str = "value") -> bool:
    """
    Validate and parse a boolean configuration value.

    Args:
        value: The value to validate (can be string or bool)
        name: Name of the configuration for error messages

    Returns:
        Boolean value
    """
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        value_lower = value.lower()
        if value_lower in ('true', '1', 'yes', 'on'):
            return True
        elif value_lower in ('false', '0', 'no', 'off'):
            return False

    raise ConfigValidationError(
        f"{name} must be a boolean (true/false, yes/no, 1/0), got {value}"
    )


def validate_file_path(value: str, name: str = "path", must_exist: bool = False) -> str:
    """
    Validate that a value is a valid file path.

    Args:
        value: The file path to validate
        name: Name of the configuration for error messages
        must_exist: Whether the file must exist

    Returns:
        Valid file path

    Raises:
        ConfigValidationError: If the path is invalid or doesn't exist when required
    """
    if not value or not isinstance(value, str):
        raise ConfigValidationError(f"{name} must be a non-empty string")

    if must_exist and not os.path.exists(value):
        raise ConfigValidationError(f"{name} does not exist: {value}")

    return value


def validate_api_key(value: Optional[str], name: str = "api_key",
                     required: bool = True) -> Optional[str]:
    """
    Validate an API key.

    Args:
        value: The API key to validate
        name: Name of the configuration for error messages
        required: Whether the API key is required

    Returns:
        Valid API key or None if not required

    Raises:
        ConfigValidationError: If the API key is invalid or missing when required
    """
    if not value or value == "":
        if required:
            raise ConfigValidationError(f"{name} is required but not set")
        return None

    if not isinstance(value, str) or len(value) < 10:
        raise ConfigValidationError(f"{name} must be a valid API key string")

    return value.strip()