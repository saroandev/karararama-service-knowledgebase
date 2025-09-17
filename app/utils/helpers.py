"""
General utility helper functions
"""
import os
import re
import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union
import json
import unicodedata
import logging

logger = logging.getLogger(__name__)


def generate_document_id(prefix: str = "doc") -> str:
    """
    Generate unique document ID

    Args:
        prefix: ID prefix (default: "doc")

    Returns:
        Unique document ID (e.g., "doc_a1b2c3d4e5f6g7h8")
    """
    unique_id = uuid.uuid4().hex[:16]
    return f"{prefix}_{unique_id}"


def generate_chunk_id(document_id: str, chunk_index: int) -> str:
    """
    Generate chunk ID based on document ID and index

    Args:
        document_id: Parent document ID
        chunk_index: Chunk index number

    Returns:
        Chunk ID (e.g., "doc_xxxx_chunk_001")
    """
    return f"{document_id}_chunk_{chunk_index:03d}"


def format_timestamp(dt: Optional[datetime] = None, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format datetime to string

    Args:
        dt: Datetime object (default: current time)
        format_str: Format string

    Returns:
        Formatted timestamp string
    """
    if dt is None:
        dt = datetime.utcnow()
    return dt.strftime(format_str)


def calculate_file_hash(
    file_path: Optional[str] = None,
    file_obj: Optional[Any] = None,
    algorithm: str = "sha256"
) -> str:
    """
    Calculate file hash

    Args:
        file_path: Path to file
        file_obj: File object
        algorithm: Hash algorithm (sha256, md5, etc.)

    Returns:
        Hex digest of file hash
    """
    hasher = hashlib.new(algorithm)

    if file_path:
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
    elif file_obj:
        # Save current position
        current_pos = file_obj.tell()
        file_obj.seek(0)

        while chunk := file_obj.read(8192):
            hasher.update(chunk)

        # Restore position
        file_obj.seek(current_pos)
    else:
        raise ValueError("Either file_path or file_obj must be provided")

    return hasher.hexdigest()


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize filename for safe storage

    Args:
        filename: Original filename
        max_length: Maximum filename length

    Returns:
        Sanitized filename
    """
    # Remove path components
    filename = os.path.basename(filename)

    # Normalize unicode characters
    filename = unicodedata.normalize('NFKD', filename)
    filename = filename.encode('ascii', 'ignore').decode('ascii')

    # Replace invalid characters
    filename = re.sub(r'[^\w\s.-]', '_', filename)

    # Replace multiple spaces/underscores
    filename = re.sub(r'[\s_]+', '_', filename)

    # Preserve extension
    name_parts = filename.rsplit('.', 1)
    if len(name_parts) == 2:
        name, ext = name_parts
        # Truncate name if needed
        max_name_length = max_length - len(ext) - 1
        if len(name) > max_name_length:
            name = name[:max_name_length]
        filename = f"{name}.{ext}"
    else:
        # No extension
        if len(filename) > max_length:
            filename = filename[:max_length]

    return filename


def get_file_extension(filename: str) -> str:
    """
    Get file extension from filename

    Args:
        filename: Filename or path

    Returns:
        File extension with dot (e.g., ".pdf")
    """
    return Path(filename).suffix.lower()


def batch_iterator(items: List[Any], batch_size: int) -> Iterator[List[Any]]:
    """
    Create batches from a list

    Args:
        items: List of items
        batch_size: Size of each batch

    Yields:
        Batches of items
    """
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]


def merge_dicts(*dicts: Dict[str, Any], deep: bool = False) -> Dict[str, Any]:
    """
    Merge multiple dictionaries

    Args:
        *dicts: Dictionaries to merge
        deep: Whether to perform deep merge

    Returns:
        Merged dictionary
    """
    result = {}

    for d in dicts:
        if not d:
            continue

        if not deep:
            result.update(d)
        else:
            for key, value in d.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = merge_dicts(result[key], value, deep=True)
                else:
                    result[key] = value

    return result


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to maximum length

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def clean_text(text: str) -> str:
    """
    Clean text by removing extra whitespace and special characters

    Args:
        text: Text to clean

    Returns:
        Cleaned text
    """
    # Remove control characters
    text = ''.join(char for char in text if unicodedata.category(char)[0] != 'C')

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)

    # Remove leading/trailing whitespace
    text = text.strip()

    return text


def extract_numbers(text: str) -> List[float]:
    """
    Extract numbers from text

    Args:
        text: Input text

    Returns:
        List of numbers found
    """
    # Pattern for integers and floats
    pattern = r'-?\d+\.?\d*'
    matches = re.findall(pattern, text)

    numbers = []
    for match in matches:
        try:
            if '.' in match:
                numbers.append(float(match))
            else:
                numbers.append(int(match))
        except ValueError:
            continue

    return numbers


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string (e.g., "1.5 MB")
    """
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = float(size_bytes)
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.2f} {units[unit_index]}"


def parse_bool(value: Union[str, bool, int]) -> bool:
    """
    Parse boolean value from various types

    Args:
        value: Value to parse

    Returns:
        Boolean value
    """
    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return bool(value)

    if isinstance(value, str):
        value = value.lower().strip()
        if value in ('true', 'yes', '1', 'on', 'enabled'):
            return True
        elif value in ('false', 'no', '0', 'off', 'disabled'):
            return False

    raise ValueError(f"Cannot parse boolean from: {value}")


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """
    Safely load JSON with fallback

    Args:
        json_str: JSON string
        default: Default value if parsing fails

    Returns:
        Parsed JSON or default value
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to parse JSON: {e}")
        return default


def safe_get(
    dictionary: Dict[str, Any],
    key_path: str,
    default: Any = None,
    separator: str = "."
) -> Any:
    """
    Safely get nested dictionary value

    Args:
        dictionary: Source dictionary
        key_path: Dot-separated path (e.g., "user.profile.name")
        default: Default value if key not found
        separator: Path separator

    Returns:
        Value at path or default
    """
    keys = key_path.split(separator)
    current = dictionary

    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default

    return current


def flatten_dict(
    d: Dict[str, Any],
    parent_key: str = '',
    separator: str = '_'
) -> Dict[str, Any]:
    """
    Flatten nested dictionary

    Args:
        d: Dictionary to flatten
        parent_key: Parent key for recursion
        separator: Key separator

    Returns:
        Flattened dictionary
    """
    items = []

    for key, value in d.items():
        new_key = f"{parent_key}{separator}{key}" if parent_key else key

        if isinstance(value, dict):
            items.extend(flatten_dict(value, new_key, separator).items())
        else:
            items.append((new_key, value))

    return dict(items)


def estimate_tokens(text: str, chars_per_token: float = 4.0) -> int:
    """
    Estimate token count from text

    Args:
        text: Input text
        chars_per_token: Average characters per token

    Returns:
        Estimated token count
    """
    return int(len(text) / chars_per_token)


def create_batches_by_size(
    items: List[Any],
    size_func: callable,
    max_batch_size: int
) -> List[List[Any]]:
    """
    Create batches based on cumulative size

    Args:
        items: List of items
        size_func: Function to calculate item size
        max_batch_size: Maximum batch size

    Returns:
        List of batches
    """
    batches = []
    current_batch = []
    current_size = 0

    for item in items:
        item_size = size_func(item)

        if current_size + item_size > max_batch_size and current_batch:
            batches.append(current_batch)
            current_batch = []
            current_size = 0

        current_batch.append(item)
        current_size += item_size

    if current_batch:
        batches.append(current_batch)

    return batches