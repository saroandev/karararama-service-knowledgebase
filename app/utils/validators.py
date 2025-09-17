"""
Input validation utilities
"""
import os
import re
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import mimetypes
import logging

logger = logging.getLogger(__name__)

# Constants for validation
MAX_FILE_SIZE_MB = 50
MIN_QUERY_LENGTH = 3
MAX_QUERY_LENGTH = 1000
ALLOWED_PDF_EXTENSIONS = ['.pdf']
ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
ALLOWED_DOCUMENT_EXTENSIONS = ['.txt', '.md', '.docx', '.doc', '.rtf']


def validate_pdf_file(
    file_path: Optional[str] = None,
    file_obj: Optional[Any] = None,
    max_size_mb: float = MAX_FILE_SIZE_MB
) -> bool:
    """
    Validate PDF file

    Args:
        file_path: Path to PDF file
        file_obj: File object with read() and seek() methods
        max_size_mb: Maximum file size in MB

    Returns:
        True if valid PDF

    Raises:
        ValueError: If validation fails
    """
    if file_path:
        # Check file exists
        if not os.path.exists(file_path):
            raise ValueError(f"File not found: {file_path}")

        # Check extension
        ext = Path(file_path).suffix.lower()
        if ext not in ALLOWED_PDF_EXTENSIONS:
            raise ValueError(f"Invalid file extension: {ext}. Expected: {ALLOWED_PDF_EXTENSIONS}")

        # Check file size
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > max_size_mb:
            raise ValueError(f"File too large: {file_size_mb:.2f}MB. Maximum: {max_size_mb}MB")

        # Check PDF header
        with open(file_path, 'rb') as f:
            header = f.read(5)
            if header != b'%PDF-':
                raise ValueError("Invalid PDF file: missing PDF header")

    elif file_obj:
        # Check file size
        file_obj.seek(0, 2)  # Seek to end
        file_size = file_obj.tell()
        file_obj.seek(0)  # Reset to beginning

        file_size_mb = file_size / (1024 * 1024)
        if file_size_mb > max_size_mb:
            raise ValueError(f"File too large: {file_size_mb:.2f}MB. Maximum: {max_size_mb}MB")

        # Check PDF header
        header = file_obj.read(5)
        file_obj.seek(0)  # Reset

        if header != b'%PDF-':
            raise ValueError("Invalid PDF file: missing PDF header")

    else:
        raise ValueError("Either file_path or file_obj must be provided")

    return True


