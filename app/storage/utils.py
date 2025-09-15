"""
Storage utility functions
"""
import hashlib
import unicodedata
import re
import os
from datetime import datetime
from typing import Dict, Any


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage
    Handles Turkish characters and special characters

    Args:
        filename: Original filename

    Returns:
        Sanitized filename safe for storage
    """
    # Convert to lowercase first
    sanitized = filename.lower()

    # Replace Turkish characters with ASCII equivalents
    replacements = {
        'ı': 'i', 'ğ': 'g', 'ü': 'u', 'ş': 's', 'ö': 'o', 'ç': 'c',
        'İ': 'i', 'Ğ': 'g', 'Ü': 'u', 'Ş': 's', 'Ö': 'o', 'Ç': 'c',
        'â': 'a', 'î': 'i', 'û': 'u', 'ê': 'e', 'ô': 'o',
        'Â': 'a', 'Î': 'i', 'Û': 'u', 'Ê': 'e', 'Ô': 'o'
    }
    for tr_char, ascii_char in replacements.items():
        sanitized = sanitized.replace(tr_char, ascii_char)

    # Normalize unicode to handle remaining special characters
    sanitized = unicodedata.normalize('NFKD', sanitized)
    sanitized = sanitized.encode('ascii', 'ignore').decode('ascii')

    # Get name and extension separately
    name_part, ext = os.path.splitext(sanitized)

    # Replace punctuation and special chars with spaces
    name_part = re.sub(r'[^a-z0-9\s]', ' ', name_part)

    # Replace multiple spaces with single space
    name_part = re.sub(r'\s+', ' ', name_part)

    # Trim spaces and replace with underscores
    name_part = name_part.strip().replace(' ', '_')

    # Remove consecutive underscores
    name_part = re.sub(r'_+', '_', name_part)

    # Ensure name is not empty
    if not name_part:
        name_part = 'document'

    # Truncate if too long (MinIO has limits)
    max_name_length = 200
    if len(name_part) > max_name_length:
        name_part = name_part[:max_name_length]

    # Reconstruct filename
    return f"{name_part}{ext}"


def generate_document_id(file_data: bytes) -> str:
    """
    Generate unique document ID from file content

    Args:
        file_data: File content bytes

    Returns:
        Unique document ID
    """
    file_hash = hashlib.md5(file_data).hexdigest()
    return f"doc_{file_hash[:16]}"


def prepare_metadata(document_id: str, filename: str,
                    file_data: bytes, additional_metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Prepare metadata for document storage

    Args:
        document_id: Document ID
        filename: Original filename
        file_data: File content
        additional_metadata: Additional metadata to include

    Returns:
        Complete metadata dictionary
    """
    metadata = {
        "document_id": document_id,
        "original_filename": filename,
        "upload_timestamp": datetime.now().isoformat(),
        "file_size": len(file_data),
        "file_hash": hashlib.md5(file_data).hexdigest()
    }

    if additional_metadata:
        metadata.update(additional_metadata)

    return metadata


def get_cache_key(document_id: str, operation: str) -> str:
    """
    Generate cache key for a storage operation

    Args:
        document_id: Document ID
        operation: Operation type (e.g., 'document', 'chunks', 'metadata')

    Returns:
        Cache key string
    """
    return f"{operation}:{document_id}"