def validate_query(
    query: str,
    min_length: int = MIN_QUERY_LENGTH,
    max_length: int = MAX_QUERY_LENGTH,
    allow_empty: bool = False
) -> bool:
    """
    Validate search query

    Args:
        query: Query string
        min_length: Minimum query length
        max_length: Maximum query length
        allow_empty: Whether to allow empty queries

    Returns:
        True if valid query

    Raises:
        ValueError: If validation fails
    """
    if not query and not allow_empty:
        raise ValueError("Query cannot be empty")

    if query:
        query = query.strip()

        if len(query) < min_length:
            raise ValueError(f"Query too short. Minimum {min_length} characters")

        if len(query) > max_length:
            raise ValueError(f"Query too long. Maximum {max_length} characters")

        # Check for malicious patterns (SQL injection, etc.)
        dangerous_patterns = [
            r'<script',
            r'javascript:',
            r'onclick=',
            r'onerror=',
            r'DROP\s+TABLE',
            r'DELETE\s+FROM',
            r'INSERT\s+INTO'
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                raise ValueError(f"Query contains potentially dangerous content")

    return True


def validate_file_size(
    file_path: Optional[str] = None,
    file_obj: Optional[Any] = None,
    max_size_mb: float = MAX_FILE_SIZE_MB
) -> bool:
    """
    Validate file size

    Args:
        file_path: Path to file
        file_obj: File object
        max_size_mb: Maximum size in MB

    Returns:
        True if valid size

    Raises:
        ValueError: If file is too large
    """
    if file_path:
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    elif file_obj:
        file_obj.seek(0, 2)
        file_size_mb = file_obj.tell() / (1024 * 1024)
        file_obj.seek(0)
    else:
        raise ValueError("Either file_path or file_obj must be provided")

    if file_size_mb > max_size_mb:
        raise ValueError(
            f"File size ({file_size_mb:.2f}MB) exceeds maximum allowed size ({max_size_mb}MB)"
        )

    return True


def validate_config(config: Dict[str, Any], required_fields: List[str]) -> bool:
    """
    Validate configuration dictionary

    Args:
        config: Configuration dictionary
        required_fields: List of required field names

    Returns:
        True if valid

    Raises:
        ValueError: If validation fails
    """
    if not isinstance(config, dict):
        raise ValueError("Config must be a dictionary")

    # Check required fields
    missing_fields = [field for field in required_fields if field not in config]
    if missing_fields:
        raise ValueError(f"Missing required config fields: {missing_fields}")

    # Validate specific fields
    if 'chunk_size' in config:
        chunk_size = config['chunk_size']
        if not isinstance(chunk_size, int) or chunk_size < 100 or chunk_size > 2000:
            raise ValueError(f"Invalid chunk_size: {chunk_size}. Must be between 100 and 2000")

    if 'chunk_overlap' in config:
        overlap = config['chunk_overlap']
        chunk_size = config.get('chunk_size', 500)
        if not isinstance(overlap, int) or overlap < 0 or overlap >= chunk_size:
            raise ValueError(f"Invalid chunk_overlap: {overlap}. Must be between 0 and chunk_size")

    if 'top_k' in config:
        top_k = config['top_k']
        if not isinstance(top_k, int) or top_k < 1 or top_k > 100:
            raise ValueError(f"Invalid top_k: {top_k}. Must be between 1 and 100")

    if 'temperature' in config:
        temp = config['temperature']
        if not isinstance(temp, (int, float)) or temp < 0 or temp > 2:
            raise ValueError(f"Invalid temperature: {temp}. Must be between 0 and 2")

    return True


def validate_embedding_dimension(
    dimension: int,
    expected_dimension: Optional[int] = None
) -> bool:
    """
    Validate embedding dimension

    Args:
        dimension: Actual embedding dimension
        expected_dimension: Expected dimension (optional)

    Returns:
        True if valid

    Raises:
        ValueError: If validation fails
    """
    # Common embedding dimensions
    valid_dimensions = [384, 512, 768, 1024, 1536, 3072]

    if dimension not in valid_dimensions:
        logger.warning(f"Unusual embedding dimension: {dimension}")

    if expected_dimension and dimension != expected_dimension:
        raise ValueError(
            f"Embedding dimension mismatch. Expected {expected_dimension}, got {dimension}"
        )

    return True


def validate_document_id(document_id: str) -> bool:
    """
    Validate document ID format

    Args:
        document_id: Document ID string

    Returns:
        True if valid

    Raises:
        ValueError: If validation fails
    """
    if not document_id:
        raise ValueError("Document ID cannot be empty")

    # Check format (e.g., doc_xxxxxxxxxxxx)
    if not re.match(r'^doc_[a-f0-9]{16}$', document_id):
        raise ValueError(f"Invalid document ID format: {document_id}")

    return True


def validate_chunk_id(chunk_id: str) -> bool:
    """
    Validate chunk ID format

    Args:
        chunk_id: Chunk ID string

    Returns:
        True if valid

    Raises:
        ValueError: If validation fails
    """
    if not chunk_id:
        raise ValueError("Chunk ID cannot be empty")

    # Check format (e.g., doc_xxxxxxxxxxxx_chunk_xxx)
    if not re.match(r'^doc_[a-f0-9]{16}_chunk_\d+$', chunk_id):
        raise ValueError(f"Invalid chunk ID format: {chunk_id}")

    return True


def validate_minio_path(path: str) -> bool:
    """
    Validate MinIO object path

    Args:
        path: MinIO object path

    Returns:
        True if valid

    Raises:
        ValueError: If validation fails
    """
    if not path:
        raise ValueError("MinIO path cannot be empty")

    # Check for invalid characters
    invalid_chars = ['..', '//', '\\', '\0']
    for char in invalid_chars:
        if char in path:
            raise ValueError(f"Invalid character in MinIO path: {char}")

    # Check path components
    parts = path.split('/')
    for part in parts:
        if not part:
            raise ValueError("MinIO path contains empty components")

        # Check for valid characters
        if not re.match(r'^[a-zA-Z0-9._-]+$', part):
            raise ValueError(f"Invalid characters in path component: {part}")

    return True


def validate_batch_size(batch_size: int, max_batch_size: int = 100) -> bool:
    """
    Validate batch size

    Args:
        batch_size: Batch size to validate
        max_batch_size: Maximum allowed batch size

    Returns:
        True if valid

    Raises:
        ValueError: If validation fails
    """
    if not isinstance(batch_size, int):
        raise ValueError(f"Batch size must be an integer, got {type(batch_size)}")

    if batch_size < 1:
        raise ValueError(f"Batch size must be positive, got {batch_size}")

    if batch_size > max_batch_size:
        raise ValueError(f"Batch size {batch_size} exceeds maximum {max_batch_size}")

    return True


def validate_api_key(api_key: str, prefix: Optional[str] = None) -> bool:
    """
    Validate API key format

    Args:
        api_key: API key string
        prefix: Expected prefix (e.g., 'sk-' for OpenAI)

    Returns:
        True if valid

    Raises:
        ValueError: If validation fails
    """
    if not api_key:
        raise ValueError("API key cannot be empty")

    if api_key == "YOUR_API_KEY_HERE" or api_key == "PLACEHOLDER":
        raise ValueError("API key appears to be a placeholder")

    if prefix and not api_key.startswith(prefix):
        raise ValueError(f"API key should start with '{prefix}'")

    # Check minimum length
    if len(api_key) < 20:
        raise ValueError("API key appears to be too short")

    return True